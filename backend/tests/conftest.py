import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models import User, Event, ChatMessage

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.state.limiter.enabled = False

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    app.state.limiter.enabled = True


@pytest.fixture(scope="function")
def auth_headers_user_a(client):
    client.post(
        "/auth/signup",
        json={"email": "usera@example.com", "password": "Password123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "usera@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def auth_headers_user_b(client):
    client.post(
        "/auth/signup",
        json={"email": "userb@example.com", "password": "Password123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "userb@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
