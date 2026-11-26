
"""Endpoints du registre de services."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .registry import registry, RegistryError

router = APIRouter(prefix="/registry")


@router.post("/register")
async def register_service(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON body."},
        )

    if not isinstance(data, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "Request body must be a JSON object."},
        )

    try:
        name, address = registry.register(
            data.get("name"),
            data.get("address"),
        )
    except RegistryError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    return {
        "message": "Service registered successfully",
        "name": name,
        "address": address,
    }


@router.get("/services")
def get_services():
    return registry.all()
