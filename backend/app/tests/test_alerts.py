"""
Coverage for the Fraud Alerts feature: when a high-risk transaction is
detected, an alert must be created, shown on the dashboard, store its
reason, be assigned a severity, and notify the relevant (assigned) user.
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


def _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-ALERT-1", cust_id="CUST-ALERT-1"):
    # A rule with a very high weight guarantees rule_score alone pushes the
    # blended risk score into MEDIUM/HIGH territory, which is what should
    # cause an alert to be created.
    resp = client.post(
        "/api/rules",
        json={"name": "Always flags (test)", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 10}, "risk_weight": 90},
        headers=admin_headers,
    )
    assert resp.status_code == 201

    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": txn_id, "customer_id": cust_id, "amount": 5000},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_high_risk_transaction_creates_alert_with_severity_and_reason(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-a1@example.com", UserRole.ADMIN)
    risk = _trigger_high_risk_alert(client, admin_headers)
    assert risk["risk_level"] in ("MEDIUM", "HIGH")

    resp = client.get("/api/alerts", headers=admin_headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["status"] == "NEW"
    assert alert["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert alert["reason"]  # reason must be stored, not empty


def test_alert_status_supports_full_spec_lifecycle(client, db_session):
    # CONFIRMED_FRAUD / FALSE_POSITIVE are outcome statuses and must go through
    # POST /alerts/{id}/feedback (see test_feedback_* below) so they're captured as
    # labeled training/evaluation data -- NOT through the generic /review endpoint.
    admin_headers = _auth_headers(client, db_session, "admin-a2@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-ALERT-2", cust_id="CUST-ALERT-2")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    for status in ("INVESTIGATING", "RESOLVED"):
        resp = client.post(f"/api/alerts/{alert_id}/review", json={"status": status}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == status


def test_review_endpoint_rejects_outcome_statuses(client, db_session):
    """Confirming/dismissing an alert must go through /feedback so it's stored as a
    labeled Feedback record -- the generic /review endpoint must refuse to set these,
    or fraud outcomes could bypass the model-improvement data pipeline entirely."""
    admin_headers = _auth_headers(client, db_session, "admin-a2b@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-ALERT-2B", cust_id="CUST-ALERT-2B")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    for status in ("CONFIRMED_FRAUD", "FALSE_POSITIVE"):
        resp = client.post(f"/api/alerts/{alert_id}/review", json={"status": status}, headers=admin_headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "USE_FEEDBACK_ENDPOINT"

    # status must be unchanged (still NEW)
    resp = client.get(f"/api/alerts/{alert_id}", headers=admin_headers)
    assert resp.json()["status"] == "NEW"


def test_feedback_confirmed_fraud_updates_alert_and_customer(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-fb1@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-FB-1", cust_id="CUST-FB-1")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    resp = client.post(
        f"/api/alerts/{alert_id}/feedback",
        json={"actual_result": "CONFIRMED_FRAUD", "comments": "Matched a known fraud ring"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["actual_result"] == "CONFIRMED_FRAUD"
    assert body["comments"] == "Matched a known fraud ring"
    assert body["analyst_id"]

    alert = client.get(f"/api/alerts/{alert_id}", headers=admin_headers).json()
    assert alert["status"] == "CONFIRMED_FRAUD"

    customer = client.get("/api/customers/CUST-FB-1", headers=admin_headers).json()
    assert customer["previous_fraud_reports"] >= 1

    # feedback is retrievable for later export as training/evaluation data
    resp = client.get(f"/api/alerts/{alert_id}/feedback", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["actual_result"] == "CONFIRMED_FRAUD"


def test_feedback_false_positive_does_not_increment_fraud_reports(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-fb2@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-FB-2", cust_id="CUST-FB-2")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    resp = client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "FALSE_POSITIVE"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["actual_result"] == "FALSE_POSITIVE"

    alert = client.get(f"/api/alerts/{alert_id}", headers=admin_headers).json()
    assert alert["status"] == "FALSE_POSITIVE"

    customer = client.get("/api/customers/CUST-FB-2", headers=admin_headers).json()
    assert customer["previous_fraud_reports"] == 0


def test_feedback_cannot_be_submitted_twice_for_same_alert(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-fb3@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-FB-3", cust_id="CUST-FB-3")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    resp = client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "FALSE_POSITIVE"}, headers=admin_headers)
    assert resp.status_code == 200

    # A second, even contradictory, submission must be rejected -- one alert, one label.
    resp = client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "CONFIRMED_FRAUD"}, headers=admin_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "FEEDBACK_ALREADY_EXISTS"

    # original label must be unchanged
    resp = client.get(f"/api/alerts/{alert_id}/feedback", headers=admin_headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["actual_result"] == "FALSE_POSITIVE"


def test_feedback_rejects_invalid_result_value(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-fb4@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-FB-4", cust_id="CUST-FB-4")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    resp = client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "MAYBE"}, headers=admin_headers)
    assert resp.status_code == 422


def test_analyst_can_submit_feedback(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-fb5@example.com", UserRole.ADMIN)
    analyst = _make_user(db_session, "analyst-fb5@example.com", UserRole.ANALYST)
    analyst_token = _login(client, "analyst-fb5@example.com")
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}

    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-FB-5", cust_id="CUST-FB-5")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    resp = client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "CONFIRMED_FRAUD"}, headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["analyst_id"] == analyst.id


def test_model_feedback_summary_report_reflects_submitted_feedback(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-fb6@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-FB-6", cust_id="CUST-FB-6")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]
    client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "CONFIRMED_FRAUD"}, headers=admin_headers)

    resp = client.get("/api/reports/model-feedback-summary", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_labeled_alerts"] >= 1
    assert body["confirmed_fraud"] >= 1
    assert body["alert_precision"] is not None


def test_alert_shows_on_dashboard(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-a3@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-ALERT-3", cust_id="CUST-ALERT-3")

    resp = client.get("/api/dashboard/recent-alerts", headers=admin_headers)
    assert resp.status_code == 200
    assert any(a["title"] for a in resp.json())

    resp = client.get("/api/dashboard/summary", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["fraud_alerts"] >= 1


def test_new_alert_auto_assigns_to_an_analyst_and_notifies_them(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-a4@example.com", UserRole.ADMIN)
    analyst = _make_user(db_session, "analyst-a4@example.com", UserRole.ANALYST)
    analyst_token = _login(client, "analyst-a4@example.com")
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}

    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-ALERT-4", cust_id="CUST-ALERT-4")

    alert = client.get("/api/alerts", headers=admin_headers).json()[0]
    assert alert["assigned_to"] == analyst.id

    resp = client.get("/api/notifications", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] >= 1
    assert any(n["alert_id"] == alert["id"] for n in body["data"])


def test_manual_alert_assignment_notifies_new_assignee(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-a5@example.com", UserRole.ADMIN)
    analyst2 = _make_user(db_session, "analyst2-a5@example.com", UserRole.ANALYST)

    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-ALERT-5", cust_id="CUST-ALERT-5")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]

    resp = client.post(f"/api/alerts/{alert_id}/assign", json={"user_id": analyst2.id}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] == analyst2.id

    analyst2_token = _login(client, "analyst2-a5@example.com")
    resp = client.get("/api/notifications", headers={"Authorization": f"Bearer {analyst2_token}"})
    assert resp.json()["unread_count"] >= 1
