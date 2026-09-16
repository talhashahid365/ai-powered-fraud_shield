"""
Issuance, lookup, and authentication of external-business API keys
(see app.models.api_key.ApiKey for the "why").
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import API_KEY_LOOKUP_PREFIX_LEN, generate_api_key, verify_api_key
from app.models.api_key import ApiKey


def create_api_key(db: Session, business_name: str, created_by: str | None) -> tuple[ApiKey, str]:
    """Create a new key. Returns (row, raw_key) - raw_key is only ever available here."""
    raw_key, key_prefix, key_hash = generate_api_key()
    key = ApiKey(
        business_name=business_name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        created_by=created_by,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key, raw_key


def list_api_keys(db: Session) -> list[ApiKey]:
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


def revoke_api_key(db: Session, key: ApiKey) -> ApiKey:
    key.is_active = False
    key.revoked_at = datetime.utcnow()
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def authenticate_api_key(db: Session, raw_key: str) -> ApiKey | None:
    """
    Validate a raw API key presented by an external caller (X-API-Key header).
    Returns the matching, active ApiKey row, or None if invalid/inactive.
    """
    if not raw_key or len(raw_key) < API_KEY_LOOKUP_PREFIX_LEN:
        return None

    prefix = raw_key[:API_KEY_LOOKUP_PREFIX_LEN]
    candidate = db.query(ApiKey).filter(ApiKey.key_prefix == prefix, ApiKey.is_active == True).first()  # noqa: E712
    if not candidate:
        return None
    if not verify_api_key(raw_key, candidate.key_hash):
        return None

    candidate.last_used_at = datetime.utcnow()
    db.add(candidate)
    db.commit()
    return candidate
