"""
Centralized audit logging.

Call `log_action` from any service/route that performs a security-sensitive
action (login, role change, rule change, alert review, feedback submission,
etc.) so the `audit_logs` table reflects real activity, as required by
spec section "Security -> Audit logs".
"""
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: str | None,
    action: str,
    details: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip_address)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
