import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app import routes
from app.clients.orders_client import OrderView
from app.main import app
from app.messaging.kafka_events import (
    KafkaEventPublisher, build_envelope,
    payment_completed_envelope, payment_failed_envelope,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "event.envelope.v1.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


class FakeOrders:
    def __init__(self):
        self.order = OrderView("o1", 100.0, "PENDING_PAYMENT")
        self.fail_update = False

    def get_order(self, oid, auth=None):
        return self.order if oid == "o1" else None

    def mark_paid(self, oid, auth=None):
        if self.fail_update:
            raise HTTPException(503, "Could not update order status.")
        self.order.status = "PAID"


class FakeEvents:
    """Enregistre les appels (key, envelope) comme le ferait Kafka."""
    def __init__(self):
        self.sent = []

    def publish_payment_completed(self, order_id, payment_id, amount, method):
        self.sent.append((order_id, payment_completed_envelope(order_id, payment_id, amount, method)))

    def publish_payment_failed(self, order_id, method, reason):
        self.sent.append((order_id, payment_failed_envelope(order_id, method, reason)))


class ExplodingEvents:
    def publish_payment_completed(self, *a):
        raise RuntimeError("Kafka is down")

    def publish_payment_failed(self, *a):
        raise RuntimeError("Kafka is down")


@pytest.fixture
def setup(monkeypatch):
    orders, events = FakeOrders(), FakeEvents()
    monkeypatch.setattr(routes, "orders", orders)
    monkeypatch.setattr(routes, "events", events)
    from app.database import SessionLocal
    from app.models import Payment
    db = SessionLocal(); db.query(Payment).delete(); db.commit(); db.close()
    return TestClient(app), orders, events


def assert_valid(envelope):
    errors = [e.message for e in VALIDATOR.iter_errors(envelope)]
    assert errors == [], errors
    datetime.fromisoformat(envelope["occurredAt"].replace("Z", "+00:00"))


# --- Enveloppe : respect du schema du contrat ------------------------------
def test_completed_envelope_matches_schema():
    env = payment_completed_envelope("order-demo-001", "pay-1", 250.0, "CARD")
    assert_valid(env)
    assert env["eventType"] == "PaymentCompleted" and env["source"] == "payments" and env["version"] == 1
    assert env["data"] == {"orderId": "order-demo-001", "paymentId": "pay-1", "amount": 250.0, "method": "CARD"}


def test_failed_envelope_matches_schema():
    env = payment_failed_envelope("o1", "TEST_DECLINE", "card_declined")
    assert_valid(env)
    assert env["data"] == {"orderId": "o1", "method": "TEST_DECLINE", "reason": "card_declined"}


def test_event_ids_are_unique():
    a = build_envelope("PaymentFailed", {"orderId": "o", "method": "CARD", "reason": "x"})
    b = build_envelope("PaymentFailed", {"orderId": "o", "method": "CARD", "reason": "x"})
    assert a["eventId"] != b["eventId"]


def test_envelope_missing_field_is_rejected_by_schema():
    env = payment_completed_envelope("o1", "p1", 10.0, "CARD")
    del env["data"]["paymentId"]
    assert list(VALIDATOR.iter_errors(env))


# --- Quand publie-t-on ? ----------------------------------------------------
def test_completed_event_published_after_success(setup):
    c, _, events = setup
    r = c.post("/api/payments", json={"orderId": "o1", "method": "CARD"})
    assert r.status_code == 201
    assert len(events.sent) == 1
    key, env = events.sent[0]
    assert key == "o1"                                   # cle = orderId
    assert_valid(env)
    assert env["eventType"] == "PaymentCompleted"
    assert env["data"]["paymentId"] == r.json()["id"] and env["data"]["amount"] == 100.0


def test_failed_event_published_after_decline(setup):
    c, _, events = setup
    assert c.post("/api/payments", json={"orderId": "o1", "method": "TEST_DECLINE"}).status_code == 402
    assert [e["eventType"] for _, e in events.sent] == ["PaymentFailed"]
    key, env = events.sent[0]
    assert key == "o1" and env["data"]["reason"] == "card_declined"
    assert_valid(env)


def test_failed_event_published_on_provider_timeout(setup):
    c, _, events = setup
    assert c.post("/api/payments", json={"orderId": "o1", "method": "TEST_TIMEOUT"}).status_code == 503
    assert events.sent[0][1]["data"]["reason"] == "gateway_timeout"


def test_no_event_when_no_payment_attempted(setup):
    c, orders, events = setup
    assert c.post("/api/payments", json={"orderId": "zzz"}).status_code == 404
    orders.order.status = "PAID"
    assert c.post("/api/payments", json={"orderId": "o1"}).status_code == 409
    assert events.sent == []


def test_no_completed_event_when_order_update_fails(setup):
    c, orders, events = setup
    orders.fail_update = True
    assert c.post("/api/payments", json={"orderId": "o1"}).status_code == 503
    assert events.sent == []        # paiement rembourse : pas de PaymentCompleted


# --- Une panne de Kafka n'impacte jamais le paiement ------------------------
def test_publisher_exception_does_not_break_payment(setup, monkeypatch):
    c, _, _ = setup
    monkeypatch.setattr(routes, "events", ExplodingEvents())
    r = c.post("/api/payments", json={"orderId": "o1", "method": "CARD"})
    assert r.status_code == 201 and r.json()["status"] == "SUCCESS"


def test_declined_payment_keeps_its_402_when_kafka_is_down(setup, monkeypatch):
    c, _, _ = setup
    monkeypatch.setattr(routes, "events", ExplodingEvents())
    assert c.post("/api/payments", json={"orderId": "o1", "method": "TEST_DECLINE"}).status_code == 402


def test_real_publisher_with_unreachable_broker_is_fast_and_silent(setup, monkeypatch):
    c, _, _ = setup
    pub = KafkaEventPublisher(bootstrap="127.0.0.1:1", enabled=True)    # aucun broker sur ce port
    monkeypatch.setattr(routes, "events", pub)
    start = time.monotonic()
    r = c.post("/api/payments", json={"orderId": "o1", "method": "CARD"})
    elapsed = time.monotonic() - start
    pub.close()
    assert r.status_code == 201 and r.json()["status"] == "SUCCESS"
    assert elapsed < 2.0            # la reponse n'attend pas Kafka


def test_publish_never_raises_even_if_disabled_or_broken():
    KafkaEventPublisher(enabled=False).publish("o1", {"eventType": "X"})
    pub = KafkaEventPublisher(bootstrap="127.0.0.1:1", enabled=True)
    pub.publish("o1", payment_completed_envelope("o1", "p", 1.0, "CARD"))
    pub.close()
