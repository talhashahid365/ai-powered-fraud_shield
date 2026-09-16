import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ApiKey(Base):
    """
    Credential issued to an external business system (e-commerce platform,
    payment gateway, etc.) so it can call the External Business API
    (POST /api/transactions, POST /api/risk-check, GET /api/transactions/{id},
    GET /api/risk/{transaction_id}, POST /api/alerts/{id}/review) without a
    dashboard user login.

    Only a bcrypt hash of the secret is ever stored - the raw key is shown to
    the admin exactly once, at creation time (like a GitHub PAT / Stripe
    secret key), and cannot be recovered afterwards.
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # First 12 chars of the raw key (e.g. "fsk_live_ab12"), stored in the clear so we can
    # do a fast indexed lookup before paying for a bcrypt verify against every row.
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=True)  # admin user id

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
