
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.registry import ServiceRegistry, RegistryError, registry
from app.registry_api import router


@pytest.fixture
def service_registry():
    return ServiceRegistry()


@pytest.fixture
def client():
    registry._services.clear()

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as test_client:
        yield test_client

    registry._services.clear()


# Unit tests

def test_register_service(service_registry):
    result = service_registry.register(
        "catalog-service",
        "http://127.0.0.1:8082"
    )

    assert result == (
        "catalog-service",
        "http://127.0.0.1:8082"
    )


def test_get_service(service_registry):
    service_registry.register(
        "catalog-service",
        "http://127.0.0.1:8082"
    )

    assert service_registry.get("catalog-service") == (
        "http://127.0.0.1:8082"
    )


def test_replace_existing_service(service_registry):
    service_registry.register(
        "catalog-service",
        "http://127.0.0.1:8082"
    )

    service_registry.register(
        "catalog-service",
        "http://127.0.0.1:9090"
    )

    assert service_registry.get("catalog-service") == (
        "http://127.0.0.1:9090"
    )


def test_remove_service(service_registry):
    service_registry.register(
        "catalog-service",
        "http://127.0.0.1:8082"
    )

    removed = service_registry.remove("catalog-service")

    assert removed == "http://127.0.0.1:8082"
    assert service_registry.get("catalog-service") is None


def test_all_services(service_registry):
    service_registry.register("catalog", "http://localhost:8082")
    service_registry.register("orders", "http://localhost:8084")

    assert len(service_registry.all()) == 2


def test_missing_name(service_registry):
    with pytest.raises(RegistryError):
        service_registry.register("", "http://localhost:8082")


def test_missing_address(service_registry):
    with pytest.raises(RegistryError):
        service_registry.register("catalog", "")


def test_invalid_service_name(service_registry):
    with pytest.raises(RegistryError):
        service_registry.register("catalog service", "http://localhost:8082")


def test_invalid_address(service_registry):
    with pytest.raises(RegistryError):
        service_registry.register("catalog", "ftp://localhost:8082")


# API tests

def test_api_register_service(client):
    response = client.post(
        "/registry/register",
        json={
            "name": "catalog-service",
            "address": "http://127.0.0.1:8082"
        }
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Service registered successfully",
        "name": "catalog-service",
        "address": "http://127.0.0.1:8082"
    }


def test_api_get_services(client):
    client.post(
        "/registry/register",
        json={
            "name": "catalog-service",
            "address": "http://127.0.0.1:8082"
        }
    )

    response = client.get("/registry/services")

    assert response.status_code == 200
    assert response.json() == {
        "catalog-service": "http://127.0.0.1:8082"
    }


def test_api_replaces_existing_service(client):
    client.post(
        "/registry/register",
        json={
            "name": "catalog-service",
            "address": "http://localhost:8082"
        }
    )

    response = client.post(
        "/registry/register",
        json={
            "name": "catalog-service",
            "address": "http://localhost:9090"
        }
    )

    assert response.status_code == 200
    assert response.json()["address"] == "http://localhost:9090"


def test_api_missing_fields(client):
    response = client.post(
        "/registry/register",
        json={"name": "catalog-service"}
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_api_invalid_address(client):
    response = client.post(
        "/registry/register",
        json={
            "name": "catalog-service",
            "address": "not-a-valid-url"
        }
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_api_invalid_json(client):
    response = client.post(
        "/registry/register",
        content="{invalid json",
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_api_rejects_non_object_json(client):
    response = client.post(
        "/registry/register",
        json=["catalog-service", "http://localhost:8082"]
    )

    assert response.status_code == 400
    assert "error" in response.json()
