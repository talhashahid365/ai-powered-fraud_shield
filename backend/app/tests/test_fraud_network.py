"""
Coverage for the Fraud Network Detection feature:

    Customer A ── Device X ── IP 192.168.X.X
                                    │
    Customer B ─────────────────────┘
                                    │
    Customer C ── Device X

Exercises transitive ring detection (A and C are only linked through B, not
directly), the Customer -> Device -> IP -> Transaction -> Location graph
shape, the fixed 1-hop /customers/{id}/network endpoint, and access control.
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


def _create_txn(client, headers, transaction_id, customer_id, device_id=None, ip_address=None, location=None, amount=100.0):
    payload = {
        "transaction_id": transaction_id,
        "customer_id": customer_id,
        "amount": amount,
        "currency": "USD",
    }
    if device_id is not None:
        payload["device_id"] = device_id
    if ip_address is not None:
        payload["ip_address"] = ip_address
    if location is not None:
        payload["location"] = location
    resp = client.post("/api/transactions", json=payload, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    return resp


def _build_ring(client, headers):
    # A and B share Device X. B and C share IP 192.168.1.1. A and C never
    # transact from the same device or IP directly - they're only linked
    # transitively through B.
    _create_txn(client, headers, "TXN-NET-A1", "CUST-NET-A", device_id="dev-X", ip_address="10.0.0.1", location="Lahore, PK")
    _create_txn(client, headers, "TXN-NET-B1", "CUST-NET-B", device_id="dev-X", ip_address="192.168.1.1", location="Karachi, PK")
    _create_txn(client, headers, "TXN-NET-C1", "CUST-NET-C", device_id="dev-Y", ip_address="192.168.1.1", location="Multan, PK")
    # An unrelated, isolated customer that shares nothing with anyone.
    _create_txn(client, headers, "TXN-NET-D1", "CUST-NET-D", device_id="dev-Z", ip_address="8.8.8.8", location="Quetta, PK")


def test_ring_detection_finds_transitive_connections(client, db_session):
    headers = _auth_headers(client, db_session, "netadmin1@example.com", UserRole.ADMIN)
    _build_ring(client, headers)

    resp = client.get("/api/fraud-network/rings", headers=headers)
    assert resp.status_code == 200, resp.text
    rings = resp.json()["rings"]

    ring = next((r for r in rings if set(["CUST-NET-A", "CUST-NET-B", "CUST-NET-C"]) <= set(r["customer_ids"])), None)
    assert ring is not None, f"expected a ring containing A, B, C; got {rings}"
    assert ring["size"] == 3
    assert "CUST-NET-D" not in ring["customer_ids"]  # isolated customer must not be pulled in
    assert ring["shared_device_count"] >= 1
    assert ring["shared_ip_count"] >= 1


def test_isolated_customer_produces_no_ring(client, db_session):
    headers = _auth_headers(client, db_session, "netadmin2@example.com", UserRole.ADMIN)
    _create_txn(client, headers, "TXN-NET-SOLO", "CUST-NET-SOLO", device_id="dev-solo", ip_address="1.1.1.1")

    resp = client.get("/api/fraud-network/rings", headers=headers)
    assert resp.status_code == 200
    rings = resp.json()["rings"]
    assert all("CUST-NET-SOLO" not in r["customer_ids"] for r in rings)


def test_graph_includes_full_chain_for_linking_transactions_only(client, db_session):
    headers = _auth_headers(client, db_session, "netadmin3@example.com", UserRole.ADMIN)
    _build_ring(client, headers)
    # A also has a private, non-shared transaction that must NOT show up as
    # a transaction node (it's not evidence of any connection).
    _create_txn(client, headers, "TXN-NET-A2", "CUST-NET-A", device_id="dev-private", ip_address="9.9.9.9", location="Faisalabad, PK")

    resp = client.get("/api/fraud-network/graph/CUST-NET-A", headers=headers)
    assert resp.status_code == 200, resp.text
    graph = resp.json()

    node_ids = {n["id"] for n in graph["nodes"]}
    node_types = {n["type"] for n in graph["nodes"]}

    assert "CUST-NET-A" in node_ids and "CUST-NET-B" in node_ids and "CUST-NET-C" in node_ids
    assert "CUST-NET-D" not in node_ids  # not part of this ring
    assert {"customer", "device", "ip", "transaction", "location"} <= node_types
    assert "device:dev-private" not in node_ids  # non-shared device stays out
    assert "txn:TXN-NET-A2" not in node_ids  # non-linking transaction stays out
    assert "txn:TXN-NET-A1" in node_ids  # linking transaction is shown
    assert graph["customer_count"] == 3


def test_graph_404_for_unknown_customer(client, db_session):
    headers = _auth_headers(client, db_session, "netadmin4@example.com", UserRole.ADMIN)
    resp = client.get("/api/fraud-network/graph/CUST-DOES-NOT-EXIST", headers=headers)
    assert resp.status_code == 404


def test_per_customer_network_endpoint_only_links_customers_who_actually_share(client, db_session):
    # Regression test for the old bug: a related customer would get an edge
    # to EVERY device/IP the origin customer ever used, even ones the
    # related customer never touched.
    headers = _auth_headers(client, db_session, "netadmin5@example.com", UserRole.ADMIN)
    _create_txn(client, headers, "TXN-NET-E1", "CUST-NET-E", device_id="dev-shared", ip_address="10.0.0.1")
    _create_txn(client, headers, "TXN-NET-E2", "CUST-NET-E", device_id="dev-only-E", ip_address="10.0.0.2")
    _create_txn(client, headers, "TXN-NET-F1", "CUST-NET-F", device_id="dev-shared", ip_address="10.0.0.3")

    resp = client.get("/api/customers/CUST-NET-E/network", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    f_edges = [e for e in data["edges"] if e["target"] == "CUST-NET-F"]
    f_edge_sources = {e["source"] for e in f_edges}
    assert f_edge_sources == {"device:dev-shared"}  # never linked via dev-only-E


def test_fraud_network_routes_require_auth(client, db_session):
    resp = client.get("/api/fraud-network/rings")
    assert resp.status_code in (401, 403)
