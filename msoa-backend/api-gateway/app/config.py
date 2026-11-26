"""Configuration de la passerelle : table de routes et adresses statiques."""
import os

# (prefixe de chemin, nom logique du service). Les chemins ne sont jamais modifies.
ROUTES = [
    ("/api/auth", "auth-service"),
    ("/v2/products", "catalog-service"),
    ("/products", "catalog-service"),
    ("/api/inventory", "inventory-service"),
    ("/api/orders", "orders-service"),
    ("/api/payments", "payments-service"),
    ("/api/shipments", "shipping-service"),
]

# Adresses du mode "static" (probleme 1), surchargeables par variables d'environnement.
DEFAULT_ADDRESSES = {
    "auth-service": os.getenv("AUTH_URL", "http://127.0.0.1:8081"),
    "catalog-service": os.getenv("CATALOG_URL", "http://127.0.0.1:8082"),
    "inventory-service": os.getenv("INVENTORY_URL", "http://127.0.0.1:8083"),
    "orders-service": os.getenv("ORDERS_URL", "http://127.0.0.1:8084"),
    "payments-service": os.getenv("PAYMENTS_URL", "http://127.0.0.1:8085"),
    "shipping-service": os.getenv("SHIPPING_URL", "http://127.0.0.1:8086"),
}


def match_service(path: str) -> str | None:
    """Nom logique du service qui gere ce chemin, ou None."""
    for prefix, service in ROUTES:
        if path == prefix or path.startswith(prefix + "/"):
            return service
    return None