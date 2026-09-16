"""
Coverage for the Investigation System (spec section 10): an analyst opening
a flagged transaction should see customer info, transaction history,
related transactions, devices, IP addresses, locations, risk factors, the
AI explanation, related alerts, and be able to add investigation notes.
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _make_user(db_session, email, role):
    user = User(name="Test Analyst", email=email, password_hash=hash_password("Secret123!"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(client, db_session, email, role):
    _make_user(db_session, email, role)
    resp = client.post("/api/auth/login", json={"email": email, "password": "Secret123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _flag_transaction(client, headers, txn_id, cust_id, device_id="DEV-1", ip="1.2.3.4", location="Lahore, PK", amount=5000):
    resp = client.post(
        "/api/rules",
        json={"name": "Always flags (test)", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 10}, "risk_weight": 90},
        headers=headers,
    )
    # Only create the rule once across calls in a test - ignore if it already exists.
    if resp.status_code not in (201, 409, 422):
        assert resp.status_code == 201

    resp = client.post(
        "/api/risk-check",
        json={
            "transaction_id": txn_id, "customer_id": cust_id, "amount": amount,
            "device_id": device_id, "ip_address": ip, "location": location,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_investigation_case_includes_all_required_sections(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-inv1@example.com", UserRole.ADMIN)

    _flag_transaction(client, admin_headers, "TXN-INV-1", "CUST-INV-1")
    # A second customer sharing the same device/IP - should surface as a related transaction/alert.
    _flag_transaction(client, admin_headers, "TXN-INV-2", "CUST-INV-2")

    alerts = client.get("/api/alerts", headers=admin_headers).json()
    alert = next(a for a in alerts if a["transaction_id"] == "TXN-INV-1")

    resp = client.get(f"/api/investigation/case/{alert['id']}", headers=admin_headers)
    assert resp.status_code == 200
    case = resp.json()

    assert case["customer"]["customer_id"] == "CUST-INV-1"
    assert case["transaction"]["transaction_id"] == "TXN-INV-1"
    assert case["transaction"]["risk_factors"] == case["risk_factors"]
    assert "ai_explanation" in case
    assert len(case["transaction_history"]) >= 1
    assert any(t["customer_id"] == "CUST-INV-2" for t in case["related_transactions"])
    assert any(d["value"] == "DEV-1" for d in case["devices"])
    assert any(ip["value"] == "1.2.3.4" for ip in case["ip_addresses"])
    assert any(loc["value"] == "Lahore, PK" for loc in case["locations"])
    assert any(a["customer_id"] == "CUST-INV-2" for a in case["related_alerts"])
    assert case["investigation_notes"] == []


def test_investigation_notes_are_added_and_listed_with_analyst_name(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-inv2@example.com", UserRole.ADMIN)
    _flag_transaction(client, admin_headers, "TXN-INV-3", "CUST-INV-3")
    alerts = client.get("/api/alerts", headers=admin_headers).json()
    alert = next(a for a in alerts if a["transaction_id"] == "TXN-INV-3")

    resp = client.post(f"/api/alerts/{alert['id']}/notes", json={"note": "Looks like a shared device with another account."}, headers=admin_headers)
    assert resp.status_code == 200
    created = resp.json()
    assert created["note"] == "Looks like a shared device with another account."
    assert created["analyst_name"] == "Test Analyst"

    resp = client.get(f"/api/alerts/{alert['id']}/notes", headers=admin_headers)
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) == 1
    assert notes[0]["analyst_name"] == "Test Analyst"

    # Notes should also be reflected in the aggregated case view.
    case = client.get(f"/api/investigation/case/{alert['id']}", headers=admin_headers).json()
    assert len(case["investigation_notes"]) == 1
    assert case["investigation_notes"][0]["analyst_name"] == "Test Analyst"


def test_investigation_case_requires_authentication(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-inv4@example.com", UserRole.ADMIN)
    _flag_transaction(client, admin_headers, "TXN-INV-4", "CUST-INV-4")
    alerts = client.get("/api/alerts", headers=admin_headers).json()
    alert = next(a for a in alerts if a["transaction_id"] == "TXN-INV-4")

    resp = client.get(f"/api/investigation/case/{alert['id']}")
    assert resp.status_code == 401


def test_investigation_case_404_for_unknown_alert(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-inv5@example.com", UserRole.ADMIN)
    resp = client.get("/api/investigation/case/does-not-exist", headers=admin_headers)
    assert resp.status_code == 404
