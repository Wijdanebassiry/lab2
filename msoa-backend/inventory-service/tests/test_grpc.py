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

    server, port = grpc_server.build_server(0)
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = inventory_pb2_grpc.InventoryStub(channel)

    yield stub, Session

    channel.close()
    server.stop(None)


def stock_request(*items):
    return inventory_pb2.StockRequest(
        items=[inventory_pb2.StockItem(product_id=pid, quantity=qty) for pid, qty in items]
    )


def stock_of(Session, product_id):
    with Session() as db:
        return db.get(Stock, product_id).quantity


# ---------- CheckAvailability ----------


def test_check_sufficient_stock(grpc_env):
    stub, _ = grpc_env
    response = stub.CheckAvailability(stock_request(("1", 4)), timeout=5)
    assert response.available is True
    assert len(response.unavailable) == 0


def test_check_insufficient_stock_lists_the_product(grpc_env):
    stub, _ = grpc_env
    response = stub.CheckAvailability(stock_request(("2", 5)), timeout=5)
    assert response.available is False
    item = response.unavailable[0]
    assert (item.product_id, item.requested, item.available) == ("2", 5, 3)


def test_check_unknown_product_is_reported_as_unavailable(grpc_env):
    stub, _ = grpc_env
    response = stub.CheckAvailability(stock_request(("999", 2)), timeout=5)
    assert response.available is False
    assert response.unavailable[0].product_id == "999"
    assert response.unavailable[0].available == 0


def test_check_does_not_modify_stock(grpc_env):
    stub, Session = grpc_env
    stub.CheckAvailability(stock_request(("1", 4)), timeout=5)
    assert stock_of(Session, "1") == 10


def test_check_quantity_zero_is_invalid_argument(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        stub.CheckAvailability(stock_request(("1", 0)), timeout=5)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_check_empty_items_is_invalid_argument(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        stub.CheckAvailability(stock_request(), timeout=5)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_check_empty_product_id_is_invalid_argument(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        stub.CheckAvailability(stock_request(("", 1)), timeout=5)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


# ---------- Reserve ----------


def test_reserve_decrements_stock(grpc_env):
    stub, Session = grpc_env
    response = stub.Reserve(stock_request(("1", 4)), timeout=5)
    assert response.success is True
    assert len(response.unavailable) == 0
    assert stock_of(Session, "1") == 6


def test_reserve_is_all_or_nothing(grpc_env):
    stub, Session = grpc_env
    # product 1 has enough stock, product 2 does not: nothing must be reserved
    response = stub.Reserve(stock_request(("1", 2), ("2", 99)), timeout=5)
    assert response.success is False
    assert [u.product_id for u in response.unavailable] == ["2"]
    assert stock_of(Session, "1") == 10
    assert stock_of(Session, "2") == 3


def test_reserve_merges_duplicated_products(grpc_env):
    stub, Session = grpc_env
    # 2 + 2 = 4 requested, but only 3 in stock
    response = stub.Reserve(stock_request(("2", 2), ("2", 2)), timeout=5)
    assert response.success is False
    assert response.unavailable[0].requested == 4
    assert stock_of(Session, "2") == 3


def test_reserve_quantity_zero_is_invalid_argument(grpc_env):
    stub, Session = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        stub.Reserve(stock_request(("1", 0)), timeout=5)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert stock_of(Session, "1") == 10


# ---------- Release ----------


def test_release_puts_the_stock_back(grpc_env):
    stub, Session = grpc_env
    stub.Reserve(stock_request(("1", 4)), timeout=5)
    assert stock_of(Session, "1") == 6
    response = stub.Release(stock_request(("1", 4)), timeout=5)
    assert response.success is True
    assert stock_of(Session, "1") == 10


def test_release_quantity_zero_is_invalid_argument(grpc_env):
    stub, _ = grpc_env
    with pytest.raises(grpc.RpcError) as error:
        stub.Release(stock_request(("1", 0)), timeout=5)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT