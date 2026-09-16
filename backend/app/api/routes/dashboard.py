from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.database import get_db
from app.models.alert import Alert
from app.models.customer import Customer
from app.models.enums import AlertStatus, Decision, RiskLevel, UserRole
from app.models.transaction import Transaction

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _enum_value(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _apply_date_range(query, column, date_from: Optional[str], date_to: Optional[str]):
    """Filter a query by an inclusive [date_from, date_to] range on `column`.

    Dates are plain YYYY-MM-DD strings from the dashboard filter bar. `date_to`
    is treated as inclusive of the whole day by advancing to the next day's
    start, since `column` is a DateTime.
    """
    if date_from:
        query = query.filter(column >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(column < datetime.fromisoformat(date_to) + timedelta(days=1))
    return query


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    total_transactions = db.query(func.count(Transaction.id)).scalar() or 0
    high_risk = db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.HIGH).scalar() or 0
    medium_risk = db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.MEDIUM).scalar() or 0
    avg_risk_score = db.query(func.avg(Transaction.risk_score)).scalar() or 0.0

    total_alerts = db.query(func.count(Alert.id)).scalar() or 0
    confirmed_fraud = db.query(func.count(Alert.id)).filter(Alert.status == AlertStatus.CONFIRMED_FRAUD).scalar() or 0
    false_positives = db.query(func.count(Alert.id)).filter(Alert.status == AlertStatus.FALSE_POSITIVE).scalar() or 0

    return {
        "total_transactions": total_transactions,
        "high_risk_transactions": high_risk,
        "medium_risk_transactions": medium_risk,
        "fraud_alerts": total_alerts,
        "confirmed_fraud": confirmed_fraud,
        "false_positives": false_positives,
        "average_risk_score": round(float(avg_risk_score), 2),
    }


@router.get("/fraud-trend")
def fraud_trend(days: int = 14, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(func.date(Transaction.created_at).label("day"), func.count(Transaction.id).label("count"))
        .filter(Transaction.created_at >= since)
        .filter(Transaction.risk_level != RiskLevel.LOW)
        .group_by("day")
        .order_by("day")
        .all()
    )
    return [{"date": str(r.day), "suspicious_transactions": r.count} for r in rows]


@router.get("/recent-alerts")
def recent_alerts(limit: int = 10, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
    return [
        {
            "id": a.id, "title": a.title, "severity": a.severity, "status": a.status,
            "created_at": a.created_at,
        }
        for a in alerts
    ]


@router.get("/recent-transactions")
def recent_transactions(limit: int = 10, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Recently added transactions, most useful to Business Managers who are
    responsible for adding/importing transactions and want to confirm they
    went through and see the risk outcome.

    Note: transactions are not currently tagged with a "created_by" user,
    so this shows the most recent transactions system-wide rather than a
    per-user submission history.
    """
    txns = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id, "transaction_id": t.transaction_id, "amount": t.amount,
            "currency": t.currency, "risk_level": t.risk_level, "decision": t.decision,
            "created_at": t.created_at,
        }
        for t in txns
    ]


# ---------------------------------------------------------------------------
# Admin dashboard
#
# Everything below powers the dedicated Admin Dashboard page: it is
# ADMIN-only (enforced server-side via require_roles, not just hidden in the
# UI), supports an optional date_from/date_to filter shared by every widget,
# and adds the metrics/breakdowns the summary/fraud-trend endpoints above
# don't cover: full status + risk breakdowns, suspicious-customer ranking,
# and suspicious device/IP fingerprint detection.
# ---------------------------------------------------------------------------

DateFrom = Query(None, description="Start date (inclusive), format YYYY-MM-DD")
DateTo = Query(None, description="End date (inclusive), format YYYY-MM-DD")


@router.get("/admin/summary")
def admin_summary(
    date_from: Optional[str] = DateFrom,
    date_to: Optional[str] = DateTo,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    txn_q = _apply_date_range(db.query(Transaction), Transaction.transaction_datetime, date_from, date_to)
    alert_q = _apply_date_range(db.query(Alert), Alert.created_at, date_from, date_to)

    total_transactions = txn_q.count()
    high_risk = txn_q.filter(Transaction.risk_level == RiskLevel.HIGH).count()
    medium_risk = txn_q.filter(Transaction.risk_level == RiskLevel.MEDIUM).count()
    low_risk = txn_q.filter(Transaction.risk_level == RiskLevel.LOW).count()
    blocked = txn_q.filter(Transaction.decision == Decision.BLOCK).count()
    under_review = txn_q.filter(Transaction.decision == Decision.REVIEW).count()

    avg_risk_score = (
        _apply_date_range(db.query(func.avg(Transaction.risk_score)), Transaction.transaction_datetime, date_from, date_to).scalar()
        or 0.0
    )

    total_alerts = alert_q.count()
    new_alerts = alert_q.filter(Alert.status == AlertStatus.NEW).count()
    investigating = alert_q.filter(Alert.status == AlertStatus.INVESTIGATING).count()
    confirmed_fraud = alert_q.filter(Alert.status == AlertStatus.CONFIRMED_FRAUD).count()
    false_positives = alert_q.filter(Alert.status == AlertStatus.FALSE_POSITIVE).count()

    # Resolved (confirmed + false positive) is the denominator analysts have actually
    # closed out, which is a more honest "false positive rate" than dividing by all alerts.
    resolved = confirmed_fraud + false_positives
    false_positive_rate = round((false_positives / resolved) * 100, 1) if resolved else 0.0

    suspicious_customers = db.query(func.count(Customer.id)).filter(Customer.suspicious_transactions > 0).scalar() or 0

    return {
        "total_transactions": total_transactions,
        "high_risk_transactions": high_risk,
        "medium_risk_transactions": medium_risk,
        "low_risk_transactions": low_risk,
        "blocked_transactions": blocked,
        "under_review_transactions": under_review,
        "fraud_alerts": total_alerts,
        "new_alerts": new_alerts,
        "investigating_alerts": investigating,
        "confirmed_fraud": confirmed_fraud,
        "false_positives": false_positives,
        "false_positive_rate": false_positive_rate,
        "average_risk_score": round(float(avg_risk_score), 2),
        "suspicious_customers": suspicious_customers,
    }


@router.get("/admin/fraud-trend")
def admin_fraud_trend(
    days: int = 30,
    date_from: Optional[str] = DateFrom,
    date_to: Optional[str] = DateTo,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Daily transaction volume broken down by risk level, for a stacked trend chart.

    Falls back to the last `days` days when no explicit range is given.
    """
    q = db.query(
        func.date(Transaction.transaction_datetime).label("day"),
        Transaction.risk_level,
        func.count(Transaction.id).label("count"),
    )
    if date_from or date_to:
        q = _apply_date_range(q, Transaction.transaction_datetime, date_from, date_to)
    else:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(Transaction.transaction_datetime >= since)

    rows = q.group_by("day", Transaction.risk_level).order_by("day").all()

    by_day: dict = {}
    for r in rows:
        day = str(r.day)
        entry = by_day.setdefault(day, {"date": day, "low": 0, "medium": 0, "high": 0, "confirmed": 0, "total": 0})
        entry[_enum_value(r.risk_level).lower()] = r.count
        entry["total"] += r.count

    # Also fold in confirmed-fraud alerts per day (by the date the alert was
    # raised), so the trend chart can plot a "Confirmed Fraud" line alongside
    # High/Medium risk volume, using the same date range as the transactions above.
    alert_q = db.query(
        func.date(Alert.created_at).label("day"),
        func.count(Alert.id).label("count"),
    ).filter(Alert.status == AlertStatus.CONFIRMED_FRAUD)
    if date_from or date_to:
        alert_q = _apply_date_range(alert_q, Alert.created_at, date_from, date_to)
    else:
        since = datetime.utcnow() - timedelta(days=days)
        alert_q = alert_q.filter(Alert.created_at >= since)
    for day, count in alert_q.group_by("day").all():
        day = str(day)
        entry = by_day.setdefault(day, {"date": day, "low": 0, "medium": 0, "high": 0, "confirmed": 0, "total": 0})
        entry["confirmed"] = count

    return sorted(by_day.values(), key=lambda x: x["date"])


@router.get("/admin/risk-distribution")
def admin_risk_distribution(
    date_from: Optional[str] = DateFrom,
    date_to: Optional[str] = DateTo,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Transaction counts grouped by risk level, for a donut/pie chart."""
    q = _apply_date_range(
        db.query(Transaction.risk_level, func.count(Transaction.id)),
        Transaction.transaction_datetime,
        date_from,
        date_to,
    ).group_by(Transaction.risk_level)
    return [{"risk_level": _enum_value(rl), "count": c} for rl, c in q.all()]


@router.get("/admin/alert-status-breakdown")
def admin_alert_status_breakdown(
    date_from: Optional[str] = DateFrom,
    date_to: Optional[str] = DateTo,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Alert counts grouped by status (new / investigating / confirmed / false positive / resolved)."""
    q = _apply_date_range(
        db.query(Alert.status, func.count(Alert.id)),
        Alert.created_at,
        date_from,
        date_to,
    ).group_by(Alert.status)
    return [{"status": _enum_value(s), "count": c} for s, c in q.all()]


@router.get("/admin/suspicious-customers")
def admin_suspicious_customers(
    limit: int = 10,
    min_risk_score: float = 0,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Customers ranked by risk score, for the 'Suspicious Customers' widget."""
    customers = (
        db.query(Customer)
        .filter(Customer.risk_score >= min_risk_score)
        .order_by(Customer.risk_score.desc(), Customer.suspicious_transactions.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": c.id,
            "customer_id": c.customer_id,
            "name": c.name,
            "risk_score": c.risk_score,
            "risk_level": c.risk_level,
            "total_transactions": c.total_transactions,
            "suspicious_transactions": c.suspicious_transactions,
            "devices_used": c.devices_used,
            "locations_used": c.locations_used,
            "previous_fraud_reports": c.previous_fraud_reports,
        }
        for c in customers
    ]


def _fingerprint_stats(db: Session, column, date_from: Optional[str], date_to: Optional[str]):
    """Shared aggregation for the device/IP suspicion widgets: how many
    transactions, distinct customers, and high-risk hits each fingerprint
    value (device_id or ip_address) has, plus its average risk score.
    """
    q = db.query(
        column.label("value"),
        func.count(Transaction.id).label("transaction_count"),
        func.count(distinct(Transaction.customer_id)).label("customer_count"),
        func.sum(case((Transaction.risk_level == RiskLevel.HIGH, 1), else_=0)).label("high_risk_count"),
        func.avg(Transaction.risk_score).label("avg_risk_score"),
        func.max(Transaction.transaction_datetime).label("last_seen"),
    ).filter(column.isnot(None))
    q = _apply_date_range(q, Transaction.transaction_datetime, date_from, date_to)
    return q.group_by(column).having(func.count(Transaction.id) >= 2).all()


def _rank_fingerprints(rows, limit: int):
    """Rank fingerprints by a simple composite suspicion score: being shared
    across multiple customers matters most (classic fraud-ring signal),
    then how often it produced high-risk transactions, then its average
    risk score. Sorted in Python (rather than a DB-specific SQL expression)
    so this stays portable across SQLite/Postgres.
    """
    scored = []
    for r in rows:
        avg_score = float(r.avg_risk_score or 0)
        high_risk_count = int(r.high_risk_count or 0)
        composite = (r.customer_count * 25) + (high_risk_count * 8) + avg_score
        scored.append(
            {
                "value": r.value,
                "transaction_count": r.transaction_count,
                "customer_count": r.customer_count,
                "high_risk_count": high_risk_count,
                "avg_risk_score": round(avg_score, 2),
                "last_seen": r.last_seen,
                "shared_across_customers": r.customer_count > 1,
                "suspicion_score": round(composite, 2),
            }
        )
    scored.sort(key=lambda x: x["suspicion_score"], reverse=True)
    return scored[:limit]


@router.get("/admin/suspicious-devices")
def admin_suspicious_devices(
    limit: int = 10,
    date_from: Optional[str] = DateFrom,
    date_to: Optional[str] = DateTo,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Device fingerprints most likely tied to fraud: shared across many
    customers and/or producing a disproportionate number of high-risk
    transactions.
    """
    rows = _fingerprint_stats(db, Transaction.device_id, date_from, date_to)
    return _rank_fingerprints(rows, limit)


@router.get("/admin/suspicious-ips")
def admin_suspicious_ips(
    limit: int = 10,
    date_from: Optional[str] = DateFrom,
    date_to: Optional[str] = DateTo,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Same suspicion ranking as /admin/suspicious-devices, but for IP addresses."""
    rows = _fingerprint_stats(db, Transaction.ip_address, date_from, date_to)
    return _rank_fingerprints(rows, limit)
