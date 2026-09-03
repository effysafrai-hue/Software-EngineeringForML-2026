import io
import pytest
from app.models.forum import Post, Comment


def test_create_regular_post_shows_author(client, auth_headers_user_a):
    """Creating a non-anonymous post exposes author_id and author_email."""
    payload = {
        "title": "Study Group for CS101",
        "body": "Looking for study partners for the midterm!",
        "media_urls": [],
        "anonymous": False,
    }
    res = client.post("/posts", json=payload, headers=auth_headers_user_a)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Study Group for CS101"
    assert data["anonymous"] is False
    assert data["author_id"] == 1
    assert data["author_email"] == "user_a@example.com"


def test_create_anonymous_post_never_leaks_author(client, auth_headers_user_a, auth_headers_user_b):
    """Anonymous post must never expose author_id or author_email in creation, feed list, or detail endpoints."""
    payload = {
        "title": "Confession: I haven't started project 3",
        "body": "Is anyone else struggling with the autograder?",
        "media_urls": [],
        "anonymous": True,
    }
    # 1. User A creates anonymously
    res_create = client.post("/posts", json=payload, headers=auth_headers_user_a)
    assert res_create.status_code == 201
    create_data = res_create.json()
    assert create_data["anonymous"] is True
    assert create_data["author_id"] is None
    assert create_data["author_email"] is None
    assert "user_a" not in res_create.text

    post_id = create_data["id"]

    # 2. User B lists posts feed -> author is masked
    res_list = client.get("/posts", headers=auth_headers_user_b)
    assert res_list.status_code == 200
    feed = res_list.json()
    anon_post = next((p for p in feed if p["id"] == post_id), None)
    assert anon_post is not None
    assert anon_post["anonymous"] is True
    assert anon_post["author_id"] is None
    assert anon_post["author_email"] is None

    # 3. User B views post details -> author is masked
    res_detail = client.get(f"/posts/{post_id}", headers=auth_headers_user_b)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["anonymous"] is True
    assert detail["author_id"] is None
    assert detail["author_email"] is None
    assert "user_a" not in res_detail.text


def test_create_anonymous_comment_never_leaks_author(client, auth_headers_user_a, auth_headers_user_b):
    """Anonymous comments must never leak author identity."""
    # User A creates post
    post_res = client.post(
        "/posts",
        json={"title": "Midterm Advice", "body": "Any tips?", "anonymous": False},
        headers=auth_headers_user_a,
    )
    post_id = post_res.json()["id"]

    # User B comments anonymously
    comment_res = client.post(
        f"/posts/{post_id}/comments",
        json={"body": "Focus on the recursion problems!", "anonymous": True},
        headers=auth_headers_user_b,
    )
    assert comment_res.status_code == 201
    c_data = comment_res.json()
    assert c_data["anonymous"] is True
    assert c_data["author_id"] is None
    assert c_data["author_email"] is None
    assert "user_b" not in comment_res.text

    # User A fetches post detail -> comment author is masked
    detail_res = client.get(f"/posts/{post_id}", headers=auth_headers_user_a)
    assert detail_res.status_code == 200
    comments = detail_res.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["anonymous"] is True
    assert comments[0]["author_id"] is None
    assert comments[0]["author_email"] is None
    assert "user_b" not in detail_res.text


def test_file_upload_valid_image(client, auth_headers_user_a):
    """Uploading a valid PNG image succeeds and returns file URL."""
    fake_png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"fakepngbytes"
    files = {"file": ("diagram.png", io.BytesIO(fake_png_data), "image/png")}

    res = client.post("/uploads", files=files, headers=auth_headers_user_a)
    assert res.status_code == 201
    data = res.json()
    assert "url" in data
    assert data["url"].startswith("/uploads/")
    assert data["content_type"] == "image/png"
    assert data["category"] == "image"


def test_file_upload_invalid_type_rejected(client, auth_headers_user_a):
    """Uploading executable or unsupported file returns 400 Bad Request."""
    fake_exe = b"MZ\x90\x00" + b"maliciousbytes"
    files = {"file": ("malware.exe", io.BytesIO(fake_exe), "application/x-msdownload")}

    res = client.post("/uploads", files=files, headers=auth_headers_user_a)
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_file_upload_size_limit_exceeded(client, auth_headers_user_a):
    """Uploading an image larger than 10MB is rejected with 400."""
    oversized_data = b"0" * (10 * 1024 * 1024 + 1024)  # 10MB + 1KB
    files = {"file": ("huge_photo.jpg", io.BytesIO(oversized_data), "image/jpeg")}

    res = client.post("/uploads", files=files, headers=auth_headers_user_a)
    assert res.status_code == 400
    assert "exceeds maximum allowed limit" in res.json()["detail"]


def test_delete_post_author_vs_non_author(client, auth_headers_user_a, auth_headers_user_b):
    """Only the author of a post can delete it; other users receive 403 Forbidden."""
    post_res = client.post(
        "/posts",
        json={"title": "Private Note", "body": "Do not delete", "anonymous": False},
        headers=auth_headers_user_a,
    )
    post_id = post_res.json()["id"]

    # User B attempts delete -> 403
    del_b = client.delete(f"/posts/{post_id}", headers=auth_headers_user_b)
    assert del_b.status_code == 403

    # User A deletes -> 204
    del_a = client.delete(f"/posts/{post_id}", headers=auth_headers_user_a)
    assert del_a.status_code == 204

    # Now post is gone -> 404
    get_res = client.get(f"/posts/{post_id}", headers=auth_headers_user_a)
    assert get_res.status_code == 404


# ---------------------------------------------------------------------------
# Requirements 6.1 / 6.3 / 6.5 — video attachments, comment media, comment
# deletion and feed search, none of which were covered.
# ---------------------------------------------------------------------------


def _upload(client, headers, name, data, content_type):
    res = client.post("/uploads", files={"file": (name, io.BytesIO(data), content_type)}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_file_upload_valid_video(client, auth_headers_user_a):
    """Videos are an explicit requirement, and they take a different size cap."""
    fake_mp4 = b"\x00\x00\x00\x20ftypisom" + b"fakevideobytes"
    data = _upload(client, auth_headers_user_a, "lecture.mp4", fake_mp4, "video/mp4")

    assert data["category"] == "video"
    assert data["content_type"] == "video/mp4"
    assert data["url"].startswith("/uploads/")
    assert data["url"].endswith(".mp4")


def test_post_can_carry_an_image_and_a_video(client, auth_headers_user_a):
    image = _upload(client, auth_headers_user_a, "d.png", b"\x89PNG\r\n\x1a\nx", "image/png")["url"]
    video = _upload(client, auth_headers_user_a, "c.webm", b"\x1a\x45\xdf\xa3x", "video/webm")["url"]

    res = client.post(
        "/posts",
        json={
            "title": "Project demo",
            "body": "Screenshot and a clip.",
            "media_urls": [image, video],
            "anonymous": False,
        },
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201
    assert res.json()["media_urls"] == [image, video]

    detail = client.get(f"/posts/{res.json()['id']}", headers=auth_headers_user_a).json()
    assert detail["media_urls"] == [image, video]


def test_comment_can_carry_media(client, auth_headers_user_a, auth_headers_user_b):
    post_id = client.post(
        "/posts", json={"title": "Show your setup", "body": "Post a photo", "anonymous": False},
        headers=auth_headers_user_a,
    ).json()["id"]
    image = _upload(client, auth_headers_user_b, "setup.jpg", b"\xff\xd8\xffx", "image/jpeg")["url"]

    res = client.post(
        f"/posts/{post_id}/comments",
        json={"body": "Here's mine", "media_urls": [image], "anonymous": False},
        headers=auth_headers_user_b,
    )
    assert res.status_code == 201
    assert res.json()["media_urls"] == [image]


def test_delete_comment_author_vs_non_author(client, auth_headers_user_a, auth_headers_user_b):
    """Only the comment's author may remove it — the post's author may not."""
    post_id = client.post(
        "/posts", json={"title": "Thread", "body": "Discuss", "anonymous": False},
        headers=auth_headers_user_a,
    ).json()["id"]
    comment_id = client.post(
        f"/posts/{post_id}/comments",
        json={"body": "B's comment", "anonymous": False},
        headers=auth_headers_user_b,
    ).json()["id"]

    # The post owner is still not the comment's author.
    assert client.delete(f"/comments/{comment_id}", headers=auth_headers_user_a).status_code == 403
    assert client.delete(f"/comments/{comment_id}", headers=auth_headers_user_b).status_code == 204

    detail = client.get(f"/posts/{post_id}", headers=auth_headers_user_a).json()
    assert detail["comments"] == []
    assert detail["comment_count"] == 0


def test_deleting_a_missing_comment_is_404(client, auth_headers_user_a):
    assert client.delete("/comments/99999", headers=auth_headers_user_a).status_code == 404


def test_deleting_a_post_removes_its_comments(client, auth_headers_user_a, auth_headers_user_b, db_session):
    post_id = client.post(
        "/posts", json={"title": "Temporary", "body": "Gone soon", "anonymous": False},
        headers=auth_headers_user_a,
    ).json()["id"]
    client.post(
        f"/posts/{post_id}/comments", json={"body": "A reply", "anonymous": False},
        headers=auth_headers_user_b,
    )

    assert client.delete(f"/posts/{post_id}", headers=auth_headers_user_a).status_code == 204
    assert db_session.query(Comment).filter(Comment.post_id == post_id).count() == 0


def test_feed_search_matches_title_and_body(client, auth_headers_user_a):
    client.post(
        "/posts", json={"title": "Linear algebra help", "body": "Struggling with matrices", "anonymous": False},
        headers=auth_headers_user_a,
    )
    client.post(
        "/posts", json={"title": "Cafeteria hours", "body": "Closes at seven", "anonymous": False},
        headers=auth_headers_user_a,
    )

    by_title = client.get("/posts?search=algebra", headers=auth_headers_user_a).json()
    assert [p["title"] for p in by_title] == ["Linear algebra help"]

    by_body = client.get("/posts?search=seven", headers=auth_headers_user_a).json()
    assert [p["title"] for p in by_body] == ["Cafeteria hours"]

    assert client.get("/posts?search=nothingmatches", headers=auth_headers_user_a).json() == []


def test_feed_is_newest_first_and_paginates(client, auth_headers_user_a):
    for i in range(5):
        client.post(
            "/posts", json={"title": f"Post {i}", "body": "Body", "anonymous": False},
            headers=auth_headers_user_a,
        )

    page = client.get("/posts?limit=2&offset=0", headers=auth_headers_user_a).json()
    assert [p["title"] for p in page] == ["Post 4", "Post 3"]

    second = client.get("/posts?limit=2&offset=2", headers=auth_headers_user_a).json()
    assert [p["title"] for p in second] == ["Post 2", "Post 1"]


def test_forum_requires_authentication(client):
    assert client.get("/posts").status_code == 401
    assert client.post("/posts", json={"title": "x", "body": "y"}).status_code == 401
