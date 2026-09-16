"""
Password hashing, JWT, and API key helpers.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

API_KEY_PREFIX = "fsk_live_"
# How many characters of the raw key (including the "fsk_live_" prefix) are stored in
# the clear on the ApiKey row for fast lookup. Must be shorter than the full key so the
# stored prefix alone is never enough to authenticate.
API_KEY_LOOKUP_PREFIX_LEN = len(API_KEY_PREFIX) + 4


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode: dict[str, Any] = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new external-business API key.

    Returns (raw_key, key_prefix, key_hash):
    - raw_key: the full secret, e.g. "fsk_live_Xh3s...". Shown to the caller ONCE.
    - key_prefix: short, non-secret lookup prefix stored in the clear.
    - key_hash: bcrypt hash of the full raw_key, stored instead of the raw key.
    """
    raw_key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key_prefix = raw_key[:API_KEY_LOOKUP_PREFIX_LEN]
    key_hash = pwd_context.hash(raw_key)
    return raw_key, key_prefix, key_hash


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    return pwd_context.verify(raw_key, key_hash)
