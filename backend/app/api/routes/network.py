"""
Fraud Network Detection API.

Two views for analysts:
  - GET /api/fraud-network/rings          every group of 2+ customers
    connected through a shared device or IP (directly or transitively) -
    lets an analyst discover suspicious clusters without already suspecting
    a specific customer.
  - GET /api/fraud-network/graph/{id}     the full Customer -> Device -> IP
    -> Transaction -> Location relationship graph for the ring the given
    customer belongs to.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.customer import Customer
from app.services.network_service import build_customer_network, detect_fraud_rings

router = APIRouter(prefix="/api/fraud-network", tags=["Fraud Network"])


@router.get("/rings")
def list_fraud_rings(
    min_size: int = Query(2, ge=2, le=50, description="Minimum number of customers for a group to count as a ring"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Every detected fraud ring, ranked by risk level, then size, then average
    member risk score. A ring is any group of 2+ customers connected -
    directly or through a chain of shared devices/IPs - to at least one
    other member of the group.
    """
    return {"rings": detect_fraud_rings(db, min_ring_size=min_size, limit=limit)}


@router.get("/graph/{customer_id}")
def get_fraud_network_graph(
    customer_id: str,
    depth: int = Query(3, ge=1, le=4, description="How many hops to expand outward while discovering the ring"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    The full Customer -> Device -> IP -> Transaction -> Location graph for
    the fraud ring `customer_id` belongs to. Works for any customer, not
    just ones already flagged as part of a ring - an isolated customer
    simply returns a graph containing only themselves.
    """
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "CUSTOMER_NOT_FOUND", "message": "Customer was not found"}})
    return build_customer_network(db, customer, depth=depth)
