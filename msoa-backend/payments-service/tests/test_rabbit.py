import asyncio
import json
import uuid
from pathlib import Path

import jsonschema

from app.messaging import rabbit
from app.clients.orders_client import OrderView


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "shipment.requested.v1.schema.json"
)


def make_order():
    return OrderView(
        id="order-123",
        total=250.0,
        status="PAID",
        user_id="user-1",
        customer={
            "name": "Demo Customer",
            "address": "123 Main Street",
            "city": "Casablanca",
        },
    )


def test_shipment_message_matches_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    message = rabbit.build_shipment_message(make_order())

    jsonschema.validate(
        instance=message,
        schema=schema,
        format_checker=jsonschema.FormatChecker(),
    )

    assert message["type"] == "shipment.requested"
    assert message["version"] == 1
    assert message["orderId"] == "order-123"
    assert message["userId"] == "user-1"
    assert message["customer"]["city"] == "Casablanca"


def test_shipment_message_id_is_a_valid_uuid():
    message = rabbit.build_shipment_message(make_order())

    parsed_id = uuid.UUID(message["messageId"])

    assert str(parsed_id) == message["messageId"]


def test_each_shipment_message_has_a_unique_id():
    first = rabbit.build_shipment_message(make_order())
    second = rabbit.build_shipment_message(make_order())

    assert first["messageId"] != second["messageId"]


def test_unreachable_rabbit_broker_does_not_raise(monkeypatch):
    async def unavailable_broker(*args, **kwargs):
        raise OSError("RabbitMQ is unavailable")

    monkeypatch.setattr(
        rabbit.aio_pika,
        "connect_robust",
        unavailable_broker,
    )

    publisher = rabbit.RabbitPublisher()
    publisher.ATTEMPTS = 1

    message = rabbit.build_shipment_message(make_order())

    result = asyncio.run(publisher._send(message))

    assert result is False