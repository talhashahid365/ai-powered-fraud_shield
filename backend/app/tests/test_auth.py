def test_register_and_login(client):
    resp = client.post("/api/auth/register", json={
        "name": "Test Admin", "email": "test-admin@example.com", "password": "Secret123!", "role": "ADMIN",
    })
    assert resp.status_code == 201

    resp = client.post("/api/auth/login", json={"email": "test-admin@example.com", "password": "Secret123!"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_invalid_credentials(client):
    resp = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert resp.status_code == 401
