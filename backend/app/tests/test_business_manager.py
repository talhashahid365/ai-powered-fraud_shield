"""
Confirms the Business Manager role has exactly the permission boundary
the frontend now reflects: can create/import transactions, cannot act on
alerts (review/notes/feedback) or manage rules.
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _make_user(db_session, email, role):
    user = User(name="Manager", email=email, password_hash=hash_password("Secret123!"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, email, password="Secret123!"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_manager_can_create_transaction(client, db_session):
    _make_user(db_session, "manager-test@example.com", UserRole.BUSINESS_MANAGER)
    token = _login(client, "manager-test@example.com")

    resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-MGR-1", "customer_id": "CUST-MGR-1", "amount": 42.5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


def test_manager_cannot_review_alerts_or_manage_rules(client, db_session):
    _make_user(db_session, "manager-test2@example.com", UserRole.BUSINESS_MANAGER)
    token = _login(client, "manager-test2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Can still GET the alerts list (view-only) ...
    resp = client.get("/api/alerts", headers=headers)
    assert resp.status_code == 200

    # ... but cannot manage rules or act on an alert.
    resp = client.get("/api/rules", headers=headers)
    assert resp.status_code == 403

    resp = client.post(
        "/api/alerts/fake-id/review", json={"status": "RESOLVED"}, headers=headers
    )
    assert resp.status_code == 403


def test_manager_can_see_recent_transactions_dashboard(client, db_session):
    _make_user(db_session, "manager-test3@example.com", UserRole.BUSINESS_MANAGER)
    token = _login(client, "manager-test3@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-MGR-2", "customer_id": "CUST-MGR-2", "amount": 99},
        headers=headers,
    )
    resp = client.get("/api/dashboard/recent-transactions", headers=headers)
    assert resp.status_code == 200
    assert any(t["transaction_id"] == "TXN-MGR-2" for t in resp.json())
