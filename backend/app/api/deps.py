from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.security import decode_jwt_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_jwt_token(token)
    if payload is None:
        raise credentials_exception

    # A refresh token is valid, signed and long-lived (days, against the access
    # token's minutes), and it is only ever meant to be traded in at
    # /auth/refresh. Without this check it also works as a bearer credential on
    # every protected endpoint, so a leaked one would grant full API access for
    # its whole lifetime instead of being exchangeable at a single route.
    # /auth/refresh enforces the mirror of this rule.
    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user
