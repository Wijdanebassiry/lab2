from datetime import datetime
from enum import Enum 
from pydantic import BaseModel, Field, ConfigDict

class PaymentMethod(str, Enum):                         
    CARD = "CARD"
    CASH = "CASH"
    TEST_DECLINE = "TEST_DECLINE"
    TEST_TIMEOUT = "TEST_TIMEOUT"
    
class PaymentRequest(BaseModel):
    orderId: str = Field(min_length=1)
    method: PaymentMethod = PaymentMethod.CARD

class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: str
    orderId: str = Field(validation_alias="order_id")
    amount: float
    method: str | None = None
    status: str
    createdAt: datetime = Field(validation_alias="created_at")