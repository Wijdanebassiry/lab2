from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Base, SessionLocal, engine
from .models import Stock
from .routes import router

SEED = [
    {"product_id": "1", "quantity": 12},  # Lenovo ThinkPad E14
    {"product_id": "2", "quantity": 20},  # Samsung Galaxy A55
    {"product_id": "3", "quantity": 8},   # Sony WH-1000XM5
    {"product_id": "4", "quantity": 25},  # Logitech MX Master 3S
    {"product_id": "5", "quantity": 10},  # Dell UltraSharp 27
    {"product_id": "6", "quantity": 15},  # Apple iPad Air
]


def seed() -> None:
    with SessionLocal() as db:
        if db.query(Stock).count() == 0:
            db.add_all([Stock(**row) for row in SEED])
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    yield


app = FastAPI(title="Inventory Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    first = exc.errors()[0]
    loc = ".".join(str(x) for x in first["loc"] if x != "body")
    return JSONResponse(
        status_code=422,
        content={"message": "Invalid request body.", "detail": f"{loc}: {first['msg']}"},
    )


app.include_router(router)


@app.get("/health")
def health():
    return {"status": "UP", "service": "inventory"}