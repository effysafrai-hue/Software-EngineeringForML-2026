from datetime import datetime, timezone, timedelta


def test_create_event_success(client, auth_headers_user_a):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    payload = {
        "title": "Machine Learning Architecture Review",
        "description": "Discussing LLM integration and model inference pipeline",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }

    response = client.post("/events", json=payload, headers=auth_headers_user_a)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert "id" in data
    assert "user_id" in data


def test_create_event_invalid_times(client, auth_headers_user_a):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start - timedelta(hours=1)

    payload = {
        "title": "Invalid Meeting",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }

    response = client.post("/events", json=payload, headers=auth_headers_user_a)
    assert response.status_code == 422


def test_list_events_with_date_range_filter(client, auth_headers_user_a):
    now = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

    e1_payload = {
        "title": "Event June 1",
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(hours=1)).isoformat(),
    }
    e2_payload = {
        "title": "Event June 5",
        "start_time": (now + timedelta(days=4)).isoformat(),
        "end_time": (now + timedelta(days=4, hours=1)).isoformat(),
    }
    e3_payload = {
        "title": "Event June 10",
        "start_time": (now + timedelta(days=9)).isoformat(),
        "end_time": (now + timedelta(days=9, hours=1)).isoformat(),
    }

    client.post("/events", json=e1_payload, headers=auth_headers_user_a)
    client.post("/events", json=e2_payload, headers=auth_headers_user_a)
    client.post("/events", json=e3_payload, headers=auth_headers_user_a)

    filter_start = (now + timedelta(days=3)).isoformat()
    filter_end = (now + timedelta(days=5)).isoformat()

    response = client.get(
        "/events",
        params={"start_time": filter_start, "end_time": filter_end},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["title"] == "Event June 5"


def test_update_event_success(client, auth_headers_user_a):
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=1)

    create_resp = client.post(
        "/events",
        json={
            "title": "Initial Title",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=auth_headers_user_a,
    )
    event_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/events/{event_id}",
        json={"title": "Updated Title", "description": "Added description"},
        headers=auth_headers_user_a,
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Added description"


def test_cannot_access_or_edit_another_users_event(
    client, auth_headers_user_a, auth_headers_user_b
):
    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=1)

    create_resp = client.post(
        "/events",
        json={
            "title": "User A Private Planning",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=auth_headers_user_a,
    )
    event_id = create_resp.json()["id"]

    get_resp = client.get(f"/events/{event_id}", headers=auth_headers_user_b)
    assert get_resp.status_code == 403
    assert "permission" in get_resp.json()["detail"].lower()

    patch_resp = client.patch(
        f"/events/{event_id}",
        json={"title": "Hacked Title"},
        headers=auth_headers_user_b,
    )
    assert patch_resp.status_code == 403

    delete_resp = client.delete(f"/events/{event_id}", headers=auth_headers_user_b)
    assert delete_resp.status_code == 403


def test_delete_event_success(client, auth_headers_user_a):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)

    create_resp = client.post(
        "/events",
        json={
            "title": "Temporary Event",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=auth_headers_user_a,
    )
    event_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/events/{event_id}", headers=auth_headers_user_a)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/events/{event_id}", headers=auth_headers_user_a)
    assert get_resp.status_code == 404
