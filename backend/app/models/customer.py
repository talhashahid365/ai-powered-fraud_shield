import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import RiskLevel


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    account_age_days: Mapped[int] = mapped_column(Integer, default=0)

    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.LOW)

    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    suspicious_transactions: Mapped[int] = mapped_column(Integer, default=0)
    previous_fraud_reports: Mapped[int] = mapped_column(Integer, default=0)

    # Distinct device_id / location count across this customer's transaction
    # history. Kept as columns (rather than computed on every read) so the
    # risk profile endpoint is a single indexed lookup, and refreshed via
    # recompute_device_location_counts() every time a transaction is created
    # (see customer_service.update_customer_after_transaction) so the profile
    # never drifts from the underlying transactions.
    devices_used: Mapped[int] = mapped_column(Integer, default=0)
    locations_used: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
