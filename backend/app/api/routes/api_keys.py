"""
Admin-only management of API keys used by the External Business API
(see docs/api/contracts.md -> "External Business API").
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.database import get_db
from app.models.api_key import ApiKey
from app.models.enums import UserRole
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services.api_key_service import create_api_key, list_api_keys, revoke_api_key
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/api-keys", tags=["External Business API Keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
def create_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """
    Issue a new API key for an external business (e-commerce/payment system) to use
    against the External Business API. The full key is only ever returned here -
    store it securely, it cannot be retrieved again.
    """
    key, raw_key = create_api_key(db, payload.business_name, current_user.id)
    log_action(db, user_id=current_user.id, action="API_KEY_CREATED", details=f"business={payload.business_name} key_id={key.id}")
    return ApiKeyCreated(
        id=key.id,
        business_name=key.business_name,
        api_key=raw_key,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_keys(db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    return list_api_keys(db)


@router.delete("/{key_id}", response_model=ApiKeyOut)
def revoke_key(key_id: str, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "API_KEY_NOT_FOUND", "message": "API key was not found"}})
    key = revoke_api_key(db, key)
    log_action(db, user_id=current_user.id, action="API_KEY_REVOKED", details=f"key_id={key.id} business={key.business_name}")
    return key
