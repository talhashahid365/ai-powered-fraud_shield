"""
Shared FastAPI dependencies: current user resolution + role-based
authorization. Permissions are ALWAYS enforced here on the backend,
never only in the frontend.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.api_key_service import authenticate_api_key

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Dashboard-user auth stays mandatory (auto_error=True) for get_current_user, so every
# existing internal route's behavior/error shape is unchanged. The External Business API
# additionally accepts an API key, so its dependencies below use non-erroring variants of
# both schemes and decide for themselves which credential (if either) was supplied.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"success": False, "error": {"code": "INVALID_TOKEN", "message": "Could not validate credentials"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise credentials_exception

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def require_roles(*roles: UserRole):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {"code": "FORBIDDEN", "message": "You do not have permission to perform this action"},
                },
            )
        return current_user
    return checker


class ApiKeyPrincipal:
    """
    Stands in for `User` when a request is authenticated with an external-business
    API key rather than a dashboard login. Only used on the External Business API
    routes (see app.api.routes.transactions/risk/alerts). Exposes the same `.id` /
    `.role` shape the rest of the codebase (audit logging, role checks) expects.
    """

    def __init__(self, api_key_id: str, business_name: str):
        self.id = f"apikey:{api_key_id}"
        self.role = UserRole.BUSINESS_MANAGER
        self.name = f"External API ({business_name})"
        self.is_active = True
        self.is_api_key = True


def get_current_principal(
    api_key: str | None = Depends(api_key_scheme),
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User | ApiKeyPrincipal:
    """
    Authenticate an External Business API request via EITHER:
    - `X-API-Key: <key>` header (external business system), or
    - `Authorization: Bearer <token>` (dashboard user, for testing/manual use from /docs).

    If both are supplied, the API key wins. Used only by the 5 External Business API
    endpoints; every other route keeps using `get_current_user` unchanged.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"success": False, "error": {"code": "UNAUTHENTICATED", "message": "Provide a valid X-API-Key header or Bearer token"}},
    )

    if api_key:
        key_row = authenticate_api_key(db, api_key)
        if not key_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "error": {"code": "INVALID_API_KEY", "message": "API key is invalid, revoked, or unknown"}},
            )
        return ApiKeyPrincipal(api_key_id=key_row.id, business_name=key_row.business_name)

    if token:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise unauthorized
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user or not user.is_active:
            raise unauthorized
        return user

    raise unauthorized


def require_roles_or_api_key(*roles: UserRole):
    """
    Like `require_roles`, but for the External Business API: any valid API key is
    always authorized (API keys are only accepted on these 5 whitelisted routes to
    begin with), while a dashboard user must still hold one of `roles`.
    """
    def checker(principal: User | ApiKeyPrincipal = Depends(get_current_principal)) -> User | ApiKeyPrincipal:
        if getattr(principal, "is_api_key", False):
            return principal
        if principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": {"code": "FORBIDDEN", "message": "You do not have permission to perform this action"},
                },
            )
        return principal
    return checker
