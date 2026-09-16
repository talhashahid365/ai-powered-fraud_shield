from app.models.enums import UserRole
from app.core.security import hash_password
from app.models.user import User


def _make_admin(db_session):
    admin = User(name="Admin", email="admin-test@example.com", password_hash=hash_password("Secret123!"), role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_login_creates_audit_log_entry(client, db_session):
    _make_admin(db_session)
    token = _login(client, "admin-test@example.com", "Secret123!")

    resp = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    actions = [entry["action"] for entry in resp.json()]
    assert "LOGIN_SUCCESS" in actions


def test_failed_login_is_audited(client, db_session):
    _make_admin(db_session)
    client.post("/api/auth/login", json={"email": "admin-test@example.com", "password": "wrong-password"})

    token = _login(client, "admin-test@example.com", "Secret123!")
    resp = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    actions = [entry["action"] for entry in resp.json()]
    assert "LOGIN_FAILED" in actions


def test_rule_crud_is_audited(client, db_session):
    _make_admin(db_session)
    token = _login(client, "admin-test@example.com", "Secret123!")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post("/api/rules", json={
        "name": "Test Rule", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 1000}, "risk_weight": 10,
    }, headers=headers)
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]

    client.put(f"/api/rules/{rule_id}", json={"risk_weight": 20}, headers=headers)
    client.delete(f"/api/rules/{rule_id}", headers=headers)

    resp = client.get("/api/audit-logs", headers=headers)
    actions = [entry["action"] for entry in resp.json()]
    assert "RULE_CREATED" in actions
    assert "RULE_UPDATED" in actions
    assert "RULE_DELETED" in actions


def test_analyst_cannot_view_audit_logs(client, db_session):
    analyst = User(name="Analyst", email="analyst-test@example.com", password_hash=hash_password("Secret123!"), role=UserRole.ANALYST)
    db_session.add(analyst)
    db_session.commit()

    token = _login(client, "analyst-test@example.com", "Secret123!")
    resp = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
