"""
Admin-only audit log viewer.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.enums import UserRole

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs (Admin)"])


@router.get("")
def list_audit_logs(limit: int = 100, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": log.id, "user_id": log.user_id, "action": log.action,
            "details": log.details, "ip_address": log.ip_address, "created_at": log.created_at,
        }
        for log in logs
    ]
