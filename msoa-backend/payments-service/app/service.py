import uuid
from fastapi import HTTPException
from .models import Payment
from .gateway.base import GatewayTimeout

def process_payment(db, gateway, orders, order_id: str, method: str , auth: str | None = None):
    order = orders.get_order(order_id ,auth )
    if order is None:
        raise HTTPException(404, "Order not found.")
    if order.status != "PENDING_PAYMENT":
        raise HTTPException(409, "Order is not awaiting payment.")
    if db.query(Payment).filter_by(order_id=order_id, status="SUCCESS").first():
        raise HTTPException(409, "Payment already attempted for this order.")

    p = Payment(id=str(uuid.uuid4()), order_id=order_id,
                amount=order.total, method=method, status="PENDING")
    db.add(p); db.commit()

    try:
        result = gateway.charge(order.total, "MAD", method)
    except GatewayTimeout:
        p.status, p.failure_reason = "FAILED", "gateway_timeout"
        db.commit()
        raise HTTPException(503, "Payment provider unavailable.")

    p.gateway_ref = result.reference
    if result.outcome != "approved":
        p.status, p.failure_reason = "FAILED", result.reason
        db.commit()
        raise HTTPException(402, f"Payment declined: {result.reason}")

    p.status = "SUCCESS"; db.commit()

    try:
        orders.mark_paid(order_id , auth)
    except HTTPException:
        # Compensation : on a encaissé mais Orders n'est pas à jour
        gateway.refund(p.gateway_ref, p.amount)
        p.status, p.failure_reason = "REFUNDED", "order_update_failed"
        db.commit()
        raise
    return p