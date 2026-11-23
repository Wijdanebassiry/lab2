from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from .database import Base, engine
from .routes import router
from .messaging import kafka_events
from contextlib import asynccontextmanager
from .messaging import kafka_events, rabbit

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app):
    yield
    kafka_events.publisher.close()
    rabbit.publisher.close()
     # vide et ferme proprement le producteur Kafka

app = FastAPI(title="Payment Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(FHTTPException)
async def http_exc(request: Request, exc: FHTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"message": exc.detail, "detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exc(request: Request, exc: RequestValidationError):
    # Meme format d'erreur que les autres codes (cf. CONTRACTS.md)
    return JSONResponse(status_code=422,
                        content={"message": "Invalid request body.",
                                 "detail": jsonable_encoder(exc.errors())})
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "UP", "service": "payment"}
