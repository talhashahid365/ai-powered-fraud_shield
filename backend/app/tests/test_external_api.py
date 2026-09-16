"""
Coverage for the External Business API authentication (section 17 of the spec):
external e-commerce/payment systems authenticate with an `X-API-Key` header
instead of a dashboard user login, on exactly 5 routes:

    POST /api/transactions
    POST /api/risk-check
    GET  /api/transactions/{id}
    GET  /api/risk/{transaction_id}
    POST /api/alerts/{id}/review

Everything else in the API (list/CSV-import/customers/rules/dashboard/etc.)
must keep requiring a dashboard JWT exactly as before - these tests also
guard that boundary.
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


def _issue_api_key(client, admin_headers, business_name="Acme E-Commerce"):
    resp = client.post("/api/api-keys", json={"business_name": business_name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["api_key"].startswith("fsk_live_")
    return body["api_key"], body["id"]


# ---------------------------------------------------------------------------
# Key issuance / management (admin-only)
# ---------------------------------------------------------------------------

def test_admin_can_create_and_list_api_keys(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-keys1@example.com", UserRole.ADMIN)
    raw_key, key_id = _issue_api_key(client, admin_headers, "Acme Payments")

    resp = client.get("/api/api-keys", headers=admin_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert any(k["id"] == key_id for k in rows)
    # The full secret must never be echoed back on list - only the create response has it.
    assert all("api_key" not in k for k in rows)
    assert all(raw_key not in str(k) for k in rows)


def test_non_admin_cannot_create_api_key(client, db_session):
    biz_headers = _auth_headers(client, db_session, "bm-keys1@example.com", UserRole.BUSINESS_MANAGER)
    resp = client.post("/api/api-keys", json={"business_name": "Sneaky Co"}, headers=biz_headers)
    assert resp.status_code == 403

    analyst_headers = _auth_headers(client, db_session, "analyst-keys1@example.com", UserRole.ANALYST)
    resp = client.post("/api/api-keys", json={"business_name": "Sneaky Co"}, headers=analyst_headers)
    assert resp.status_code == 403


def test_creating_api_key_requires_authentication(client, db_session):
    resp = client.post("/api/api-keys", json={"business_name": "No Auth Co"})
    assert resp.status_code == 401


def test_admin_can_revoke_api_key_and_it_stops_working(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-keys2@example.com", UserRole.ADMIN)
    raw_key, key_id = _issue_api_key(client, admin_headers, "Revoke Me Inc")

    # Works before revocation.
    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-REVOKE-PRE", "customer_id": "CUST-REVOKE-1", "amount": 50},
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200

    revoke_resp = client.delete(f"/api/api-keys/{key_id}", headers=admin_headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_active"] is False

    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-REVOKE-POST", "customer_id": "CUST-REVOKE-1", "amount": 50},
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_API_KEY"


# ---------------------------------------------------------------------------
# External business calls using the API key (the actual feature)
# ---------------------------------------------------------------------------

def test_external_system_can_create_transaction_with_api_key(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-ext1@example.com", UserRole.ADMIN)
    raw_key, _ = _issue_api_key(client, admin_headers, "Acme E-Commerce")

    resp = client.post(
        "/api/transactions",
        json={
            "transaction_id": "TXN-API-1",
            "customer_id": "CUST-API-1",
            "amount": 250.0,
            "currency": "USD",
            "payment_method": "CARD",
            "ip_address": "203.0.113.9",
            "device_id": "device-ext-1",
            "location": "Lahore, PK",
        },
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["transaction_id"] == "TXN-API-1"
    # Exact response shape the external system integrates against.
    assert isinstance(body["risk_score"], (int, float))
    assert body["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert body["decision"] in ("APPROVE", "REVIEW", "BLOCK")


def test_external_system_can_use_risk_check_with_api_key(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-ext2@example.com", UserRole.ADMIN)
    raw_key, _ = _issue_api_key(client, admin_headers, "Acme Payments")

    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-API-2", "customer_id": "CUST-API-2", "amount": 500},
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(["risk_score", "risk_level", "decision"]).issubset(body.keys())


def test_external_system_can_fetch_transaction_and_risk_by_id_with_api_key(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-ext3@example.com", UserRole.ADMIN)
    raw_key, _ = _issue_api_key(client, admin_headers, "Acme E-Commerce")
    headers = {"X-API-Key": raw_key}

    create_resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-API-3", "customer_id": "CUST-API-3", "amount": 75},
        headers=headers,
    )
    txn_internal_id = create_resp.json()["id"]

    resp = client.get(f"/api/transactions/{txn_internal_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == "TXN-API-3"

    resp = client.get("/api/risk/TXN-API-3", headers=headers)
    assert resp.status_code == 200
    assert "risk_score" in resp.json()


def test_invalid_api_key_rejected(client, db_session):
    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-BAD-KEY", "customer_id": "CUST-BAD-1", "amount": 10},
        headers={"X-API-Key": "fsk_live_totally-made-up-key"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_API_KEY"


def test_missing_credentials_rejected_on_external_endpoints(client, db_session):
    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-NOCREDS", "customer_id": "CUST-NOCREDS-1", "amount": 10},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"

    resp = client.get("/api/risk/TXN-NOCREDS")
    assert resp.status_code == 401


def test_dashboard_jwt_still_works_on_external_endpoints(client, db_session):
    """The External Business API accepts EITHER credential type - a dashboard
    admin's Bearer token must still work exactly as before the API-key change."""
    headers = _auth_headers(client, db_session, "admin-ext4@example.com", UserRole.ADMIN)
    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-JWT-STILL-WORKS", "customer_id": "CUST-JWT-1", "amount": 10},
        headers=headers,
    )
    assert resp.status_code == 200


def test_api_key_cannot_access_dashboard_only_endpoints(client, db_session):
    """API keys are only valid on the 5 whitelisted external routes. Everything
    else (e.g. listing transactions, rules, customers) still requires a real
    dashboard login - an API key alone must not unlock the rest of the app."""
    admin_headers = _auth_headers(client, db_session, "admin-ext5@example.com", UserRole.ADMIN)
    raw_key, _ = _issue_api_key(client, admin_headers, "Scope Test Co")

    resp = client.get("/api/transactions", headers={"X-API-Key": raw_key})
    assert resp.status_code == 401  # this route only knows the OAuth2 Bearer scheme

    resp = client.get("/api/rules", headers={"X-API-Key": raw_key})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Alert review via API key (5th endpoint of the External Business API)
# ---------------------------------------------------------------------------

def _create_transaction_that_triggers_an_alert(client, headers, transaction_id, customer_id):
    """Stack enough rule weight (>=100, capped) to guarantee a non-LOW risk
    level - and therefore an auto-created alert - regardless of what the
    trained ML anomaly model happens to score this transaction."""
    client.post(
        "/api/rules",
        json={"name": "Amount (ext test)", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 1000}, "risk_weight": 40},
        headers=headers,
    )
    client.post(
        "/api/rules",
        json={"name": "New device high value (ext test)", "rule_type": "NEW_DEVICE_HIGH_VALUE", "configuration": {"threshold": 500}, "risk_weight": 35},
        headers=headers,
    )
    client.post(
        "/api/rules",
        json={"name": "New account high value (ext test)", "rule_type": "NEW_ACCOUNT_HIGH_VALUE", "configuration": {"max_age_days": 7, "threshold": 500}, "risk_weight": 30},
        headers=headers,
    )
    resp = client.post(
        "/api/transactions",
        json={
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "amount": 2000,
            "device_id": "device-alert-trigger",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["risk_level"] != "LOW"


def test_external_system_can_review_alert_with_api_key(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-ext6@example.com", UserRole.ADMIN)
    raw_key, _ = _issue_api_key(client, admin_headers, "Acme E-Commerce")

    _create_transaction_that_triggers_an_alert(client, admin_headers, "TXN-ALERT-API-1", "CUST-ALERT-API-1")

    alerts_resp = client.get("/api/alerts", headers=admin_headers)
    matching = [a for a in alerts_resp.json() if a["transaction_id"] == "TXN-ALERT-API-1"]
    assert len(matching) == 1
    alert_id = matching[0]["id"]
    assert matching[0]["status"] == "NEW"

    resp = client.post(
        f"/api/alerts/{alert_id}/review",
        json={"status": "INVESTIGATING"},
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "INVESTIGATING"
