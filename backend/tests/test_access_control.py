"""Access control across the whole API — requirements 1.1 and 7.

Per-resource ownership already has its own coverage (`test_events.py`,
`test_notifications.py`, `test_forum.py`, `test_messages.py`,
`test_shared_calendars.py`, `test_user_memory.py`). What was missing, and is
covered here, is the part that no single feature's tests would catch:

* every route that should need a token actually needs one, enumerated from the
  live OpenAPI schema rather than from a hand-written list that goes stale the
  next time a router is added;
* the two token types are not interchangeable in either direction; and
* the WebSocket, whose credential arrives in the query string because a browser
  cannot set a header on a handshake, is checked to the same standard as a
  bearer token.
"""

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, create_refresh_token
from app.models import User

# Deliberately reachable without a token, each for a stated reason.
PUBLIC_ROUTES = {
    ("POST", "/auth/signup"),      # creating the account that gets the token
    ("POST", "/auth/login"),       # obtaining the token
    ("POST", "/auth/refresh"),     # renewing it; authenticated by the token in the body
    ("GET", "/health"),            # liveness probe, no data
    ("GET", "/memory/questions"),  # the sign-up form renders these before an account exists
    ("GET", "/memory/categories"),  # static labels for the same form
}

# Docs and the schema itself are FastAPI's own, and carry no user data.
_SCHEMA_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/uploads")

# A body that is structurally wrong for every route, so a 422 can never be
# mistaken for "the request was accepted". Auth runs before validation, so an
# unauthenticated call must still answer 401.
_JUNK_BODY = {"__not_a_real_field__": "x"}


def _protected_routes(app):
    """Every (method, path) in the app that is not on the public list."""
    routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not methods or path.startswith(_SCHEMA_PREFIXES):
            continue
        for method in sorted(methods - {"HEAD", "OPTIONS"}):
            if (method, path) not in PUBLIC_ROUTES:
                routes.append((method, path))
    return sorted(set(routes))


def test_every_protected_route_requires_a_token(client):
    """Enumerated from the app itself, so a new router cannot quietly ship open."""
    from app.main import app

    routes = _protected_routes(app)
    assert len(routes) > 25, "route discovery found suspiciously few routes"

    unprotected = []
    for method, path in routes:
        # Path parameters are filled with an id that exists for nobody: auth is
        # checked before the row is looked up, so the answer must still be 401.
        concrete = path.replace("{event_id}", "1").replace("{post_id}", "1")
        concrete = concrete.replace("{comment_id}", "1").replace("{memory_id}", "1")
        concrete = concrete.replace("{calendar_id}", "1").replace("{notification_id}", "1")
        concrete = concrete.replace("{other_user_id}", "2")

        res = client.request(method, concrete, json=_JUNK_BODY)
        if res.status_code != 401:
            unprotected.append((method, concrete, res.status_code))

    assert unprotected == []


def test_the_public_routes_are_the_ones_we_meant(client):
    """The other half of the check above: this list is the whole exception set."""
    from app.main import app

    discovered = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if path.startswith(_SCHEMA_PREFIXES):
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            if (method, path) in PUBLIC_ROUTES:
                discovered.add((method, path))

    # Every entry on the list is a route that still exists, so the list cannot
    # rot into permitting something that was renamed.
    assert discovered == PUBLIC_ROUTES


# ---------------------------------------------------------------------------
# The two token types are not interchangeable
# ---------------------------------------------------------------------------


def test_a_refresh_token_is_not_accepted_as_a_bearer_token(client):
    """A refresh token is signed, valid and lasts days rather than minutes.

    It is only meant to be traded in at /auth/refresh. If it also worked as a
    bearer credential, a leaked one would grant the whole API for its entire
    lifetime — so this is checked on a route that reads data, not just on /me.
    """
    refresh = create_refresh_token(subject="1")

    for path in ("/auth/me", "/events", "/memory", "/chat/history", "/notifications"):
        res = client.get(path, headers={"Authorization": f"Bearer {refresh}"})
        assert res.status_code == 401, f"{path} accepted a refresh token"


def test_an_access_token_is_still_accepted_everywhere_it_should_be(client, auth_headers_user_a):
    """The mirror of the test above: tightening the check must not lock out the
    credential the app actually issues."""
    for path in ("/auth/me", "/events", "/memory", "/chat/history", "/notifications"):
        assert client.get(path, headers=auth_headers_user_a).status_code == 200, path


def test_a_token_with_no_type_claim_is_rejected(client):
    """Tokens minted before the type claim existed must not be grandfathered in."""
    from jose import jwt

    from app.core.config import settings

    legacy = jwt.encode(
        {"sub": "1", "exp": 9_999_999_999},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 401


def test_a_token_signed_with_the_wrong_secret_is_rejected(client):
    from jose import jwt

    forged = jwt.encode({"sub": "1", "type": "access", "exp": 9_999_999_999}, "not-our-secret", algorithm="HS256")

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# ---------------------------------------------------------------------------
# The notification WebSocket
# ---------------------------------------------------------------------------


def _ws_url(token: str) -> str:
    return f"/ws/notifications?token={token}"


def test_the_websocket_accepts_a_valid_access_token(client, db_session):
    with client.websocket_connect(_ws_url(create_access_token(subject="1"))) as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


@pytest.mark.parametrize(
    "token_factory,reason",
    [
        (lambda: "not.a.real.token", "garbage"),
        (lambda: create_refresh_token(subject="1"), "a refresh token"),
        (lambda: create_access_token(subject="4242"), "a token for a user that does not exist"),
    ],
)
def test_the_websocket_refuses_anything_but_a_live_users_access_token(
    client, db_session, token_factory, reason
):
    """Everything pushed over this socket is addressed to one user, so the
    handshake credential is held to the same standard as a bearer token."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(_ws_url(token_factory())) as ws:
            ws.receive_text()


def test_a_deleted_users_socket_is_refused(client, db_session):
    """The token stays cryptographically valid until it expires; the account is
    gone, so the socket must not be registered under its id."""
    token = create_access_token(subject="3")
    db_session.query(User).filter(User.id == 3).delete()
    db_session.commit()

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(_ws_url(token)) as ws:
            ws.receive_text()


def test_the_websocket_requires_a_token_at_all(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/notifications") as ws:
            ws.receive_text()
