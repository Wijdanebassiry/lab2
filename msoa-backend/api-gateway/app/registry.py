"""Registre de services en memoire. A CODER PAR [Orders]."""


class RegistryError(ValueError):
    """Enregistrement invalide (renvoye en HTTP 400)."""


class ServiceRegistry:
    def register(self, name, address):
        """Valide puis enregistre (remplace l'existant). Renvoie (name, address)."""
        raise NotImplementedError("a implementer (branche lab5/registry)")

    def get(self, name):
        raise NotImplementedError

    def remove(self, name):
        raise NotImplementedError

    def all(self):
        raise NotImplementedError


registry = ServiceRegistry()   # instance unique, utilisee par registry_api et resolver