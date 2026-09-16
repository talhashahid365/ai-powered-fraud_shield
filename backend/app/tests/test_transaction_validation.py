"""
Coverage for the "Data Validation" step of the real-time detection flow
(schemas/transaction.py::TransactionCreate). Before these validators existed,
any string/float would pass through to the rule engine and ML pipeline
unchecked (see the docstring in schemas/transaction.py for the concrete
risks that created).
"""
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _make_admin(db_session, email="validator-admin@example.com"):
    user = User(name="Admin", email=email, password_hash=hash_password("Secret123!"), role=UserRole.ADMIN)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(client, db_session, email="validator-admin@example.com"):
    _make_admin(db_session, email)
    resp = client.post("/api/auth/login", json={"email": email, "password": "Secret123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _base_payload(**overrides):
    payload = {"transaction_id": "TXN-VALID-1", "customer_id": "CUST-VALID-1", "amount": 100.0}
    payload.update(overrides)
    return payload


def test_zero_amount_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(amount=0), headers=headers)
    assert resp.status_code == 422


def test_negative_amount_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(amount=-50), headers=headers)
    assert resp.status_code == 422


def test_absurdly_large_amount_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(amount=1_000_000_000), headers=headers)
    assert resp.status_code == 422


def test_blank_transaction_id_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(transaction_id="   "), headers=headers)
    assert resp.status_code == 422


def test_transaction_id_with_invalid_characters_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(transaction_id="<script>alert(1)</script>"), headers=headers)
    assert resp.status_code == 422


def test_invalid_currency_code_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(currency="DOLLARS"), headers=headers)
    assert resp.status_code == 422


def test_currency_is_normalized_to_uppercase(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post("/api/transactions", json=_base_payload(currency="usd"), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["currency"] == "USD"


def test_invalid_ip_address_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post(
        "/api/transactions",
        json=_base_payload(ip_address="not-an-ip-address"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_future_transaction_datetime_rejected(client, db_session):
    headers = _auth_headers(client, db_session)
    resp = client.post(
        "/api/transactions",
        json=_base_payload(transaction_datetime="2099-01-01T00:00:00"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_valid_transaction_still_accepted(client, db_session):
    """Sanity check: legitimate, well-formed input is unaffected by the new validators."""
    headers = _auth_headers(client, db_session)
    resp = client.post(
        "/api/transactions",
        json=_base_payload(
            ip_address="203.0.113.9",
            device_id="device-xyz",
            location="Karachi, PK",
            payment_method="CARD",
        ),
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 100.0
    assert body["location"] == "Karachi, PK"
