import pytest
from app.models.user import User


def test_signup_success(client):
    payload = {
        "email": "newuser@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "hashed_password" not in data


def test_signup_duplicate_email(client):
    payload = {
        "email": "user_a@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_signup_invalid_email(client):
    payload = {
        "email": "invalid-email",
        "password": "Password123!",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


def test_signup_weak_password(client):
    payload = {
        "email": "weak@example.com",
        "password": "short",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


def test_login_success(client):
    payload = {
        "email": "user_a@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    payload = {
        "email": "user_a@example.com",
        "password": "WrongPassword123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    payload = {
        "email": "nonexistent@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401


def test_get_me_authenticated(client):
    signup_payload = {
        "email": "me_user@example.com",
        "password": "Password789!",
    }
    signup_resp = client.post("/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201
    user_id = signup_resp.json()["id"]

    login_resp = client.post("/auth/login", json=signup_payload)
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == user_id
    assert me_resp.json()["email"] == "me_user@example.com"


def test_get_me_unauthenticated(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Requirement 1.1 / 7 — "the authentication system must be secure"
# ---------------------------------------------------------------------------


def _signup_and_login(client, email="token_user@example.com", password="Password123!"):
    client.post("/auth/signup", json={"email": email, "password": password})
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()


def test_password_is_hashed_and_never_returned(client, db_session):
    """A plaintext password must not reach the database or any response body."""
    from app.models import User

    password = "Password123!"
    res = client.post("/auth/signup", json={"email": "hash_user@example.com", "password": password})
    assert res.status_code == 201
    assert password not in res.text
    assert "password" not in res.json()

    user = db_session.query(User).filter(User.email == "hash_user@example.com").first()
    assert user.hashed_password != password
    assert user.hashed_password.startswith("$2")  # bcrypt


def test_refresh_returns_a_usable_new_access_token(client):
    tokens = _signup_and_login(client)

    res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    refreshed = res.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {refreshed['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "token_user@example.com"


def test_refresh_rejects_an_access_token(client):
    """Access and refresh tokens are not interchangeable.

    Accepting an access token here would let a leaked short-lived token be
    traded for indefinite access.
    """
    tokens = _signup_and_login(client, email="swap_user@example.com")

    res = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert res.status_code == 401


def test_refresh_rejects_a_garbage_token(client):
    res = client.post("/auth/refresh", json={"refresh_token": "not.a.real.token"})
    assert res.status_code == 401


def test_the_refresh_token_is_not_accepted_in_the_query_string(client):
    """A refresh token lives for days, so it must not end up in a URL — access
    logs, proxy logs, browser history and Referer headers all keep those."""
    tokens = _signup_and_login(client, email="query_user@example.com")

    res = client.post("/auth/refresh", params={"refresh_token": tokens["refresh_token"]})

    assert res.status_code == 422


def test_a_tampered_access_token_is_rejected(client):
    """Flipping the payload must invalidate the signature."""
    tokens = _signup_and_login(client, email="tamper_user@example.com")
    header, payload, signature = tokens["access_token"].split(".")
    # Deterministic: pick a tail the signature does not already end with.
    tail = "BBBB" if signature.endswith("AAAA") else "AAAA"
    forged = f"{header}.{payload}.{signature[:-4]}{tail}"
    assert forged != tokens["access_token"]

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


def test_a_token_for_a_deleted_user_is_rejected(client, db_session):
    from app.models import User

    tokens = _signup_and_login(client, email="ghost_user@example.com")
    db_session.query(User).filter(User.email == "ghost_user@example.com").delete()
    db_session.commit()

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert res.status_code == 401


def test_login_is_rate_limited_against_brute_force(client):
    """Requirement 7 — password guessing must not be free."""
    from app.core.config import settings

    allowed = int(settings.RATE_LIMIT_LOGIN.split("/")[0])
    client.post("/auth/signup", json={"email": "brute@example.com", "password": "Password123!"})

    statuses = [
        client.post("/auth/login", json={"email": "brute@example.com", "password": "WrongPassword1!"}).status_code
        for _ in range(allowed + 1)
    ]

    assert statuses[:allowed] == [401] * allowed
    assert statuses[allowed] == 429


def test_signup_is_rate_limited(client):
    from app.core.config import settings

    allowed = int(settings.RATE_LIMIT_SIGNUP.split("/")[0])
    statuses = [
        client.post("/auth/signup", json={"email": f"flood{i}@example.com", "password": "Password123!"}).status_code
        for i in range(allowed + 1)
    ]

    assert statuses[allowed] == 429
