from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserOut
from app.services.audit_service import log_action
from app.services.auth_service import authenticate_user, create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    if get_user_by_email(db, payload.email):
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": {"code": "EMAIL_TAKEN", "message": "Email already registered"}},
        )
    user = create_user(db, payload)
    log_action(
        db, user_id=user.id, action="USER_REGISTERED",
        details=f"New {user.role.value} account created for {user.email}",
        ip_address=request.client.host if request.client else None,
    )
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    client_ip = request.client.host if request.client else None
    if not user:
        # Log failed attempts without leaking whether the email exists.
        log_action(db, user_id=None, action="LOGIN_FAILED", details=f"email={payload.email}", ip_address=client_ip)
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}},
        )
    token = create_access_token(subject=user.id, role=user.role.value)
    log_action(db, user_id=user.id, action="LOGIN_SUCCESS", details=f"role={user.role.value}", ip_address=client_ip)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user
