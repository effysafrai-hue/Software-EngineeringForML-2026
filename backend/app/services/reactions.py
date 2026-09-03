"""Batched like/dislike lookups for the forum.

Reading counts off `post.reactions` would issue one query per row, so a 50-post
feed would cost 50 round-trips (and 50 more for the comments). Everything the
serializers need is instead loaded up front in two aggregate queries and handed
around as a `ReactionIndex`.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.forum import Post, Reaction, REACTION_DISLIKE, REACTION_LIKE

# (kind, item_id) -> {"like": n, "dislike": n}
_CountKey = Tuple[str, int]

EMPTY_SUMMARY = {"like_count": 0, "dislike_count": 0, "my_reaction": None}


@dataclass
class ReactionIndex:
    counts: Dict[_CountKey, Dict[str, int]] = field(default_factory=dict)
    mine: Dict[_CountKey, str] = field(default_factory=dict)

    def _summary(self, kind: str, item_id: Optional[int]) -> Dict[str, object]:
        if item_id is None:
            return dict(EMPTY_SUMMARY)
        key = (kind, item_id)
        counts = self.counts.get(key, {})
        return {
            "like_count": counts.get(REACTION_LIKE, 0),
            "dislike_count": counts.get(REACTION_DISLIKE, 0),
            "my_reaction": self.mine.get(key),
        }

    def for_post(self, post_id: Optional[int]) -> Dict[str, object]:
        return self._summary("post", post_id)

    def for_comment(self, comment_id: Optional[int]) -> Dict[str, object]:
        return self._summary("comment", comment_id)


def build_reaction_index(
    db: Session,
    current_user_id: Optional[int],
    post_ids: Optional[Iterable[int]] = None,
    comment_ids: Optional[Iterable[int]] = None,
) -> ReactionIndex:
    """Load counts, plus the caller's own reaction, for the given items."""
    posts = [pid for pid in (post_ids or []) if pid is not None]
    comments = [cid for cid in (comment_ids or []) if cid is not None]
    index = ReactionIndex()
    if not posts and not comments:
        return index

    rows = (
        db.query(Reaction.post_id, Reaction.comment_id, Reaction.value, func.count(Reaction.id))
        .filter(_target_filter(posts, comments))
        .group_by(Reaction.post_id, Reaction.comment_id, Reaction.value)
        .all()
    )
    for post_id, comment_id, value, count in rows:
        key: _CountKey = ("post", post_id) if post_id is not None else ("comment", comment_id)
        index.counts.setdefault(key, {})[value] = count

    if current_user_id is not None:
        own = (
            db.query(Reaction.post_id, Reaction.comment_id, Reaction.value)
            .filter(Reaction.user_id == current_user_id)
            .filter(_target_filter(posts, comments))
            .all()
        )
        for post_id, comment_id, value in own:
            key = ("post", post_id) if post_id is not None else ("comment", comment_id)
            index.mine[key] = value

    return index


def _target_filter(posts, comments):
    clauses = []
    if posts:
        clauses.append(Reaction.post_id.in_(posts))
    if comments:
        clauses.append(Reaction.comment_id.in_(comments))
    return or_(*clauses) if len(clauses) > 1 else clauses[0]


def index_for_posts(db: Session, current_user_id: Optional[int], posts: Iterable[Post]) -> ReactionIndex:
    """Convenience wrapper covering a set of posts and every comment they carry."""
    post_list = list(posts)
    comment_ids = [c.id for p in post_list for c in (p.comments or [])]
    return build_reaction_index(
        db,
        current_user_id,
        post_ids=[p.id for p in post_list],
        comment_ids=comment_ids,
    )


def totals_for_author(db: Session, author_id: int) -> Dict[str, int]:
    """Total likes and dislikes the author's posts have received.

    Counts reactions on posts only; reactions on the author's comments are not
    folded in, so the number lines up with what the "my posts" list shows.
    """
    rows = (
        db.query(Reaction.value, func.count(Reaction.id))
        .join(Post, Post.id == Reaction.post_id)
        .filter(Post.user_id == author_id)
        .group_by(Reaction.value)
        .all()
    )
    tally = {value: count for value, count in rows}
    return {
        "total_likes": tally.get(REACTION_LIKE, 0),
        "total_dislikes": tally.get(REACTION_DISLIKE, 0),
    }
