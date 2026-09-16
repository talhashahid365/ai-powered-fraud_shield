from datetime import datetime

from pydantic import BaseModel

from app.models.enums import RiskLevel


class CustomerOut(BaseModel):
    id: str
    customer_id: str
    name: str
    email: str | None
    account_age_days: int
    risk_score: float
    risk_level: RiskLevel
    total_transactions: int
    suspicious_transactions: int
    devices_used: int
    locations_used: int
    previous_fraud_reports: int
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerRiskProfile(BaseModel):
    """
    Dedicated risk-profile view of a customer:

        Customer: CUST-1029
        Risk Level: Medium
        Risk Score: 64
        Total Transactions: 128
        Suspicious Transactions: 7
        Devices Used: 4
        Locations Used: 3
        Previous Fraud Reports: 1

    Backed by columns on Customer that are refreshed on every transaction
    (see services.customer_service.update_customer_after_transaction), so
    this always reflects the customer's current state rather than a
    point-in-time snapshot.
    """

    customer_id: str
    name: str
    risk_level: RiskLevel
    risk_score: float
    total_transactions: int
    suspicious_transactions: int
    devices_used: int
    locations_used: int
    previous_fraud_reports: int
    last_updated: datetime

    class Config:
        from_attributes = True
