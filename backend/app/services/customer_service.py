from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.enums import RiskLevel
from app.models.transaction import Transaction


def get_or_create_customer(db: Session, business_customer_id: str, name: str | None = None) -> Customer:
    customer = db.query(Customer).filter(Customer.customer_id == business_customer_id).first()
    if customer:
        return customer
    customer = Customer(
        customer_id=business_customer_id,
        name=name or business_customer_id,
        risk_score=0.0,
        risk_level=RiskLevel.LOW,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def recompute_device_location_counts(db: Session, customer: Customer) -> None:
    """
    Recompute the customer's distinct-device and distinct-location counts
    straight from their transaction history. Doing this as a fresh COUNT
    DISTINCT (instead of an incremental "+1 if new" counter) means the
    numbers on the risk profile are always exactly right even if history is
    backfilled, imported out of order, or a transaction is re-processed —
    there's nothing to drift.
    """
    devices_used = (
        db.query(func.count(func.distinct(Transaction.device_id)))
        .filter(Transaction.customer_id == customer.id, Transaction.device_id.isnot(None))
        .scalar()
    ) or 0
    locations_used = (
        db.query(func.count(func.distinct(Transaction.location)))
        .filter(Transaction.customer_id == customer.id, Transaction.location.isnot(None))
        .scalar()
    ) or 0
    customer.devices_used = devices_used
    customer.locations_used = locations_used


def update_customer_after_transaction(db: Session, customer: Customer, txn_risk_score: float, is_suspicious: bool) -> None:
    customer.total_transactions += 1
    if is_suspicious:
        customer.suspicious_transactions += 1

    # Exponential moving average keeps the long-term risk score stable
    # while still reacting to new suspicious activity.
    alpha = 0.3
    customer.risk_score = float((1 - alpha) * customer.risk_score + alpha * txn_risk_score)

    if customer.risk_score <= 30:
        customer.risk_level = RiskLevel.LOW
    elif customer.risk_score <= 70:
        customer.risk_level = RiskLevel.MEDIUM
    else:
        customer.risk_level = RiskLevel.HIGH

    # Keep the risk profile's device/location footprint current on every
    # single transaction, so "Devices Used" / "Locations Used" are always
    # up to date rather than only recalculated on demand.
    recompute_device_location_counts(db, customer)

    db.add(customer)
    db.commit()
    db.refresh(customer)
