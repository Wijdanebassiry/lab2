"""Publication des evenements Payments dans Kafka (Lab 4, cas 3).

Regles du contrat (CONTRACTS.md, section Lab 4) :
  - topic `payments.events`, cle du message = orderId ;
  - enveloppe commune : eventId, eventType, version, occurredAt, source, data ;
  - publication APRES l'enregistrement en base ;
  - une panne de Kafka ne fait JAMAIS echouer le paiement.

aiokafka est asynchrone alors que les routes de Payments sont synchrones. Le
producteur tourne donc dans un thread d'arriere-plan qui possede sa propre
boucle asyncio : publish() rend la main immediatement, sans jamais bloquer ni
lever d'exception.
"""
import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone

log = logging.getLogger("payments.kafka")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_PAYMENTS_TOPIC", "payments.events")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() != "false"
SOURCE = "payments"


# ---------------------------------------------------------------------------
# Enveloppe (fonction pure, a partager avec Orders et Shipping)
# ---------------------------------------------------------------------------
def build_envelope(event_type: str, data: dict, source: str = SOURCE) -> dict:
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "version": 1,
        "occurredAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "source": source,
        "data": data,
    }


def payment_completed_envelope(order_id: str, payment_id: str, amount: float, method: str) -> dict:
    return build_envelope("PaymentCompleted", {
        "orderId": order_id, "paymentId": payment_id,
        "amount": float(amount), "method": str(method),
    })


def payment_failed_envelope(order_id: str, method: str, reason: str) -> dict:
    return build_envelope("PaymentFailed", {
        "orderId": order_id, "method": str(method), "reason": reason or "declined",
    })


# ---------------------------------------------------------------------------
# Producteur
# ---------------------------------------------------------------------------
class KafkaEventPublisher:
    ATTEMPTS = 3          # essais par evenement (pause de 1 s, puis 2 s)
    TIMEOUT_S = 5         # delai maximal par connexion / envoi

    def __init__(self, bootstrap: str = KAFKA_BOOTSTRAP, topic: str = KAFKA_TOPIC,
                 enabled: bool = KAFKA_ENABLED):
        self.bootstrap, self.topic, self.enabled = bootstrap, topic, enabled
        self._loop = None
        self._thread = None
        self._producer = None
        self._lock = threading.Lock()

    # -- API utilisee par le service metier ---------------------------------
    def publish_payment_completed(self, order_id, payment_id, amount, method):
        self.publish(order_id, payment_completed_envelope(order_id, payment_id, amount, method))

    def publish_payment_failed(self, order_id, method, reason):
        self.publish(order_id, payment_failed_envelope(order_id, method, reason))

    def publish(self, key: str, envelope: dict) -> None:
        """Planifie l'envoi et rend la main tout de suite. Ne leve jamais."""
        if not self.enabled:
            log.debug("Kafka desactive, evenement ignore : %s", envelope.get("eventType"))
            return
        try:
            loop = self._ensure_loop()
            fut = asyncio.run_coroutine_threadsafe(self._send(key, envelope), loop)
            fut.add_done_callback(self._on_done)
        except Exception as exc:  # jamais d'impact sur le paiement
            log.warning("Evenement %s non planifie : %s", envelope.get("eventType"), exc)

    def close(self, timeout: float = 5.0) -> None:
        with self._lock:
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._stop(), loop).result(timeout)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
        if thread:
            thread.join(timeout)

    # -- Interne -------------------------------------------------------------
    def _ensure_loop(self):
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(target=self._run, args=(loop,),
                                          name="kafka-producer", daemon=True)
                thread.start()
                self._loop, self._thread = loop, thread
            return self._loop

    @staticmethod
    def _run(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    @staticmethod
    def _on_done(fut):
        try:
            fut.result()
        except BaseException as exc:
            log.warning("Envoi Kafka interrompu : %r", exc)

    async def _get_producer(self):
        if self._producer is not None:
            return self._producer
        from aiokafka import AIOKafkaProducer   # import tardif : un probleme de librairie ne bloque pas le service
        producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap, acks="all",
                                    enable_idempotence=True, request_timeout_ms=3000,
                                    client_id="payments-service")
        try:
            await asyncio.wait_for(producer.start(), timeout=self.TIMEOUT_S)
        except Exception:
            try:
                await producer.stop()
            except Exception:
                pass
            raise
        self._producer = producer
        return producer

    async def _send(self, key: str, envelope: dict) -> bool:
        value = json.dumps(envelope).encode("utf-8")
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                producer = await self._get_producer()
                await asyncio.wait_for(
                    producer.send_and_wait(self.topic, value=value, key=str(key).encode("utf-8")),
                    timeout=self.TIMEOUT_S)
                log.info("Kafka <- %s (%s) sur %s", envelope["eventType"], key, self.topic)
                return True
            except Exception as exc:
                log.warning("Kafka indisponible (essai %d/%d) : %s", attempt, self.ATTEMPTS, exc)
                if attempt < self.ATTEMPTS:
                    await asyncio.sleep(attempt)
        log.error("Evenement %s abandonne apres %d essais (orderId=%s)",
                  envelope["eventType"], self.ATTEMPTS, key)
        return False

    async def _stop(self):
        current = asyncio.current_task()
        for t in asyncio.all_tasks():
            if t is not current:
                t.cancel()
        if self._producer is not None:
            try:
                await self._producer.stop()
            except Exception:
                pass
            self._producer = None


publisher = KafkaEventPublisher()
