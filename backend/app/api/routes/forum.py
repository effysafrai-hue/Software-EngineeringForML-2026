from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.forum import Post, Comment
from app.schemas.forum import (
    PostCreate,
    CommentCreate,
    PostResponse,
    PostDetailResponse,
    CommentResponse,
    FileUploadResponse,
    serialize_post,
    serialize_comment,
)
from app.services.upload_service import save_uploaded_file

router = APIRouter(tags=["Forum"])


@router.post("/uploads", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_file(
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
    return [serialize_post(p, include_comments=False, current_user_id=current_user.id) for p in posts]


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post_in: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new post in the forum with optional anonymous authorship."""
    post = Post(
        user_id=current_user.id,
        title=post_in.title.strip(),
        body=post_in.body.strip(),
        media_urls=post_in.media_urls or [],
        anonymous=post_in.anonymous,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return serialize_post(post, include_comments=False, current_user_id=current_user.id)


@router.get("/posts/{post_id}", response_model=PostDetailResponse)
def get_post_detail(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single post with all its comments, preserving strict anonymity."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    return serialize_post(post, include_comments=True, current_user_id=current_user.id)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a post (only permitted for the author)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post.",
        )

    db.delete(post)
    db.commit()
    return None


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    post_id: int,
    comment_in: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a post with optional anonymous authorship."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        body=comment_in.body.strip(),
        media_urls=comment_in.media_urls or [],
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
