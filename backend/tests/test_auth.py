def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_signup_success(client):
    payload = {
        "email": "developer@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "developer@example.com"
    assert "id" in data
    assert "created_at" in data
    assert "hashed_password" not in data


def test_signup_duplicate_email(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "StrongPassword123!",
    }
    first_resp = client.post("/auth/signup", json=payload)
    assert first_resp.status_code == 201

    dup_resp = client.post("/auth/signup", json=payload)
    assert dup_resp.status_code == 409
    assert "already registered" in dup_resp.json()["detail"].lower()


def test_signup_weak_password(client):
    payload = {
        "email": "weak@example.com",
        "password": "short",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


def test_login_success(client):
    signup_payload = {
        "email": "login_user@example.com",
        "password": "SecurePassword456!",
    }
    client.post("/auth/signup", json=signup_payload)

    login_payload = {
        "email": "login_user@example.com",
        "password": "SecurePassword456!",
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800


def test_login_wrong_password(client):
    signup_payload = {
        "email": "wrongpass@example.com",
        "password": "CorrectPassword123!",
    }
    client.post("/auth/signup", json=signup_payload)

    login_payload = {
        "email": "wrongpass@example.com",
        "password": "IncorrectPassword999!",
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


def test_login_nonexistent_user(client):
    login_payload = {
        "email": "nonexistent@example.com",
        "password": "AnyPassword123!",
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 401


def test_get_me_authenticated(client):
    signup_payload = {
        "email": "me_user@example.com",
        "password": "Password789!",
    }
    signup_resp = client.post("/auth/signup", json=signup_payload)
    user_id = signup_resp.json()["id"]

    login_payload = {
        "email": "me_user@example.com",
        "password": "Password789!",
    }
    login_resp = client.post("/auth/login", json=login_payload)
    token = login_resp.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == "me_user@example.com"


def test_get_me_unauthorized(client):
    resp_no_token = client.get("/auth/me")
    assert resp_no_token.status_code in [401, 403]

    resp_invalid_token = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp_invalid_token.status_code == 401
