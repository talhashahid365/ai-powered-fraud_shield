"""
Reports API (spec section 16).

Report types:
    - Daily fraud activity
    - Monthly fraud activity
    - High-risk customers
    - High-risk transactions
    - Confirmed fraud
    - False positives
    - Fraud trends

Every report has a JSON endpoint for on-screen display and can also be
downloaded as CSV via GET /api/reports/export/{report_type}, which reuses
the exact same data functions in app.services.report_service so the export
can never drift from what's rendered on screen. The legacy
`/fraud-outcomes` and `/model-feedback-summary` endpoints are kept as-is
for backwards compatibility with existing callers.
"""
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.alert import Alert
from app.models.enums import AlertSeverity, AlertStatus, FeedbackResult
from app.models.feedback import Feedback
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["Reports"])

REPORT_TYPES = [
    "daily-fraud-activity",
    "monthly-fraud-activity",
    "high-risk-customers",
    "high-risk-transactions",
    "confirmed-fraud",
    "false-positives",
    "fraud-trends",
]


def _bad_request(message: str):
    return HTTPException(
        status_code=400,
        detail={"success": False, "error": {"code": "INVALID_REPORT_PARAMS", "message": message}},
    )


# ---------------------------------------------------------------------------
# 1. Daily fraud activity
# ---------------------------------------------------------------------------

@router.get("/daily-fraud-activity")
def daily_fraud_activity(
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today (UTC)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return report_service.daily_fraud_activity(db, date)
    except ValueError as exc:
        raise _bad_request(str(exc))


# ---------------------------------------------------------------------------
# 2. Monthly fraud activity
# ---------------------------------------------------------------------------

@router.get("/monthly-fraud-activity")
def monthly_fraud_activity(
    year: Optional[int] = Query(None, description="Defaults to current year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Defaults to current month"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.utcnow()
    try:
        return report_service.monthly_fraud_activity(db, year or now.year, month or now.month)
    except ValueError as exc:
        raise _bad_request(str(exc))


# ---------------------------------------------------------------------------
# 3. High-risk customers
# ---------------------------------------------------------------------------

@router.get("/high-risk-customers")
def high_risk_customers(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return report_service.high_risk_customers(db, limit)


# ---------------------------------------------------------------------------
# 4. High-risk transactions
# ---------------------------------------------------------------------------

@router.get("/high-risk-transactions")
def high_risk_transactions(
    limit: int = Query(200, ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return report_service.high_risk_transactions(db, limit, start_date, end_date)
    except ValueError as exc:
        raise _bad_request(str(exc))


# ---------------------------------------------------------------------------
# 5. Confirmed fraud (drill-down list)
# ---------------------------------------------------------------------------

@router.get("/confirmed-fraud")
def confirmed_fraud(
    limit: int = Query(200, ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return report_service.confirmed_fraud(db, start_date, end_date, limit)
    except ValueError as exc:
        raise _bad_request(str(exc))


# ---------------------------------------------------------------------------
# 6. False positives (drill-down list)
# ---------------------------------------------------------------------------

@router.get("/false-positives")
def false_positives(
    limit: int = Query(200, ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return report_service.false_positives(db, start_date, end_date, limit)
    except ValueError as exc:
        raise _bad_request(str(exc))


# ---------------------------------------------------------------------------
# 7. Fraud trends
# ---------------------------------------------------------------------------

@router.get("/fraud-trends")
def fraud_trends(
    days: int = Query(30, ge=1, le=180, description="Size of the trailing window, in days"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return report_service.fraud_trends(db, days)


# ---------------------------------------------------------------------------
# Legacy summary endpoints (kept for backwards compatibility)
# ---------------------------------------------------------------------------

@router.get("/fraud-outcomes")
def fraud_outcomes(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    confirmed = db.query(func.count(Alert.id)).filter(Alert.status == AlertStatus.CONFIRMED_FRAUD).scalar() or 0
    false_pos = db.query(func.count(Alert.id)).filter(Alert.status == AlertStatus.FALSE_POSITIVE).scalar() or 0
    return {"confirmed_fraud": confirmed, "false_positives": false_pos}


@router.get("/model-feedback-summary")
def model_feedback_summary(days: int = 90, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Analyst-feedback-driven view of how well the fraud model's alerts are holding up,
    i.e. what fraction of alerts the model raises actually turn out to be fraud once an
    analyst reviews them. This is the same Feedback data used to build the labeled
    training/evaluation set in ml/training/export_feedback_dataset.py -- surfacing it here
    lets an admin see label volume and precision trending over time without needing to
    run the ML scripts, and gauge whether there's enough feedback yet to be worth
    training a supervised classifier (see ml/training/train_supervised_from_feedback.py).
    """
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(Feedback.actual_result, Alert.severity, Feedback.created_at)
        .join(Alert, Feedback.alert_id == Alert.id)
        .filter(Feedback.created_at >= since)
        .all()
    )

    total = len(rows)
    confirmed = sum(1 for r in rows if r.actual_result == FeedbackResult.CONFIRMED_FRAUD)
    false_pos = total - confirmed
    precision = round(confirmed / total, 4) if total else None

    by_severity: dict[str, dict[str, int]] = {s.value: {"confirmed_fraud": 0, "false_positives": 0} for s in AlertSeverity}
    for r in rows:
        bucket = by_severity[r.severity.value]
        if r.actual_result == FeedbackResult.CONFIRMED_FRAUD:
            bucket["confirmed_fraud"] += 1
        else:
            bucket["false_positives"] += 1

    weekly: dict[str, dict[str, int]] = {}
    for r in rows:
        week_start = (r.created_at - timedelta(days=r.created_at.weekday())).strftime("%Y-%m-%d")
        bucket = weekly.setdefault(week_start, {"confirmed_fraud": 0, "false_positives": 0})
        if r.actual_result == FeedbackResult.CONFIRMED_FRAUD:
            bucket["confirmed_fraud"] += 1
        else:
            bucket["false_positives"] += 1

    return {
        "window_days": days,
        "total_labeled_alerts": total,
        "confirmed_fraud": confirmed,
        "false_positives": false_pos,
        "alert_precision": precision,  # share of reviewed alerts that were real fraud
        "by_severity": by_severity,
        "weekly_trend": [{"week_start": k, **v} for k, v in sorted(weekly.items())],
        "training_data_note": (
            "This same feedback data can be exported as a labeled dataset via "
            "ml/training/export_feedback_dataset.py for training/evaluating the fraud model."
        ),
    }


# ---------------------------------------------------------------------------
# CSV export -- shared by every report type above
# ---------------------------------------------------------------------------

@router.get("/export/{report_type}")
def export_report(
    report_type: str,
    date: Optional[str] = Query(None, description="For daily-fraud-activity: YYYY-MM-DD"),
    year: Optional[int] = Query(None, description="For monthly-fraud-activity"),
    month: Optional[int] = Query(None, ge=1, le=12, description="For monthly-fraud-activity"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD, for list/date-ranged reports"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD, for list/date-ranged reports"),
    days: int = Query(30, ge=1, le=180, description="For fraud-trends"),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": {
                    "code": "UNKNOWN_REPORT_TYPE",
                    "message": f"Unknown report type '{report_type}'. Valid types: {', '.join(REPORT_TYPES)}",
                },
            },
        )

    try:
        if report_type == "daily-fraud-activity":
            rows = [report_service.daily_fraud_activity(db, date)]
        elif report_type == "monthly-fraud-activity":
            now = datetime.utcnow()
            rows = [report_service.monthly_fraud_activity(db, year or now.year, month or now.month)]
        elif report_type == "high-risk-customers":
            rows = report_service.high_risk_customers(db, limit)
        elif report_type == "high-risk-transactions":
            rows = report_service.high_risk_transactions(db, limit, start_date, end_date)
        elif report_type == "confirmed-fraud":
            rows = report_service.confirmed_fraud(db, start_date, end_date, limit)
        elif report_type == "false-positives":
            rows = report_service.false_positives(db, start_date, end_date, limit)
        else:  # fraud-trends
            rows = report_service.fraud_trends(db, days)["daily"]
    except ValueError as exc:
        raise _bad_request(str(exc))

    buffer = io.StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    else:
        writer = csv.writer(buffer)
        writer.writerow(["message"])
        writer.writerow(["No data available for this report and date range"])

    buffer.seek(0)
    filename = f"{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
