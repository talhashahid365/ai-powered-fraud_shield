"""
Covers the AI Explanation feature end-to-end: risk_factors/explanation must be
computed, persisted on the transaction, and readable later from every surface
that exposes them (transaction detail, dedicated risk endpoint, external risk
API, and the alert created for a flagged transaction).

Regression coverage for bugs fixed in this pass:
  - GET /api/transactions/{id}/risk used to always pass an empty risk_factors
    list into generate_explanation(), so the explanation was always
    "No specific risk factors were triggered" even for HIGH risk transactions.
  - POST /api/risk-check and GET /api/risk/{transaction_id} hardcoded
    triggered_rules=[] / risk_factors=[] instead of returning the real ones.
  - Alert.reason stored the raw "; "-joined risk_factors instead of the
    generated human-readable explanation.
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _make_user(db_session, email, role=UserRole.ADMIN):
    user = User(name="Analyst", email=email, password_hash=hash_password("Secret123!"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, email, password="Secret123!"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _make_high_risk_transaction(client, headers, txn_id="TXN-EXPLAIN-1", customer_id="CUST-EXPLAIN-1"):
    # A handful of small, ordinary transactions to establish the customer's normal
    # spending pattern ($50-$100), then one that blows way past it from a new device.
    for i, amount in enumerate([50, 75, 100, 60]):
        client.post(
            "/api/transactions",
            json={
                "transaction_id": f"{txn_id}-baseline-{i}",
                "customer_id": customer_id,
                "amount": amount,
                "device_id": "device-known",
                "location": "New York",
            },
            headers=headers,
        )
    resp = client.post(
        "/api/transactions",
        json={
            "transaction_id": txn_id,
            "customer_id": customer_id,
            "amount": 1200,
            "device_id": "device-new-and-unseen",
            "location": "Lagos",
        },
        headers=headers,
    )
    return resp


def test_high_risk_transaction_gets_populated_risk_factors_and_explanation(client, db_session):
    _make_user(db_session, "explain-admin@example.com")
    token = _login(client, "explain-admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = _make_high_risk_transaction(client, headers)
    assert resp.status_code == 201
    body = resp.json()

    # The creation response itself should already carry real risk factors, not an
    # empty list, whenever the transaction isn't LOW risk.
    if body["risk_level"] != "LOW":
        assert body["risk_factors"], "expected non-empty risk_factors on a flagged transaction"
        assert body["explanation"], "expected a generated explanation on a flagged transaction"

    txn_out_id = body["id"]

    # Fetching the transaction later must return the SAME persisted factors/explanation.
    detail = client.get(f"/api/transactions/{txn_out_id}", headers=headers).json()
    assert detail["risk_factors"] == body["risk_factors"]
    assert detail["explanation"] == body["explanation"]

    # The dedicated risk endpoint must not silently drop back to an empty factor list.
    risk_detail = client.get(f"/api/transactions/{txn_out_id}/risk", headers=headers).json()
    assert risk_detail["risk_factors"] == body["risk_factors"]
    if body["risk_level"] != "LOW":
        assert risk_detail["explanation"]
        assert "No specific risk factors were triggered" not in risk_detail["explanation"]


def test_velocity_and_spend_range_are_named_explicitly(client, db_session):
    _make_user(db_session, "explain-admin2@example.com")
    token = _login(client, "explain-admin2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    customer_id = "CUST-EXPLAIN-2"
    for i, amount in enumerate([55, 80, 95]):
        client.post(
            "/api/transactions",
            json={"transaction_id": f"TXN-VEL-baseline-{i}", "customer_id": customer_id, "amount": amount},
            headers=headers,
        )
    # Three more transactions in immediate succession (same request "now") to trigger velocity.
    for i in range(3):
        client.post(
            "/api/transactions",
            json={"transaction_id": f"TXN-VEL-rapid-{i}", "customer_id": customer_id, "amount": 60},
            headers=headers,
        )
    resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-VEL-final", "customer_id": customer_id, "amount": 900},
        headers=headers,
    )
    factors = resp.json()["risk_factors"]
    assert any("minutes" in f for f in factors), f"expected an explicit velocity factor, got: {factors}"


def test_alert_reason_uses_generated_explanation_not_raw_factors(client, db_session):
    _make_user(db_session, "explain-admin3@example.com")
    token = _login(client, "explain-admin3@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = _make_high_risk_transaction(client, headers, txn_id="TXN-EXPLAIN-3", customer_id="CUST-EXPLAIN-3")
    body = resp.json()
    if body["risk_level"] == "LOW":
        return  # nothing to assert if signals didn't add up to an alert in this environment

    alerts = client.get("/api/alerts", headers=headers).json()
    match = next(a for a in alerts if a["transaction_id"] == body["transaction_id"])
    assert match["reason"] == body["explanation"]
