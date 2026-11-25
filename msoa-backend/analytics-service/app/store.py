"""Stockage SQLite des evenements recus de Kafka.

Une seule table `events`. L'idempotence repose sur `event_id` (UNIQUE) : un
evenement livre deux fois par Kafka n'est stocke qu'une fois. Le resume est
recalcule a partir de cette table, donc un rejeu depuis le debut donne
exactement les memes chiffres.
"""
import json
import os
import sqlite3
import threading


class EventStore:
    def __init__(self, path: str | None = None):
        path = path or os.getenv("ANALYTICS_DB", "data/analytics.db")
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    topic TEXT, partition INTEGER, kafka_offset INTEGER,
                    event_type TEXT NOT NULL, source TEXT NOT NULL,
                    order_id TEXT, occurred_at TEXT NOT NULL, data TEXT NOT NULL)"""
            )
            self._db.commit()

    def add(self, envelope: dict, topic=None, partition=None, offset=None) -> bool:
        """Retourne True si l'evenement est nouveau, False si c'est un doublon."""
        data = envelope["data"]
        order_id = data.get("orderId")
        with self._lock:
            cur = self._db.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, topic, partition, kafka_offset, event_type, source,
                    order_id, occurred_at, data) VALUES (?,?,?,?,?,?,?,?,?)""",
                (envelope["eventId"], topic, partition, offset, envelope["eventType"],
                 envelope["source"], None if order_id is None else str(order_id),
                 envelope["occurredAt"], json.dumps(data)),
            )
            self._db.commit()
            return cur.rowcount == 1

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM events")
            self._db.commit()

    def _rows(self, where="", params=(), order="occurred_at, seq", limit=None):
        sql = f"SELECT * FROM events {where} ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    @staticmethod
    def _to_dict(r) -> dict:
        return {
            "eventId": r["event_id"], "eventType": r["event_type"], "source": r["source"],
            "occurredAt": r["occurred_at"], "orderId": r["order_id"],
            "topic": r["topic"], "partition": r["partition"], "offset": r["kafka_offset"],
            "data": json.loads(r["data"]),
        }

    def list_events(self, event_type=None, order_id=None, limit=100) -> list[dict]:
        clauses, params = [], []
        if event_type:
            clauses.append("event_type = ?"); params.append(event_type)
        if order_id:
            clauses.append("order_id = ?"); params.append(order_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return [self._to_dict(r) for r in self._rows(where, tuple(params), "seq DESC", limit)]

    def summary(self) -> dict:
        rows = self._rows()
        created, cancelled = set(), set()
        completed, failed = {}, 0
        shipments: dict[str, str] = {}
        for r in rows:                      # tries par date de l'evenement
            d, t = json.loads(r["data"]), r["event_type"]
            if t == "OrderCreated":
                created.add(str(d["orderId"]))
            elif t == "OrderCancelled":
                cancelled.add(str(d["orderId"]))
            elif t == "PaymentCompleted":
                completed[str(d["paymentId"])] = float(d["amount"])
            elif t == "PaymentFailed":
                failed += 1
            elif t == "ShipmentCreated":
                shipments.setdefault(str(d["shipmentId"]), "PREPARING")
            elif t == "ShipmentStatusChanged":
                shipments[str(d["shipmentId"])] = str(d["status"])
        by_status: dict[str, int] = {}
        for s in shipments.values():
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "orders": {"created": len(created), "cancelled": len(cancelled),
                       "active": len(created - cancelled)},
            "payments": {"completed": len(completed), "failed": failed},
            "revenue": {"amount": round(sum(completed.values()), 2), "currency": "MAD"},
            "shipments": {"total": len(shipments), "byStatus": by_status},
            "eventsProcessed": len(rows),
            "lastEventAt": rows[-1]["occurred_at"] if rows else None,
        }
