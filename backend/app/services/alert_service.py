"""
Alert creation and lifecycle management.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.customer import Customer
from app.models.enums import AlertSeverity, AlertStatus, FeedbackResult, UserRole
from app.models.feedback import Feedback
from app.models.investigation_note import InvestigationNote
from app.models.notification import Notification
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import RiskCheckResponse

# Statuses that represent a ground-truth fraud outcome. These may ONLY be reached through
# record_feedback() (POST /api/alerts/{id}/feedback), never through update_alert_status()
# (POST /api/alerts/{id}/review). Feedback is how the platform captures training/evaluation
# data for the fraud model (see ml/training/export_feedback_dataset.py); if the generic
# status-review endpoint could also set these, an analyst could resolve an alert as
# confirmed/false-positive without ever creating a Feedback row, silently starving the
# model-improvement pipeline of labels.
OUTCOME_STATUSES = {AlertStatus.CONFIRMED_FRAUD, AlertStatus.FALSE_POSITIVE}


class FeedbackAlreadyExistsError(Exception):
    """Raised when feedback is submitted for an alert that already has a feedback record."""


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is attempted through the wrong code path."""


def _severity_from_score(score: float) -> AlertSeverity:
    if score >= 90:
        return AlertSeverity.CRITICAL
    if score >= 71:
        return AlertSeverity.HIGH
    if score >= 31:
        return AlertSeverity.MEDIUM
    return AlertSeverity.LOW


def _pick_analyst_to_assign(db: Session) -> User | None:
    """
    Load-balance new alerts across active analysts: assign to whichever
    active ANALYST currently has the fewest open (NEW/INVESTIGATING) alerts
    assigned to them. Falls back to None (unassigned) if there are no
    active analysts yet - an admin can still assign manually later via
    POST /api/alerts/{id}/assign.
    """
    open_counts = (
        db.query(Alert.assigned_to, func.count(Alert.id))
        .filter(Alert.status.in_([AlertStatus.NEW, AlertStatus.INVESTIGATING]))
        .filter(Alert.assigned_to.isnot(None))
        .group_by(Alert.assigned_to)
        .all()
    )
    open_count_by_user = {user_id: count for user_id, count in open_counts}

    analysts = db.query(User).filter(User.role == UserRole.ANALYST, User.is_active == True).all()  # noqa: E712
    if not analysts:
        return None

    return min(analysts, key=lambda a: open_count_by_user.get(a.id, 0))


def _notify_user(db: Session, user_id: str, alert: Alert, message: str) -> Notification:
    notification = Notification(user_id=user_id, alert_id=alert.id, message=message)
    db.add(notification)
    return notification


def create_alert_for_transaction(db: Session, txn: Transaction, customer: Customer, risk: RiskCheckResponse) -> Alert:
    # Prefer the human-readable, LLM/template-generated explanation (what the analyst
    # should actually read) over the raw "; "-joined structured facts. Previously this
    # always used the raw facts, so a configured LLM provider's nicer narrative was
    # computed but discarded and never surfaced on the alert.
    reason = risk.explanation or "; ".join(risk.risk_factors) or "Elevated risk score"
    assignee = _pick_analyst_to_assign(db)
    alert = Alert(
        transaction_id=txn.id,
        customer_id=customer.id,
        severity=_severity_from_score(risk.risk_score),
        title=f"{risk.risk_level.value} risk transaction {txn.transaction_id}",
        reason=reason,
        status=AlertStatus.NEW,
        assigned_to=assignee.id if assignee else None,
    )
    db.add(alert)
    db.flush()  # assigns alert.id without committing yet, so the notification below can reference it

    if assignee:
        _notify_user(
            db, assignee.id, alert,
            f"New {alert.severity.value} severity alert assigned to you: {alert.title}",
        )

    db.commit()
    db.refresh(alert)
    return alert


def assign_alert(db: Session, alert: Alert, user: User) -> Alert:
    alert.assigned_to = user.id
    db.add(alert)
    _notify_user(db, user.id, alert, f"Alert assigned to you: {alert.title}")
    db.commit()
    db.refresh(alert)
    return alert


def mark_notifications_read(db: Session, user_id: str, notification_ids: list[str] | None = None) -> int:
    """Mark the given notifications (or all of the user's unread notifications
    if notification_ids is None) as read. Returns the number of rows updated."""
    query = db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
    if notification_ids is not None:
        query = query.filter(Notification.id.in_(notification_ids))
    count = query.update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return count


def update_alert_status(db: Session, alert: Alert, status: AlertStatus) -> Alert:
    if status in OUTCOME_STATUSES:
        raise InvalidStatusTransitionError(
            f"{status.value} must be recorded via POST /api/alerts/{{id}}/feedback, "
            "not /review, so the outcome is captured as labeled training/evaluation data."
        )
    alert.status = status
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def add_investigation_note(db: Session, alert: Alert, analyst_id: str, note_text: str) -> InvestigationNote:
    note = InvestigationNote(alert_id=alert.id, analyst_id=analyst_id, note=note_text)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def record_feedback(db: Session, alert: Alert, analyst_id: str, actual_result: str, comments: str | None) -> Feedback:
    """
    Store an analyst's ground-truth verdict (Confirmed Fraud / False Positive) on an alert.

    This is the single write path for fraud outcomes: it's what feeds
    ml/training/export_feedback_dataset.py, so every alert should be resolved through here
    rather than through the generic /review status endpoint (see OUTCOME_STATUSES above).
    One alert gets exactly one feedback record -- resubmitting raises FeedbackAlreadyExistsError
    rather than silently creating a second, possibly contradictory, label.
    """
    existing = db.query(Feedback).filter(Feedback.alert_id == alert.id).first()
    if existing is not None:
        raise FeedbackAlreadyExistsError(
            f"Alert {alert.id} was already marked {existing.actual_result.value} "
            f"by analyst {existing.analyst_id} at {existing.created_at.isoformat()}."
        )

    result_enum = FeedbackResult(actual_result)
    feedback = Feedback(alert_id=alert.id, analyst_id=analyst_id, actual_result=result_enum, comments=comments)
    db.add(feedback)

    new_status = AlertStatus.CONFIRMED_FRAUD if result_enum == FeedbackResult.CONFIRMED_FRAUD else AlertStatus.FALSE_POSITIVE
    alert.status = new_status
    db.add(alert)

    customer = db.query(Customer).filter(Customer.id == alert.customer_id).first()
    if customer and result_enum == FeedbackResult.CONFIRMED_FRAUD:
        customer.previous_fraud_reports += 1
        db.add(customer)

    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback_for_alert(db: Session, alert_id: str) -> list[Feedback]:
    return db.query(Feedback).filter(Feedback.alert_id == alert_id).order_by(Feedback.created_at.desc()).all()
