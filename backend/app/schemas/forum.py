from datetime import datetime
from typing import List, Optional
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


class CommentResponse(BaseModel):
    id: int
    post_id: int
    body: str
    media_urls: List[str] = []
    anonymous: bool
    created_at: datetime
    author_id: Optional[int] = None
    author_email: Optional[str] = None

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

    class Config:
        from_attributes = True


class PostDetailResponse(PostResponse):
    comments: List[CommentResponse] = []


class FileUploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size_bytes: int
    category: str


def serialize_comment(comment, current_user_id: Optional[int] = None) -> dict:
    """Format comment dictionary with strict anonymity masking."""
    is_anon = bool(comment.anonymous)
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "body": comment.body,
        "media_urls": comment.media_urls or [],
        "anonymous": is_anon,
        "created_at": comment.created_at,
        "author_id": None if is_anon else comment.user_id,
        "author_email": None if is_anon else (comment.user.email if comment.user else None),
    }


def serialize_post(post, include_comments: bool = False, current_user_id: Optional[int] = None) -> dict:
    """Format post dictionary with strict anonymity masking."""
    is_anon = bool(post.anonymous)
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
    }
    if include_comments:
        data["comments"] = [
            serialize_comment(c, current_user_id=current_user_id)
            for c in (post.comments or [])
        ]
    return data
