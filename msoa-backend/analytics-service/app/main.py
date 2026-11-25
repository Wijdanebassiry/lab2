import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .consumer import AnalyticsConsumer
from .store import EventStore

logging.basicConfig(level=logging.INFO)

store = EventStore()
consumer = AnalyticsConsumer(store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer.start()
    yield
    await consumer.stop()


app = FastAPI(title="Analytics Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/analytics/summary")
def summary():
    return store.summary()


@app.get("/api/analytics/events")
def events(eventType: str | None = None, orderId: str | None = None, limit: int = 100):
    return store.list_events(eventType, orderId, max(1, min(limit, 1000)))


@app.post("/api/analytics/replay", status_code=202)
def replay():
    consumer.request_replay()
    return {"status": "REPLAY_SCHEDULED",
            "message": "Les evenements sont relus depuis le debut des topics Kafka."}


@app.get("/health")
def health():
    kafka = "disabled" if not consumer.enabled else ("connected" if consumer.connected else "disconnected")
    return {"status": "UP", "service": "analytics", "kafka": kafka, "consumer": consumer.stats}
