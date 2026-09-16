"""
Investigation System (spec section 10).

Assembles everything an analyst needs to investigate a flagged transaction
into a single "case" bundle: customer info, transaction history, related
transactions (linked by shared device/IP/location - i.e. potential fraud
rings), devices, IP addresses, locations, risk factors, the AI explanation,
related alerts, and investigation notes.
"""
from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.device import Device
from app.models.investigation_note import InvestigationNote
from app.models.ip_address import IPAddress
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.customer import CustomerOut

HISTORY_LIMIT = 50
RELATED_LIMIT = 50


def txn_summary(t: Transaction) -> dict:
    return {
        "id": t.id,
        "transaction_id": t.transaction_id,
        "customer_id": t.customer.customer_id if t.customer else None,
        "amount": t.amount,
        "currency": t.currency,
        "transaction_datetime": t.transaction_datetime,
        "payment_method": t.payment_method,
        "device_id": t.device_id,
        "ip_address": t.ip_address,
        "location": t.location,
        "transaction_status": t.transaction_status.value,
        "risk_score": t.risk_score,
        "risk_level": t.risk_level.value,
        "decision": t.decision.value,
    }


def txn_detail(t: Transaction) -> dict:
    return {
        **txn_summary(t),
        "account_age_days": t.account_age_days,
        "anomaly_score": t.anomaly_score,
        "rule_score": t.rule_score,
        "risk_factors": t.risk_factors or [],
        "triggered_rules": t.triggered_rules or [],
        "explanation": t.explanation,
        "created_at": t.created_at,
    }


def alert_summary(a: Alert) -> dict:
    return {
        "id": a.id,
        "transaction_id": a.transaction.transaction_id if a.transaction else None,
        "customer_id": a.customer.customer_id if a.customer else None,
        "severity": a.severity.value,
        "title": a.title,
        "reason": a.reason,
        "status": a.status.value,
        "created_at": a.created_at,
    }


def _grouped_field(db: Session, customer_id: str, column) -> list[dict]:
    """Group this customer's transactions by a fingerprint column (device_id,
    ip_address, or location), returning usage counts and first/last seen."""
    rows = (
        db.query(column, func.count(Transaction.id), func.min(Transaction.transaction_datetime), func.max(Transaction.transaction_datetime))
        .filter(Transaction.customer_id == customer_id, column.isnot(None))
        .group_by(column)
        .order_by(func.count(Transaction.id).desc())
        .all()
    )
    return [
        {"value": value, "transaction_count": count, "first_seen": first_seen, "last_seen": last_seen}
        for value, count, first_seen, last_seen in rows
    ]


def get_investigation_case(db: Session, alert: Alert) -> dict:
    txn = alert.transaction
    customer = alert.customer

    # Transaction history: this customer's own recent transactions.
    history = (
        db.query(Transaction)
        .filter(Transaction.customer_id == customer.id)
        .order_by(Transaction.transaction_datetime.desc())
        .limit(HISTORY_LIMIT)
        .all()
    )

    # Devices / IP addresses / locations this customer has used, derived from
    # their transaction history (the source of truth - Device/IPAddress rows
    # are enrichment only, e.g. country/city, and may not exist yet).
    devices = _grouped_field(db, customer.id, Transaction.device_id)
    ip_addresses = _grouped_field(db, customer.id, Transaction.ip_address)
    locations = _grouped_field(db, customer.id, Transaction.location)

    if devices:
        device_meta = {d.device_id: d for d in db.query(Device).filter(Device.device_id.in_([d["value"] for d in devices])).all()}
        for d in devices:
            meta = device_meta.get(d["value"])
            d["device_type"] = meta.device_type if meta else None

    if ip_addresses:
        ip_meta = {i.ip_address: i for i in db.query(IPAddress).filter(IPAddress.ip_address.in_([i["value"] for i in ip_addresses])).all()}
        for i in ip_addresses:
            meta = ip_meta.get(i["value"])
            i["country"] = meta.country if meta else None
            i["city"] = meta.city if meta else None

    # Related transactions: OTHER customers' transactions sharing this
    # transaction's device, IP, or location - i.e. potential fraud-ring
    # connections, distinct from this customer's own history above.
    fingerprint_filters = []
    if txn.device_id:
        fingerprint_filters.append(Transaction.device_id == txn.device_id)
    if txn.ip_address:
        fingerprint_filters.append(Transaction.ip_address == txn.ip_address)
    if txn.location:
        fingerprint_filters.append(Transaction.location == txn.location)

    related_transactions: list[Transaction] = []
    if fingerprint_filters:
        related_transactions = (
            db.query(Transaction)
            .filter(or_(*fingerprint_filters))
            .filter(Transaction.customer_id != customer.id)
            .order_by(Transaction.transaction_datetime.desc())
            .limit(RELATED_LIMIT)
            .all()
        )

    # Related alerts: other alerts on this customer, plus alerts on any
    # customer linked through the shared device/IP/location above.
    related_customer_ids = {t.customer_id for t in related_transactions}
    related_alert_query = db.query(Alert).filter(Alert.id != alert.id)
    if related_customer_ids:
        related_alert_query = related_alert_query.filter(or_(Alert.customer_id == customer.id, Alert.customer_id.in_(related_customer_ids)))
    else:
        related_alert_query = related_alert_query.filter(Alert.customer_id == customer.id)
    related_alerts = related_alert_query.order_by(Alert.created_at.desc()).limit(RELATED_LIMIT).all()

    # Investigation notes, oldest first, with the analyst's name resolved.
    notes = (
        db.query(InvestigationNote)
        .filter(InvestigationNote.alert_id == alert.id)
        .order_by(InvestigationNote.created_at.asc())
        .all()
    )
    analyst_ids = {n.analyst_id for n in notes}
    analysts = {u.id: u.name for u in db.query(User).filter(User.id.in_(analyst_ids)).all()} if analyst_ids else {}

    return {
        "alert": alert_summary(alert),
        "customer": CustomerOut.model_validate(customer).model_dump(),
        "transaction": txn_detail(txn),
        "risk_factors": txn.risk_factors or [],
        "triggered_rules": txn.triggered_rules or [],
        "ai_explanation": txn.explanation,
        "transaction_history": [txn_summary(t) for t in history],
        "related_transactions": [txn_summary(t) for t in related_transactions],
        "devices": devices,
        "ip_addresses": ip_addresses,
        "locations": locations,
        "related_alerts": [alert_summary(a) for a in related_alerts],
        "investigation_notes": [
            {
                "id": n.id,
                "alert_id": n.alert_id,
                "analyst_id": n.analyst_id,
                "analyst_name": analysts.get(n.analyst_id, "Unknown analyst"),
                "note": n.note,
                "created_at": n.created_at,
            }
            for n in notes
        ],
    }
