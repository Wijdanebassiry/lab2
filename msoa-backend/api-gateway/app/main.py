"""API Gateway (Lab 5) : point d'entree unique, port 8080.

Squelette de l'etape 0 : il relie les modules ecrits par l'equipe.
  proxy.py        -> forward()        [Auth]
  registry*.py    -> registre + API   [Orders]
  resolver.py     -> resolve()        [Payments]
"""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import match_service
from .proxy import forward
from .registry_api import router as registry_router
from .resolver import resolve

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def create_app(transport=None, timeout: float | None = None) -> FastAPI:
    timeout = timeout if timeout is not None else float(os.getenv("GATEWAY_TIMEOUT", "30"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = httpx.AsyncClient(transport=transport, timeout=timeout)
        yield
        await app.state.client.aclose()

    app = FastAPI(title="API Gateway", version="1.0.0", lifespan=lifespan)
    app.include_router(registry_router)          # /registry/* : traite par la passerelle elle-meme

    @app.get("/health")
    def health():
        return {"status": "UP", "service": "api-gateway", "mode": os.getenv("GATEWAY_MODE", "dynamic")}

    @app.api_route("/{full_path:path}", methods=METHODS)   # reverse proxy : tout le reste
    async def proxy(request: Request, full_path: str):
        service = match_service(request.url.path)
        if service is None:
            return JSONResponse({"error": "No route for this path"}, status_code=404)
        address = resolve(service)
        if not address:
            return JSONResponse({"error": f"{service} is not registered"}, status_code=503)
        return await forward(request, service, address, request.app.state.client)

    return app


app = create_app()