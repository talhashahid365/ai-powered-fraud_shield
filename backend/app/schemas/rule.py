from datetime import datetime

from pydantic import BaseModel, field_validator

from app.ai.rules_engine import RULE_REGISTRY


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    rule_type: str
    configuration: dict = {}
    risk_weight: float = 10.0
    is_active: bool = True

    @field_validator("rule_type")
    @classmethod
    def rule_type_must_be_known(cls, v: str) -> str:
        if v not in RULE_REGISTRY:
            raise ValueError(
                f"Unknown rule_type '{v}'. Must be one of: {', '.join(sorted(RULE_REGISTRY))}"
            )
        return v


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    configuration: dict | None = None
    risk_weight: float | None = None
    is_active: bool | None = None


class RuleOut(BaseModel):
    id: str
    name: str
    description: str | None
    rule_type: str
    configuration: dict
    risk_weight: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
