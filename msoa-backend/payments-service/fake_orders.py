from fastapi import FastAPI, HTTPException

app = FastAPI()
order = {"id": "o1", "total": 250.0, "status": "PENDING_PAYMENT"}

@app.get("/api/orders/{oid}")
def get_order(oid: str):
    if oid != "o1":
        raise HTTPException(404, "Order not found.")
    return order

@app.patch("/api/orders/{oid}/status")
def set_status(oid: str, body: dict):
    order["status"] = body["status"]
    return order