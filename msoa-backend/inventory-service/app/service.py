from collections import defaultdict

from sqlalchemy import update
from sqlalchemy.orm import Session

from .models import Stock
from .schemas import Item


def merge_items(items: list[Item]) -> dict[str, int]:
    """[{1,2},{1,3}] becomes {"1": 5}"""
    merged: dict[str, int] = defaultdict(int)
    for it in items:
        merged[it.productId] += it.quantity
    return dict(merged)


def _detail(db: Session, product_id: str, requested: int) -> dict:
    stock = db.get(Stock, product_id)
    return {
        "productId": product_id,
        "requested": requested,
        "available": stock.quantity if stock else 0,
    }


def find_unavailable(db: Session, merged: dict[str, int]) -> list[dict]:
    result = []
    for pid, qty in merged.items():
        stock = db.get(Stock, pid)
        if (stock.quantity if stock else 0) < qty:
            result.append(_detail(db, pid, qty))
    return result


def reserve(db: Session, merged: dict[str, int]) -> list[dict]:
    """All-or-nothing. Returns [] on success, or the list of unavailable items."""
    failed = []
    for pid, qty in merged.items():
        res = db.execute(
            update(Stock)
            .where(Stock.product_id == pid, Stock.quantity >= qty)
            .values(quantity=Stock.quantity - qty)
        )
        if res.rowcount == 0:
            failed.append(pid)

    if failed:
        db.rollback()  # undo every decrement made in this request
        return [_detail(db, pid, merged[pid]) for pid in failed]

    db.commit()
    return []


def release(db: Session, merged: dict[str, int]) -> None:
    for pid, qty in merged.items():
        db.execute(
            update(Stock)
            .where(Stock.product_id == pid)
            .values(quantity=Stock.quantity + qty)
        )
    db.commit()