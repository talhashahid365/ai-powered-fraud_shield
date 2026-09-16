from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles, require_roles_or_api_key
from app.db.database import get_db
from app.models.alert import Alert
from app.models.customer import Customer
from app.models.enums import AlertStatus, UserRole
from app.models.investigation_note import InvestigationNote
from app.models.user import User
from app.schemas.alert import (
    AlertAssign,
    AlertOut,
    AlertStatusUpdate,
    FeedbackCreate,
    FeedbackOut,
    InvestigationNoteCreate,
    InvestigationNoteOut,
)
from app.services.alert_service import (
    FeedbackAlreadyExistsError,
    InvalidStatusTransitionError,
    add_investigation_note,
    assign_alert,
    list_feedback_for_alert,
    record_feedback,
    update_alert_status,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


def _notes_to_out(db: Session, notes: list[InvestigationNote]) -> list[InvestigationNoteOut]:
    analyst_ids = {n.analyst_id for n in notes}
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_(analyst_ids)).all()} if analyst_ids else {}
    return [
        InvestigationNoteOut(
            id=n.id,
            alert_id=n.alert_id,
            analyst_id=n.analyst_id,
            analyst_name=names.get(n.analyst_id),
            note=n.note,
            created_at=n.created_at,
        )
        for n in notes
    ]


def _feedback_to_out(db: Session, feedback_rows: list) -> list[FeedbackOut]:
    analyst_ids = {f.analyst_id for f in feedback_rows}
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_(analyst_ids)).all()} if analyst_ids else {}
    return [
        FeedbackOut(
            id=f.id,
            alert_id=f.alert_id,
            analyst_id=f.analyst_id,
            analyst_name=names.get(f.analyst_id),
            actual_result=f.actual_result.value,
            comments=f.comments,
            created_at=f.created_at,
        )
        for f in feedback_rows
    ]


def _to_out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        transaction_id=alert.transaction.transaction_id if alert.transaction else "",
        customer_id=alert.customer.customer_id if alert.customer else "",
        severity=alert.severity,
        title=alert.title,
        reason=alert.reason,
        status=alert.status,
        assigned_to=alert.assigned_to,
        risk_score=alert.transaction.risk_score if alert.transaction else None,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(status_filter: AlertStatus | None = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    query = db.query(Alert)
    if status_filter:
        query = query.filter(Alert.status == status_filter)
    alerts = query.order_by(Alert.created_at.desc()).limit(200).all()
    return [_to_out(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    return _to_out(alert)


@router.post("/{alert_id}/review", response_model=AlertOut)
def review_alert(
    alert_id: str,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    # Part of the External Business API: an external system can update an alert's
    # status (e.g. NEW -> INVESTIGATING) with an X-API-Key, in addition to the normal
    # dashboard ADMIN/ANALYST Bearer-token path.
    current_user=Depends(require_roles_or_api_key(UserRole.ADMIN, UserRole.ANALYST)),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    old_status = alert.status.value
    try:
        alert = update_alert_status(db, alert, payload.status)
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=422,
            detail={"success": False, "error": {"code": "USE_FEEDBACK_ENDPOINT", "message": str(exc)}},
        )
    log_action(db, user_id=current_user.id, action="ALERT_STATUS_CHANGED", details=f"alert={alert.id} {old_status} -> {payload.status.value}")
    return _to_out(alert)


@router.post("/{alert_id}/assign", response_model=AlertOut)
def assign_alert_to_user(
    alert_id: str,
    payload: AlertAssign,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User was not found"}})
    if user.role not in (UserRole.ADMIN, UserRole.ANALYST):
        raise HTTPException(status_code=422, detail={"success": False, "error": {"code": "INVALID_ASSIGNEE", "message": "Alerts can only be assigned to admins or analysts"}})
    alert = assign_alert(db, alert, user)
    log_action(db, user_id=current_user.id, action="ALERT_ASSIGNED", details=f"alert={alert.id} -> user={user.id}")
    return _to_out(alert)


@router.get("/{alert_id}/notes", response_model=list[InvestigationNoteOut])
def list_notes(alert_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    notes = (
        db.query(InvestigationNote)
        .filter(InvestigationNote.alert_id == alert_id)
        .order_by(InvestigationNote.created_at.asc())
        .all()
    )
    return _notes_to_out(db, notes)


@router.post("/{alert_id}/notes", response_model=InvestigationNoteOut)
def add_note(
    alert_id: str,
    payload: InvestigationNoteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    note = add_investigation_note(db, alert, current_user.id, payload.note)
    return _notes_to_out(db, [note])[0]


@router.get("/{alert_id}/feedback", response_model=list[FeedbackOut])
def get_feedback(alert_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    return _feedback_to_out(db, list_feedback_for_alert(db, alert_id))


@router.post("/{alert_id}/feedback", response_model=FeedbackOut)
def submit_feedback(
    alert_id: str,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    if payload.actual_result not in ("CONFIRMED_FRAUD", "FALSE_POSITIVE"):
        raise HTTPException(
            status_code=422,
            detail={"success": False, "error": {"code": "INVALID_RESULT", "message": "actual_result must be CONFIRMED_FRAUD or FALSE_POSITIVE"}},
        )
    try:
        feedback = record_feedback(db, alert, current_user.id, payload.actual_result, payload.comments)
    except FeedbackAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail={"success": False, "error": {"code": "FEEDBACK_ALREADY_EXISTS", "message": str(exc)}},
        )
    log_action(db, user_id=current_user.id, action="FEEDBACK_SUBMITTED", details=f"alert={alert.id} result={payload.actual_result}")
    return _feedback_to_out(db, [feedback])[0]
