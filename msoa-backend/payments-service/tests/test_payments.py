import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import app
from app import routes
from app.clients.orders_client import OrderView

class FakeOrders:
    def __init__(self): self.seen_auth = []; self.order = OrderView("o1", 100.0, "PENDING_PAYMENT"); self.paid = False; self.fail_update = False
    def get_order(self, oid, auth=None):
        self.seen_auth.append(auth)
        return self.order if oid == "o1" else None
    def mark_paid(self, oid, auth=None):
        self.seen_auth.append(auth)
        if self.fail_update: raise HTTPException(503, "Could not update order status.")
        self.paid = True; self.order.status = "PAID"
        
@pytest.fixture
def client(monkeypatch):
    fake = FakeOrders()
    monkeypatch.setattr(routes, "orders", fake)
    from app.database import SessionLocal
    from app.models import Payment
    db = SessionLocal(); db.query(Payment).delete(); db.commit(); db.close()
    return TestClient(app), fake

def test_success(client):
    c, fake = client
    r = c.post("/api/payments", json={"orderId": "o1", "method": "CARD"})
    assert r.status_code == 201 and r.json()["status"] == "SUCCESS" and r.json()["amount"] == 100.0
    assert fake.paid

def test_unknown_order(client):
    c, _ = client
    assert c.post("/api/payments", json={"orderId": "zzz"}).status_code == 404

def test_double_payment(client):
    c, fake = client
    c.post("/api/payments", json={"orderId": "o1"})
    fake.order.status = "PENDING_PAYMENT"
    assert c.post("/api/payments", json={"orderId": "o1"}).status_code == 409

def test_decline(client):
    c, fake = client
    r = c.post("/api/payments", json={"orderId": "o1", "method": "TEST_DECLINE"})
    assert r.status_code == 402 and not fake.paid

def test_timeout(client):
    c, _ = client
    assert c.post("/api/payments", json={"orderId": "o1", "method": "TEST_TIMEOUT"}).status_code == 503

def test_refund_on_orders_failure(client):
    c, fake = client
    fake.fail_update = True
    assert c.post("/api/payments", json={"orderId": "o1"}).status_code == 503
    assert c.get("/api/payments/order/o1").json()["status"] == "REFUNDED"

def test_by_order_404(client):
    c, _ = client
    assert c.get("/api/payments/order/none").status_code == 404

def test_missing_order_id(client):
    c, _ = client
    assert c.post("/api/payments", json={}).status_code == 422

def test_health(client):
    c, _ = client
    assert c.get("/health").json()["status"] == "UP"

def test_token_forwarded_to_orders(client):
    c, fake = client
    r = c.post("/api/payments", json={"orderId": "o1"}, headers={"Authorization": "Bearer abc"})
    assert r.status_code == 201
    assert fake.seen_auth == ["Bearer abc", "Bearer abc"]

def test_works_without_token(client):
    c, fake = client
    assert c.post("/api/payments", json={"orderId": "o1"}).status_code == 201
    assert fake.seen_auth == [None, None]