"""The /chat HTTP surface: persistence, history and failure handling.

`tests/test_chat.py` drives `process_chat` directly against a live model and so
covers the AI's behaviour. Nothing covered the route around it — that it stores
both sides of the exchange, that history is per-user, and that an unavailable
model surfaces as 503 rather than a 500. Those are deterministic, so the model
is stubbed here and these tests run in milliseconds.
"""

import pytest

from app.models import ChatMessage
from app.services.ai_agent import LLMUnavailableError


@pytest.fixture
def stub_llm(monkeypatch):
    """Replace the model call with a canned reply, recording what it was asked."""
    seen = []

    def fake_process_chat(message, user_id, db, reference_time=None, timezone_name=None):
        seen.append({"message": message, "user_id": user_id})
        return {"reply": f"Noted: {message}", "action_taken": "create_event"}

    monkeypatch.setattr("app.api.routes.chat.process_chat", fake_process_chat)
    return seen


@pytest.fixture
def broken_llm(monkeypatch):
    def fake_process_chat(message, user_id, db, reference_time=None, timezone_name=None):
        raise LLMUnavailableError("model is not reachable")

    monkeypatch.setattr("app.api.routes.chat.process_chat", fake_process_chat)


def test_chat_returns_the_reply_and_the_action(client, auth_headers_user_a, stub_llm):
    res = client.post("/chat", json={"message": "Remind me to water the plant"}, headers=auth_headers_user_a)

    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "Noted: Remind me to water the plant"
    assert body["action_taken"] == "create_event"
    assert stub_llm[0]["user_id"] == 1


def test_chat_persists_both_sides_of_the_exchange(client, auth_headers_user_a, stub_llm, db_session):
    """Requirement 6.10 — chats must be saved."""
    client.post("/chat", json={"message": "What is on today?"}, headers=auth_headers_user_a)

    rows = db_session.query(ChatMessage).filter(ChatMessage.user_id == 1).order_by(ChatMessage.id.asc()).all()
    assert [r.role for r in rows] == ["user", "assistant"]
    assert rows[0].content == "What is on today?"
    assert rows[1].content == "Noted: What is on today?"


def test_chat_history_is_retrievable_in_order(client, auth_headers_user_a, stub_llm):
    """Requirement 6.10 — saved chats must be retrievable."""
    client.post("/chat", json={"message": "First question"}, headers=auth_headers_user_a)
    client.post("/chat", json={"message": "Second question"}, headers=auth_headers_user_a)

    res = client.get("/chat/history", headers=auth_headers_user_a)
    assert res.status_code == 200
    history = res.json()

    assert [m["content"] for m in history] == [
        "First question",
        "Noted: First question",
        "Second question",
        "Noted: Second question",
    ]
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]


def test_chat_history_is_private_to_its_owner(client, auth_headers_user_a, auth_headers_user_b, stub_llm):
    client.post("/chat", json={"message": "My private planning note"}, headers=auth_headers_user_a)

    res = client.get("/chat/history", headers=auth_headers_user_b)
    assert res.status_code == 200
    assert res.json() == []
    assert "private planning note" not in res.text


def test_empty_chat_message_is_rejected(client, auth_headers_user_a, stub_llm, db_session):
    res = client.post("/chat", json={"message": "   "}, headers=auth_headers_user_a)

    assert res.status_code == 422
    # A rejected message must not be stored.
    assert db_session.query(ChatMessage).count() == 0
    assert stub_llm == []


def test_an_unavailable_model_surfaces_as_503(client, auth_headers_user_a, broken_llm):
    """The chat path has no offline fallback, so it must fail loudly, not silently."""
    res = client.post("/chat", json={"message": "Schedule something"}, headers=auth_headers_user_a)

    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()


def test_chat_requires_authentication(client):
    res = client.post("/chat", json={"message": "Hello"})
    assert res.status_code == 401


def test_chat_history_requires_authentication(client):
    res = client.get("/chat/history")
    assert res.status_code == 401
