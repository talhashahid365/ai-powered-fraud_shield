from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_principal, get_current_user, require_roles, require_roles_or_api_key
from app.db.database import get_db
from app.models.customer import Customer
from app.models.enums import RiskLevel, UserRole
from app.models.transaction import Transaction
from app.schemas.transaction import (
    CSVImportSummary,
    RiskCheckResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionOut,
)
from app.services import transaction_service

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


def _to_out(db: Session, txn: Transaction) -> TransactionOut:
    customer = txn.customer
    previous_count = (
        db.query(Transaction)
        .filter(
            Transaction.customer_id == txn.customer_id,
            Transaction.transaction_datetime < txn.transaction_datetime,
        )
        .count()
    )
    return TransactionOut(
        id=txn.id,
        transaction_id=txn.transaction_id,
        customer_id=customer.customer_id if customer else "",
        amount=txn.amount,
        currency=txn.currency,
        transaction_datetime=txn.transaction_datetime,
        payment_method=txn.payment_method,
        ip_address=txn.ip_address,
        device_id=txn.device_id,
        location=txn.location,
        account_age_days=txn.account_age_days,
        previous_transaction_count=previous_count,
        transaction_status=txn.transaction_status,
        risk_score=txn.risk_score,
        risk_level=txn.risk_level,
        decision=txn.decision,
        anomaly_score=txn.anomaly_score,
        rule_score=txn.rule_score,
        risk_factors=txn.risk_factors or [],
        explanation=txn.explanation,
        created_at=txn.created_at,
    )


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    # Part of the External Business API: an e-commerce/payment system authenticates
    # with an `X-API-Key` header (see app/api/routes/api_keys.py to issue one), or a
    # dashboard ADMIN/BUSINESS_MANAGER can call this directly with their Bearer token.
    current_user=Depends(require_roles_or_api_key(UserRole.ADMIN, UserRole.BUSINESS_MANAGER)),
):
    try:
        txn = transaction_service.create_transaction(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"success": False, "error": {"code": "DUPLICATE_TRANSACTION", "message": str(exc)}})
    return _to_out(db, txn)


@router.post("/import-csv", response_model=CSVImportSummary)
def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.BUSINESS_MANAGER)),
):
    content = file.file.read()
    return transaction_service.import_csv(db, content)


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = None,
    risk_level: RiskLevel | None = None,
    payment_method: str | None = None,
    customer_id: str | None = None,
    location: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Transaction).join(Customer)

    if search:
        query = query.filter(or_(Transaction.transaction_id.ilike(f"%{search}%"), Customer.customer_id.ilike(f"%{search}%")))
    if risk_level:
        query = query.filter(Transaction.risk_level == risk_level)
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)
    if customer_id:
        query = query.filter(Customer.customer_id == customer_id)
    if location:
        query = query.filter(Transaction.location == location)

    total = query.count()
    items = (
        query.order_by(Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TransactionListResponse(data=[_to_out(db, t) for t in items], page=page, page_size=page_size, total=total)


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_principal)):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "TRANSACTION_NOT_FOUND", "message": "Transaction was not found"}})
    return _to_out(db, txn)


@router.get("/{transaction_id}/risk", response_model=RiskCheckResponse)
def get_transaction_risk(transaction_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "TRANSACTION_NOT_FOUND", "message": "Transaction was not found"}})

    # Use the risk_factors computed and stored at decision time (previously this always
    # passed an empty list here, so every explanation silently came back as "No specific
    # risk factors were triggered" regardless of the transaction's actual risk level).
    from app.ai.llm_service import generate_explanation
    risk_factors = txn.risk_factors or []
    explanation = txn.explanation or generate_explanation(txn.risk_score, txn.risk_level.value, risk_factors)
    return RiskCheckResponse(
        risk_score=txn.risk_score, risk_level=txn.risk_level, decision=txn.decision,
        triggered_rules=txn.triggered_rules or [], anomaly_score=txn.anomaly_score, risk_factors=risk_factors, explanation=explanation,
    )
