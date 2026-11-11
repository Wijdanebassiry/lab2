from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import service
from .database import get_db
from .models import Stock
from .schemas import ItemsRequest

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def error(message: str, detail: str, status: int, **extra):
    return JSONResponse(status_code=status, content={"message": message, "detail": detail, **extra})


def fmt(s: Stock) -> dict:
    return {"productId": s.product_id, "stock": s.quantity}   # ← "quantity" devient "stock"


@router.get("")
def list_stock(db: Session = Depends(get_db)):
    return [fmt(s) for s in db.scalars(select(Stock).order_by(Stock.product_id))]


@router.get("/{product_id}")
def get_stock(product_id: str, db: Session = Depends(get_db)):
    stock = db.get(Stock, product_id)
    if not stock:
        return error("Product not found.", f"No stock record for product {product_id}", 404)
    return fmt(stock)


@router.post("/check")
def check(body: ItemsRequest, db: Session = Depends(get_db)):
    unavailable = service.find_unavailable(db, service.merge_items(body.items))
    return {"available": len(unavailable) == 0, "unavailable": unavailable}


@router.post("/reserve")
def reserve(body: ItemsRequest, db: Session = Depends(get_db)):
    unavailable = service.reserve(db, service.merge_items(body.items))
    if unavailable:
        return error(
            "Insufficient stock.",
            "Some products are not available in the requested quantity",
            409,
            unavailable=unavailable,
        )
    return {"success": True}                                   # ← était {"reserved": True}


@router.post("/release")
def release(body: ItemsRequest, db: Session = Depends(get_db)):
    service.release(db, service.merge_items(body.items))
    return {"success": True}                                   # ← était {"released": True}