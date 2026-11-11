import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Stock


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Session = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        db.add_all([Stock(product_id="1", quantity=10), Stock(product_id="2", quantity=3)])
        db.commit()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)  # no "with": lifespan (real DB seeding) is not run
    app.dependency_overrides.clear()


def qty(client, pid):
    return client.get(f"/api/inventory/{pid}").json()["stock"]


def test_health(client):
    assert client.get("/health").json() == {"status": "UP", "service": "inventory"}


def test_reserve_decrements_stock(client):
    r = client.post("/api/inventory/reserve", json={"items": [{"productId": "1", "quantity": 4}]})
    assert r.status_code == 200 and r.json() == {"success": True}
    assert qty(client, "1") == 6


def test_reserve_is_atomic(client):
    r = client.post(
        "/api/inventory/reserve",
        json={"items": [{"productId": "1", "quantity": 2}, {"productId": "2", "quantity": 99}]},
    )
    assert r.status_code == 409
    assert r.json()["unavailable"][0]["productId"] == "2"
    assert qty(client, "1") == 10  # untouched
    assert qty(client, "2") == 3


def test_reserve_merges_duplicates(client):
    r = client.post(
        "/api/inventory/reserve",
        json={"items": [{"productId": "2", "quantity": 2}, {"productId": "2", "quantity": 2}]},
    )
    assert r.status_code == 409  # 4 > 3 in stock
    assert qty(client, "2") == 3


def test_numeric_product_id_is_accepted(client):
    r = client.post("/api/inventory/reserve", json={"items": [{"productId": 1, "quantity": 1}]})
    assert r.status_code == 200
    assert qty(client, "1") == 9


def test_release_restores_stock(client):
    r = client.post("/api/inventory/release", json={"items": [{"productId": "2", "quantity": 5}]})
    assert r.status_code == 200
    assert qty(client, "2") == 8


def test_check_does_not_modify_stock(client):
    r = client.post("/api/inventory/check", json={"items": [{"productId": "1", "quantity": 5}]})
    assert r.json() == {"available": True, "unavailable": []}
    assert qty(client, "1") == 10


def test_invalid_body_returns_422(client):
    r = client.post("/api/inventory/reserve", json={})
    assert r.status_code == 422 and "message" in r.json()


def test_unknown_product_returns_404(client):
    assert client.get("/api/inventory/999").status_code == 404