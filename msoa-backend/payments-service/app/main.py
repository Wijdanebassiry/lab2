from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FHTTPException
from .database import Base, engine
from .routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Payment Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(FHTTPException)
async def http_exc(request: Request, exc: FHTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"message": exc.detail, "detail": exc.detail})

app.include_router(router)

@app.get("/health")
def health():
    return {"status": "UP", "service": "payment"}
