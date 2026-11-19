from abc import ABC, abstractmethod
from dataclasses import dataclass

class GatewayTimeout(Exception):
    pass

@dataclass
class GatewayResult:
    outcome: str        # "approved" | "declined"  (vocabulaire du prestataire)
    reference: str      # identifiant côté prestataire
    reason: str | None = None

class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: float, currency: str, method: str) -> GatewayResult: ...
    @abstractmethod
    def refund(self, reference: str, amount: float) -> GatewayResult: ...