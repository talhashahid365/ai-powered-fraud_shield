import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Notification(Base):
    """
    In-app notification for a user about an alert (e.g. "a new alert was
    assigned to you"). This is how the Fraud Alerts spec's "Notify the
    relevant user" requirement is fulfilled: every alert is auto-assigned
    to an analyst at creation time (see app.services.alert_service), and a
    Notification row is created for that analyst in the same transaction.

    Scoped to in-app notifications only (no email/SMS) since no mail/SMS
    provider is configured anywhere else in this codebase (see
    app.core.config.Settings - only an optional LLM provider is wired up).
    """
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    alert_id: Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id"), nullable=True)

    user = relationship("User", backref="notifications")
    alert = relationship("Alert", backref="notifications")

    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
