from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=120, description="Name of the external business/system this key is issued to")


class ApiKeyCreated(BaseModel):
    """Returned exactly once, at creation time. The raw `api_key` is never shown again."""
    id: str
    business_name: str
    api_key: str
    key_prefix: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: str
    business_name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None

    class Config:
        from_attributes = True
