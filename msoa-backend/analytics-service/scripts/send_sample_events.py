"""Envoie quelques evenements de test dans Kafka (sans Orders/Shipping).

    python scripts/send_sample_events.py

Utile pour tester Analytics seul. Les topics doivent exister (infra/README.md).
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")


def env(event_type, source, data):
    return {"eventId": str(uuid.uuid4()), "eventType": event_type, "version": 1,
            "occurredAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "source": source, "data": data}


async def main():
    oid = f"demo-{uuid.uuid4().hex[:6]}"
    events = [
        ("orders.events", env("OrderCreated", "orders", {"orderId": oid, "userId": "u1", "total": 250.0,
                              "currency": "MAD", "items": [{"productId": "1", "quantity": 1, "price": 250.0}]})),
        ("payments.events", env("PaymentCompleted", "payments", {"orderId": oid, "paymentId": f"pay-{oid}",
                                "amount": 250.0, "method": "CARD"})),
        ("shipments.events", env("ShipmentCreated", "shipping", {"orderId": oid, "shipmentId": uuid.uuid4().hex[:6],
                                 "trackingNumber": "TRK-DEMO"})),
    ]
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await producer.start()
    try:
        for topic, e in events:
            await producer.send_and_wait(topic, json.dumps(e).encode(), key=oid.encode())
            print("envoye", e["eventType"], "->", topic)
    finally:
        await producer.stop()


asyncio.run(main())
