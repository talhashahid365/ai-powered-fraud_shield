"""
Coverage for the Transaction Management feature set:
manual add, CSV import, list/search/filter, transaction detail, and the
external risk-check API. Previously this area had no dedicated tests even
though it's a core, business-facing feature.
"""
import io

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


# ---------------------------------------------------------------------------
# Manual creation
# ---------------------------------------------------------------------------

def test_admin_can_create_transaction_with_full_details(client, db_session):
    headers = _auth_headers(client, db_session, "admin1@example.com", UserRole.ADMIN)

    resp = client.post(
        "/api/transactions",
        json={
            "transaction_id": "TXN-FULL-1",
            "customer_id": "CUST-FULL-1",
            "amount": 250.0,
            "currency": "USD",
            "payment_method": "CARD",
            "ip_address": "203.0.113.5",
            "device_id": "device-abc-123",
            "location": "Lahore, PK",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["transaction_id"] == "TXN-FULL-1"
    assert body["customer_id"] == "CUST-FULL-1"
    assert body["payment_method"] == "CARD"
    assert body["ip_address"] == "203.0.113.5"
    assert body["device_id"] == "device-abc-123"
    assert body["location"] == "Lahore, PK"
    # Freshly created customer -> no prior transactions.
    assert body["previous_transaction_count"] == 0
    assert body["account_age_days"] == 0


def test_duplicate_transaction_id_rejected(client, db_session):
    headers = _auth_headers(client, db_session, "admin2@example.com", UserRole.ADMIN)
    payload = {"transaction_id": "TXN-DUP-1", "customer_id": "CUST-DUP-1", "amount": 10}

    resp1 = client.post("/api/transactions", json=payload, headers=headers)
    assert resp1.status_code == 201

    resp2 = client.post("/api/transactions", json=payload, headers=headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "DUPLICATE_TRANSACTION"


def test_analyst_cannot_create_transaction(client, db_session):
    headers = _auth_headers(client, db_session, "analyst1@example.com", UserRole.ANALYST)
    resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-ANALYST-1", "customer_id": "CUST-A-1", "amount": 10},
        headers=headers,
    )
    assert resp.status_code == 403


def test_create_transaction_requires_authentication(client, db_session):
    resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-NOAUTH-1", "customer_id": "CUST-NA-1", "amount": 10},
    )
    assert resp.status_code == 401


def test_previous_transaction_count_increments(client, db_session):
    headers = _auth_headers(client, db_session, "admin3@example.com", UserRole.ADMIN)
    customer_id = "CUST-HIST-1"

    for i in range(3):
        resp = client.post(
            "/api/transactions",
            json={"transaction_id": f"TXN-HIST-{i}", "customer_id": customer_id, "amount": 20 + i},
            headers=headers,
        )
        assert resp.status_code == 201

    resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-HIST-LAST", "customer_id": customer_id, "amount": 99},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["previous_transaction_count"] == 3


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def test_csv_import_success_and_duplicates(client, db_session):
    headers = _auth_headers(client, db_session, "admin4@example.com", UserRole.ADMIN)

    csv_content = (
        "transaction_id,customer_id,amount,currency,payment_method,ip_address,device_id,location\n"
        "TXN-CSV-1,CUST-CSV-1,100,USD,CARD,10.0.0.1,dev-1,Karachi\n"
        "TXN-CSV-2,CUST-CSV-1,150,USD,CARD,10.0.0.1,dev-1,Karachi\n"
    )
    resp = client.post(
        "/api/transactions/import-csv",
        files={"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_rows"] == 2
    assert summary["successful_rows"] == 2
    assert summary["failed_rows"] == 0
    assert summary["duplicate_rows"] == 0

    # Re-importing the same file should now report duplicates, not failures.
    resp2 = client.post(
        "/api/transactions/import-csv",
        files={"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers,
    )
    summary2 = resp2.json()
    assert summary2["duplicate_rows"] == 2
    assert summary2["successful_rows"] == 0


def test_csv_import_missing_required_columns(client, db_session):
    headers = _auth_headers(client, db_session, "admin5@example.com", UserRole.ADMIN)
    csv_content = "customer_id,amount\nCUST-1,100\n"
    resp = client.post(
        "/api/transactions/import-csv",
        files={"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_rows"] == 0
    assert "transaction_id" in summary["errors"][0]


def test_csv_import_reports_row_level_errors(client, db_session):
    headers = _auth_headers(client, db_session, "admin6@example.com", UserRole.ADMIN)
    csv_content = (
        "transaction_id,customer_id,amount\n"
        "TXN-BADROW-1,CUST-BR-1,not-a-number\n"
        "TXN-BADROW-2,CUST-BR-1,50\n"
    )
    resp = client.post(
        "/api/transactions/import-csv",
        files={"file": ("mixed.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers,
    )
    summary = resp.json()
    assert summary["total_rows"] == 2
    assert summary["successful_rows"] == 1
    assert summary["failed_rows"] == 1


def test_analyst_cannot_import_csv(client, db_session):
    headers = _auth_headers(client, db_session, "analyst2@example.com", UserRole.ANALYST)
    csv_content = "transaction_id,customer_id,amount\nTXN-X,CUST-X,10\n"
    resp = client.post(
        "/api/transactions/import-csv",
        files={"file": ("t.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List / search / filter
# ---------------------------------------------------------------------------

def test_list_transactions_search_and_filters(client, db_session):
    headers = _auth_headers(client, db_session, "admin7@example.com", UserRole.ADMIN)
    client.post(
        "/api/transactions",
        json={
            "transaction_id": "TXN-SEARCH-1", "customer_id": "CUST-SEARCH-1", "amount": 30,
            "payment_method": "WALLET", "location": "Islamabad",
        },
        headers=headers,
    )
    client.post(
        "/api/transactions",
        json={
            "transaction_id": "TXN-SEARCH-2", "customer_id": "CUST-SEARCH-2", "amount": 40,
            "payment_method": "CARD", "location": "Lahore",
        },
        headers=headers,
    )

    # Any authenticated role (e.g. ANALYST) can view/search the list.
    analyst_headers = _auth_headers(client, db_session, "analyst3@example.com", UserRole.ANALYST)

    resp = client.get("/api/transactions", params={"search": "TXN-SEARCH-1"}, headers=analyst_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(t["transaction_id"] == "TXN-SEARCH-1" for t in data)
    assert all(t["transaction_id"] != "TXN-SEARCH-2" for t in data)

    resp = client.get("/api/transactions", params={"payment_method": "CARD"}, headers=analyst_headers)
    ids = [t["transaction_id"] for t in resp.json()["data"]]
    assert "TXN-SEARCH-2" in ids
    assert "TXN-SEARCH-1" not in ids

    resp = client.get("/api/transactions", params={"location": "Islamabad"}, headers=analyst_headers)
    ids = [t["transaction_id"] for t in resp.json()["data"]]
    assert "TXN-SEARCH-1" in ids
    assert "TXN-SEARCH-2" not in ids


def test_list_transactions_requires_authentication(client, db_session):
    resp = client.get("/api/transactions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Transaction detail + risk explanation
# ---------------------------------------------------------------------------

def test_get_transaction_detail_and_not_found(client, db_session):
    headers = _auth_headers(client, db_session, "admin8@example.com", UserRole.ADMIN)
    create_resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-DETAIL-1", "customer_id": "CUST-DETAIL-1", "amount": 75},
        headers=headers,
    )
    txn_id = create_resp.json()["id"]

    resp = client.get(f"/api/transactions/{txn_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == "TXN-DETAIL-1"

    resp = client.get("/api/transactions/does-not-exist", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRANSACTION_NOT_FOUND"


def test_get_transaction_risk_explanation(client, db_session):
    headers = _auth_headers(client, db_session, "admin9@example.com", UserRole.ADMIN)
    create_resp = client.post(
        "/api/transactions",
        json={"transaction_id": "TXN-RISK-1", "customer_id": "CUST-RISK-1", "amount": 60},
        headers=headers,
    )
    txn_id = create_resp.json()["id"]

    resp = client.get(f"/api/transactions/{txn_id}/risk", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "risk_score" in body
    assert "risk_level" in body
    assert "decision" in body


# ---------------------------------------------------------------------------
# External risk-check API (the "receive transactions through API" path)
# ---------------------------------------------------------------------------

def test_risk_check_endpoint_creates_and_scores_transaction(client, db_session):
    headers = _auth_headers(client, db_session, "admin10@example.com", UserRole.ADMIN)
    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-EXT-1", "customer_id": "CUST-EXT-1", "amount": 500},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "risk_score" in body
    assert "decision" in body

    # The transaction should now also be retrievable through the normal list/detail API.
    resp = client.get("/api/transactions", params={"search": "TXN-EXT-1"}, headers=headers)
    assert any(t["transaction_id"] == "TXN-EXT-1" for t in resp.json()["data"])


def test_get_risk_by_business_id_requires_authentication(client, db_session):
    # Regression test: this endpoint previously had no auth dependency at all,
    # meaning any unauthenticated caller could pull risk data for any
    # transaction by guessing its business-facing transaction_id.
    headers = _auth_headers(client, db_session, "admin11@example.com", UserRole.ADMIN)
    client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-SECURE-1", "customer_id": "CUST-SECURE-1", "amount": 20},
        headers=headers,
    )

    resp = client.get("/api/risk/TXN-SECURE-1")
    assert resp.status_code == 401

    resp = client.get("/api/risk/TXN-SECURE-1", headers=headers)
    assert resp.status_code == 200


def test_triggered_rules_included_in_risk_check_response(client, db_session):
    """Regression test: GET /api/transactions/{id}/risk, GET /api/risk/{id}, and
    POST /api/risk-check previously all hardcoded triggered_rules=[] on read,
    because evaluate_rules()'s result was only ever held in memory for the
    original request and never persisted onto the transaction row - so the
    "Rules" contribution to the combined risk score was invisible on every
    later read, even when a rule had actually fired.
    """
    headers = _auth_headers(client, db_session, "admin12@example.com", UserRole.ADMIN)

    # A rule that will definitely fire for a $9,000 transaction.
    resp = client.post(
        "/api/rules",
        json={"name": "High amount (test)", "rule_type": "AMOUNT_THRESHOLD", "configuration": {"threshold": 5000}, "risk_weight": 40},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.post(
        "/api/risk-check",
        json={"transaction_id": "TXN-RULES-1", "customer_id": "CUST-RULES-1", "amount": 9000},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "High amount (test)" in resp.json()["triggered_rules"]

    # Same rule name must still be present on later reads, not just the initial response.
    resp = client.get("/api/risk/TXN-RULES-1", headers=headers)
    assert resp.status_code == 200
    assert "High amount (test)" in resp.json()["triggered_rules"]

    txn_id = client.get("/api/transactions", params={"search": "TXN-RULES-1"}, headers=headers).json()["data"][0]["id"]
    resp = client.get(f"/api/transactions/{txn_id}/risk", headers=headers)
    assert resp.status_code == 200
    assert "High amount (test)" in resp.json()["triggered_rules"]
