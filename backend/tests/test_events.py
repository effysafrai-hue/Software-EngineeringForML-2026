from datetime import datetime, timezone, timedelta
import pytest
from app.models.event import Event


def test_create_event(client, auth_headers_user_a):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)
    payload = {
        "title": "Dentist Appointment",
        "description": "Routine checkup",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }
    response = client.post("/events", json=payload, headers=auth_headers_user_a)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Dentist Appointment"
    assert data["user_id"] == 1


def test_list_events(client, auth_headers_user_a):
    response = client.get("/events", headers=auth_headers_user_a)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_update_event(client, auth_headers_user_a, db_session):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)
    event = Event(
        user_id=1,
        title="Old Title",
        start_time=start,
        end_time=end,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    response = client.patch(
        f"/events/{event.id}",
        json={"title": "Updated Title"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


def test_delete_event(client, auth_headers_user_a, db_session):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)
    event = Event(
        user_id=1,
        title="To Delete",
        start_time=start,
        end_time=end,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    response = client.delete(f"/events/{event.id}", headers=auth_headers_user_a)
    assert response.status_code == 204

    get_resp = client.get(f"/events/{event.id}", headers=auth_headers_user_a)
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Requirement 1.4 — manual calendar editing, and the isolation it depends on
# ---------------------------------------------------------------------------


def _make_event(db_session, user_id=1, title="Owned event"):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    event = Event(user_id=user_id, title=title, start_time=start, end_time=start + timedelta(hours=1))
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def test_get_single_event(client, auth_headers_user_a, db_session):
    event = _make_event(db_session, title="Dentist")

    res = client.get(f"/events/{event.id}", headers=auth_headers_user_a)
    assert res.status_code == 200
    assert res.json()["title"] == "Dentist"
    assert res.json()["id"] == event.id


def test_get_missing_event_is_404(client, auth_headers_user_a):
    assert client.get("/events/99999", headers=auth_headers_user_a).status_code == 404


def test_another_users_event_is_invisible_and_unmodifiable(
    client, auth_headers_user_b, db_session
):
    """User B must not read, edit or delete user A's private event.

    404 rather than 403 on purpose: a 403 would confirm the event exists.
    """
    event = _make_event(db_session, user_id=1, title="A's private appointment")

    assert client.get(f"/events/{event.id}", headers=auth_headers_user_b).status_code == 404
    assert (
        client.patch(
            f"/events/{event.id}", json={"title": "Hijacked"}, headers=auth_headers_user_b
        ).status_code
        == 404
    )
    assert client.delete(f"/events/{event.id}", headers=auth_headers_user_b).status_code == 404

    db_session.refresh(event)
    assert event.title == "A's private appointment"


def test_list_events_only_returns_your_own(client, auth_headers_user_b, db_session):
    _make_event(db_session, user_id=1, title="A's event")
    _make_event(db_session, user_id=2, title="B's event")

    res = client.get("/events", headers=auth_headers_user_b)
    assert res.status_code == 200
    assert [e["title"] for e in res.json()] == ["B's event"]


def test_create_event_rejects_a_backwards_range(client, auth_headers_user_a):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    res = client.post(
        "/events",
        json={
            "title": "Time travel",
            "start_time": start.isoformat(),
            "end_time": (start - timedelta(hours=1)).isoformat(),
        },
        headers=auth_headers_user_a,
    )
    assert res.status_code == 422


def test_events_require_authentication(client):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    body = {
        "title": "Uninvited",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=1)).isoformat(),
    }
    assert client.get("/events").status_code == 401
    # A valid body, so a 401 here is about auth and not about validation.
    assert client.post("/events", json=body).status_code == 401
