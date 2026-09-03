from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.limiter import limiter
from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_jwt_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserSignupRequest, UserLoginRequest, TokenResponse, UserResponse
from app.api.deps import get_current_user
from app.services.user_memory import seed_from_signup_answers

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_SIGNUP)
def signup(request: Request, user_in: UserSignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    answers = user_in.preferences.to_dict() if user_in.preferences else {}
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        preferences=answers,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Requirement 2.2 — the sign-up answers become long-term memory immediately,
    # so the assistant has something to personalise with on the very first turn
    # rather than only after it has learned it from conversation.
    if answers:
        seed_from_signup_answers(db, user.id, answers)

    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, user_in: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_jwt_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    access_token = create_access_token(subject=str(user.id))
    new_refresh = create_refresh_token(subject=str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
