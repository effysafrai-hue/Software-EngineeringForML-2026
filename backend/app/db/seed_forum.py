"""Cold-start seed for the forum.

An empty forum gives a first visitor nothing to react to, so this creates a
handful of demo accounts and a small thread of realistic posts, comments and
reactions. Idempotent: it keys off the demo email addresses and the post titles,
so re-running it adds nothing.

Run once after migrations:

    docker compose exec backend python -m app.db.seed_forum
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.forum import Comment, Post, Reaction, REACTION_DISLIKE, REACTION_LIKE
from app.models.message import Message
from app.models.user import User

logger = logging.getLogger("seed_forum")
logger.setLevel(logging.INFO)

# Shared by every demo account. These are sample accounts for a local forum that
# would otherwise be empty; do not seed them into a deployment reachable from
# outside, and change the password if you do.
DEMO_PASSWORD = "DemoPassword123!"

DEMO_USERS = [
    {"key": "maya", "email": "maya.demo@campus.example"},
    {"key": "omar", "email": "omar.demo@campus.example"},
    {"key": "lena", "email": "lena.demo@campus.example"},
    {"key": "theo", "email": "theo.demo@campus.example"},
]

# `author` / `by` reference the keys above. `age_hours` backdates created_at so
# the feed has a believable ordering instead of four posts at the same instant.
DEMO_POSTS = [
    {
        "author": "maya",
        "title": "CS101 midterm study group — Thursday evening",
        "body": (
            "I've booked a room in the library for Thursday at 18:00. Planning to work "
            "through the past two years of midterms, mostly the recursion and dictionary "
            "questions. Bring a laptop. Everyone welcome, no need to be caught up."
        ),
        "anonymous": False,
        "age_hours": 52,
        "likes": ["omar", "lena", "theo"],
        "dislikes": [],
        "comments": [
            {"by": "omar", "body": "I'll be there. Can we cover the file I/O section too?", "anonymous": False, "age_hours": 50},
            {"by": "lena", "body": "Same here — recursion is the part that keeps breaking my brain.", "anonymous": False, "age_hours": 47},
        ],
    },
    {
        "author": "omar",
        "title": "Is CS229 worth taking alongside a heavy semester?",
        "body": (
            "I'm signed up for four other courses and keep hearing CS229 is a serious time "
            "commitment. For anyone who has taken it: was the problem-set load manageable "
            "with a full schedule, or should I push it to next year?"
        ),
        "anonymous": False,
        "age_hours": 30,
        "likes": ["maya", "theo"],
        "dislikes": [],
        "comments": [
            {
                "by": "theo",
                "body": (
                    "Took it last year with three other courses. Doable, but the problem sets "
                    "genuinely take 12-15 hours a week. The maths is the bottleneck, not the coding."
                ),
                "anonymous": False,
                "age_hours": 28,
            },
            {"by": "lena", "body": "Seconding this. Do the linear algebra refresher before week one.", "anonymous": True, "age_hours": 26},
        ],
    },
    {
        "author": "lena",
        "title": "Confession: I still don't understand pointers",
        "body": (
            "Third year, and every time someone draws the boxes-and-arrows diagram I nod along "
            "and understand nothing. Has anyone found an explanation that actually landed for them?"
        ),
        "anonymous": True,
        "age_hours": 18,
        "likes": ["maya", "omar", "theo"],
        "dislikes": [],
        "comments": [
            {
                "by": "maya",
                "body": "Honestly it clicked for me only after writing a linked list by hand on paper. Twice.",
                "anonymous": False,
                "age_hours": 16,
            },
        ],
    },
    {
        "author": "theo",
        "title": "Lost: blue water bottle, Hoffman building 2nd floor",
        "body": "Left it in the lab on Monday afternoon. It has a dented lid and a physics-society sticker. Message me if you spot it.",
        "anonymous": False,
        "age_hours": 6,
        "likes": ["lena"],
        "dislikes": [],
        "comments": [],
    },
    {
        "author": "maya",
        "title": "Cafeteria hours changed and nobody announced it",
        "body": "It now closes at 19:00 on weekdays instead of 21:00. Found out the hard way after a late lab. Plan accordingly.",
        "anonymous": False,
        "age_hours": 3,
        "likes": ["omar"],
        "dislikes": ["theo", "lena"],
        "comments": [
            {"by": "omar", "body": "This explains a lot. Thanks for posting.", "anonymous": False, "age_hours": 2},
        ],
    },
]

DEMO_MESSAGES = [
    {"from": "omar", "to": "maya", "body": "Hey — is the Thursday study group still on?", "age_hours": 20},
    {"from": "maya", "to": "omar", "body": "Yes! Library room 2B, 18:00. I'll bring the past papers.", "age_hours": 19},
    {"from": "omar", "to": "maya", "body": "Perfect, see you then.", "age_hours": 19},
]


def _hours_ago(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def seed_forum_data(db: Session) -> dict:
    """Create demo users, posts, comments, reactions and a DM thread.

    Returns a small tally so the caller can report what it did.
    """
    tally = {"users": 0, "posts": 0, "comments": 0, "reactions": 0, "messages": 0}

    users: dict = {}
    for spec in DEMO_USERS:
        user = db.query(User).filter(User.email == spec["email"]).first()
        if not user:
            user = User(email=spec["email"], hashed_password=get_password_hash(DEMO_PASSWORD), preferences={})
            db.add(user)
            db.commit()
            db.refresh(user)
            tally["users"] += 1
        users[spec["key"]] = user

    for post_spec in DEMO_POSTS:
        existing = db.query(Post).filter(Post.title == post_spec["title"]).first()
        if existing:
            continue

        author = users[post_spec["author"]]
        post = Post(
            user_id=author.id,
            title=post_spec["title"],
            body=post_spec["body"],
            media_urls=[],
            anonymous=post_spec["anonymous"],
            created_at=_hours_ago(post_spec["age_hours"]),
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        tally["posts"] += 1

        for comment_spec in post_spec["comments"]:
            comment = Comment(
                post_id=post.id,
                user_id=users[comment_spec["by"]].id,
                body=comment_spec["body"],
                media_urls=[],
                anonymous=comment_spec["anonymous"],
                created_at=_hours_ago(comment_spec["age_hours"]),
            )
            db.add(comment)
            tally["comments"] += 1

        for key in post_spec["likes"]:
            db.add(Reaction(user_id=users[key].id, post_id=post.id, value=REACTION_LIKE))
            tally["reactions"] += 1
        for key in post_spec["dislikes"]:
            db.add(Reaction(user_id=users[key].id, post_id=post.id, value=REACTION_DISLIKE))
            tally["reactions"] += 1

        db.commit()
        logger.info(f"Seeded post '{post.title}' by {post_spec['author']}")

    for msg_spec in DEMO_MESSAGES:
        sender = users[msg_spec["from"]]
        receiver = users[msg_spec["to"]]
        already = (
            db.query(Message)
            .filter(
                Message.sender_id == sender.id,
                Message.receiver_id == receiver.id,
                Message.body == msg_spec["body"],
            )
            .first()
        )
        if already:
            continue
        db.add(
            Message(
                sender_id=sender.id,
                receiver_id=receiver.id,
                body=msg_spec["body"],
                media_urls=[],
                read=True,
                created_at=_hours_ago(msg_spec["age_hours"]),
            )
        )
        tally["messages"] += 1
    db.commit()

    return tally


if __name__ == "__main__":
    session = SessionLocal()
    try:
        result = seed_forum_data(session)
        print(
            "Forum seeded: "
            f"{result['users']} users, {result['posts']} posts, {result['comments']} comments, "
            f"{result['reactions']} reactions, {result['messages']} messages."
        )
        if not any(result.values()):
            print("(Nothing to do — the demo content was already present.)")
    finally:
        session.close()
