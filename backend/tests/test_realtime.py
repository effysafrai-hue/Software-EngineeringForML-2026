"""Requirement 6.10 — live forum/DM updates without a page refresh.

Two layers are covered separately:

* `ConnectionManager` routing, driven directly with stub sockets, so "who
  receives which frame" is asserted without any event-loop plumbing; and
* the routes, with the `realtime` helpers replaced by recording spies, so
  "which frames does this endpoint emit, and to whom" is asserted without
  waiting on a real socket (a missed push would otherwise hang the suite).
"""

import pytest

from app.services import realtime
from app.services.ws_manager import ConnectionManager


class StubSocket:
    """Stands in for a WebSocket. Records what was sent; can be made to fail."""

    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    async def send_json(self, data):
        if self.fail:
            raise RuntimeError("socket is gone")
        self.sent.append(data)


@pytest.fixture
def spy_realtime(monkeypatch):
    """Replace the realtime helpers with recorders.

    `notify_user` is deliberately left alone so it still writes its Notification
    row; its WebSocket side is captured through `push_to_user`, which it calls
    by module global.
    """
    calls = {"push": [], "broadcast": []}

    def fake_push(user_id, payload):
        calls["push"].append((user_id, payload))

    def fake_broadcast(payload, exclude_user_id=None):
        calls["broadcast"].append((payload, exclude_user_id))

    monkeypatch.setattr("app.services.realtime.push_to_user", fake_push)
    monkeypatch.setattr("app.services.realtime.broadcast", fake_broadcast)
    return calls


# --------------------------------------------------------------------------
# ConnectionManager routing
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_to_user_reaches_only_that_user():
    manager = ConnectionManager()
    alice, bob = StubSocket(), StubSocket()
    manager.active_connections = {1: [alice], 2: [bob]}

    await manager.send_to_user(1, {"type": "test", "n": 1})

    assert alice.sent == [{"type": "test", "n": 1}]
    assert bob.sent == []


@pytest.mark.asyncio
async def test_send_to_user_fans_out_to_every_tab_of_that_user():
    manager = ConnectionManager()
    tab_one, tab_two = StubSocket(), StubSocket()
    manager.active_connections = {1: [tab_one, tab_two]}

    await manager.send_to_user(1, {"type": "test"})

    assert tab_one.sent == [{"type": "test"}]
    assert tab_two.sent == [{"type": "test"}]


@pytest.mark.asyncio
async def test_send_to_an_unconnected_user_is_a_no_op():
    manager = ConnectionManager()
    manager.active_connections = {}
    await manager.send_to_user(99, {"type": "test"})  # must not raise


@pytest.mark.asyncio
async def test_broadcast_reaches_everyone_except_the_excluded_user():
    manager = ConnectionManager()
    alice, bob, carol = StubSocket(), StubSocket(), StubSocket()
    manager.active_connections = {1: [alice], 2: [bob], 3: [carol]}

    await manager.broadcast({"type": "forum.post.created"}, exclude_user_id=2)

    assert alice.sent == [{"type": "forum.post.created"}]
    assert carol.sent == [{"type": "forum.post.created"}]
    assert bob.sent == []


@pytest.mark.asyncio
async def test_a_dead_socket_is_dropped_and_does_not_block_the_others():
    manager = ConnectionManager()
    dead, alive = StubSocket(fail=True), StubSocket()
    manager.active_connections = {1: [dead, alive]}

    await manager.send_to_user(1, {"type": "test"})

    assert alive.sent == [{"type": "test"}]
    assert manager.active_connections[1] == [alive]


@pytest.mark.asyncio
async def test_dropping_the_last_socket_removes_the_user_entry():
    manager = ConnectionManager()
    dead = StubSocket(fail=True)
    manager.active_connections = {1: [dead]}

    await manager.send_to_user(1, {"type": "test"})

    assert 1 not in manager.active_connections


def test_dispatch_without_a_bound_loop_does_not_raise():
    """Scripts and unit tests have no loop; the push is dropped, not exploded."""
    manager = ConnectionManager()
    manager.active_connections = {1: [StubSocket()]}
    manager.send_to_user_sync(1, {"type": "test"})
    manager.broadcast_sync({"type": "test"})


# --------------------------------------------------------------------------
# Which frames the routes emit
# --------------------------------------------------------------------------


def _create_post(client, headers, title="Live post", body="Body."):
    res = client.post(
        "/posts", json={"title": title, "body": body, "anonymous": False}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_new_post_is_broadcast_to_everyone_but_the_author(client, auth_headers_user_a, spy_realtime):
    _create_post(client, auth_headers_user_a, title="Fresh news")

    assert len(spy_realtime["broadcast"]) == 1
    payload, exclude = spy_realtime["broadcast"][0]
    assert payload["type"] == realtime.EVENT_NEW_POST
    assert payload["post"]["title"] == "Fresh news"
    assert exclude == 1


def test_new_comment_is_broadcast_and_notifies_the_author(
    client, auth_headers_user_a, auth_headers_user_b, spy_realtime
):
    post_id = _create_post(client, auth_headers_user_a, title="Question")
    client.post(
        f"/posts/{post_id}/comments",
        json={"body": "An answer", "anonymous": False},
        headers=auth_headers_user_b,
    )

    comment_frames = [p for p, _ in spy_realtime["broadcast"] if p["type"] == realtime.EVENT_NEW_COMMENT]
    assert len(comment_frames) == 1
    assert comment_frames[0]["post_id"] == post_id
    assert comment_frames[0]["comment"]["body"] == "An answer"

    # notify_user ran for real and pushed to the post's author, not the commenter.
    pushed_to = [user_id for user_id, _ in spy_realtime["push"]]
    assert pushed_to == [1]


def test_the_broadcast_frame_for_an_anonymous_comment_does_not_leak_the_author(
    client, auth_headers_user_a, auth_headers_user_b, spy_realtime
):
    """The live frame must mask identity exactly as the REST response does."""
    post_id = _create_post(client, auth_headers_user_a)
    client.post(
        f"/posts/{post_id}/comments",
        json={"body": "Anonymous thought", "anonymous": True},
        headers=auth_headers_user_b,
    )

    frame = next(p for p, _ in spy_realtime["broadcast"] if p["type"] == realtime.EVENT_NEW_COMMENT)
    assert frame["comment"]["anonymous"] is True
    assert frame["comment"]["author_id"] is None
    assert frame["comment"]["author_email"] is None
    assert "user_b" not in str(frame)


def test_reaction_frames_carry_counts_but_never_a_per_viewer_field(
    client, auth_headers_user_a, auth_headers_user_b, spy_realtime
):
    """my_reaction is per-viewer, so broadcasting it would be wrong for everyone else."""
    post_id = _create_post(client, auth_headers_user_a)
    client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_b)

    frame = next(p for p, _ in spy_realtime["broadcast"] if p["type"] == realtime.EVENT_REACTION)
    assert frame["like_count"] == 1
    assert frame["dislike_count"] == 0
    assert "my_reaction" not in frame


def test_a_direct_message_is_never_broadcast(client, auth_headers_user_a, spy_realtime):
    """The security property behind requirement 6.5.

    A DM must reach the two parties and nobody else. Broadcasting one would put
    private text on every open socket, so assert the broadcast channel stays
    untouched and the pushes are addressed.
    """
    res = client.post(
        "/messages", json={"receiver_id": 2, "body": "Private plans"}, headers=auth_headers_user_a
    )
    assert res.status_code == 201

    assert spy_realtime["broadcast"] == []

    pushed_to = sorted(user_id for user_id, _ in spy_realtime["push"])
    assert pushed_to == [1, 2]
    for _, payload in spy_realtime["push"]:
        assert payload["type"] == realtime.EVENT_NEW_MESSAGE
        assert payload["message_data"]["body"] == "Private plans"


def test_notify_user_does_not_notify_the_actor(client, auth_headers_user_a, spy_realtime, db_session):
    """Reacting to your own post produces neither a row nor a push."""
    from app.models import Notification

    post_id = _create_post(client, auth_headers_user_a)
    client.put(f"/posts/{post_id}/reactions", json={"value": "like"}, headers=auth_headers_user_a)

    assert spy_realtime["push"] == []
    assert db_session.query(Notification).count() == 0
