"""Spam, abuse and injection protections on user-generated forum content."""

import io

import pytest

from app.core.config import settings
from app.core.limiter import reset_rate_limits
from app.models import Post


def _limit_count(spec: str) -> int:
    """"5/minute" -> 5."""
    return int(spec.split("/")[0].strip())


def test_rate_limit_reset_actually_clears_storage():
    """Guards the other tests in this file.

    Every case here depends on the autouse reset in conftest genuinely emptying
    slowapi's counters. If the attribute it reaches for ever disappears, the
    reset silently becomes a no-op and the rate-limit tests start failing for
    the wrong reason — so assert the reset reports success.
    """
    assert reset_rate_limits() is True


def test_post_rate_limit_kicks_in_after_the_configured_burst(client, auth_headers_user_a, db_session):
    """The (N+1)th rapid post is refused with 429, and is not written."""
    allowed = _limit_count(settings.RATE_LIMIT_POST)

    for i in range(allowed):
        res = client.post(
            "/posts",
            json={"title": f"Rapid post {i}", "body": "Body text.", "anonymous": False},
            headers=auth_headers_user_a,
        )
        assert res.status_code == 201, f"request {i + 1} should have been allowed: {res.text}"

    blocked = client.post(
        "/posts",
        json={"title": "One too many", "body": "Body text.", "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert blocked.status_code == 429

    # The refused request left nothing behind.
    assert db_session.query(Post).count() == allowed
    assert db_session.query(Post).filter(Post.title == "One too many").first() is None


def test_comment_rate_limit_kicks_in(client, auth_headers_user_a, auth_headers_user_b):
    allowed = _limit_count(settings.RATE_LIMIT_COMMENT)
    post_id = client.post(
        "/posts",
        json={"title": "Comment target", "body": "Discuss.", "anonymous": False},
        headers=auth_headers_user_a,
    ).json()["id"]

    for i in range(allowed):
        res = client.post(
            f"/posts/{post_id}/comments",
            json={"body": f"Comment {i}", "anonymous": False},
            headers=auth_headers_user_b,
        )
        assert res.status_code == 201, f"request {i + 1} should have been allowed: {res.text}"

    blocked = client.post(
        f"/posts/{post_id}/comments",
        json={"body": "Spam", "anonymous": False},
        headers=auth_headers_user_b,
    )
    assert blocked.status_code == 429


def test_message_rate_limit_kicks_in(client, auth_headers_user_a):
    allowed = _limit_count(settings.RATE_LIMIT_MESSAGE)

    for i in range(allowed):
        res = client.post("/messages", json={"receiver_id": 2, "body": f"Ping {i}"}, headers=auth_headers_user_a)
        assert res.status_code == 201, f"request {i + 1} should have been allowed: {res.text}"

    blocked = client.post("/messages", json={"receiver_id": 2, "body": "Ping again"}, headers=auth_headers_user_a)
    assert blocked.status_code == 429


def test_rate_limit_is_per_user_not_per_connection(client, auth_headers_user_a, auth_headers_user_b):
    """User A exhausting their budget must not lock user B out.

    Both users hit the API from the same test client address, so an IP-keyed
    limiter would fail this.
    """
    allowed = _limit_count(settings.RATE_LIMIT_POST)

    for i in range(allowed):
        client.post(
            "/posts",
            json={"title": f"A's post {i}", "body": "Body.", "anonymous": False},
            headers=auth_headers_user_a,
        )
    assert (
        client.post(
            "/posts", json={"title": "A blocked", "body": "Body.", "anonymous": False}, headers=auth_headers_user_a
        ).status_code
        == 429
    )

    b_res = client.post(
        "/posts", json={"title": "B's first post", "body": "Body.", "anonymous": False}, headers=auth_headers_user_b
    )
    assert b_res.status_code == 201


def test_oversized_upload_is_rejected_server_side(client, auth_headers_user_a, monkeypatch):
    """The size cap lives on the server, not only in the frontend.

    The limit is patched down instead of pushing 10MB through the test client so
    the check is exercised in milliseconds; `test_file_upload_size_limit_exceeded`
    in test_forum.py covers the real 10MB boundary.
    """
    monkeypatch.setattr("app.services.upload_service.MAX_IMAGE_SIZE", 1024)

    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * 4096
    files = {"file": ("big.png", io.BytesIO(oversized), "image/png")}

    res = client.post("/uploads", files=files, headers=auth_headers_user_a)
    assert res.status_code == 400
    assert "exceeds maximum allowed limit" in res.json()["detail"]


def test_oversized_upload_leaves_no_partial_file_on_disk(client, auth_headers_user_a, monkeypatch, tmp_path):
    """A rejected upload must not leave the bytes it already streamed behind."""
    monkeypatch.setattr("app.services.upload_service.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.upload_service.MAX_IMAGE_SIZE", 1024)

    files = {"file": ("big.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 8192), "image/png")}
    res = client.post("/uploads", files=files, headers=auth_headers_user_a)

    assert res.status_code == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "hostile_body, must_not_contain",
    [
        ("<script>alert('xss')</script>Hello there", ["script", "alert"]),
        ("<img src=x onerror=alert(1)>Caption", ["onerror", "<img"]),
        ("<iframe src='//evil.tld'></iframe>Read this", ["iframe", "evil.tld"]),
        ("<svg/onload=alert(1)>Diagram", ["svg", "onload"]),
    ],
)
def test_post_body_is_sanitized_against_xss(client, auth_headers_user_a, hostile_body, must_not_contain):
    res = client.post(
        "/posts",
        json={"title": "Harmless title", "body": hostile_body, "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201, res.text
    stored = res.json()["body"].lower()
    for fragment in must_not_contain:
        assert fragment.lower() not in stored


def test_sanitizer_keeps_ordinary_text_intact(client, auth_headers_user_a):
    """Stripping markup must not mangle normal writing."""
    body = "Is a < b the same as b > a? I read 'JavaScript: The Good Parts' and I'm still unsure."
    res = client.post(
        "/posts",
        json={"title": "Comparison operators", "body": body, "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201
    stored = res.json()["body"]
    assert "JavaScript: The Good Parts" in stored
    assert "Is a < b" in stored


def test_javascript_uri_is_neutralised(client, auth_headers_user_a):
    res = client.post(
        "/posts",
        json={"title": "Click here", "body": "Go to javascript:alert(document.cookie) now", "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201
    assert "javascript:alert" not in res.json()["body"]
    assert "[blocked]" in res.json()["body"]


def test_a_body_that_is_only_markup_is_rejected(client, auth_headers_user_a):
    res = client.post(
        "/posts",
        json={"title": "Nothing to see", "body": "<script>alert(1)</script>", "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 400
    assert "empty after removing markup" in res.json()["detail"]


def test_media_urls_must_reference_our_own_uploads(client, auth_headers_user_a):
    """media_urls is client-supplied, so it cannot be trusted as a render source."""
    for hostile in ["https://evil.example/x.png", "//evil.example/x.png", "/uploads/../../etc/passwd", "javascript:alert(1)"]:
        res = client.post(
            "/posts",
            json={"title": "With media", "body": "Look", "media_urls": [hostile], "anonymous": False},
            headers=auth_headers_user_a,
        )
        assert res.status_code == 400, f"{hostile!r} should have been refused"
        assert "Invalid media reference" in res.json()["detail"]


def test_media_urls_from_the_upload_endpoint_are_accepted(client, auth_headers_user_a):
    upload = client.post(
        "/uploads",
        files={"file": ("photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\nsmall"), "image/png")},
        headers=auth_headers_user_a,
    )
    assert upload.status_code == 201
    url = upload.json()["url"]

    res = client.post(
        "/posts",
        json={"title": "With media", "body": "Look at this", "media_urls": [url], "anonymous": False},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201
    assert res.json()["media_urls"] == [url]
