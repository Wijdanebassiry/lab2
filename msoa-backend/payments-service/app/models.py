from sqlalchemy import Column, String, Float, DateTime, Text
from datetime import datetime, timezone
from .database import Base

class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True)
    order_id = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="MAD")
    method = Column(String)
    status = Column(String, nullable=False)   # PENDING | SUCCESS | FAILED | REFUNDED
    gateway_ref = Column(String)
    failure_reason = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))