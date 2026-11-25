"""Consommateur Kafka d'Analytics (groupe `analytics`, lecture depuis le debut).

- Valide chaque message avec le schema du contrat ; un message invalide est
  ignore (journalise et compte), il ne bloque jamais le consommateur.
- Idempotent : un doublon (meme eventId) n'est pas stocke deux fois.
- L'offset n'est valide (commit) qu'APRES l'enregistrement en base.
- Si Kafka est arrete, le service reste en vie et se reconnecte tout seul.
"""
import asyncio
import json
import logging
import os
from pathlib import Path

from jsonschema import Draft202012Validator

from .store import EventStore

log = logging.getLogger("analytics.consumer")

TOPICS = [t.strip() for t in os.getenv(
    "KAFKA_TOPICS", "orders.events,payments.events,shipments.events").split(",")]
SCHEMA_PATH = Path(os.getenv("ANALYTICS_SCHEMA_PATH") or
                   Path(__file__).resolve().parents[2] / "contracts" / "event.envelope.v1.schema.json")


def load_validator(path: Path = SCHEMA_PATH):
    try:
        return Draft202012Validator(json.loads(Path(path).read_text(encoding="utf-8")))
    except OSError:
        log.warning("Schema %s introuvable : validation du contrat desactivee", path)
        return None


class AnalyticsConsumer:
    def __init__(self, store: EventStore, validator=None, bootstrap: str | None = None,
                 group: str | None = None, enabled: bool | None = None):
        self.store = store
        self.validator = validator if validator is not None else load_validator()
        self.bootstrap = bootstrap or os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
        self.group = group or os.getenv("ANALYTICS_GROUP", "analytics")
        self.enabled = enabled if enabled is not None else \
            os.getenv("KAFKA_ENABLED", "true").lower() != "false"
        self.connected = False
        self.stats = {"stored": 0, "duplicates": 0, "rejected": 0}
        self._replay = False
        self._task: asyncio.Task | None = None

    # -- Traitement d'un message (fonction testable sans Kafka) ---------------
    def process(self, topic, partition, offset, raw: bytes | str) -> str:
        try:
            envelope = json.loads(raw)
            if self.validator is not None:
                errors = [e.message for e in self.validator.iter_errors(envelope)]
                if errors:
                    raise ValueError(errors[0])
            elif not isinstance(envelope, dict) or "eventId" not in envelope:
                raise ValueError("enveloppe invalide")
        except (ValueError, TypeError) as exc:
            self.stats["rejected"] += 1
            log.warning("Message rejete (%s, p%s, offset %s) : %s", topic, partition, offset, exc)
            return "rejected"
        if self.store.add(envelope, topic, partition, offset):
            self.stats["stored"] += 1
            return "stored"
        self.stats["duplicates"] += 1
        return "duplicate"

    # -- Rejeu ----------------------------------------------------------------
    def request_replay(self) -> None:
        """Recalcule tout depuis le debut du journal Kafka."""
        self._replay = True
        if not self.connected:
            self.store.clear()          # vue coherente tout de suite ; relecture a la reconnexion

    # -- Boucle Kafka -----------------------------------------------------------
    def start(self) -> None:
        if self.enabled and self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _run(self) -> None:
        from aiokafka import AIOKafkaConsumer      # import tardif
        while True:
            consumer = AIOKafkaConsumer(
                *TOPICS, bootstrap_servers=self.bootstrap, group_id=self.group,
                auto_offset_reset="earliest", enable_auto_commit=False,
                client_id="analytics-service")
            try:
                await consumer.start()
                self.connected = True
                log.info("Connecte a Kafka (%s), groupe %s, topics %s", self.bootstrap, self.group, TOPICS)
                await self._consume(consumer)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Kafka indisponible : %s (nouvel essai dans 3 s)", exc)
            finally:
                self.connected = False
                try:
                    await consumer.stop()
                except Exception:
                    pass
            await asyncio.sleep(3)

    async def _consume(self, consumer) -> None:
        while True:
            if self._replay:
                await self._do_replay(consumer)
            batches = await consumer.getmany(timeout_ms=1000)
            if not batches:
                continue
            for tp, messages in batches.items():
                for m in messages:
                    self.process(m.topic, m.partition, m.offset, m.value)
            await consumer.commit()              # apres l'enregistrement en base

    async def _do_replay(self, consumer) -> None:
        self._replay = False
        self.store.clear()
        await consumer.seek_to_beginning()
        log.info("Rejeu : base videe, relecture depuis le debut")
