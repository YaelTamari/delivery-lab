from fastapi import FastAPI, Request, HTTPException, Response, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# התאמת שגיאות ולידציה לחוזה של המטלה (מחזיר error ולא detail עם סטטוס 400)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body or missing fields"}
    )

class DeliveryCreate(BaseModel):
    recipient: Optional[object] = None
    address: Optional[object] = None

class StatusUpdate(BaseModel):
    status: Optional[object] = None

deliveries_db = {}
next_id = 1
VALID_STATUSES = ["created", "in_transit", "delivered"]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/deliveries")
def get_deliveries(status: Optional[str] = Query(None)):
    if status is not None:
        if status not in VALID_STATUSES:
            return JSONResponse(status_code=400, content={"error": "Invalid status filter"})
        return [d for d in deliveries_db.values() if d["status"] == status]
    return list(deliveries_db.values())

@app.post("/deliveries")
def create_delivery(data: DeliveryCreate, response: Response):
    global next_id
    
    # בדיקת תקינות לפי דרישות המטלה (מחרוזות לא ריקות)
    if not isinstance(data.recipient, str) or not data.recipient.strip():
        return JSONResponse(status_code=400, content={"error": "Invalid recipient"})
    if not isinstance(data.address, str) or not data.address.strip():
        return JSONResponse(status_code=400, content={"error": "Invalid address"})

    delivery = {
        "id": next_id,
        "recipient": data.recipient.strip(),
        "address": data.address.strip(),
        "status": "created"
    }
    deliveries_db[next_id] = delivery
    next_id += 1
    
    response.status_code = 201
    return delivery

@app.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int):
    if delivery_id in deliveries_db:
        return deliveries_db[delivery_id]
    return JSONResponse(status_code=404, content={"error": "Delivery not found"})

@app.patch("/deliveries/{delivery_id}/status")
def update_status(delivery_id: int, body: StatusUpdate):
    if delivery_id not in deliveries_db:
        return JSONResponse(status_code=404, content={"error": "Delivery not found"})

    if not isinstance(body.status, str) or body.status not in VALID_STATUSES:
        return JSONResponse(status_code=400, content={"error": "Invalid status"})

    delivery = deliveries_db[delivery_id]
    current = delivery["status"]
    target = body.status

    # מעבר סטטוס חוקי רק קדימה ובצעד אחד בלבד
    if current == target:
        return JSONResponse(status_code=409, content={"error": "Status is already set to this value"})

    allowed_transitions = {
        "created": "in_transit",
        "in_transit": "delivered"
    }

    if allowed_transitions.get(current) != target:
        return JSONResponse(status_code=409, content={"error": "Invalid status transition"})

    delivery["status"] = target
    return delivery

@app.delete("/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int, response: Response):
    if delivery_id not in deliveries_db:
        return JSONResponse(status_code=404, content={"error": "Delivery not found"})

    delivery = deliveries_db[delivery_id]
    # מוחקים רק משלוח בסטטוס created
    if delivery["status"] != "created":
        return JSONResponse(status_code=409, content={"error": "Cannot delete delivery that is not in created status"})

    del deliveries_db[delivery_id]
    response.status_code = 204
    return Response(status_code=204)