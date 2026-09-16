import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import Decision, RiskLevel, TransactionStatus


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False)
    customer = relationship("Customer", backref="transactions")

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    transaction_datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    payment_method: Mapped[str] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=True)
    location: Mapped[str] = mapped_column(String(120), nullable=True)
    account_age_days: Mapped[int] = mapped_column(Integer, default=0)

    transaction_status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.PENDING
    )

    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.LOW)
    decision: Mapped[Decision] = mapped_column(Enum(Decision), default=Decision.APPROVE)

    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    rule_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Structured facts ("New device", "3 transactions in 5 minutes", ...) computed by the
    # risk engine at decision time, and the human-readable narrative generated from them
    # (see app.ai.llm_service.generate_explanation). Persisted so the "why" behind a score
    # is still available on every later read (transaction detail, external risk API,
    # alerts) instead of only existing for the instant the transaction was created.
    risk_factors: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=True)

    # Names of the rules (from app.ai.rules_engine) that fired for this transaction at
    # decision time. Persisted for the same reason as risk_factors/explanation above:
    # without this, every read after the initial request has no way to know which rules
    # (if any) contributed to rule_score, since evaluate_rules() is only called once,
    # during the original risk pipeline run.
    triggered_rules: Mapped[list] = mapped_column(JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
