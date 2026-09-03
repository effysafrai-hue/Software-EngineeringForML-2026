import os
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Chat tests exercise the real Ollama tool-calling path. The first call also
# pays for loading the model, and a reschedule costs three round-trips
# (list_events, update_event, final answer). Override per-run with
# OLLAMA_TIMEOUT if your host is slower or faster.
os.environ.setdefault("OLLAMA_TIMEOUT", "300.0")

from app.main import app
from app.db.session import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.core.limiter import reset_rate_limits as _reset_rate_limits
from app.models.user import User

# In-memory SQLite for high-speed, isolated test execution
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_addoption(parser):
    """Named subsets of the suite, on top of the default "run everything"."""
    group = parser.getgroup("ai", "AI / LLM test selection")
    group.addoption(
        "--ai-only",
        action="store_true",
        default=False,
        help="Run only tests that call a real LLM (marked live_llm).",
    )
    group.addoption(
        "--no-ai",
        action="store_true",
        default=False,
        help="Skip tests that call a real LLM: deterministic, offline, no provider quota.",
    )


def pytest_collection_modifyitems(config, items):
    ai_only = config.getoption("--ai-only")
    no_ai = config.getoption("--no-ai")

    if ai_only and no_ai:
        raise pytest.UsageError("--ai-only and --no-ai cannot be used together.")
    if not (ai_only or no_ai):
        return  # default: run everything

    # Deselect rather than skip, so the summary reports a count instead of
    # padding the output with one skip line per excluded test.
    selected, deselected = [], []
    for item in items:
        is_ai = item.get_closest_marker("live_llm") is not None
        keep = is_ai if ai_only else not is_ai
        (selected if keep else deselected).append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset SlowAPI rate limit storage before and after each test.

    Limits are keyed per user, so without this the posts one test creates would
    eat into the budget of every later test using the same account.
    """
    _reset_rate_limits()
    yield
    _reset_rate_limits()


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        # Seed test users
        user_a = User(
            id=1,
            email="user_a@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        user_b = User(
            id=2,
            email="user_b@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        user_c = User(
            id=3,
            email="user_c@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        session.add_all([user_a, user_b, user_c])
        session.commit()

        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers_user_a():
    token = create_access_token(subject="1")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b():
    token = create_access_token(subject="2")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_c():
    token = create_access_token(subject="3")
    return {"Authorization": f"Bearer {token}"}
