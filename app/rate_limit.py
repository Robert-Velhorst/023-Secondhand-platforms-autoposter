import hashlib
import heapq
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic

from fastapi import HTTPException
from sqlalchemy import case, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LoginThrottle


@dataclass(frozen=True, slots=True)
class LoginReservation:
    identifier_hash: str
    attempt_token: str


@dataclass(slots=True)
class ApiBucket:
    requests: int
    expires_at: float


api_buckets: dict[str, ApiBucket] = {}
MAX_API_BUCKETS = 10_000
# Exactly one expiry entry per bucket, not one per request. Do not evict active
# quotas to admit new identities: that would let identity churn reset limits.
_api_expirations: list[tuple[float, str]] = []
_api_lock = Lock()


def _identifier_hash(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def reserve_login_attempt(db: Session, identifier: str) -> LoginReservation:
    """Commit one atomic admission before password work; failures keep the slot."""
    settings = get_settings()
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=settings.login_rate_limit_window_seconds)
    reservation = LoginReservation(_identifier_hash(identifier), uuid.uuid4().hex)
    dialect = db.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Atomic login admission requires SQLite or PostgreSQL")
    insert = sqlite_insert if dialect == "sqlite" else postgres_insert
    expired = LoginThrottle.window_started_at <= cutoff
    statement = insert(LoginThrottle).values(
        identifier_hash=reservation.identifier_hash, attempts=1,
        window_started_at=now, last_failed_at=now, attempt_token=reservation.attempt_token,
    ).on_conflict_do_update(
        index_elements=[LoginThrottle.identifier_hash],
        set_={
            "attempts": case((expired, 1), else_=LoginThrottle.attempts + 1),
            "window_started_at": case((expired, now), else_=LoginThrottle.window_started_at),
            # Legacy column name: now records the most recent admitted attempt.
            "last_failed_at": now,
            "attempt_token": reservation.attempt_token,
        },
        where=or_(expired, LoginThrottle.attempts < settings.login_rate_limit_attempts),
    ).returning(LoginThrottle.attempt_token)
    if db.execute(statement).scalar_one_or_none() is not None:
        db.commit()  # No throttle row lock is held while checking the password.
        return reservation
    started_at = db.scalar(select(LoginThrottle.window_started_at).where(
        LoginThrottle.identifier_hash == reservation.identifier_hash,
    ))
    db.rollback()
    retry_after = settings.login_rate_limit_window_seconds
    if started_at is not None:
        expires_at = _aware_utc(started_at) + timedelta(seconds=retry_after)
        retry_after = max(1, math.ceil((expires_at - datetime.now(UTC)).total_seconds()))
    raise HTTPException(
        status_code=429, detail="Too many login attempts. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def clear_successful_login(db: Session, reservation: LoginReservation) -> None:
    """Clear only this still-latest admission, in the session-creation transaction."""
    db.execute(delete(LoginThrottle).where(
        LoginThrottle.identifier_hash == reservation.identifier_hash,
        LoginThrottle.attempt_token == reservation.attempt_token,
    ).execution_options(synchronize_session=False))


def purge_expired_login_throttles(db: Session, batch_size: int = 100) -> int:
    if batch_size <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().login_rate_limit_window_seconds)
    candidates = select(LoginThrottle.id).where(LoginThrottle.window_started_at <= cutoff).order_by(
        LoginThrottle.window_started_at, LoginThrottle.id,
    ).limit(min(batch_size, 100))
    result = db.execute(delete(LoginThrottle).where(
        LoginThrottle.id.in_(candidates), LoginThrottle.window_started_at <= cutoff,
    ).execution_options(synchronize_session=False))
    db.commit()
    return result.rowcount


def check_api_rate_limit(identifier: str, limit: int, window_seconds: int) -> int | None:
    bucket_key = _identifier_hash(identifier)
    with _api_lock:
        now = monotonic()
        while _api_expirations and _api_expirations[0][0] <= now:
            _, expired_key = heapq.heappop(_api_expirations)
            api_buckets.pop(expired_key, None)
        bucket = api_buckets.get(bucket_key)
        if bucket is None:
            if len(api_buckets) >= MAX_API_BUCKETS:
                return max(1, math.ceil(_api_expirations[0][0] - now))
            expires_at = now + window_seconds
            api_buckets[bucket_key] = ApiBucket(requests=1, expires_at=expires_at)
            heapq.heappush(_api_expirations, (expires_at, bucket_key))
            return None
        if bucket.requests >= limit:
            return max(1, math.ceil(bucket.expires_at - now))
        bucket.requests += 1
        return None
