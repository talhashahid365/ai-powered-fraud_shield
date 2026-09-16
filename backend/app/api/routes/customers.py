from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.schemas.customer import CustomerOut, CustomerRiskProfile
from app.schemas.transaction import TransactionOut
from app.services.customer_service import recompute_device_location_counts

router = APIRouter(prefix="/api/customers", tags=["Customers"])


def _get_customer_or_404(customer_id: str, db: Session) -> Customer:
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "CUSTOMER_NOT_FOUND", "message": "Customer was not found"}})
    return customer


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    customers = db.query(Customer).order_by(Customer.risk_score.desc()).limit(200).all()
    return [CustomerOut.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "CUSTOMER_NOT_FOUND", "message": "Customer was not found"}})
    return CustomerOut.model_validate(customer)


@router.get("/{customer_id}/risk-profile", response_model=CustomerRiskProfile)
def get_customer_risk_profile(customer_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    The customer's risk profile: risk level/score, transaction and
    suspicious-transaction counts, distinct devices/locations used, and
    prior confirmed-fraud reports. Continuously kept current — every
    transaction updates risk_score/risk_level (EMA) and recomputes
    devices_used/locations_used from the transaction history (see
    services.customer_service.update_customer_after_transaction), and
    previous_fraud_reports increments the moment an alert is confirmed as
    fraud (see services.alert_service).
    """
    customer = _get_customer_or_404(customer_id, db)
    return CustomerRiskProfile(
        customer_id=customer.customer_id,
        name=customer.name,
        risk_level=customer.risk_level,
        risk_score=customer.risk_score,
        total_transactions=customer.total_transactions,
        suspicious_transactions=customer.suspicious_transactions,
        devices_used=customer.devices_used,
        locations_used=customer.locations_used,
        previous_fraud_reports=customer.previous_fraud_reports,
        last_updated=customer.updated_at,
    )


@router.post("/{customer_id}/risk-profile/recalculate", response_model=CustomerRiskProfile)
def recalculate_customer_risk_profile(customer_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Force a recompute of devices_used/locations_used from the transaction
    table. The profile already refreshes automatically on every new
    transaction; this exists for backfilled/imported history or manual data
    fixes where you want the count corrected on demand without waiting for
    the customer's next transaction.
    """
    customer = _get_customer_or_404(customer_id, db)
    recompute_device_location_counts(db, customer)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerRiskProfile(
        customer_id=customer.customer_id,
        name=customer.name,
        risk_level=customer.risk_level,
        risk_score=customer.risk_score,
        total_transactions=customer.total_transactions,
        suspicious_transactions=customer.suspicious_transactions,
        devices_used=customer.devices_used,
        locations_used=customer.locations_used,
        previous_fraud_reports=customer.previous_fraud_reports,
        last_updated=customer.updated_at,
    )


@router.get("/{customer_id}/transactions")
def get_customer_transactions(customer_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "CUSTOMER_NOT_FOUND", "message": "Customer was not found"}})
    txns = (
        db.query(Transaction)
        .filter(Transaction.customer_id == customer.id)
        .order_by(Transaction.transaction_datetime.desc())
        .limit(200)
        .all()
    )
    return {
        "customer": CustomerOut.model_validate(customer),
        "transactions": [
            {
                "id": t.id, "transaction_id": t.transaction_id, "amount": t.amount,
                "risk_score": t.risk_score, "risk_level": t.risk_level,
                "device_id": t.device_id, "ip_address": t.ip_address, "location": t.location,
                "transaction_datetime": t.transaction_datetime,
            }
            for t in txns
        ],
    }


@router.get("/{customer_id}/network")
def get_customer_network(customer_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Quick 1-hop view for the customer profile page: this customer's own
    devices/IPs, plus any other customers who were seen on those *same*
    device(s) or IP(s). For the full multi-hop fraud ring (which can chain
    through customers who don't directly share anything with this one - see
    services.network_service for why that matters) use
    GET /api/fraud-network/graph/{customer_id} instead.
    """
    customer = _get_customer_or_404(customer_id, db)

    txns = db.query(Transaction).filter(Transaction.customer_id == customer.id).all()
    device_ids = {t.device_id for t in txns if t.device_id}
    ip_addresses = {t.ip_address for t in txns if t.ip_address}

    related_customer_ids: set[str] = set()
    if device_ids:
        rows = db.query(Transaction.customer_id).filter(Transaction.device_id.in_(device_ids)).distinct().all()
        related_customer_ids.update(r[0] for r in rows)
    if ip_addresses:
        rows = db.query(Transaction.customer_id).filter(Transaction.ip_address.in_(ip_addresses)).distinct().all()
        related_customer_ids.update(r[0] for r in rows)
    related_customer_ids.discard(customer.id)

    related_customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(related_customer_ids)).all()}

    nodes = [{"id": customer.customer_id, "type": "customer", "label": customer.customer_id, "risk_level": customer.risk_level.value}]
    edges = []
    for d in device_ids:
        nodes.append({"id": f"device:{d}", "type": "device", "label": d})
        edges.append({"source": customer.customer_id, "target": f"device:{d}"})
    for ip in ip_addresses:
        nodes.append({"id": f"ip:{ip}", "type": "ip", "label": ip})
        edges.append({"source": customer.customer_id, "target": f"ip:{ip}"})

    # Only wire a related customer to the specific device(s)/IP(s) THEY
    # actually used - not every device/IP the origin customer has ever had.
    # Without this filter, a customer who shares just one old IP with the
    # origin would incorrectly appear connected to every device the origin
    # customer has ever used.
    related_txns = (
        db.query(Transaction).filter(Transaction.customer_id.in_(related_customer_ids)).all()
        if related_customer_ids
        else []
    )
    added_related_customer_ids: set[str] = set()
    for t in related_txns:
        rc = related_customers.get(t.customer_id)
        if not rc:
            continue
        matches_device = t.device_id and t.device_id in device_ids
        matches_ip = t.ip_address and t.ip_address in ip_addresses
        if not (matches_device or matches_ip):
            continue

        if rc.customer_id not in added_related_customer_ids:
            nodes.append({"id": rc.customer_id, "type": "customer", "label": rc.customer_id, "risk_level": rc.risk_level.value})
            added_related_customer_ids.add(rc.customer_id)
        if matches_device:
            edges.append({"source": f"device:{t.device_id}", "target": rc.customer_id})
        if matches_ip:
            edges.append({"source": f"ip:{t.ip_address}", "target": rc.customer_id})

    return {"nodes": nodes, "edges": edges}
