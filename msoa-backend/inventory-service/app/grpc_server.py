"""gRPC server of the Inventory service.

Contract: contracts/inventory.proto (package inventory.v1, service Inventory).
The server starts with the API (see the lifespan in app/main.py) and reuses the
stock logic of app/service.py, so REST and gRPC always give the same answers.
"""

import logging
import os
from concurrent import futures

import grpc

from . import service
from .database import SessionLocal
from .grpc_gen import inventory_pb2, inventory_pb2_grpc
from .schemas import Item

logger = logging.getLogger("inventory.grpc")


def _merged_items(request, context) -> dict[str, int]:
    """Validate a StockRequest and merge duplicated products."""
    if not request.items:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "items must not be empty")

    items = []
    for it in request.items:
        if not it.product_id or it.quantity <= 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "each item needs a product_id and a quantity greater than 0",
            )
        items.append(Item(productId=it.product_id, quantity=it.quantity))
    return service.merge_items(items)


def _unavailable(details: list[dict]):
    return [
        inventory_pb2.Unavailable(
            product_id=d["productId"],
            requested=d["requested"],
            available=d["available"],
        )
        for d in details
    ]


class InventoryServicer(inventory_pb2_grpc.InventoryServicer):
    def CheckAvailability(self, request, context):
        merged = _merged_items(request, context)
        with SessionLocal() as db:
            unavailable = service.find_unavailable(db, merged)
        return inventory_pb2.CheckResponse(
            available=not unavailable,
            unavailable=_unavailable(unavailable),
        )

    def Reserve(self, request, context):
        merged = _merged_items(request, context)
        with SessionLocal() as db:
            # all or nothing: service.reserve rolls back if one product is short
            unavailable = service.reserve(db, merged)
        return inventory_pb2.ReserveResponse(
            success=not unavailable,
            unavailable=_unavailable(unavailable),
        )

    def Release(self, request, context):
        merged = _merged_items(request, context)
        with SessionLocal() as db:
            service.release(db, merged)
        return inventory_pb2.ReleaseResponse(success=True)


def build_server(port: int) -> tuple[grpc.Server, int]:
    """Create the server (not started). Returns it with the port really bound."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServicer_to_server(InventoryServicer(), server)
    bound_port = server.add_insecure_port(f"[::]:{port}")
    return server, bound_port


def start_grpc(port: int | None = None) -> grpc.Server:
    """Start the gRPC server in background threads (port: GRPC_PORT, default 50051)."""
    if port is None:
        port = int(os.getenv("GRPC_PORT", "50051"))
    server, bound_port = build_server(port)
    if bound_port == 0:
        raise RuntimeError(f"gRPC: cannot listen on port {port} (already in use?)")
    server.start()
    logger.info("Inventory gRPC server listening on port %s", bound_port)
    return server