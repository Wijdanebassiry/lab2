import uuid
from fastapi import HTTPException
from .models import Payment
from .gateway.base import GatewayTimeout


def _emit(events, name, *args):
    """Publie un evenement sans jamais faire echouer le paiement."""
    if events is None:
        return
    try:
        getattr(events, name)(*args)
    except Exception:
        pass


def process_payment(
    db, gateway, orders, order_id: str, method: str,
    auth: str | None = None, events=None, shipment_events=None
):
    order = orders.get_order(order_id, auth)

    if order is None:
        raise HTTPException(404, "Order not found.")

    if order.status != "PENDING_PAYMENT":
        raise HTTPException(409, "Order is not awaiting payment.")

    if db.query(Payment).filter_by(
        order_id=order_id, status="SUCCESS"
    ).first():
        raise HTTPException(409, "Payment already attempted for this order.")

    p = Payment(
        id=str(uuid.uuid4()),
        order_id=order_id,
        amount=order.total,
        method=method,
        status="PENDING",
    )
    db.add(p)
    db.commit()

    try:
        result = gateway.charge(order.total, "MAD", method)
    except GatewayTimeout:
        p.status, p.failure_reason = "FAILED", "gateway_timeout"
        db.commit()
        _emit(events, "publish_payment_failed", order_id, method, "gateway_timeout")
        raise HTTPException(503, "Payment provider unavailable.")

    p.gateway_ref = result.reference

    if result.outcome != "approved":
        p.status, p.failure_reason = "FAILED", result.reason
        db.commit()
        _emit(events, "publish_payment_failed", order_id, method, result.reason or "declined")
        raise HTTPException(402, f"Payment declined: {result.reason}")

    p.status = "SUCCESS"
    db.commit()

    try:
        orders.mark_paid(order_id, auth)
    except HTTPException:
        gateway.refund(p.gateway_ref, p.amount)
        p.status, p.failure_reason = "REFUNDED", "order_update_failed"
        db.commit()
        raise

    # Kafka: evenements Payments existants.
    _emit(events, "publish_payment_completed", order_id, p.id, p.amount, method)

    # RabbitMQ: demande de livraison apres confirmation PAID.
    _emit(shipment_events, "publish_shipment_requested", order)

    return p