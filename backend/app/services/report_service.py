"""
Business logic for the Reports feature (section 16 of the spec):
    - Daily fraud activity
    - Monthly fraud activity
    - High-risk customers
    - High-risk transactions
    - Confirmed fraud
    - False positives
    - Fraud trends

Every function here returns plain dicts/lists (not pydantic models) so the
exact same data can back both the JSON report endpoints in
app.api.routes.reports and the CSV export endpoint -- one source of truth,
so an export can never drift from what's shown on screen.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.customer import Customer
from app.models.enums import AlertStatus, Decision, RiskLevel
from app.models.transaction import Transaction

MAX_TREND_DAYS = 180
MAX_LIST_LIMIT = 1000


def _parse_date(label: str, value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid {label} '{value}'. Expected format: YYYY-MM-DD")


def _day_bounds(date_str: Optional[str]) -> tuple[datetime, datetime]:
    day = _parse_date("date", date_str) if date_str else datetime.utcnow()
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


# ---------------------------------------------------------------------------
# Daily / monthly fraud activity
# ---------------------------------------------------------------------------

def daily_fraud_activity(db: Session, date: Optional[str] = None) -> dict:
    start, end = _day_bounds(date)

    txns = db.query(Transaction).filter(Transaction.created_at >= start, Transaction.created_at < end).all()
    alerts = db.query(Alert).filter(Alert.created_at >= start, Alert.created_at < end).all()

    total_amount = sum(t.amount for t in txns)

    return {
        "date": start.strftime("%Y-%m-%d"),
        "total_transactions": len(txns),
        "total_amount": round(total_amount, 2),
        "high_risk": sum(1 for t in txns if t.risk_level == RiskLevel.HIGH),
        "medium_risk": sum(1 for t in txns if t.risk_level == RiskLevel.MEDIUM),
        "low_risk": sum(1 for t in txns if t.risk_level == RiskLevel.LOW),
        "blocked": sum(1 for t in txns if t.decision == Decision.BLOCK),
        "alerts_created": len(alerts),
        "confirmed_fraud": sum(1 for a in alerts if a.status == AlertStatus.CONFIRMED_FRAUD),
        "false_positives": sum(1 for a in alerts if a.status == AlertStatus.FALSE_POSITIVE),
    }


def monthly_fraud_activity(db: Session, year: int, month: int) -> dict:
    if not (1 <= month <= 12):
        raise ValueError("Month must be between 1 and 12")

    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    txns = db.query(Transaction).filter(Transaction.created_at >= start, Transaction.created_at < end).all()
    alerts = db.query(Alert).filter(Alert.created_at >= start, Alert.created_at < end).all()

    total_amount = sum(t.amount for t in txns)
    confirmed = sum(1 for a in alerts if a.status == AlertStatus.CONFIRMED_FRAUD)
    false_pos = sum(1 for a in alerts if a.status == AlertStatus.FALSE_POSITIVE)

    return {
        "period": f"{year}-{month:02d}",
        "total_transactions": len(txns),
        "total_amount": round(total_amount, 2),
        "high_risk": sum(1 for t in txns if t.risk_level == RiskLevel.HIGH),
        "medium_risk": sum(1 for t in txns if t.risk_level == RiskLevel.MEDIUM),
        "low_risk": sum(1 for t in txns if t.risk_level == RiskLevel.LOW),
        "blocked": sum(1 for t in txns if t.decision == Decision.BLOCK),
        "alerts_created": len(alerts),
        "confirmed_fraud": confirmed,
        "false_positives": false_pos,
        # Share of reviewed alerts that turned out to be real fraud this month.
        "precision": round(confirmed / (confirmed + false_pos), 4) if (confirmed + false_pos) else None,
    }


# ---------------------------------------------------------------------------
# High-risk customers / transactions
# ---------------------------------------------------------------------------

def high_risk_customers(db: Session, limit: int = 200) -> list[dict]:
    limit = max(1, min(limit, MAX_LIST_LIMIT))
    customers = (
        db.query(Customer)
        .filter(Customer.risk_level == RiskLevel.HIGH)
        .order_by(Customer.risk_score.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "customer_id": c.customer_id,
            "name": c.name,
            "risk_score": round(c.risk_score, 2),
            "risk_level": c.risk_level.value,
            "total_transactions": c.total_transactions,
            "suspicious_transactions": c.suspicious_transactions,
            "previous_fraud_reports": c.previous_fraud_reports,
        }
        for c in customers
    ]


def high_risk_transactions(
    db: Session,
    limit: int = 200,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    limit = max(1, min(limit, MAX_LIST_LIMIT))
    query = db.query(Transaction).filter(Transaction.risk_level == RiskLevel.HIGH)
    if start_date:
        query = query.filter(Transaction.created_at >= _parse_date("start_date", start_date))
    if end_date:
        query = query.filter(Transaction.created_at < _parse_date("end_date", end_date) + timedelta(days=1))

    txns = query.order_by(Transaction.created_at.desc()).limit(limit).all()
    return [
        {
            "transaction_id": t.transaction_id,
            "customer_id": t.customer.customer_id if t.customer else "",
            "amount": t.amount,
            "currency": t.currency,
            "risk_score": round(t.risk_score, 2),
            "decision": t.decision.value,
            "transaction_status": t.transaction_status.value,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for t in txns
    ]


# ---------------------------------------------------------------------------
# Confirmed fraud / false positives (drill-down lists behind the summary
# counts previously exposed only via /fraud-outcomes)
# ---------------------------------------------------------------------------

def _alerts_by_status(
    db: Session,
    status: AlertStatus,
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
) -> list[dict]:
    limit = max(1, min(limit, MAX_LIST_LIMIT))
    query = db.query(Alert).filter(Alert.status == status)
    if start_date:
        query = query.filter(Alert.created_at >= _parse_date("start_date", start_date))
    if end_date:
        query = query.filter(Alert.created_at < _parse_date("end_date", end_date) + timedelta(days=1))

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    rows = []
    for a in alerts:
        txn = a.transaction
        cust = a.customer
        rows.append(
            {
                "alert_id": a.id,
                "transaction_id": txn.transaction_id if txn else "",
                "customer_id": cust.customer_id if cust else "",
                "severity": a.severity.value,
                "title": a.title,
                "reason": a.reason or "",
                "amount": txn.amount if txn else None,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return rows


def confirmed_fraud(
    db: Session,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    return _alerts_by_status(db, AlertStatus.CONFIRMED_FRAUD, start_date, end_date, limit)


def false_positives(
    db: Session,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    return _alerts_by_status(db, AlertStatus.FALSE_POSITIVE, start_date, end_date, limit)


# ---------------------------------------------------------------------------
# Fraud trends
# ---------------------------------------------------------------------------

def fraud_trends(db: Session, days: int = 30) -> dict:
    days = max(1, min(days, MAX_TREND_DAYS))

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = today_start + timedelta(days=1)
    start = end - timedelta(days=days)

    txns = db.query(Transaction).filter(Transaction.created_at >= start, Transaction.created_at < end).all()
    alerts = db.query(Alert).filter(Alert.created_at >= start, Alert.created_at < end).all()

    buckets: dict[str, dict] = {}
    for i in range(days):
        key = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[key] = {
            "date": key,
            "total_transactions": 0,
            "high_risk": 0,
            "alerts_created": 0,
            "confirmed_fraud": 0,
            "false_positives": 0,
        }

    for t in txns:
        key = t.created_at.strftime("%Y-%m-%d")
        bucket = buckets.get(key)
        if bucket is None:
            continue
        bucket["total_transactions"] += 1
        if t.risk_level == RiskLevel.HIGH:
            bucket["high_risk"] += 1

    for a in alerts:
        key = a.created_at.strftime("%Y-%m-%d")
        bucket = buckets.get(key)
        if bucket is None:
            continue
        bucket["alerts_created"] += 1
        if a.status == AlertStatus.CONFIRMED_FRAUD:
            bucket["confirmed_fraud"] += 1
        elif a.status == AlertStatus.FALSE_POSITIVE:
            bucket["false_positives"] += 1

    series = [buckets[k] for k in sorted(buckets)]
    for row in series:
        row["fraud_rate_pct"] = (
            round(row["confirmed_fraud"] / row["total_transactions"] * 100, 2)
            if row["total_transactions"]
            else 0.0
        )

    # Trend direction: compare average daily confirmed-fraud count in the
    # first half of the window against the second half.
    half = len(series) // 2
    direction = "stable"
    change_pct = 0.0
    if half > 0:
        first_avg = sum(r["confirmed_fraud"] for r in series[:half]) / half
        second_avg = sum(r["confirmed_fraud"] for r in series[half:]) / (len(series) - half)
        if first_avg == 0 and second_avg == 0:
            direction, change_pct = "stable", 0.0
        elif first_avg == 0:
            direction, change_pct = "increasing", 100.0
        else:
            change_pct = round((second_avg - first_avg) / first_avg * 100, 1)
            if change_pct > 5:
                direction = "increasing"
            elif change_pct < -5:
                direction = "decreasing"
            else:
                direction = "stable"

    total_confirmed = sum(r["confirmed_fraud"] for r in series)
    total_false_pos = sum(r["false_positives"] for r in series)

    return {
        "window_days": days,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": (end - timedelta(days=1)).strftime("%Y-%m-%d"),
        "total_confirmed_fraud": total_confirmed,
        "total_false_positives": total_false_pos,
        "trend_direction": direction,
        "change_pct": change_pct,
        "daily": series,
    }
