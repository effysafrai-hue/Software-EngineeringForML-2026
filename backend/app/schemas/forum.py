from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    media_urls: List[str] = Field(default_factory=list)
    anonymous: bool = False


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
    media_urls: List[str] = Field(default_factory=list)
    anonymous: bool = False


class ReactionRequest(BaseModel):
    value: Literal["like", "dislike"]


class ReactionSummary(BaseModel):
    """Counts for one item plus the calling user's own reaction, if any."""

    like_count: int = 0
    dislike_count: int = 0
    my_reaction: Optional[Literal["like", "dislike"]] = None


class ShareAsEventRequest(BaseModel):
    """Turn a post into a calendar entry on the caller's own calendar."""

    start_time: datetime
    end_time: Optional[datetime] = None
    title: Optional[str] = Field(None, max_length=255)


class CommentResponse(BaseModel):
    id: int
    post_id: int
    body: str
    media_urls: List[str] = []
    anonymous: bool
    created_at: datetime
    author_id: Optional[int] = None
    author_email: Optional[str] = None
    like_count: int = 0
    dislike_count: int = 0
    my_reaction: Optional[Literal["like", "dislike"]] = None

    class Config:
        from_attributes = True


class PostResponse(BaseModel):
    id: int
    title: str
    body: str
    media_urls: List[str] = []
    anonymous: bool
    created_at: datetime
    author_id: Optional[int] = None
    author_email: Optional[str] = None
    comment_count: int = 0
    like_count: int = 0
    dislike_count: int = 0
    my_reaction: Optional[Literal["like", "dislike"]] = None

    class Config:
        from_attributes = True


class PostDetailResponse(PostResponse):
    comments: List[CommentResponse] = []


class MyPostsResponse(BaseModel):
    """The caller's own posts, with the reception they have had in aggregate."""

    total_likes: int = 0
    total_dislikes: int = 0
    post_count: int = 0
    posts: List[PostResponse] = []


class FileUploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size_bytes: int
    category: str


def serialize_comment(comment, current_user_id: Optional[int] = None, reactions=None) -> dict:
    """Format comment dictionary with strict anonymity masking."""
    is_anon = bool(comment.anonymous)
    summary = reactions.for_comment(comment.id) if reactions is not None else {}
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "body": comment.body,
        "media_urls": comment.media_urls or [],
        "anonymous": is_anon,
        "created_at": comment.created_at,
        "author_id": None if is_anon else comment.user_id,
        "author_email": None if is_anon else (comment.user.email if comment.user else None),
        "like_count": summary.get("like_count", 0),
        "dislike_count": summary.get("dislike_count", 0),
        "my_reaction": summary.get("my_reaction"),
    }


def serialize_post(
    post,
    include_comments: bool = False,
    current_user_id: Optional[int] = None,
    reactions=None,
) -> dict:
    """Format post dictionary with strict anonymity masking.

    `reactions` is a ReactionIndex prepared by the caller. It is optional so the
    anonymity masking stays testable without a database, but every route passes
    one — omitting it reports zero counts rather than issuing a query per post.
    """
    is_anon = bool(post.anonymous)
    summary = reactions.for_post(post.id) if reactions is not None else {}
    data = {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "media_urls": post.media_urls or [],
        "anonymous": is_anon,
        "created_at": post.created_at,
        "author_id": None if is_anon else post.user_id,
        "author_email": None if is_anon else (post.user.email if post.user else None),
        "comment_count": len(post.comments) if post.comments is not None else 0,
        "like_count": summary.get("like_count", 0),
        "dislike_count": summary.get("dislike_count", 0),
        "my_reaction": summary.get("my_reaction"),
    }
    if include_comments:
        data["comments"] = [
            serialize_comment(c, current_user_id=current_user_id, reactions=reactions)
            for c in (post.comments or [])
        ]
    return data
