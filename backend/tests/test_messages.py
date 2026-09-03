from app.models import Message, Notification

SECRET_BODY = "Meet me by the fountain at six, do not tell anyone."


def _send(client, headers, receiver_id, body):
    return client.post("/messages", json={"receiver_id": receiver_id, "body": body}, headers=headers)


def test_send_and_read_a_conversation(client, auth_headers_user_a, auth_headers_user_b):
    sent = _send(client, auth_headers_user_a, 2, "Hey, did you get the lab notes?")
    assert sent.status_code == 201, sent.text
    data = sent.json()
    assert data["sender_id"] == 1
    assert data["receiver_id"] == 2
    assert data["read"] is False

    _send(client, auth_headers_user_b, 1, "Yes — sending them over now.")

    # Both parties see the same thread, oldest first.
    as_a = client.get("/messages/2", headers=auth_headers_user_a).json()
    as_b = client.get("/messages/1", headers=auth_headers_user_b).json()

    assert [m["body"] for m in as_a["messages"]] == [
        "Hey, did you get the lab notes?",
        "Yes — sending them over now.",
    ]
    assert [m["body"] for m in as_b["messages"]] == [m["body"] for m in as_a["messages"]]
    assert as_a["peer_id"] == 2
    assert as_a["peer_email"] == "user_b@example.com"


def test_a_dm_is_invisible_to_a_third_user(
    client, auth_headers_user_a, auth_headers_user_b, auth_headers_user_c, db_session
):
    """User C must not be able to reach the A<->B thread from any angle."""
    sent = _send(client, auth_headers_user_a, 2, SECRET_BODY)
    assert sent.status_code == 201
    message_id = sent.json()["id"]

    # The message exists.
    assert db_session.query(Message).filter(Message.id == message_id).first() is not None

    # C asking for their conversation with A sees nothing, and no leaked body.
    with_a = client.get("/messages/1", headers=auth_headers_user_c)
    assert with_a.status_code == 200
    assert with_a.json()["messages"] == []
    assert SECRET_BODY not in with_a.text

    # C asking for their conversation with B likewise.
    with_b = client.get("/messages/2", headers=auth_headers_user_c)
    assert with_b.status_code == 200
    assert with_b.json()["messages"] == []
    assert SECRET_BODY not in with_b.text

    # C cannot mark someone else's thread read either.
    marked = client.post("/messages/1/read", headers=auth_headers_user_c)
    assert marked.status_code == 200
    assert marked.json()["updated"] == 0
    db_session.expire_all()
    assert db_session.query(Message).filter(Message.id == message_id).first().read is False

    # And the two real parties still see it.
    assert SECRET_BODY in client.get("/messages/2", headers=auth_headers_user_a).text
    assert SECRET_BODY in client.get("/messages/1", headers=auth_headers_user_b).text


def test_unread_count_and_marking_a_conversation_read(client, auth_headers_user_a, auth_headers_user_b, db_session):
    _send(client, auth_headers_user_a, 2, "First")
    _send(client, auth_headers_user_a, 2, "Second")

    convo = client.get("/messages/1", headers=auth_headers_user_b).json()
    assert convo["unread_count"] == 2

    # Reading is idempotent: the GET above must not have cleared anything.
    assert client.get("/messages/1", headers=auth_headers_user_b).json()["unread_count"] == 2

    marked = client.post("/messages/1/read", headers=auth_headers_user_b)
    assert marked.status_code == 200
    assert marked.json()["updated"] == 2

    assert client.get("/messages/1", headers=auth_headers_user_b).json()["unread_count"] == 0
    # The sender's own view of their outgoing messages is unaffected by unread state.
    assert client.get("/messages/2", headers=auth_headers_user_a).json()["unread_count"] == 0


def test_receiving_a_dm_creates_a_notification_for_the_recipient_only(
    client, auth_headers_user_a, db_session
):
    _send(client, auth_headers_user_a, 2, "Quick question about the assignment.")

    for_receiver = db_session.query(Notification).filter(Notification.user_id == 2).all()
    assert len(for_receiver) == 1
    assert "user_a@example.com" in for_receiver[0].message
    assert for_receiver[0].read is False

    assert db_session.query(Notification).filter(Notification.user_id == 1).count() == 0


def test_cannot_message_yourself(client, auth_headers_user_a):
    res = _send(client, auth_headers_user_a, 1, "Talking to myself.")
    assert res.status_code == 400
    assert "yourself" in res.json()["detail"]


def test_cannot_message_a_user_that_does_not_exist(client, auth_headers_user_a):
    res = _send(client, auth_headers_user_a, 4242, "Hello?")
    assert res.status_code == 404
    assert "Recipient not found" in res.json()["detail"]


def test_dm_body_is_sanitized(client, auth_headers_user_a, db_session):
    res = _send(client, auth_headers_user_a, 2, "<script>steal(document.cookie)</script>Hi there")
    assert res.status_code == 201
    body = res.json()["body"]
    assert "script" not in body.lower()
    assert "steal" not in body
    assert "Hi there" in body


def test_dm_rejects_media_urls_that_did_not_come_from_our_uploads(client, auth_headers_user_a):
    res = client.post(
        "/messages",
        json={"receiver_id": 2, "body": "Look at this", "media_urls": ["https://evil.example/x.png"]},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 400
    assert "Invalid media reference" in res.json()["detail"]
