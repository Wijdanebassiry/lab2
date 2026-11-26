
"""Registre de services en memoire."""

import re
from threading import RLock
from urllib.parse import urlsplit


class RegistryError(ValueError):
    """Enregistrement invalide."""


class ServiceRegistry:
    def __init__(self):
        self._services = {}
        self._lock = RLock()

    def register(self, name, address):
        if not isinstance(name, str) or not name.strip():
            raise RegistryError("Service name is required.")

        if not isinstance(address, str) or not address.strip():
            raise RegistryError("Service address is required.")

        name = name.strip()
        address = address.strip()

        if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise RegistryError("Invalid service name.")

        try:
            parsed = urlsplit(address)
            valid_url = (
                parsed.scheme in ("http", "https")
                and bool(parsed.hostname)
                and parsed.port != 0
            )
        except ValueError:
            valid_url = False

        if not valid_url:
            raise RegistryError("Invalid service address.")

        address = address.rstrip("/")

        with self._lock:
            self._services[name] = address

        return name, address

    def get(self, name):
        with self._lock:
            return self._services.get(name)

    def remove(self, name):
        with self._lock:
            return self._services.pop(name, None)

    def all(self):
        with self._lock:
            return dict(self._services)


registry = ServiceRegistry()
