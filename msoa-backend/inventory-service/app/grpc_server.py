"""gRPC server of the Inventory service.

Run from the inventory-service folder:
    python -m app.grpc_server

It reuses the stock logic of app/service.py, so the REST API and the gRPC API
always give the same answers. The REST routes are not modified.
"""

import os
from concurrent import futures

import grpc

from . import service
from .database import Base, SessionLocal, engine
from .grpc_gen import inventory_pb2, inventory_pb2_grpc
from .models import Stock
from .schemas import Item


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckAvailability(self, request, context):
        if not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "items must not be empty")

        items = []
        for it in request.items:
            if not it.productId or it.quantity <= 0:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "each item needs a productId and a quantity greater than 0",
                )
            items.append(Item(productId=it.productId, quantity=it.quantity))

        merged = service.merge_items(items)

        with SessionLocal() as db:
            for product_id in merged:
                if db.get(Stock, product_id) is None:
                    context.abort(
                        grpc.StatusCode.NOT_FOUND,
                        f"Product {product_id} not found",
                    )
            unavailable = service.find_unavailable(db, merged)

        return inventory_pb2.AvailabilityResponse(
            available=len(unavailable) == 0,
            unavailable=[
                inventory_pb2.UnavailableItem(
                    productId=u["productId"],
                    requested=u["requested"],
                    availableQuantity=u["available"],
                )
                for u in unavailable
            ],
        )


def build_server(port: int) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        InventoryServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    return server


if __name__ == "__main__":
    from .main import seed

    # same tables and demo stock as the REST service
    Base.metadata.create_all(engine)
    seed()

    port = int(os.getenv("GRPC_PORT", "50051"))
    server = build_server(port)
    server.start()
    print(f"Inventory gRPC server listening on port {port}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
        print("Inventory gRPC server stopped")