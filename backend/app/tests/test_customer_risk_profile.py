"""
Coverage for the Customer Risk Profile feature:

    Customer: CUST-1029
    Risk Level: Medium
    Risk Score: 64
    Total Transactions: 128
    Suspicious Transactions: 7
    Devices Used: 4
    Locations Used: 3
    Previous Fraud Reports: 1

Verifies the profile is exposed via GET /api/customers/{id}/risk-profile,
that devices_used/locations_used count DISTINCT devices/locations (not raw
transaction counts), and that the profile keeps itself current as new
transactions arrive.
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _make_user(db_session, email, role):
    user = User(name="Test User", email=email, password_hash=hash_password("Secret123!"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, email, password="Secret123!"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth_headers(client, db_session, email, role):
    _make_user(db_session, email, role)
    token = _login(client, email)
    return {"Authorization": f"Bearer {token}"}


def _create_txn(client, headers, **overrides):
    payload = {
        "transaction_id": overrides.pop("transaction_id"),
        "customer_id": "CUST-RISKPROFILE-1",
        "amount": 100.0,
        "currency": "USD",
    }
    payload.update(overrides)
    resp = client.post("/api/transactions", json=payload, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    return resp


def test_risk_profile_reflects_distinct_devices_and_locations(client, db_session):
    headers = _auth_headers(client, db_session, "admin@example.com", UserRole.ADMIN)

    # Two transactions reuse the same device/location; a third and fourth
    # introduce a new device and a new location respectively. Distinct
    # counts should be 3 devices, 3 locations - not 4 (raw transaction count).
    _create_txn(client, headers, transaction_id="TXN-RP-1", device_id="dev-A", location="Lahore, PK")
    _create_txn(client, headers, transaction_id="TXN-RP-2", device_id="dev-A", location="Lahore, PK")
    _create_txn(client, headers, transaction_id="TXN-RP-3", device_id="dev-B", location="Lahore, PK")
    _create_txn(client, headers, transaction_id="TXN-RP-4", device_id="dev-C", location="Karachi, PK")

    resp = client.get("/api/customers/CUST-RISKPROFILE-1/risk-profile", headers=headers)
    assert resp.status_code == 200, resp.text
    profile = resp.json()

    assert profile["customer_id"] == "CUST-RISKPROFILE-1"
    assert profile["total_transactions"] == 4
    assert profile["devices_used"] == 3
    assert profile["locations_used"] == 2
    assert "risk_level" in profile and "risk_score" in profile
    assert profile["suspicious_transactions"] >= 0
    assert profile["previous_fraud_reports"] == 0


def test_risk_profile_updates_continuously_as_transactions_arrive(client, db_session):
    headers = _auth_headers(client, db_session, "admin2@example.com", UserRole.ADMIN)

    _create_txn(client, headers, transaction_id="TXN-RP-5", customer_id="CUST-RISKPROFILE-2",
                device_id="dev-X", location="Islamabad, PK")
    first = client.get("/api/customers/CUST-RISKPROFILE-2/risk-profile", headers=headers).json()
    assert first["devices_used"] == 1
    assert first["locations_used"] == 1
    assert first["total_transactions"] == 1

    _create_txn(client, headers, transaction_id="TXN-RP-6", customer_id="CUST-RISKPROFILE-2",
                device_id="dev-Y", location="Multan, PK")
    second = client.get("/api/customers/CUST-RISKPROFILE-2/risk-profile", headers=headers).json()
    assert second["devices_used"] == 2
    assert second["locations_used"] == 2
    assert second["total_transactions"] == 2


def test_risk_profile_404_for_unknown_customer(client, db_session):
    headers = _auth_headers(client, db_session, "admin3@example.com", UserRole.ADMIN)
    resp = client.get("/api/customers/CUST-DOES-NOT-EXIST/risk-profile", headers=headers)
    assert resp.status_code == 404


def test_risk_profile_recalculate_endpoint_fixes_counts(client, db_session):
    headers = _auth_headers(client, db_session, "admin4@example.com", UserRole.ADMIN)
    _create_txn(client, headers, transaction_id="TXN-RP-7", customer_id="CUST-RISKPROFILE-3",
                device_id="dev-Z", location="Peshawar, PK")

    resp = client.post("/api/customers/CUST-RISKPROFILE-3/risk-profile/recalculate", headers=headers)
    assert resp.status_code == 200, resp.text
    profile = resp.json()
    assert profile["devices_used"] == 1
    assert profile["locations_used"] == 1
