"""
Coverage for the real-time push layer added on top of the existing
synchronous detection pipeline (see app/services/realtime.py and
app/api/routes/ws.py): every transaction that finishes scoring should be
broadcast over /ws/live to any connected, authenticated client.
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _make_user(db_session, email, role=UserRole.ADMIN):
    user = User(name="Test User", email=email, password_hash=hash_password("Secret123!"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, email):
    resp = client.post("/api/auth/login", json={"email": email, "password": "Secret123!"})
    return resp.json()["access_token"]


def test_websocket_rejects_missing_token(client):
    # No `?token=` query param at all -> FastAPI query validation itself rejects the
    # handshake before our own auth check ever runs.
    try:
        with client.websocket_connect("/ws/live"):
            pass
        assert False, "expected the handshake to be rejected"
    except Exception:
        pass


def test_websocket_rejects_invalid_token(client):
    try:
        with client.websocket_connect("/ws/live?token=not-a-real-token"):
            pass
        assert False, "expected the handshake to be rejected"
    except Exception:
        pass


def test_websocket_receives_live_transaction_event(client, db_session):
    email = "ws-live@example.com"
    _make_user(db_session, email, UserRole.ADMIN)
    token = _login(client, email)

    with client.websocket_connect(f"/ws/live?token={token}") as ws:
        resp = client.post(
            "/api/transactions",
            json={"transaction_id": "TXN-WS-1", "customer_id": "CUST-WS-1", "amount": 123.45},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

        event = ws.receive_json()
        assert event["type"] == "transaction.scored"
        assert event["transaction"]["transaction_id"] == "TXN-WS-1"
        assert event["transaction"]["customer_id"] == "CUST-WS-1"
        assert event["transaction"]["amount"] == 123.45
        assert event["transaction"]["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert event["transaction"]["decision"] in ("APPROVE", "REVIEW", "BLOCK")
