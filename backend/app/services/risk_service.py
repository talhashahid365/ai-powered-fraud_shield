"""
Orchestrates the full real-time detection flow for a single transaction:

New Transaction -> Validation -> Rule Engine -> ML Anomaly -> Customer
History -> Risk Decision Engine -> Risk Score -> Decision -> Alert/Approve

Signals considered (beyond raw amount): amount deviation from the customer's
own average, transaction velocity (multiple transactions in a short window),
new device, new location (never seen before for this customer, not just
"different from last time"), device/IP sharing across multiple customer
accounts, sudden change in customer behavior (EMA of historical risk +
suspicious-transaction ratio), unusual time-of-day activity (proxy for
login/activity-pattern anomalies), and high-value transactions from recently
created accounts.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.ai.anomaly_detection import TransactionFeatures, anomaly_detector
from app.ai.llm_service import generate_explanation
from app.ai.risk_engine import calculate_final_risk
from app.ai.rules_engine import RuleContext, evaluate_rules
from app.models.customer import Customer
from app.models.enums import Decision as DecisionEnum
from app.models.enums import TransactionStatus
from app.models.transaction import Transaction
from app.schemas.transaction import RiskCheckResponse


def _gather_context(db: Session, customer: Customer, txn: Transaction) -> tuple[RuleContext, TransactionFeatures, dict]:
    recent = (
        db.query(Transaction)
        .filter(Transaction.customer_id == customer.id)
        .filter(Transaction.transaction_datetime < txn.transaction_datetime)
        .order_by(Transaction.transaction_datetime.desc())
        .limit(50)
        .all()
    )

    devices_seen = {t.device_id for t in recent if t.device_id}
    is_new_device = bool(txn.device_id) and txn.device_id not in devices_seen

    ips_seen = {t.ip_address for t in recent if t.ip_address}

    # True "new location" detection: has this customer EVER transacted from this
    # location before (not just whether it differs from their single most recent
    # transaction, which would false-flag a customer alternating between two
    # known cities every time they switch).
    locations_seen = {t.location for t in recent if t.location}
    is_new_location = bool(txn.location) and txn.location not in locations_seen

    same_device_customers = set()
    same_ip_customers = set()
    if txn.device_id:
        rows = db.query(Transaction.customer_id).filter(Transaction.device_id == txn.device_id).distinct().all()
        same_device_customers = {r[0] for r in rows}
    if txn.ip_address:
        rows = db.query(Transaction.customer_id).filter(Transaction.ip_address == txn.ip_address).distinct().all()
        same_ip_customers = {r[0] for r in rows}

    now = txn.transaction_datetime
    count_5 = sum(1 for t in recent if t.transaction_datetime >= now - timedelta(minutes=5))
    count_10 = sum(1 for t in recent if t.transaction_datetime >= now - timedelta(minutes=10))
    count_30 = sum(1 for t in recent if t.transaction_datetime >= now - timedelta(minutes=30))

    amounts = [t.amount for t in recent] or [txn.amount]
    avg_amount = sum(amounts) / len(amounts)
    std_amount = (sum((a - avg_amount) ** 2 for a in amounts) / len(amounts)) ** 0.5 or 1.0
    deviation = (txn.amount - avg_amount) / (std_amount + 1e-6)

    # High-value transaction from an account that barely has any history yet.
    is_new_account_high_value = txn.account_age_days <= 7 and txn.amount > max(500.0, avg_amount * 3)

    # Unusual time-of-day compared to the customer's own historical activity.
    # This is our proxy for "unusual login/activity pattern": the platform only
    # observes transaction timestamps, not customer login sessions, so time-of-day
    # deviation is the closest available signal. Requires some history to be
    # meaningful (a handful of prior transactions minimum).
    is_unusual_hour = False
    if len(recent) >= 5:
        hours = [t.transaction_datetime.hour for t in recent]
        mean_hour = sum(hours) / len(hours)
        is_unusual_hour = abs(now.hour - mean_hour) > 6

    ctx = RuleContext(
        transaction={
            "amount": txn.amount,
            "transaction_datetime": txn.transaction_datetime,
            "location": txn.location,
            "is_new_device": is_new_device,
            "is_new_location": is_new_location,
            "account_age_days": txn.account_age_days,
            "is_unusual_hour": is_unusual_hour,
        },
        recent_customer_transactions=recent,
        same_device_customer_ids=same_device_customers,
        same_ip_customer_ids=same_ip_customers,
    )

    features = TransactionFeatures(
        amount=txn.amount,
        amount_deviation_from_avg=deviation,
        txn_count_last_5min=count_5,
        txn_count_last_10min=count_10,
        txn_count_last_30min=count_30,
        num_devices_used=len(devices_seen) + (1 if is_new_device else 0),
        num_ips_used=len(ips_seen),
        is_new_device=int(is_new_device),
        is_new_location=int(is_new_location),
        account_age_days=txn.account_age_days,
        is_new_account_high_value=int(is_new_account_high_value),
        is_unusual_hour=int(is_unusual_hour),
    )

    signals = {
        "is_new_device": is_new_device,
        "is_new_location": is_new_location,
        "is_new_account_high_value": is_new_account_high_value,
        "is_unusual_hour": is_unusual_hour,
    }

    return ctx, features, signals


def run_risk_pipeline(db: Session, customer: Customer, txn: Transaction) -> RiskCheckResponse:
    ctx, features, signals = _gather_context(db, customer, txn)

    rule_score, triggered_rules = evaluate_rules(db, ctx)
    anomaly_score = anomaly_detector.score(features)

    amounts = [t.amount for t in ctx.recent_customer_transactions] or [txn.amount]
    customer_avg_amount = sum(amounts) / len(amounts)
    customer_min_amount = min(amounts)
    customer_max_amount = max(amounts)
    suspicious_ratio = (
        customer.suspicious_transactions / customer.total_transactions
        if customer.total_transactions
        else 0.0
    )

    # Count in the same 5-minute window used by the default "Rapid transactions" rule,
    # so the explanation can state the concrete number ("3 transactions in 5 minutes")
    # rather than just the abstract rule name.
    velocity_count = sum(
        1 for t in ctx.recent_customer_transactions
        if t.transaction_datetime >= txn.transaction_datetime - timedelta(minutes=5)
    )

    result = calculate_final_risk(
        rule_score=rule_score,
        anomaly_score=anomaly_score,
        customer_risk_score=customer.risk_score,
        suspicious_ratio=suspicious_ratio,
        triggered_rules=triggered_rules,
        is_new_device=signals["is_new_device"],
        is_new_location=signals["is_new_location"],
        is_new_account_high_value=signals["is_new_account_high_value"],
        is_unusual_hour=signals["is_unusual_hour"],
        amount=txn.amount,
        customer_avg_amount=customer_avg_amount,
        customer_min_amount=customer_min_amount,
        customer_max_amount=customer_max_amount,
        velocity_count=velocity_count,
        velocity_window_minutes=5,
        allow_auto_block=False,
    )

    # Persist results onto the transaction row.
    txn.risk_score = result.risk_score
    txn.risk_level = result.risk_level
    txn.decision = result.decision
    txn.anomaly_score = result.anomaly_score
    txn.rule_score = result.rule_score
    txn.transaction_status = {
        DecisionEnum.APPROVE: TransactionStatus.APPROVED,
        DecisionEnum.REVIEW: TransactionStatus.REVIEW,
        DecisionEnum.BLOCK: TransactionStatus.BLOCKED,
    }[result.decision]

    # Persist the structured facts unconditionally (even for LOW risk, where the list is
    # usually empty) so a later read of this transaction always reflects what was actually
    # evaluated. The narrative explanation is only LLM/template-generated for non-LOW risk
    # to avoid unnecessary LLM calls on routine approvals, but callers can still generate
    # one on demand later from the stored risk_factors (see routes/transactions.py).
    explanation = None
    if result.risk_level.value != "LOW":
        explanation = generate_explanation(result.risk_score, result.risk_level.value, result.risk_factors)

    txn.risk_factors = result.risk_factors
    txn.explanation = explanation
    txn.triggered_rules = result.triggered_rules

    db.add(txn)
    db.commit()
    db.refresh(txn)

    return RiskCheckResponse(
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        decision=result.decision,
        triggered_rules=result.triggered_rules,
        anomaly_score=result.anomaly_score,
        risk_factors=result.risk_factors,
        explanation=explanation,
    )
