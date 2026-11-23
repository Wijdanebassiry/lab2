"""RabbitMQ producer: Payments -> Shipping."""
import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone

import aio_pika

log = logging.getLogger("payments.rabbit")

RABBITMQ_URL = os.getenv(
    "RABBITMQ_URL",
    "amqp://guest:guest@localhost:5672/"
)

EXCHANGE = "shipping.exchange"
DLX = "shipping.dlx"
QUEUE = "shipment.requests"
DLQ = "shipment.requests.dlq"
ROUTING_KEY = "shipment.requested"


def build_shipment_message(order):
    customer = order.customer

    return {
        "messageId": str(uuid.uuid4()),
        "type": "shipment.requested",
        "version": 1,
        "occurredAt": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "orderId": str(order.id),
        "userId": str(order.user_id),
        "customer": {
            "name": customer["name"],
            "address": customer["address"],
            "city": customer["city"],
        },
    }


class RabbitPublisher:
    ATTEMPTS = 3
    TIMEOUT_S = 3

    def __init__(self, url=RABBITMQ_URL, enabled=True):
        self.url = url
        self.enabled = enabled
        self._loop = None
        self._thread = None
        self._lock = threading.Lock()

    def publish_shipment_requested(self, order):
        """Schedule publication without blocking the payment."""
        if not self.enabled:
            return

        try:
            message = build_shipment_message(order)
            loop = self._ensure_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._send(message), loop
            )
            future.add_done_callback(self._on_done)
        except Exception as exc:
            log.warning("RabbitMQ publication not scheduled: %s", exc)

    def _ensure_loop(self):
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=self._run,
                    args=(loop,),
                    name="rabbit-producer",
                    daemon=True,
                )
                thread.start()
                self._loop = loop
                self._thread = thread
            return self._loop

    @staticmethod
    def _run(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    @staticmethod
    def _on_done(future):
        try:
            future.result()
        except Exception as exc:
            log.warning("RabbitMQ publication failed: %s", exc)

    async def _send(self, payload):
        for attempt in range(1, self.ATTEMPTS + 1):
            connection = None
            try:
                connection = await asyncio.wait_for(
                    aio_pika.connect_robust(self.url),
                    timeout=self.TIMEOUT_S,
                )

                async with connection:
                    channel = await connection.channel(
                        publisher_confirms=True
                    )

                    exchange = await channel.declare_exchange(
                        EXCHANGE,
                        aio_pika.ExchangeType.DIRECT,
                        durable=True,
                    )

                    dlx = await channel.declare_exchange(
                        DLX,
                        aio_pika.ExchangeType.DIRECT,
                        durable=True,
                    )

                    queue = await channel.declare_queue(
                        QUEUE,
                        durable=True,
                        arguments={
                            "x-dead-letter-exchange": DLX,
                            "x-dead-letter-routing-key": DLQ,
                        },
                    )

                    dead_queue = await channel.declare_queue(
                        DLQ,
                        durable=True,
                    )

                    await queue.bind(
                        exchange,
                        routing_key=ROUTING_KEY,
                    )

                    await dead_queue.bind(
                        dlx,
                        routing_key=DLQ,
                    )

                    message = aio_pika.Message(
                        body=json.dumps(payload).encode("utf-8"),
                        content_type="application/json",
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        message_id=payload["messageId"],
                    )

                    await exchange.publish(
                        message,
                        routing_key=ROUTING_KEY,
                    )

                log.info(
                    "RabbitMQ: shipment.requested published for order %s",
                    payload["orderId"],
                )
                return True

            except Exception as exc:
                log.warning(
                    "RabbitMQ unavailable (attempt %d/%d): %s",
                    attempt,
                    self.ATTEMPTS,
                    exc,
                )
                if attempt < self.ATTEMPTS:
                    await asyncio.sleep(attempt)

        log.error(
            "Shipment event abandoned for order %s",
            payload["orderId"],
        )
        return False

    def close(self, timeout=5.0):
        with self._lock:
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None

        if loop is None:
            return

        loop.call_soon_threadsafe(loop.stop)

        if thread:
            thread.join(timeout)


publisher = RabbitPublisher()