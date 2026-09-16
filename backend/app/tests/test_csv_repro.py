import io
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


def _admin_headers(client, db_session):
    user = User(name="Admin", email="admin-csv@example.com", password_hash=hash_password("Secret123!"), role=UserRole.ADMIN)
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": "admin-csv@example.com", "password": "Secret123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_repro_dummy_plus_csv(client, db_session):
    headers = _admin_headers(client, db_session)

    # "dummy" data - created directly via API, simulating existing seed/sample data
    for i in range(3):
        r = client.post("/api/transactions", json={
            "transaction_id": f"DUMMY-{i}", "customer_id": f"CUST-DUMMY-{i}", "amount": 100 + i,
        }, headers=headers)
        print("dummy create status", r.status_code, r.json())

    r = client.get("/api/transactions", headers=headers)
    print("after dummy, total:", r.json()["total"])
    assert r.json()["total"] == 3

    csv_content = (
        "transaction_id,customer_id,amount,transaction_datetime,payment_method,ip_address,location,device_id\n"
        "TEST-001,CUST-001,150.00,2026-09-09 10:00:00,card,192.168.1.10,Islamabad,DEVICE-001\n"
        "TEST-002,CUST-002,2500.00,2026-09-09 10:05:00,card,192.168.1.11,Rawalpindi,DEVICE-002\n"
        "TEST-003,CUST-003,75.00,2026-09-09 10:10:00,cash,192.168.1.12,Lahore,DEVICE-003\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = client.post("/api/transactions/import-csv", files=files, headers=headers)
    print("import status", r.status_code, r.json())
    assert r.status_code == 200
    summary = r.json()
    assert summary["successful_rows"] == 3

    r = client.get("/api/transactions", headers=headers)
    body = r.json()
    print("after csv import, total:", body["total"])
    ids = [t["transaction_id"] for t in body["data"]]
    print("ids on page 1:", ids)
    assert body["total"] == 6

    # duplicate import
    r = client.post("/api/transactions/import-csv", files={"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}, headers=headers)
    print("duplicate import status", r.status_code, r.json())
    summary2 = r.json()
    assert summary2["duplicate_rows"] == 3

    r = client.get("/api/transactions", headers=headers)
    print("after duplicate import, total:", r.json()["total"])
    assert r.json()["total"] == 6


def test_csv_import_accepts_header_aliases_and_case_variants(client, db_session):
    """Real-world CSVs rarely spell the columns exactly like the DB fields
    (e.g. 'date_time' and 'device' instead of 'transaction_datetime' and
    'device_id', or different casing) - the import should still work."""
    headers = _admin_headers(client, db_session)

    csv_content = (
        "Transaction_ID,Customer_ID,Amount,date_time,payment_method,ip_address,location,device\n"
        "TEST-101,CUST-101,150.00,2026-09-09 10:00:00,card,192.168.1.10,Islamabad,DEVICE-001\n"
        "TEST-102,CUST-102,2500.00,2026-09-09 10:05:00,card,192.168.1.11,Rawalpindi,DEVICE-002\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = client.post("/api/transactions/import-csv", files=files, headers=headers)
    assert r.status_code == 200
    summary = r.json()
    assert summary["successful_rows"] == 2, summary

    r = client.get("/api/transactions", params={"search": "TEST-101"}, headers=headers)
    assert r.status_code == 200
    txn = r.json()["data"][0]
    assert txn["device_id"] == "DEVICE-001"
    assert "2026-09-09" in txn["transaction_datetime"]
