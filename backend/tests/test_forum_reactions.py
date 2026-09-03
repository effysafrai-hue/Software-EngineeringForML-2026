from datetime import datetime, timezone, timedelta

from app.models import Event, Notification, Reaction


def _create_post(client, headers, title="Reaction target", body="Body text here."):
    res = client.post(
        "/posts",
        json={"title": title, "body": body, "media_urls": [], "anonymous": False},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_like_then_switch_to_dislike_replaces_the_reaction(
    client, auth_headers_user_a, auth_headers_user_b, db_session
):
    """One reaction per user per item: changing your mind updates, never accumulates."""
    post_id = _create_post(client, auth_headers_user_a)

    liked = client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_b)
    assert liked.status_code == 200
    assert liked.json() == {"like_count": 1, "dislike_count": 0, "my_reaction": "like"}

    switched = client.put(f"/posts/{post_id}/reactions", json={"value": "dislike"}, headers=auth_headers_user_b)
    assert switched.status_code == 200
    assert switched.json() == {"like_count": 0, "dislike_count": 1, "my_reaction": "dislike"}

    # One row, not two.
    rows = db_session.query(Reaction).filter(Reaction.post_id == post_id).all()
    assert len(rows) == 1
    assert rows[0].value == "dislike"


def test_repeating_the_same_reaction_is_idempotent(client, auth_headers_user_a, auth_headers_user_b, db_session):
    """A double-tapped button must not double-count."""
    post_id = _create_post(client, auth_headers_user_a)

    for _ in range(3):
        res = client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_b)
        assert res.status_code == 200
        assert res.json()["like_count"] == 1

    assert db_session.query(Reaction).filter(Reaction.post_id == post_id).count() == 1


def test_clearing_a_reaction_removes_it(client, auth_headers_user_a, auth_headers_user_b, db_session):
    post_id = _create_post(client, auth_headers_user_a)
    client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_b)

    cleared = client.delete(f"/posts/{post_id}/reactions", headers=auth_headers_user_b)
    assert cleared.status_code == 200
    assert cleared.json() == {"like_count": 0, "dislike_count": 0, "my_reaction": None}
    assert db_session.query(Reaction).filter(Reaction.post_id == post_id).count() == 0


def test_reaction_counts_are_shared_but_my_reaction_is_per_viewer(
    client, auth_headers_user_a, auth_headers_user_b, auth_headers_user_c
):
    """Counts aggregate everyone; my_reaction reflects only the caller."""
    post_id = _create_post(client, auth_headers_user_a)
    client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_b)
    client.put(f"/posts/{post_id}/reactions", json={"value": "dislike"}, headers=auth_headers_user_c)

    as_b = client.get(f"/posts/{post_id}", headers=auth_headers_user_b).json()
    as_c = client.get(f"/posts/{post_id}", headers=auth_headers_user_c).json()
    as_a = client.get(f"/posts/{post_id}", headers=auth_headers_user_a).json()

    for view in (as_a, as_b, as_c):
        assert view["like_count"] == 1
        assert view["dislike_count"] == 1

    assert as_b["my_reaction"] == "like"
    assert as_c["my_reaction"] == "dislike"
    assert as_a["my_reaction"] is None


def test_comment_reactions_are_counted_separately_from_the_post(
    client, auth_headers_user_a, auth_headers_user_b
):
    post_id = _create_post(client, auth_headers_user_a)
    comment_id = client.post(
        f"/posts/{post_id}/comments",
        json={"body": "Useful tip here.", "anonymous": False},
        headers=auth_headers_user_b,
    ).json()["id"]

    client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_b)
    res = client.put(f"/comments/{comment_id}/reactions", json={"value": "like"}, headers=auth_headers_user_a)
    assert res.status_code == 200
    assert res.json()["like_count"] == 1

    detail = client.get(f"/posts/{post_id}", headers=auth_headers_user_a).json()
    assert detail["like_count"] == 1
    assert detail["comments"][0]["like_count"] == 1
    assert detail["comments"][0]["my_reaction"] == "like"


def test_my_posts_reports_totals_received(client, auth_headers_user_a, auth_headers_user_b, auth_headers_user_c):
    """The author's own view aggregates likes/dislikes across all their posts."""
    first = _create_post(client, auth_headers_user_a, title="First post")
    second = _create_post(client, auth_headers_user_a, title="Second post")
    # A post by somebody else must not land in user A's totals.
    other = _create_post(client, auth_headers_user_b, title="Not mine")

    client.put(f"/posts/{first}/reactions", json={"value": "like"}, headers=auth_headers_user_b)
    client.put(f"/posts/{first}/reactions", json={"value": "like"}, headers=auth_headers_user_c)
    client.put(f"/posts/{second}/reactions", json={"value": "dislike"}, headers=auth_headers_user_b)
    client.put(f"/posts/{other}/reactions", json={"value": "like"}, headers=auth_headers_user_a)

    res = client.get("/posts/mine", headers=auth_headers_user_a)
    assert res.status_code == 200
    data = res.json()

    assert data["post_count"] == 2
    assert data["total_likes"] == 2
    assert data["total_dislikes"] == 1
    assert {p["title"] for p in data["posts"]} == {"First post", "Second post"}


def test_my_posts_route_is_not_swallowed_by_the_post_id_route(client, auth_headers_user_a):
    """/posts/mine must resolve to the listing, not be parsed as post_id='mine'."""
    res = client.get("/posts/mine", headers=auth_headers_user_a)
    assert res.status_code == 200
    assert "posts" in res.json()


def test_share_post_as_event_creates_it_on_the_callers_calendar(
    client, auth_headers_user_a, auth_headers_user_b, db_session
):
    """The event belongs to whoever clicks, not to the post's author."""
    post_id = _create_post(client, auth_headers_user_a, title="Guest lecture on compilers")
    start = datetime(2026, 7, 1, 14, 0, 0, tzinfo=timezone.utc)

    res = client.post(
        f"/posts/{post_id}/share-as-event",
        json={"start_time": start.isoformat()},
        headers=auth_headers_user_b,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["user_id"] == 2
    assert data["title"] == "Guest lecture on compilers"
    assert f"forum post #{post_id}" in data["description"]

    event = db_session.query(Event).filter(Event.id == data["id"]).first()
    assert event is not None
    assert event.user_id == 2
    # No end given -> one hour, matching the assistant's default.
    assert (event.end_time - event.start_time) == timedelta(hours=1)

    # The author's own calendar is untouched.
    assert db_session.query(Event).filter(Event.user_id == 1).count() == 0


def test_share_post_as_event_rejects_a_backwards_range(client, auth_headers_user_a):
    post_id = _create_post(client, auth_headers_user_a)
    start = datetime(2026, 7, 1, 14, 0, 0, tzinfo=timezone.utc)

    res = client.post(
        f"/posts/{post_id}/share-as-event",
        json={"start_time": start.isoformat(), "end_time": (start - timedelta(hours=1)).isoformat()},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 400
    assert "strictly after" in res.json()["detail"]


def test_reacting_to_a_missing_post_is_404(client, auth_headers_user_a):
    res = client.put("/posts/99999/reactions", json={"value": "like"}, headers=auth_headers_user_a)
    assert res.status_code == 404


def test_commenting_notifies_the_post_author_only(client, auth_headers_user_a, auth_headers_user_b, db_session):
    """The author gets a notification; the commenter does not notify themselves."""
    post_id = _create_post(client, auth_headers_user_a, title="Anyone free Friday?")
    client.post(
        f"/posts/{post_id}/comments",
        json={"body": "I am!", "anonymous": False},
        headers=auth_headers_user_b,
    )

    for_author = db_session.query(Notification).filter(Notification.user_id == 1).all()
    assert len(for_author) == 1
    assert "Anyone free Friday?" in for_author[0].message

    # Author commenting on their own post creates nothing new.
    client.post(
        f"/posts/{post_id}/comments",
        json={"body": "Bumping this.", "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert db_session.query(Notification).filter(Notification.user_id == 1).count() == 1
