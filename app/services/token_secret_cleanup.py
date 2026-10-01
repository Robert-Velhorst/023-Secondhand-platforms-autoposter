"""Retryable deletion of OAuth token files after account changes."""

import logging
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import PlatformAccount, TokenSecretDeletion, now_utc
from app.services.secrets import get_token_secret_store

logger = logging.getLogger("autoposter.token_secret_cleanup")
MAX_BATCH_SIZE = 5
CLAIM_SECONDS = 300


def queue_token_secret_deletions(db: Session, secret_refs: Iterable[str]) -> list[str]:
    ids = []
    for secret_ref in sorted({ref for ref in secret_refs if ref}):
        deletion_id = uuid.uuid4().hex
        db.add(TokenSecretDeletion(id=deletion_id, secret_ref=secret_ref))
        ids.append(deletion_id)
    return ids


def process_due_token_secret_deletions(
    db: Session,
    *,
    limit: int = MAX_BATCH_SIZE,
    ids: Sequence[str] | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    settings = settings or get_settings()
    now = now or now_utc()
    if limit <= 0 or ids == []:
        return 0
    query = db.query(
        TokenSecretDeletion.id, TokenSecretDeletion.secret_ref, TokenSecretDeletion.attempts
    ).filter(TokenSecretDeletion.next_attempt_at <= now)
    if ids is not None:
        query = query.filter(TokenSecretDeletion.id.in_(ids))
    candidates = query.order_by(TokenSecretDeletion.next_attempt_at, TokenSecretDeletion.id).limit(
        min(limit, MAX_BATCH_SIZE)
    ).all()
    completed = 0
    store = get_token_secret_store(settings)
    for deletion_id, secret_ref, prior_attempts in candidates:
        token = uuid.uuid4().hex
        claimed = db.query(TokenSecretDeletion).filter(
            TokenSecretDeletion.id == deletion_id,
            TokenSecretDeletion.next_attempt_at <= now,
        ).update(
            {
                "claim_token": token,
                "next_attempt_at": now + timedelta(seconds=CLAIM_SECONDS),
                "attempts": min(prior_attempts + 1, 2_000_000_000),
            },
            synchronize_session=False,
        )
        db.commit()
        if not claimed:
            continue

        still_referenced = (
            db.query(PlatformAccount.id).filter(PlatformAccount.secret_ref == secret_ref).first() is not None
        )
        db.rollback()  # release the database transaction before filesystem I/O
        error_type = ""
        if not still_referenced:
            try:
                store.delete_json(secret_ref)
            except Exception as exc:
                error_type = type(exc).__name__[:80]
                logger.warning("Token-secret cleanup deferred (%s)", error_type)

        owned = db.query(TokenSecretDeletion).filter(
            TokenSecretDeletion.id == deletion_id,
            TokenSecretDeletion.claim_token == token,
        )
        if error_type:
            delay = min(3600, 60 * 2 ** min(prior_attempts, 6))
            owned.update(
                {
                    "last_error_type": error_type,
                    "claim_token": None,
                    "next_attempt_at": now + timedelta(seconds=delay),
                },
                synchronize_session=False,
            )
        else:
            completed += owned.delete(synchronize_session=False)
        db.commit()
    return completed


def cleanup_token_secrets_after_commit(
    ids: Sequence[str], *, bind: Engine | Connection | None = None
) -> None:
    """Best-effort fast path; durable worker retries remain authoritative."""
    if not ids:
        return
    try:
        with (SessionLocal() if bind is None else Session(bind=bind)) as db:
            process_due_token_secret_deletions(db, ids=ids[:MAX_BATCH_SIZE])
    except Exception as exc:
        logger.warning("Token-secret cleanup deferred (%s)", type(exc).__name__)
