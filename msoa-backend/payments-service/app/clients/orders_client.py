import os, httpx
from dataclasses import dataclass
from fastapi import HTTPException

ORDERS_URL = os.getenv("ORDERS_URL", "http://localhost:8084")

@dataclass
class OrderView:
    id: str
    total: float
    status: str

class OrdersClient:
    def __init__(self, base_url: str = ORDERS_URL, timeout: float = 5.0):
        self.base_url, self.timeout = base_url, timeout

    @staticmethod
    def _headers(auth: str | None):
        return {"Authorization": auth} if auth else {}

    def get_order(self, order_id: str, auth: str | None = None):
        try:
            r = httpx.get(f"{self.base_url}/api/orders/{order_id}",
                          headers=self._headers(auth), timeout=self.timeout)
        except httpx.RequestError:
            raise HTTPException(503, "Orders service unavailable.")
        if r.status_code == 404:
            return None
        if r.status_code in (401, 403):
            raise HTTPException(r.status_code, "Not authorized to access this order.")
        if r.status_code >= 400:
            raise HTTPException(503, "Orders service error.")
        d = r.json()
        return OrderView(id=d["id"], total=float(d["total"]), status=d["status"])

    def mark_paid(self, order_id: str, auth: str | None = None):
        try:
            r = httpx.patch(f"{self.base_url}/api/orders/{order_id}/status",
                            json={"status": "PAID"},
                            headers=self._headers(auth), timeout=self.timeout)
            r.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError):
            raise HTTPException(503, "Could not update order status.")