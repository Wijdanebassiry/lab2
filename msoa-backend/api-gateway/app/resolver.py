"""Resolution nom logique -> adresse (Payments)."""
import os

from .config import DEFAULT_ADDRESSES
from .registry import registry   # instance unique de ServiceRegistry (par [Orders])

VALID_MODES = ("static", "dynamic")


def get_mode() -> str:
    """GATEWAY_MODE est lu a chaque appel (pas a l'import) : testable et sans cache."""
    mode = os.getenv("GATEWAY_MODE", "dynamic").lower()
    if mode not in VALID_MODES:
        raise ValueError(f"GATEWAY_MODE invalide : {mode!r} (attendu : static ou dynamic)")
    return mode


def resolve(service: str) -> str | None:
    """Mode static : adresse de config.py. Mode dynamic : adresse du registre. None si inconnu."""
    if get_mode() == "static":
        return DEFAULT_ADDRESSES.get(service)
    return registry.get(service)