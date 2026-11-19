from concurrent import futures

import grpc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import grpc_server
from app.database import Base
from app.grpc_gen import inventory_pb2, inventory_pb2_grpc
from app.models import Stock


@pytest.fixture
def grpc_env(tmp_path, monkeypatch):
    """Real gRPC server on a free port, backed by a temporary SQLite database."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'grpc-test.db'}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        db.add_all([Stock(product_id="1", quantity=10), Stock(product_id="2", quantity=3)])
        db.commit()

    # the servicer opens its own sessions: point it to the test database
    monkeypatch.setattr(grpc_server, "SessionLocal", Session)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        grpc_server.InventoryServicer(), server
    )
    port = server.add_insecure_port("localhost:0")
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = inventory_pb2_grpc.InventoryServiceStub(channel)

    yield stub, Session

    channel.close()
    server.stop(None)


def check(stub, *items):
    request = inventory_pb2.AvailabilityRequest(
        items=[inventory_pb2.StockItem(productId=pid, quantity=qty) for pid, qty in items]
    )
    return stub.CheckAvailability(request, timeout=5)


def test_sufficient_stock(grpc_env):
    stub, _ = grpc_env
    response = check(stub, ("1", 4))
    assert response.available is True
    assert len(response.unavailable) == 0


def test_insufficient_stock(grpc_env):
    stub, _ = grpc_env
    response = check(stub, ("2", 5))
    assert response.available is False
    assert len(response.unavailable) == 1
    item = response.unavailable[0]
    assert item.productId == "2"
    assert item.requested == 5
    assert item.availableQuantity == 3


def test_unknown_product_returns_not_found(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        check(stub, ("999", 2))
    assert error.value.code() == grpc.StatusCode.NOT_FOUND


def test_invalid_quantity_returns_invalid_argument(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        check(stub, ("1", 0))
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_empty_items_returns_invalid_argument(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        check(stub)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_only_short_products_are_listed(grpc_env):
    stub, _ = grpc_env
    response = check(stub, ("1", 2), ("2", 99))
    assert response.available is False
    assert [u.productId for u in response.unavailable] == ["2"]


def test_duplicate_products_are_merged(grpc_env):
    stub, _ = grpc_env
    # 2 + 2 = 4 requested, but only 3 in stock
    response = check(stub, ("2", 2), ("2", 2))
    assert response.available is False
    assert response.unavailable[0].requested == 4


def test_check_does_not_modify_stock(grpc_env):
    stub, Session = grpc_env
    check(stub, ("1", 4))
    with Session() as db:
        assert db.get(Stock, "1").quantity == 10