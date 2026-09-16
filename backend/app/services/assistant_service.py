"""
AI Investigation Assistant - evidence gathering (spec item 14).

CRITICAL RULE (same as app.ai.llm_service): the LLM is only ever given
structured facts assembled here from the database. It never queries the
database itself and it never sees more than what this module hands it, so
it cannot invent a transaction, customer, or device that isn't real.

This module maps the four core analyst intents from the spec onto evidence
sections. A single question can trigger more than one section at once (e.g.
"summarize the investigation for the customer connected to DEV-4471" hits
all three), so sections are additive, not mutually exclusive:

  - "Why is this customer suspicious?"                -> customer + flagged_transaction
  - "Show me unusual activity from this customer."    -> unusual_activity
  - "What transactions are connected to this device?" -> device
  - "Summarize this investigation."                   -> investigation_case_summary
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.services.investigation_service import get_investigation_case, txn_summary

# Matches tokens shaped like a device id (letters/digits with a hyphen, e.g.
# "DEV-4471", "DEVICE-A1B2"). This is a best-effort convenience so an analyst
# who types "what's connected to DEV-4471?" doesn't also have to fill in a
# separate device field - it is never the only way to target a device.
_DEVICE_TOKEN_PATTERN = re.compile(r"\b([A-Za-z]{2,12}-[A-Za-z0-9]{2,24})\b")

_UNUSUAL_KEYWORDS = ("unusual", "anomal", "suspicious activity", "strange", "odd behavior", "out of pattern")
_SUMMARY_KEYWORDS = ("summar", "recap", "overview", "brief me", "tl;dr")

RECENT_TXN_LIMIT = 20
UNUSUAL_TXN_LIMIT = 10
DEVICE_TXN_LIMIT = 30
# Below this anomaly/risk score, a transaction isn't worth calling "unusual".
UNUSUAL_SCORE_THRESHOLD = 40


def extract_device_id(question: str) -> str | None:
    """Best-effort extraction of a device id mentioned inline in a question."""
    for token in _DEVICE_TOKEN_PATTERN.findall(question):
        if token.upper().startswith("DEV"):
            return token
    return None


def wants_unusual_activity(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in _UNUSUAL_KEYWORDS)


def wants_summary(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in _SUMMARY_KEYWORDS)


def _customer_brief(customer: Customer) -> dict:
    return {
        "customer_id": customer.customer_id,
        "risk_score": round(customer.risk_score, 1),
        "risk_level": customer.risk_level.value,
        "total_transactions": customer.total_transactions,
        "suspicious_transactions": customer.suspicious_transactions,
        "devices_used": customer.devices_used,
        "locations_used": customer.locations_used,
        "previous_fraud_reports": customer.previous_fraud_reports,
    }


def gather_unusual_activity(db: Session, customer: Customer, limit: int = UNUSUAL_TXN_LIMIT) -> dict:
    """
    This customer's own transactions that stand out from their normal
    pattern - ranked by anomaly/risk score rather than recency, so a
    six-month-old outlier still surfaces ahead of an ordinary transaction
    from this morning.
    """
    candidates = (
        db.query(Transaction)
        .filter(Transaction.customer_id == customer.id)
        .order_by(Transaction.anomaly_score.desc(), Transaction.risk_score.desc())
        .limit(limit)
        .all()
    )
    flagged = [t for t in candidates if (t.anomaly_score or 0) >= UNUSUAL_SCORE_THRESHOLD or (t.risk_factors or [])]
    shown = flagged or candidates[:5]

    return {
        "customer_id": customer.customer_id,
        "unusual_transactions": [
            {
                **txn_summary(t),
                "anomaly_score": t.anomaly_score,
                "risk_factors": t.risk_factors or [],
            }
            for t in shown
        ],
        "note": (
            "Ranked by anomaly score and risk score, not recency."
            if flagged
            else "No transaction cleared the anomaly/risk-factor threshold; showing the highest-scoring ones on record instead."
        ),
    }


def gather_device_evidence(db: Session, device_id: str, limit: int = DEVICE_TXN_LIMIT) -> dict:
    """
    Every transaction that has ever used this device, across every
    customer - the direct answer to "what transactions are connected to
    this device?" and a quick signal for device-sharing fraud rings.
    """
    txns = (
        db.query(Transaction)
        .filter(Transaction.device_id == device_id)
        .order_by(Transaction.transaction_datetime.desc())
        .limit(limit)
        .all()
    )
    distinct_customers = sorted({t.customer.customer_id for t in txns if t.customer})
    return {
        "device_id": device_id,
        "transaction_count": len(txns),
        "distinct_customer_count": len(distinct_customers),
        "distinct_customers": distinct_customers,
        "shared_by_multiple_customers": len(distinct_customers) > 1,
        "transactions": [txn_summary(t) for t in txns],
    }


def build_assistant_evidence(
    db: Session,
    question: str,
    alert_id: str | None = None,
    customer_id: str | None = None,
    device_id: str | None = None,
) -> dict:
    """Assemble the evidence dict handed to the LLM for one analyst question."""
    evidence: dict = {}

    alert: Alert | None = None
    customer: Customer | None = None

    if alert_id:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if alert:
        customer = alert.customer
        customer_id = customer_id or (customer.customer_id if customer else None)
        if wants_summary(question):
            # Full case bundle: notes, related alerts, fingerprints, everything -
            # this is the one section that duplicates data covered elsewhere
            # below, on purpose, since a summary request wants the whole picture.
            evidence["investigation_case_summary"] = get_investigation_case(db, alert)
        else:
            evidence["alert"] = {
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "reason": alert.reason,
            }
            evidence["flagged_transaction"] = {
                **txn_summary(alert.transaction),
                "risk_factors": alert.transaction.risk_factors or [],
                "explanation": alert.transaction.explanation,
            }

    if customer_id and not customer:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()

    if customer:
        evidence["customer"] = _customer_brief(customer)
        recent_txns = (
            db.query(Transaction)
            .filter(Transaction.customer_id == customer.id)
            .order_by(Transaction.transaction_datetime.desc())
            .limit(RECENT_TXN_LIMIT)
            .all()
        )
        evidence["recent_transactions"] = [txn_summary(t) for t in recent_txns]

        if wants_unusual_activity(question):
            evidence["unusual_activity"] = gather_unusual_activity(db, customer)

    resolved_device_id = device_id or extract_device_id(question)
    if resolved_device_id:
        evidence["device"] = gather_device_evidence(db, resolved_device_id)

    return evidence
