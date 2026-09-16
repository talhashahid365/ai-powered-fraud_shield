from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AlertSeverity, AlertStatus


class AlertOut(BaseModel):
    id: str
    transaction_id: str
    customer_id: str
    severity: AlertSeverity
    title: str
    reason: str | None
    status: AlertStatus
    assigned_to: str | None
    risk_score: float | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class InvestigationNoteCreate(BaseModel):
    note: str


class InvestigationNoteOut(BaseModel):
    id: str
    alert_id: str
    analyst_id: str
    analyst_name: str | None = None
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    actual_result: str  # CONFIRMED_FRAUD | FALSE_POSITIVE
    comments: str | None = None


class FeedbackOut(BaseModel):
    id: str
    alert_id: str
    analyst_id: str
    analyst_name: str | None = None
    actual_result: str
    comments: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertAssign(BaseModel):
    user_id: str


class NotificationOut(BaseModel):
    id: str
    alert_id: str | None
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationMarkRead(BaseModel):
    notification_ids: list[str] | None = None  # None = mark all unread as read
