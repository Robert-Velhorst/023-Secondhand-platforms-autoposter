from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.demo import demo_mode_enabled, ensure_demo_user
from app.models import User, UserSession
from app.security import hash_token


def get_authenticated_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserSession:
    """Validate session credentials without granting active-account access.

    Only session revocation should depend on this directly. Data endpoints
    must use get_current_session/get_current_user to enforce account status.
    """
    settings = get_settings()
    if settings.dev_auto_login:
        if not demo_mode_enabled(settings):
            raise HTTPException(status_code=403, detail="Demo auto-login is only allowed in development")
        user = ensure_demo_user(db)
        return UserSession(
            user_id=user.id,
            token_hash="dev-auto-login",
            expires_at=datetime.now(UTC),
            user=user,
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    session = (
        db.query(UserSession)
        .options(selectinload(UserSession.user))
        .filter(UserSession.token_hash == hash_token(token))
        .one_or_none()
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    expires_at = session.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def get_current_session(session: UserSession = Depends(get_authenticated_session)) -> UserSession:
    if not session.user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")
    return session


def get_current_user(session: UserSession = Depends(get_current_session)) -> User:
    return session.user
