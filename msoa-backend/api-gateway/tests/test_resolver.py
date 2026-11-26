import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import main, resolver
from app.config import DEFAULT_ADDRESSES


class FakeRegistry:
    """Registre en memoire : isole les tests du code de [Orders]."""

    def __init__(self):
        self.services = {}

    def register(self, name, address):
        self.services[name] = address

    def get(self, name):
        return self.services.get(name)


@pytest.fixture
def fake_registry(monkeypatch):
    fake = FakeRegistry()
    monkeypatch.setattr(resolver, "registry", fake)
    return fake


@pytest.fixture
def calls(monkeypatch):
    """Faux forward : enregistre (service, adresse) au lieu d'appeler un vrai service."""
    recorded = []

    async def fake_forward(request, service, address, client):
        recorded.append((service, address))
        return JSONResponse({"service": service, "address": address})

    monkeypatch.setattr(main, "forward", fake_forward)
    return recorded


@pytest.fixture
def client(calls):
    with TestClient(main.create_app()) as c:
        yield c


# --- mode static ---------------------------------------------------------
def test_static_resolves_from_config(monkeypatch):
    monkeypatch.setenv("GATEWAY_MODE", "static")
    assert resolver.resolve("catalog-service") == DEFAULT_ADDRESSES["catalog-service"]


def test_static_unknown_service_returns_none(monkeypatch):
    monkeypatch.setenv("GATEWAY_MODE", "static")
    assert resolver.resolve("foo-service") is None


def test_static_request_reaches_configured_address(monkeypatch, client, calls):
    monkeypatch.setenv("GATEWAY_MODE", "static")
    monkeypatch.setitem(DEFAULT_ADDRESSES, "catalog-service", "http://127.0.0.1:8082")
    assert client.get("/products").status_code == 200
    assert calls == [("catalog-service", "http://127.0.0.1:8082")]


# --- mode dynamic --------------------------------------------------------
def test_dynamic_unregistered_gives_503_and_no_forward(monkeypatch, fake_registry, client, calls):
    monkeypatch.setenv("GATEWAY_MODE", "dynamic")
    assert client.get("/products").status_code == 503
    assert calls == []                      # aucune requete transmise


def test_dynamic_registered_request_reaches_address(monkeypatch, fake_registry, client, calls):
    monkeypatch.setenv("GATEWAY_MODE", "dynamic")
    fake_registry.register("catalog-service", "http://127.0.0.1:8082")
    assert client.get("/products").status_code == 200
    assert calls == [("catalog-service", "http://127.0.0.1:8082")]


def test_dynamic_relocation(monkeypatch, fake_registry, client, calls):
    monkeypatch.setenv("GATEWAY_MODE", "dynamic")

    fake_registry.register("catalog-service", "http://127.0.0.1:8082")
    client.get("/products")
    assert calls[-1] == ("catalog-service", "http://127.0.0.1:8082")

    fake_registry.register("catalog-service", "http://127.0.0.1:9192")   # relocalisation
    client.get("/products")
    assert calls[-1] == ("catalog-service", "http://127.0.0.1:9192")
    assert len(calls) == 2


def test_dynamic_is_default_mode(monkeypatch, fake_registry):
    monkeypatch.delenv("GATEWAY_MODE", raising=False)
    assert resolver.get_mode() == "dynamic"


# --- mode invalide -------------------------------------------------------
def test_invalid_mode_raises(monkeypatch):
    monkeypatch.setenv("GATEWAY_MODE", "banana")
    with pytest.raises(ValueError):
        resolver.resolve("catalog-service")