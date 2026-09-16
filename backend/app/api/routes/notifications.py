from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.notification import Notification
from app.schemas.alert import NotificationMarkRead, NotificationOut
from app.services.alert_service import mark_notifications_read

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .scalar()
        or 0
    )
    return {
        "data": [NotificationOut.model_validate(n) for n in notifications],
        "unread_count": unread_count,
    }


@router.post("/read")
def mark_read(
    payload: NotificationMarkRead,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    count = mark_notifications_read(db, current_user.id, payload.notification_ids)
    return {"success": True, "marked_read": count}
