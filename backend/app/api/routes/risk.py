"""
External-facing risk-check API, per section 23 of the spec.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_principal, require_roles_or_api_key
from app.db.database import get_db
from app.models.enums import UserRole
from app.models.transaction import Transaction
from app.schemas.transaction import RiskCheckResponse, TransactionCreate
from app.services import transaction_service

router = APIRouter(prefix="/api", tags=["External Risk API"])


@router.post("/risk-check", response_model=RiskCheckResponse)
def risk_check(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    # External business systems authenticate with X-API-Key here; dashboard
    # ADMIN/BUSINESS_MANAGER users can also call this directly with a Bearer token.
    current_user=Depends(require_roles_or_api_key(UserRole.ADMIN, UserRole.BUSINESS_MANAGER)),
):
    """Create a transaction and immediately return its risk decision (used by external systems)."""
    try:
        txn = transaction_service.create_transaction(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"success": False, "error": {"code": "DUPLICATE_TRANSACTION", "message": str(exc)}})
    # risk_factors/explanation are computed by the risk pipeline inside create_transaction
    # and persisted on the transaction - read them back rather than hardcoding empty lists,
    # so external callers actually receive the "why" behind the score.
    return RiskCheckResponse(
        risk_score=txn.risk_score,
        risk_level=txn.risk_level,
        decision=txn.decision,
        triggered_rules=txn.triggered_rules or [],
        anomaly_score=txn.anomaly_score,
        risk_factors=txn.risk_factors or [],
        explanation=txn.explanation,
    )


@router.get("/risk/{transaction_id}", response_model=RiskCheckResponse)
def get_risk(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_principal),
):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "TRANSACTION_NOT_FOUND", "message": "Transaction was not found"}})
    return RiskCheckResponse(
        risk_score=txn.risk_score, risk_level=txn.risk_level, decision=txn.decision,
        triggered_rules=txn.triggered_rules or [], anomaly_score=txn.anomaly_score,
        risk_factors=txn.risk_factors or [], explanation=txn.explanation,
    )
