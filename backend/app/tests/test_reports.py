"""
Coverage for the Reports feature (spec section 16): daily/monthly fraud
activity, high-risk customers/transactions, confirmed fraud, false
positives, fraud trends, and CSV export of each.
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


def _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-1", cust_id="CUST-RPT-1", amount=5000):
    resp = client.post(
        "/api/rules",
        json={"name": "Always flags (report test)", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 10}, "risk_weight": 90},
        headers=admin_headers,
    )
    assert resp.status_code in (201, 409)  # 409 if already created by an earlier test in this module run

    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": txn_id, "customer_id": cust_id, "amount": amount},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_daily_fraud_activity_reflects_created_transactions_and_alerts(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt1@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-DAILY", cust_id="CUST-RPT-DAILY")

    resp = client.get("/api/reports/daily-fraud-activity", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] >= 1
    assert body["alerts_created"] >= 1
    assert "high_risk" in body and "confirmed_fraud" in body and "false_positives" in body


def test_daily_fraud_activity_rejects_bad_date(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt2@example.com", UserRole.ADMIN)
    resp = client.get("/api/reports/daily-fraud-activity", params={"date": "not-a-date"}, headers=admin_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REPORT_PARAMS"


def test_monthly_fraud_activity_defaults_to_current_month(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt3@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-MONTHLY", cust_id="CUST-RPT-MONTHLY")

    resp = client.get("/api/reports/monthly-fraud-activity", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] >= 1
    assert body["confirmed_fraud"] == 0  # no feedback submitted yet
    assert body["precision"] is None  # no confirmed/false-positive labels yet


def test_high_risk_customers_and_transactions_reports(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt4@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-HR", cust_id="CUST-RPT-HR")

    resp = client.get("/api/reports/high-risk-customers", headers=admin_headers)
    assert resp.status_code == 200
    customers = resp.json()
    assert any(c["customer_id"] == "CUST-RPT-HR" for c in customers)

    resp = client.get("/api/reports/high-risk-transactions", headers=admin_headers)
    assert resp.status_code == 200
    txns = resp.json()
    assert any(t["transaction_id"] == "TXN-RPT-HR" for t in txns)


def test_confirmed_fraud_and_false_positive_reports_reflect_feedback(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt5@example.com", UserRole.ADMIN)

    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-CONF", cust_id="CUST-RPT-CONF")
    alert_id = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]
    client.post(f"/api/alerts/{alert_id}/feedback", json={"actual_result": "CONFIRMED_FRAUD"}, headers=admin_headers)

    resp = client.get("/api/reports/confirmed-fraud", headers=admin_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["transaction_id"] == "TXN-RPT-CONF"
    assert rows[0]["customer_id"] == "CUST-RPT-CONF"

    resp = client.get("/api/reports/false-positives", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_fraud_trends_report_has_daily_series_and_direction(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt6@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-TREND", cust_id="CUST-RPT-TREND")

    resp = client.get("/api/reports/fraud-trends", params={"days": 7}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_days"] == 7
    assert len(body["daily"]) == 7
    assert body["trend_direction"] in ("increasing", "decreasing", "stable")
    assert all("fraud_rate_pct" in day for day in body["daily"])
    # today's bucket should have picked up the alert created above
    assert sum(d["alerts_created"] for d in body["daily"]) >= 1


def test_export_high_risk_customers_returns_csv(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt7@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-EXP1", cust_id="CUST-RPT-EXP1")

    resp = client.get("/api/reports/export/high-risk-customers", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment;" in resp.headers["content-disposition"]
    assert "CUST-RPT-EXP1" in resp.text
    assert resp.text.splitlines()[0].startswith("customer_id,")


def test_export_handles_report_with_no_data(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt8@example.com", UserRole.ADMIN)
    resp = client.get("/api/reports/export/confirmed-fraud", headers=admin_headers)
    assert resp.status_code == 200
    assert "No data available" in resp.text


def test_export_rejects_unknown_report_type(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt9@example.com", UserRole.ADMIN)
    resp = client.get("/api/reports/export/not-a-real-report", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "UNKNOWN_REPORT_TYPE"


def test_export_fraud_trends_returns_daily_rows_as_csv(client, db_session):
    admin_headers = _auth_headers(client, db_session, "admin-rpt10@example.com", UserRole.ADMIN)
    _trigger_high_risk_alert(client, admin_headers, txn_id="TXN-RPT-EXP2", cust_id="CUST-RPT-EXP2")

    resp = client.get("/api/reports/export/fraud-trends", params={"days": 5}, headers=admin_headers)
    assert resp.status_code == 200
    lines = [l for l in resp.text.splitlines() if l.strip()]
    assert lines[0].startswith("date,")
    assert len(lines) == 6  # header + 5 daily rows


def test_reports_require_authentication(client, db_session):
    resp = client.get("/api/reports/daily-fraud-activity")
    assert resp.status_code == 401
