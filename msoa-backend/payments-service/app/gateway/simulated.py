import uuid, time
from .base import PaymentGateway, GatewayResult, GatewayTimeout

class SimulatedGateway(PaymentGateway):
    def charge(self, amount, currency, method):
        if method == "TEST_TIMEOUT":
            time.sleep(0.5)
            raise GatewayTimeout()
        if method == "TEST_DECLINE":
            return GatewayResult("declined", "gw_" + uuid.uuid4().hex[:8], "card_declined")
        if amount > 50000:
            return GatewayResult("declined", "gw_" + uuid.uuid4().hex[:8], "limit_exceeded")
        return GatewayResult("approved", "gw_" + uuid.uuid4().hex[:8])

    def refund(self, reference, amount):
        return GatewayResult("approved", "rf_" + uuid.uuid4().hex[:8])