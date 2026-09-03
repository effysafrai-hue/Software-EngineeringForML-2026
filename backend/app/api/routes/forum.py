from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.models.event import Event
from app.models.forum import Post, Comment, Reaction
from app.schemas.event import EventResponse
from app.schemas.forum import (
    PostCreate,
    CommentCreate,
    PostResponse,
    PostDetailResponse,
    CommentResponse,
    FileUploadResponse,
    MyPostsResponse,
    ReactionRequest,
    ReactionSummary,
    ShareAsEventRequest,
    serialize_post,
    serialize_comment,
)
from app.services import realtime
from app.services.reactions import build_reaction_index, index_for_posts, totals_for_author
from app.services.sanitize import sanitize_user_text, validate_media_urls
from app.services.upload_service import save_uploaded_file

router = APIRouter(tags=["Forum"])


@router.post("/uploads", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_media_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload image (max 10MB) or video (max 100MB) with strict content-type and size validation."""
    result = await save_uploaded_file(file)
    return result


@router.get("/posts", response_model=List[PostResponse])
def list_posts(
    search: Optional[str] = Query(None, description="Search post titles or content"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent posts in the forum with anonymous author masking."""
    query = db.query(Post)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Post.title.ilike(term), Post.body.ilike(term)))

    posts = query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
    reactions = build_reaction_index(db, current_user.id, post_ids=[p.id for p in posts])
    return [
        serialize_post(p, include_comments=False, current_user_id=current_user.id, reactions=reactions)
        for p in posts
    ]


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_POST)
def create_post(
    request: Request,
    post_in: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new post in the forum with optional anonymous authorship."""
    post = Post(
        user_id=current_user.id,
        title=sanitize_user_text(post_in.title, field="title")[:255],
        body=sanitize_user_text(post_in.body, field="body"),
        media_urls=validate_media_urls(post_in.media_urls),
        anonymous=post_in.anonymous,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    payload = serialize_post(post, include_comments=False, current_user_id=None)
    realtime.broadcast(
        {"type": realtime.EVENT_NEW_POST, "post": _jsonable(payload)},
        exclude_user_id=current_user.id,
    )

    return serialize_post(post, include_comments=False, current_user_id=current_user.id)


# Registered before /posts/{post_id} on purpose: FastAPI matches in declaration
# order, and "mine" would otherwise be parsed as a post_id and 422.
@router.get("/posts/mine", response_model=MyPostsResponse)
def list_my_posts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The caller's own posts and the total likes/dislikes they have received.

    Includes the caller's anonymous posts: masking exists to hide the author
    from other readers, and this view is only ever shown to the author.
    """
    query = db.query(Post).filter(Post.user_id == current_user.id)
    total_count = query.count()
    posts = query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
    reactions = build_reaction_index(db, current_user.id, post_ids=[p.id for p in posts])
    totals = totals_for_author(db, current_user.id)

    return {
        **totals,
        "post_count": total_count,
        "posts": [
            serialize_post(p, include_comments=False, current_user_id=current_user.id, reactions=reactions)
            for p in posts
        ],
    }


@router.get("/posts/{post_id}", response_model=PostDetailResponse)
def get_post_detail(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single post with all its comments, preserving strict anonymity."""
    post = _get_post_or_404(db, post_id)
    reactions = index_for_posts(db, current_user.id, [post])
    return serialize_post(
        post, include_comments=True, current_user_id=current_user.id, reactions=reactions
    )


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a post (only permitted for the author)."""
    post = _get_post_or_404(db, post_id)

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post.",
        )

    db.delete(post)
    db.commit()
    return None


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_COMMENT)
def add_comment(
    request: Request,
    post_id: int,
    comment_in: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a post with optional anonymous authorship."""
    post = _get_post_or_404(db, post_id)

    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        body=sanitize_user_text(comment_in.body, field="body"),
        media_urls=validate_media_urls(comment_in.media_urls),
        anonymous=comment_in.anonymous,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return serialize_comment(comment, current_user_id=current_user.id)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment (only permitted for the author)."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this comment.",
        )

    db.delete(comment)
    db.commit()
    return None


@router.put("/posts/{post_id}/reactions", response_model=ReactionSummary)
@limiter.limit(settings.RATE_LIMIT_REACTION)
def react_to_post(
    request: Request,
    post_id: int,
    reaction_in: ReactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Like or dislike a post. Sending a different value replaces the previous one."""
    post = _get_post_or_404(db, post_id)
    changed = _upsert_reaction(db, current_user.id, reaction_in.value, post_id=post_id)
    summary = build_reaction_index(db, current_user.id, post_ids=[post_id]).for_post(post_id)

    realtime.broadcast(
        {"type": realtime.EVENT_REACTION, "post_id": post_id, "comment_id": None, **_counts_only(summary)}
    )
    if changed:
        # Reacting is public but not attributable in the notification: telling
        # the author "user_b liked this" would out someone who reacted to an
        # anonymous thread they thought was private.
        verb = "liked" if reaction_in.value == "like" else "disliked"
        realtime.notify_user(
            db,
            user_id=post.user_id,
            actor_id=current_user.id,
            message=f"Someone {verb} your post '{post.title}'.",
            payload={"type": realtime.EVENT_REACTION, "post_id": post_id, **_counts_only(summary)},
        )

    return summary


@router.delete("/posts/{post_id}/reactions", response_model=ReactionSummary)
def clear_post_reaction(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the caller's reaction from a post."""
    _get_post_or_404(db, post_id)
    _delete_reaction(db, current_user.id, post_id=post_id)
    summary = build_reaction_index(db, current_user.id, post_ids=[post_id]).for_post(post_id)
    realtime.broadcast(
        {"type": realtime.EVENT_REACTION, "post_id": post_id, "comment_id": None, **_counts_only(summary)}
    )
    return summary


@router.put("/comments/{comment_id}/reactions", response_model=ReactionSummary)
@limiter.limit(settings.RATE_LIMIT_REACTION)
def react_to_comment(
    request: Request,
    comment_id: int,
    reaction_in: ReactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Like or dislike a comment. Sending a different value replaces the previous one."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    _upsert_reaction(db, current_user.id, reaction_in.value, comment_id=comment_id)
    summary = build_reaction_index(db, current_user.id, comment_ids=[comment_id]).for_comment(comment_id)
    realtime.broadcast(
        {
            "type": realtime.EVENT_REACTION,
            "post_id": comment.post_id,
            "comment_id": comment_id,
            **_counts_only(summary),
        }
    )
    return summary


@router.delete("/comments/{comment_id}/reactions", response_model=ReactionSummary)
def clear_comment_reaction(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the caller's reaction from a comment."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    _delete_reaction(db, current_user.id, comment_id=comment_id)
    summary = build_reaction_index(db, current_user.id, comment_ids=[comment_id]).for_comment(comment_id)
    realtime.broadcast(
        {
            "type": realtime.EVENT_REACTION,
            "post_id": comment.post_id,
            "comment_id": comment_id,
            **_counts_only(summary),
        }
    )
    return summary


@router.post(
    "/posts/{post_id}/share-as-event",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def share_post_as_event(
    post_id: int,
    share_in: ShareAsEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Copy a post onto the caller's own calendar.

    The event belongs to whoever clicks, not to the post's author, so the same
    post can be added by any number of readers independently. A post carries no
    date of its own, so the caller supplies the start; with no end given the
    event runs for an hour, matching the assistant's own default.
    """
    post = _get_post_or_404(db, post_id)

    start_time = share_in.start_time
    end_time = share_in.end_time or (start_time + timedelta(hours=1))
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be strictly after start_time.",
        )

    title = (share_in.title or post.title).strip()[:255]
    description = post.body if len(post.body) <= 2000 else f"{post.body[:2000]}…"

    event = Event(
        user_id=current_user.id,
        title=title,
        description=f"Shared from forum post #{post.id}\n\n{description}",
        start_time=start_time,
        end_time=end_time,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _get_post_or_404(db: Session, post_id: int) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return post


def _upsert_reaction(
    db: Session,
    user_id: int,
    value: str,
    post_id: Optional[int] = None,
    comment_id: Optional[int] = None,
) -> bool:
    """Create or update the caller's single reaction. Returns True if it changed.

    Re-sending the value already stored is a no-op rather than an error, so a
    double-tapped button does not produce a second notification.
    """
    existing = _find_reaction(db, user_id, post_id=post_id, comment_id=comment_id)
    if existing:
        if existing.value == value:
            return False
        existing.value = value
        db.commit()
        return True

    reaction = Reaction(user_id=user_id, post_id=post_id, comment_id=comment_id, value=value)
    db.add(reaction)
    try:
        db.commit()
    except IntegrityError:
        # Two clicks racing each other: the unique constraint kept the second
        # row out, so fall back to updating the row that won.
        db.rollback()
        existing = _find_reaction(db, user_id, post_id=post_id, comment_id=comment_id)
        if not existing:
            raise
        if existing.value == value:
            return False
        existing.value = value
        db.commit()
    return True


def _delete_reaction(
    db: Session,
    user_id: int,
    post_id: Optional[int] = None,
    comment_id: Optional[int] = None,
) -> None:
    existing = _find_reaction(db, user_id, post_id=post_id, comment_id=comment_id)
    if existing:
        db.delete(existing)
        db.commit()


def _find_reaction(
    db: Session,
    user_id: int,
    post_id: Optional[int] = None,
    comment_id: Optional[int] = None,
) -> Optional[Reaction]:
    query = db.query(Reaction).filter(Reaction.user_id == user_id)
    if post_id is not None:
        query = query.filter(Reaction.post_id == post_id)
    else:
        query = query.filter(Reaction.comment_id == comment_id)
    return query.first()


def _counts_only(summary: dict) -> dict:
    """Strip `my_reaction` before broadcasting: it is per-viewer, not per-item."""
    return {
        "like_count": summary.get("like_count", 0),
        "dislike_count": summary.get("dislike_count", 0),
    }


def _jsonable(payload: dict) -> dict:
    """Datetimes to ISO strings so the payload survives WebSocket JSON encoding."""
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in payload.items()}
