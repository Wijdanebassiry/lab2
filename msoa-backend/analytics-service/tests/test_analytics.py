import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.consumer import AnalyticsConsumer
from app.main import app, consumer as app_consumer, store as app_store
from app.store import EventStore


def env(event_type, source, data, event_id=None, at=None):
    return {"eventId": event_id or str(uuid.uuid4()), "eventType": event_type, "version": 1,
            "occurredAt": at or datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "source": source, "data": data}


def order_created(oid="o1", total=250.0, **kw):
    return env("OrderCreated", "orders", {"orderId": oid, "userId": "u1", "total": total, "currency": "MAD",
               "items": [{"productId": "1", "quantity": 1, "price": total}]}, **kw)


def payment_completed(oid="o1", pid="p1", amount=250.0, **kw):
    return env("PaymentCompleted", "payments", {"orderId": oid, "paymentId": pid, "amount": amount, "method": "CARD"}, **kw)


@pytest.fixture
def c():
    store = EventStore(":memory:")
    return AnalyticsConsumer(store, enabled=False), store


def send(consumer, topic, envelope, offset=0):
    return consumer.process(topic, 0, offset, json.dumps(envelope))


def test_valid_event_is_stored(c):
    consumer, store = c
    assert send(consumer, "orders.events", order_created()) == "stored"
    assert store.summary()["orders"]["created"] == 1


def test_duplicate_event_is_ignored(c):
    consumer, store = c
    e = order_created(event_id="same-id")
    assert send(consumer, "orders.events", e) == "stored"
    assert send(consumer, "orders.events", e, offset=1) == "duplicate"
    assert store.summary()["eventsProcessed"] == 1 and consumer.stats["duplicates"] == 1


def test_invalid_messages_are_rejected_without_crash(c):
    consumer, store = c
    assert consumer.process("t", 0, 0, b"not json") == "rejected"
    bad = payment_completed(); del bad["data"]["paymentId"]
    assert send(consumer, "payments.events", bad) == "rejected"
    wrong_source = payment_completed(); wrong_source["source"] = "orders"
    assert send(consumer, "payments.events", wrong_source) == "rejected"
    assert store.summary()["eventsProcessed"] == 0 and consumer.stats["rejected"] == 3


def test_summary_counts_orders_payments_revenue_and_shipments(c):
    consumer, store = c
    send(consumer, "orders.events", order_created("o1", 250.0, at="2026-11-23T10:00:00.000Z"))
    send(consumer, "orders.events", order_created("o2", 100.0, at="2026-11-23T10:01:00.000Z"))
    send(consumer, "orders.events", env("OrderCancelled", "orders", {"orderId": "o2", "userId": "u1"}, at="2026-11-23T10:02:00.000Z"))
    send(consumer, "payments.events", payment_completed("o1", "p1", 250.0, at="2026-11-23T10:03:00.000Z"))
    send(consumer, "payments.events", env("PaymentFailed", "payments", {"orderId": "o3", "method": "CARD", "reason": "card_declined"}))
    send(consumer, "shipments.events", env("ShipmentCreated", "shipping", {"orderId": "o1", "shipmentId": 7, "trackingNumber": "TRK1"}, at="2026-11-23T10:04:00.000Z"))
    send(consumer, "shipments.events", env("ShipmentStatusChanged", "shipping",
         {"orderId": "o1", "shipmentId": 7, "status": "SHIPPED", "previousStatus": "PREPARING"}, at="2026-11-23T10:05:00.000Z"))
    s = store.summary()
    assert s["orders"] == {"created": 2, "cancelled": 1, "active": 1}
    assert s["payments"] == {"completed": 1, "failed": 1}
    assert s["revenue"] == {"amount": 250.0, "currency": "MAD"}
    assert s["shipments"] == {"total": 1, "byStatus": {"SHIPPED": 1}}


def test_summary_is_independent_of_arrival_order(c):
    consumer, store = c
    send(consumer, "shipments.events", env("ShipmentStatusChanged", "shipping",
         {"orderId": "o1", "shipmentId": 7, "status": "SHIPPED", "previousStatus": "PREPARING"}, at="2026-11-23T10:05:00.000Z"))
    send(consumer, "shipments.events", env("ShipmentCreated", "shipping",
         {"orderId": "o1", "shipmentId": 7, "trackingNumber": "T"}, at="2026-11-23T10:04:00.000Z"))
    assert store.summary()["shipments"]["byStatus"] == {"SHIPPED": 1}


# --- API HTTP -----------------------------------------------------------------
@pytest.fixture
def client():
    app_store.clear()
    with TestClient(app) as cl:
        yield cl
    app_store.clear()


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "UP" and r["service"] == "analytics" and r["kafka"] == "disabled"


def test_summary_and_events_endpoints(client):
    send(app_consumer, "orders.events", order_created("o1"))
    send(app_consumer, "payments.events", payment_completed("o1"))
    assert client.get("/api/analytics/summary").json()["orders"]["created"] == 1
    assert len(client.get("/api/analytics/events").json()) == 2
    only = client.get("/api/analytics/events", params={"eventType": "PaymentCompleted"}).json()
    assert [e["eventType"] for e in only] == ["PaymentCompleted"]
    assert len(client.get("/api/analytics/events", params={"orderId": "zzz"}).json()) == 0


def test_replay_endpoint_is_accepted_and_resets_view_when_kafka_is_off(client):
    send(app_consumer, "orders.events", order_created("o1"))
    r = client.post("/api/analytics/replay")
    assert r.status_code == 202 and r.json()["status"] == "REPLAY_SCHEDULED"
    assert client.get("/api/analytics/summary").json()["eventsProcessed"] == 0


# --- Boucle Kafka avec un faux consommateur (commit apres stockage, rejeu) ------
class FakeMsg:
    def __init__(self, topic, offset, value):
        self.topic, self.partition, self.offset, self.value = topic, 0, offset, value


class FakeKafka:
    def __init__(self, messages):
        self.messages, self.calls, self.seeked, self.commits = messages, 0, 0, []

    async def getmany(self, timeout_ms=0):
        import asyncio
        self.calls += 1
        if self.calls == 1:
            return {("t", 0): self.messages}
        raise asyncio.CancelledError

    async def commit(self):
        self.commits.append(c_store_count())   # nombre d'evenements deja en base au moment du commit

    async def seek_to_beginning(self):
        self.seeked += 1


_current = {}


def c_store_count():
    return _current["store"].summary()["eventsProcessed"]


def run_loop(consumer, fake):
    import asyncio
    _current["store"] = consumer.store
    try:
        asyncio.run(consumer._consume(fake))
    except asyncio.CancelledError:
        pass


def test_loop_commits_only_after_events_are_stored(c):
    consumer, store = c
    fake = FakeKafka([FakeMsg("orders.events", 0, json.dumps(order_created("o1"))),
                      FakeMsg("orders.events", 1, json.dumps(order_created("o2")))])
    run_loop(consumer, fake)
    assert fake.commits == [2]            # commit appele quand les 2 evenements sont deja stockes


def test_loop_replay_clears_store_and_seeks_to_beginning(c):
    consumer, store = c
    send(consumer, "orders.events", order_created("old"))
    consumer._replay = True
    fake = FakeKafka([FakeMsg("orders.events", 0, json.dumps(order_created("o1")))])
    run_loop(consumer, fake)
    assert fake.seeked == 1
    assert store.summary()["orders"]["created"] == 1      # "old" a disparu, "o1" relu
