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


def test_shared_memory_created_via_chat_visible_to_other_member(client, auth_headers_user_a, auth_headers_user_b):
    """
    Test that a shared memory/preference created via shared chat by User A
    is persisted and visible to User B of the same shared calendar.
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
