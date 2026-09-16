import re
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, field_validator

from app.models.enums import Decision, RiskLevel, TransactionStatus

# Real-time detection step 1 ("Data Validation") lives here. Previously this schema only
# enforced types (any string, any float would pass), so malformed or abusive input could
# reach the rule engine / ML pipeline / DB unchecked -- e.g. a negative or zero amount
# would silently poison a customer's average-amount stats, an empty transaction_id would
# collide with itself, and unbounded strings could bloat the DB. These validators reject
# bad input immediately with a clear 422, before any downstream analysis runs.
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
CURRENCY_PATTERN = re.compile(r"^[A-Za-z]{3}$")
# Loose but real IPv4/IPv6 shape check -- catches obvious garbage ("not-an-ip", HTML/script
# fragments) without pulling in a full IP-address library.
IP_PATTERN = re.compile(r"^[0-9a-fA-F:.]{2,45}$")


class TransactionCreate(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=128)
    customer_id: str = Field(..., min_length=1, max_length=128)  # business-facing customer_id, e.g. CUST-1029
    amount: float = Field(..., gt=0, le=100_000_000)
    currency: str = "USD"
    transaction_datetime: datetime | None = None
    payment_method: str | None = Field(None, max_length=64)
    ip_address: str | None = Field(None, max_length=45)
    device_id: str | None = Field(None, max_length=128)
    location: str | None = Field(None, max_length=128)
    # Optional: lets a business pass the customer's real account age (e.g. when
    # backfilling history from their own system). If omitted, it is computed
    # automatically from how long the customer has existed on this platform.
    account_age_days: int | None = Field(None, ge=0, le=100_000)

    @field_validator("transaction_id", "customer_id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        if not ID_PATTERN.match(v):
            raise ValueError("may only contain letters, numbers, '_', '-', and '.'")
        return v

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        v = (v or "USD").strip().upper()
        if not CURRENCY_PATTERN.match(v):
            raise ValueError("must be a 3-letter currency code, e.g. USD")
        return v

    @field_validator("ip_address")
    @classmethod
    def _validate_ip(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not IP_PATTERN.match(v):
            raise ValueError("does not look like a valid IP address")
        return v

    @field_validator("payment_method", "device_id", "location")
    @classmethod
    def _strip_optional(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("transaction_datetime")
    @classmethod
    def _validate_datetime(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        # Reject clock-skew-implausible future timestamps (e.g. a caller-side bug sending
        # a date decades out) rather than letting them silently distort velocity/time-of-day
        # signals, which key off "now" relative to this field.
        compare_now = datetime.now(timezone.utc) if v.tzinfo else datetime.utcnow()
        if v > compare_now + timedelta(days=1):
            raise ValueError("transaction_datetime cannot be in the future")
        return v


class TransactionOut(BaseModel):
    id: str
    transaction_id: str
    customer_id: str
    amount: float
    currency: str
    transaction_datetime: datetime
    payment_method: str | None
    ip_address: str | None
    device_id: str | None
    location: str | None
    account_age_days: int
    previous_transaction_count: int
    transaction_status: TransactionStatus
    risk_score: float
    risk_level: RiskLevel
    decision: Decision
    anomaly_score: float
    rule_score: float
    risk_factors: list[str] = []
    explanation: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    data: list[TransactionOut]
    page: int
    page_size: int
    total: int


class RiskCheckResponse(BaseModel):
    risk_score: float
    risk_level: RiskLevel
    decision: Decision
    triggered_rules: list[str]
    anomaly_score: float
    risk_factors: list[str]
    explanation: str | None = None


class CSVImportSummary(BaseModel):
    total_rows: int
    successful_rows: int
    failed_rows: int
    duplicate_rows: int
    errors: list[str]
