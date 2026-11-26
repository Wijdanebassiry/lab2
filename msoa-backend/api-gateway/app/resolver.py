"""Resolution nom logique -> adresse. A CODER PAR [Payments]."""


def resolve(service: str) -> str | None:
    """Mode static : adresse de config.py. Mode dynamic : adresse du registre. None si inconnu."""
    raise NotImplementedError("a implementer (branche lab5/resolver)")