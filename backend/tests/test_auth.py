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
