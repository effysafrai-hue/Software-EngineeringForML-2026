from datetime import datetime, timezone, timedelta
import pytest
from app.models import Event, ChatMessage, SharedCalendar, SharedCalendarMember, SharedMemory


def test_create_and_list_shared_calendar(client, auth_headers_user_a, auth_headers_user_b):
    """Test creating a shared calendar and verifying only members list it."""
    # User A creates a calendar
    res = client.post(
        "/shared-calendars",
        json={"name": "Machine Learning Study Group"},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201
    cal_data = res.json()
    assert cal_data["name"] == "Machine Learning Study Group"
    cal_id = cal_data["id"]

    # User A lists their calendars -> sees it
    res_a = client.get("/shared-calendars", headers=auth_headers_user_a)
    assert res_a.status_code == 200
    assert any(c["id"] == cal_id for c in res_a.json())

    # User B lists their calendars -> does not see it yet
    res_b = client.get("/shared-calendars", headers=auth_headers_user_b)
    assert res_b.status_code == 200
    assert not any(c["id"] == cal_id for c in res_b.json())


def test_add_member_and_access_details(client, auth_headers_user_a, auth_headers_user_b):
    """Test inviting a user to a shared calendar."""
    # 1. User A creates calendar
    res = client.post(
        "/shared-calendars",
        json={"name": "SE Project Team"},
        headers=auth_headers_user_a,
    )
    cal_id = res.json()["id"]

    # 2. User A invites User B by email
    add_res = client.post(
        f"/shared-calendars/{cal_id}/members",
        json={"email": "user_b@example.com", "role": "member"},
        headers=auth_headers_user_a,
    )
    assert add_res.status_code == 201

    # 3. User B can now access calendar details
    details_b = client.get(f"/shared-calendars/{cal_id}", headers=auth_headers_user_b)
    assert details_b.status_code == 200
    data = details_b.json()
    assert len(data["members"]) == 2
    assert any(m["email"] == "user_b@example.com" for m in data["members"])


def test_non_member_gets_403_forbidden(client, auth_headers_user_a, auth_headers_user_c):
    """Test non-members (User C) are rejected with 403 Forbidden on all calendar resources."""
    # User A creates calendar
    res = client.post(
        "/shared-calendars",
        json={"name": "Confidential Research"},
        headers=auth_headers_user_a,
    )
    cal_id = res.json()["id"]

    # User C (non-member) tries to get details -> 403
    res_get = client.get(f"/shared-calendars/{cal_id}", headers=auth_headers_user_c)
    assert res_get.status_code == 403

    # User C tries to list events -> 403
    res_events = client.get(f"/shared-calendars/{cal_id}/events", headers=auth_headers_user_c)
    assert res_events.status_code == 403

    # User C tries to create event -> 403
    start = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    res_create = client.post(
        f"/shared-calendars/{cal_id}/events",
        json={
            "title": "Hacked Meeting",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
        },
        headers=auth_headers_user_c,
    )
    assert res_create.status_code == 403

    # User C tries to view memories -> 403
    res_mem = client.get(f"/shared-calendars/{cal_id}/memories", headers=auth_headers_user_c)
    assert res_mem.status_code == 403

    # User C tries to send shared chat -> 403
    res_chat = client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "Hello?"},
        headers=auth_headers_user_c,
    )
    assert res_chat.status_code == 403

    # User C tries to read the shared chat history -> 403
    res_hist = client.get(f"/shared-calendars/{cal_id}/chat/history", headers=auth_headers_user_c)
    assert res_hist.status_code == 403

    # And the calendar never shows up in their own list.
    res_list = client.get("/shared-calendars", headers=auth_headers_user_c)
    assert res_list.status_code == 200
    assert all(c["id"] != cal_id for c in res_list.json())


def test_shared_events_crud_by_any_member(client, auth_headers_user_a, auth_headers_user_b):
    """Test that any member of a shared calendar can create, update, and delete shared events."""
    # User A creates calendar and adds User B
    cal_res = client.post(
        "/shared-calendars",
        json={"name": "Sprint Squad"},
        headers=auth_headers_user_a,
    )
    cal_id = cal_res.json()["id"]
    client.post(
        f"/shared-calendars/{cal_id}/members",
        json={"email": "user_b@example.com"},
        headers=auth_headers_user_a,
    )

    # User A creates a shared event
    start = datetime(2026, 9, 2, 14, 0, 0, tzinfo=timezone.utc)
    ev_res = client.post(
        f"/shared-calendars/{cal_id}/events",
        json={
            "title": "Sprint Kickoff",
            "description": "Planning Q4",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
        },
        headers=auth_headers_user_a,
    )
    assert ev_res.status_code == 201
    ev_id = ev_res.json()["id"]

    # User B lists events -> sees Sprint Kickoff
    list_b = client.get(f"/shared-calendars/{cal_id}/events", headers=auth_headers_user_b)
    assert list_b.status_code == 200
    assert any(e["id"] == ev_id for e in list_b.json())

    # User B updates the event title
    update_b = client.patch(
        f"/shared-calendars/{cal_id}/events/{ev_id}",
        json={"title": "Sprint Kickoff & Roadmap"},
        headers=auth_headers_user_b,
    )
    assert update_b.status_code == 200
    assert update_b.json()["title"] == "Sprint Kickoff & Roadmap"

    # User B deletes the event
    del_b = client.delete(f"/shared-calendars/{cal_id}/events/{ev_id}", headers=auth_headers_user_b)
    assert del_b.status_code == 204

    # Verification: event is gone
    final_list = client.get(f"/shared-calendars/{cal_id}/events", headers=auth_headers_user_a)
    assert len(final_list.json()) == 0


@pytest.mark.live_llm
def test_shared_memory_created_via_chat_visible_to_other_member(client, auth_headers_user_a, auth_headers_user_b):
    """
    Test that a shared memory/preference created via shared chat by User A
    is persisted and visible to User B of the same shared calendar.

    Calls the real model, so it is excluded from the default run. The same
    behaviour is asserted deterministically in the stubbed tests below.
    """
    # 1. User A creates calendar and adds User B
    cal_res = client.post(
        "/shared-calendars",
        json={"name": "Weekly Study Group"},
        headers=auth_headers_user_a,
    )
    cal_id = cal_res.json()["id"]
    client.post(
        f"/shared-calendars/{cal_id}/members",
        json={"email": "user_b@example.com"},
        headers=auth_headers_user_a,
    )

    # 2. User A uses the shared chat to establish a group memory
    chat_prompt = "Remember that this group meets Tuesdays, avoid scheduling then"
    chat_res = client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": chat_prompt},
        headers=auth_headers_user_a,
    )
    assert chat_res.status_code == 200

    # 3. User B queries shared memories -> sees the group rule created by User A
    mem_res_b = client.get(f"/shared-calendars/{cal_id}/memories", headers=auth_headers_user_b)
    assert mem_res_b.status_code == 200
    memories = mem_res_b.json()
    assert len(memories) >= 1
    assert any("meets tuesdays" in m["content"].lower() or "avoid scheduling" in m["content"].lower() for m in memories)

    # 4. User B checks shared chat history -> sees User A's message and the assistant's reply
    hist_b = client.get(f"/shared-calendars/{cal_id}/chat/history", headers=auth_headers_user_b)
    assert hist_b.status_code == 200
    history = hist_b.json()
    assert len(history) >= 2
    assert history[0]["role"] == "user"
    assert "meets tuesdays" in history[0]["content"].lower()


# ---------------------------------------------------------------------------
# Requirements 4.3 / 4.4 / 4.5, asserted without the model.
#
# The memory extraction and the shared-chat bookkeeping around the AI call are
# ordinary deterministic code, so they belong in the default suite. Only the
# model's own judgement needs a live run.
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_shared_llm(monkeypatch):
    """Canned assistant reply, recording the prompt the route assembled."""
    seen = []

    def fake_process_chat(message, user_id, db, reference_time=None, timezone_name=None):
        seen.append(message)
        return {"reply": "Understood, noted for the group.", "action_taken": None}

    monkeypatch.setattr("app.api.routes.shared_calendars.process_chat", fake_process_chat)
    return seen


def _calendar_with_both_members(client, auth_headers_user_a, name="Study Group"):
    cal_id = client.post("/shared-calendars", json={"name": name}, headers=auth_headers_user_a).json()["id"]
    client.post(
        f"/shared-calendars/{cal_id}/members",
        json={"email": "user_b@example.com"},
        headers=auth_headers_user_a,
    )
    return cal_id


def test_shared_memory_is_extracted_and_visible_to_the_other_member(
    client, auth_headers_user_a, auth_headers_user_b, stub_shared_llm
):
    """Requirement 4.4 — the shared calendar keeps its own long-term memory."""
    cal_id = _calendar_with_both_members(client, auth_headers_user_a)

    res = client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "Remember that this group meets Tuesdays, avoid scheduling then"},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200

    memories = client.get(f"/shared-calendars/{cal_id}/memories", headers=auth_headers_user_b).json()
    assert len(memories) == 1
    # The "Remember that" prefix is stripped before storing.
    assert memories[0]["content"].lower().startswith("this group meets tuesdays")


def test_stored_memory_is_fed_back_into_the_next_prompt(
    client, auth_headers_user_a, stub_shared_llm
):
    """Requirement 4.4 — the memory must actually reach the model, not just sit in a table."""
    cal_id = _calendar_with_both_members(client, auth_headers_user_a)

    client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "Remember that this group meets Tuesdays, avoid scheduling then"},
        headers=auth_headers_user_a,
    )
    client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "When should we do the review?"},
        headers=auth_headers_user_a,
    )

    second_prompt = stub_shared_llm[1]
    assert "When should we do the review?" in second_prompt
    assert "SHARED GROUP MEMORIES" in second_prompt
    assert "meets Tuesdays" in second_prompt


def test_ordinary_chat_does_not_create_a_memory(client, auth_headers_user_a, stub_shared_llm):
    """Only preference-shaped messages become durable group rules."""
    cal_id = _calendar_with_both_members(client, auth_headers_user_a)

    client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "What time is the lecture?"},
        headers=auth_headers_user_a,
    )

    assert client.get(f"/shared-calendars/{cal_id}/memories", headers=auth_headers_user_a).json() == []


def test_shared_chat_history_is_shared_between_members(
    client, auth_headers_user_a, auth_headers_user_b, stub_shared_llm
):
    """Requirement 4.5 — the chat itself is shared, not per-user."""
    cal_id = _calendar_with_both_members(client, auth_headers_user_a)

    client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "A asks the group something"},
        headers=auth_headers_user_a,
    )
    client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "B answers in the same thread"},
        headers=auth_headers_user_b,
    )

    for headers in (auth_headers_user_a, auth_headers_user_b):
        history = client.get(f"/shared-calendars/{cal_id}/chat/history", headers=headers).json()
        assert [m["content"] for m in history] == [
            "A asks the group something",
            "Understood, noted for the group.",
            "B answers in the same thread",
            "Understood, noted for the group.",
        ]


def test_shared_chat_stays_out_of_the_personal_chat_history(
    client, auth_headers_user_a, stub_shared_llm
):
    """A group conversation must not leak into the user's private /chat/history."""
    cal_id = _calendar_with_both_members(client, auth_headers_user_a)
    client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "Group-only planning message"},
        headers=auth_headers_user_a,
    )

    personal = client.get("/chat/history", headers=auth_headers_user_a)
    assert personal.status_code == 200
    assert personal.json() == []


def test_an_event_created_through_shared_chat_lands_on_the_shared_calendar(
    client, auth_headers_user_a, auth_headers_user_b, monkeypatch, db_session
):
    """Requirement 4.3 — a user's own chat can add tasks to the shared calendar."""
    cal_id = _calendar_with_both_members(client, auth_headers_user_a)

    def fake_process_chat(message, user_id, db, reference_time=None, timezone_name=None):
        # Stand in for the model's create_event tool call.
        start = datetime(2026, 7, 2, 9, 0, 0, tzinfo=timezone.utc)
        db.add(Event(user_id=user_id, title="Group revision session", start_time=start, end_time=start + timedelta(hours=1)))
        db.commit()
        return {"reply": "Added it to the group calendar.", "action_taken": "create_event"}

    monkeypatch.setattr("app.api.routes.shared_calendars.process_chat", fake_process_chat)

    res = client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "Book a group revision session on Thursday morning"},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200
    assert res.json()["action_taken"] == "create_event"

    # Requirement 4.2 — the other member sees it.
    events_b = client.get(f"/shared-calendars/{cal_id}/events", headers=auth_headers_user_b).json()
    assert [e["title"] for e in events_b] == ["Group revision session"]

    event = db_session.query(Event).filter(Event.title == "Group revision session").first()
    assert event.shared_calendar_id == cal_id


def test_shared_chat_reports_an_unavailable_model_as_503(client, auth_headers_user_a, monkeypatch):
    from app.services.ai_agent import LLMUnavailableError

    cal_id = _calendar_with_both_members(client, auth_headers_user_a)

    def broken(message, user_id, db, reference_time=None, timezone_name=None):
        raise LLMUnavailableError("model is not reachable")

    monkeypatch.setattr("app.api.routes.shared_calendars.process_chat", broken)

    res = client.post(
        f"/shared-calendars/{cal_id}/chat", json={"message": "Hello"}, headers=auth_headers_user_a
    )
    assert res.status_code == 503
