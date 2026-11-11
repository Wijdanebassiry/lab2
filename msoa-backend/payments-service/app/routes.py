from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import Payment
from .schemas import PaymentRequest, PaymentResponse
from .gateway.simulated import SimulatedGateway
from .clients.orders_client import OrdersClient
from . import service

router = APIRouter(prefix="/api/payments")
gateway, orders = SimulatedGateway(), OrdersClient()

@router.get("", response_model=list[PaymentResponse])
def list_all(db: Session = Depends(get_db)):
    return db.query(Payment).all()

@router.get("/order/{order_id}", response_model=PaymentResponse)
def by_order(order_id: str, db: Session = Depends(get_db)):
    p = (db.query(Payment).filter_by(order_id=order_id)
           .order_by(Payment.created_at.desc()).first())
    if not p:
        raise HTTPException(404, "Payment not found.")
    return p

@router.post("", response_model=PaymentResponse, status_code=201,
             responses={402: {"description": "Payment declined"},
                        404: {"description": "Order not found"},
                        409: {"description": "Order not awaiting payment"},
                        503: {"description": "Provider or Orders unavailable"}})


def create(data: PaymentRequest, db: Session = Depends(get_db),authorization: str | None = Header(None)):
    # Le token de l'utilisateur est transmis tel quel à Orders (s'il existe)
    return service.process_payment(db, gateway, orders, data.orderId, data.method, authorization)