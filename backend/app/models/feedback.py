import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import FeedbackResult


class Feedback(Base):
    """
    Analyst ground-truth label for an alert (Confirmed Fraud / False Positive).

    This is the platform's supervised-learning signal: ml/training/export_feedback_dataset.py
    joins this table back to the flagged transaction to build a labeled dataset, and
    ml/training/train_supervised_from_feedback.py trains/evaluates a classifier on it.
    That makes label quality important, which is why alert_id is unique below -- an alert
    should have exactly one ground-truth outcome, not several (possibly contradictory) ones.
    """

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # unique=True: one feedback record per alert. Enforced at the DB level here and checked
    # explicitly (with a friendly 409) in app.services.alert_service.record_feedback so a
    # double-click or a retried request can't silently corrupt training data with duplicate
    # or contradictory labels for the same alert.
    alert_id: Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id"), nullable=False, unique=True)
    analyst_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    actual_result: Mapped[FeedbackResult] = mapped_column(Enum(FeedbackResult), nullable=False)
    comments: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
