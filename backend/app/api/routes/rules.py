from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.database import get_db
from app.models.enums import UserRole
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleOut, RuleUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/rules", tags=["Rules Engine (Admin)"])


@router.get("", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    return db.query(Rule).order_by(Rule.created_at.desc()).all()


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    rule = Rule(**payload.model_dump(), created_by=current_user.id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    log_action(db, user_id=current_user.id, action="RULE_CREATED", details=f"'{rule.name}' ({rule.rule_type})")
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: str, payload: RuleUpdate, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "RULE_NOT_FOUND", "message": "Rule was not found"}})
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(rule, field, value)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    log_action(db, user_id=current_user.id, action="RULE_UPDATED", details=f"'{rule.name}': {changes}")
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.ADMIN))):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "RULE_NOT_FOUND", "message": "Rule was not found"}})
    rule_name = rule.name
    db.delete(rule)
    db.commit()
    log_action(db, user_id=current_user.id, action="RULE_DELETED", details=f"'{rule_name}'")
