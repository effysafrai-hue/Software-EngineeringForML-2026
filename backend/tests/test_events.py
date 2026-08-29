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
