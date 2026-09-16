"""
Coverage for the AI Investigation Assistant (spec item 14): an analyst
should be able to ask free-text questions about a customer, a flagged
alert, or a device, and get back an answer grounded only in real
platform data - never invented facts.
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


def _flag_transaction(client, headers, txn_id, cust_id, device_id="DEV-9001", ip="5.6.7.8", location="Karachi, PK", amount=9000):
    resp = client.post(
        "/api/rules",
        json={"name": "Always flags (assistant test)", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 10}, "risk_weight": 90},
        headers=headers,
    )
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


def test_ask_requires_context(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai1@example.com", UserRole.ANALYST)
    resp = client.post("/api/investigation/ask", json={"question": "Why is this suspicious?"}, headers=headers)
    assert resp.status_code == 400


def test_ask_about_customer_returns_grounded_answer(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai2@example.com", UserRole.ANALYST)
    _flag_transaction(client, headers, "TXN-AI-1", "CUST-AI-1")

    resp = client.post(
        "/api/investigation/ask",
        json={"question": "Why is this customer suspicious?", "customer_id": "CUST-AI-1"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body and body["answer"]
    assert body["evidence_used"]["customer"]["customer_id"] == "CUST-AI-1"
    assert any(t["transaction_id"] == "TXN-AI-1" for t in body["evidence_used"]["recent_transactions"])


def test_ask_unusual_activity_includes_unusual_section(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai3@example.com", UserRole.ANALYST)
    _flag_transaction(client, headers, "TXN-AI-2", "CUST-AI-2")

    resp = client.post(
        "/api/investigation/ask",
        json={"question": "Show me unusual activity from this customer.", "customer_id": "CUST-AI-2"},
        headers=headers,
    )
    assert resp.status_code == 200
    evidence = resp.json()["evidence_used"]
    assert "unusual_activity" in evidence
    assert evidence["unusual_activity"]["customer_id"] == "CUST-AI-2"


def test_ask_about_device_returns_all_customers_on_it(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai4@example.com", UserRole.ANALYST)
    _flag_transaction(client, headers, "TXN-AI-3", "CUST-AI-3", device_id="DEV-SHARED")
    _flag_transaction(client, headers, "TXN-AI-4", "CUST-AI-4", device_id="DEV-SHARED")

    resp = client.post(
        "/api/investigation/ask",
        json={"question": "What transactions are connected to this device?", "device_id": "DEV-SHARED"},
        headers=headers,
    )
    assert resp.status_code == 200
    device_evidence = resp.json()["evidence_used"]["device"]
    assert device_evidence["transaction_count"] == 2
    assert device_evidence["shared_by_multiple_customers"] is True
    assert set(device_evidence["distinct_customers"]) == {"CUST-AI-3", "CUST-AI-4"}


def test_ask_can_detect_device_id_mentioned_in_question_text(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai5@example.com", UserRole.ANALYST)
    _flag_transaction(client, headers, "TXN-AI-5", "CUST-AI-5", device_id="DEV-4471")

    resp = client.post(
        "/api/investigation/ask",
        json={"question": "What transactions are connected to DEV-4471?"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["evidence_used"]["device"]["device_id"] == "DEV-4471"


def test_ask_summarize_investigation_uses_full_case_bundle(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai6@example.com", UserRole.ANALYST)
    _flag_transaction(client, headers, "TXN-AI-6", "CUST-AI-6")
    alerts = client.get("/api/alerts", headers=headers).json()
    alert = next(a for a in alerts if a["transaction_id"] == "TXN-AI-6")

    resp = client.post(
        "/api/investigation/ask",
        json={"question": "Summarize this investigation.", "alert_id": alert["id"]},
        headers=headers,
    )
    assert resp.status_code == 200
    evidence = resp.json()["evidence_used"]
    assert "investigation_case_summary" in evidence
    assert evidence["investigation_case_summary"]["transaction"]["transaction_id"] == "TXN-AI-6"


def test_viewer_role_cannot_use_assistant(client, db_session):
    headers = _auth_headers(client, db_session, "manager-ai1@example.com", UserRole.BUSINESS_MANAGER)
    resp = client.post(
        "/api/investigation/ask",
        json={"question": "Why is this customer suspicious?", "customer_id": "CUST-AI-1"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_conversation_history_is_accepted(client, db_session):
    headers = _auth_headers(client, db_session, "analyst-ai7@example.com", UserRole.ANALYST)
    _flag_transaction(client, headers, "TXN-AI-7", "CUST-AI-7")

    resp = client.post(
        "/api/investigation/ask",
        json={
            "question": "What about last week?",
            "customer_id": "CUST-AI-7",
            "conversation_history": [
                {"role": "user", "content": "Why is this customer suspicious?"},
                {"role": "assistant", "content": "The customer has one flagged transaction."},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
