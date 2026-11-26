
"""
Enregistre un ou plusieurs microservices auprès de l'API Gateway.

Sans arguments : enregistre les six microservices.
Avec deux arguments : enregistre uniquement le service indiqué.

Utilise uniquement la bibliothèque standard urllib.
"""

import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8080")

SERVICES = {
    "auth-service": "http://127.0.0.1:8081",
    "catalog-service": "http://127.0.0.1:8082",
    "inventory-service": "http://127.0.0.1:8083",
    "orders-service": "http://127.0.0.1:8084",
    "payments-service": "http://127.0.0.1:8085",
    "shipping-service": "http://127.0.0.1:8086",
}


def register_service(name, address):
    """Envoie une demande d'enregistrement au Gateway."""

    url = GATEWAY_URL.rstrip("/") + "/registry/register"

    data = json.dumps({
        "name": name,
        "address": address
    }).encode("utf-8")

    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urlopen(request, timeout=5) as response:
            result = response.read().decode("utf-8")
            print(f"[OK] {name}: {result}")

    except HTTPError as error:
        details = error.read().decode("utf-8")
        print(f"[ERREUR HTTP {error.code}] {name}: {details}")

    except URLError as error:
        print(f"[ERREUR CONNEXION] {name}: {error.reason}")


def main():
    if len(sys.argv) == 1:
        # Aucun argument : enregistrer les six services.
        for name, address in SERVICES.items():
            register_service(name, address)

    elif len(sys.argv) == 3:
        # Deux arguments : enregistrer un seul service.
        name = sys.argv[1]
        address = sys.argv[2]
        register_service(name, address)

    else:
        print("Utilisation :")
        print("  python scripts/register.py")
        print("  python scripts/register.py <name> <address>")
        sys.exit(1)


if __name__ == "__main__":
    main()
