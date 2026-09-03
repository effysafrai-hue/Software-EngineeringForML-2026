"""Requirement 6.9 — the forum ships with content instead of an empty page."""

from app.db.seed_forum import DEMO_USERS, seed_forum_data
from app.models import Comment, Message, Post, Reaction, User


def test_seeding_creates_users_posts_and_comments(db_session):
    tally = seed_forum_data(db_session)

    assert tally["users"] == len(DEMO_USERS)
    assert tally["posts"] >= 3
    assert tally["comments"] >= 3

    # The demo accounts are real, usable users.
    for spec in DEMO_USERS:
        user = db_session.query(User).filter(User.email == spec["email"]).first()
        assert user is not None
        assert user.hashed_password and user.hashed_password != "DemoPassword123!"

    assert db_session.query(Post).count() == tally["posts"]
    assert db_session.query(Comment).count() >= 3


def test_seeded_posts_have_titles_bodies_and_authors(db_session):
    seed_forum_data(db_session)

    for post in db_session.query(Post).all():
        assert post.title.strip()
        assert post.body.strip()
        assert post.user_id is not None
        assert post.created_at is not None

    # At least one anonymous post, so the masking path has demo content too.
    assert db_session.query(Post).filter(Post.anonymous == True).count() >= 1  # noqa: E712


def test_seeding_gives_the_feed_reactions_and_a_dm_thread(db_session):
    seed_forum_data(db_session)

    assert db_session.query(Reaction).count() >= 1
    assert db_session.query(Message).count() >= 1

    # Every seeded reaction targets exactly one item, as the schema requires.
    for reaction in db_session.query(Reaction).all():
        assert (reaction.post_id is None) != (reaction.comment_id is None)
        assert reaction.value in ("like", "dislike")


def test_seeding_twice_adds_nothing(db_session):
    """It is run on deploy, so a second run must not duplicate the forum."""
    first = seed_forum_data(db_session)
    assert first["posts"] > 0

    counts_after_first = (
        db_session.query(User).count(),
        db_session.query(Post).count(),
        db_session.query(Comment).count(),
        db_session.query(Reaction).count(),
        db_session.query(Message).count(),
    )

    second = seed_forum_data(db_session)

    assert second == {"users": 0, "posts": 0, "comments": 0, "reactions": 0, "messages": 0}
    assert (
        db_session.query(User).count(),
        db_session.query(Post).count(),
        db_session.query(Comment).count(),
        db_session.query(Reaction).count(),
        db_session.query(Message).count(),
    ) == counts_after_first


def test_seeded_content_is_visible_through_the_api(client, auth_headers_user_a, db_session):
    """Cold content has to actually show up in the feed a first visitor loads."""
    seed_forum_data(db_session)

    res = client.get("/posts", headers=auth_headers_user_a)
    assert res.status_code == 200
    feed = res.json()
    assert len(feed) >= 3

    # Newest first, and the anonymous demo post is masked to a reader.
    timestamps = [p["created_at"] for p in feed]
    assert timestamps == sorted(timestamps, reverse=True)
    for post in feed:
        if post["anonymous"]:
            assert post["author_id"] is None
            assert post["author_email"] is None
