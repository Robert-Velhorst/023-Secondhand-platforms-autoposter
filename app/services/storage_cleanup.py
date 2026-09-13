"""At-least-once cleanup for immutable, uniquely named uploaded objects.

Enqueue in the caller's deletion transaction; never perform storage I/O there.
Claims commit before I/O, so crashes leave retryable work rather than lost intent.
No database write lock is held across filesystem/network I/O. Claim tokens fence
late acknowledgments; an expired claim may repeat an idempotent object deletion.
"""

import logging
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import ListingImage, StorageDeletion, now_utc
from app.storage import delete_stored_file

logger = logging.getLogger("autoposter.storage_cleanup")
MAX_BATCH_SIZE = 5
CLAIM_SECONDS = 300


def queue_storage_deletions(db: Session, paths: Iterable[str]) -> list[str]:
    ids = []
    for path in sorted(set(paths)):
        deletion_id = uuid.uuid4().hex
        db.add(StorageDeletion(id=deletion_id, storage_path=path))
        ids.append(deletion_id)
    return ids


def process_due_storage_deletions(
    db: Session,
    *,
    limit: int = MAX_BATCH_SIZE,
    ids: Sequence[str] | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Complete a bounded batch; retain failures with 1 minute to 1 hour backoff."""
    settings = settings or get_settings()
    now = now or now_utc()
    if limit <= 0 or ids == []:
        return 0
    limit = min(limit, 1 if settings.storage_backend.lower() == "s3" else MAX_BATCH_SIZE)
    query = db.query(StorageDeletion.id, StorageDeletion.storage_path, StorageDeletion.attempts).filter(
        StorageDeletion.next_attempt_at <= now
    )
    if ids is not None:
        query = query.filter(StorageDeletion.id.in_(ids))
    candidates = query.order_by(StorageDeletion.next_attempt_at, StorageDeletion.id).limit(limit).all()
    completed = 0
    for deletion_id, path, prior_attempts in candidates:
        token = uuid.uuid4().hex
        claimed = db.query(StorageDeletion).filter(
            StorageDeletion.id == deletion_id, StorageDeletion.next_attempt_at <= now
        ).update({
            "claim_token": token,
            "next_attempt_at": now + timedelta(seconds=CLAIM_SECONDS),
            "attempts": min(prior_attempts + 1, 2_000_000_000),
        }, synchronize_session=False)
        db.commit()
        if not claimed:
            continue
        referenced = db.query(ListingImage.id).filter(ListingImage.storage_path == path).first() is not None
        db.rollback()  # release the read transaction before external storage I/O
        error_type = ""
        if not referenced:
            try:
                delete_stored_file(path, settings)
            except Exception as exc:
                # Provider/OS messages can contain filenames, signed URLs or credentials.
                error_type = type(exc).__name__[:80]
                logger.warning("Storage cleanup deferred (%s)", error_type)
        owned = db.query(StorageDeletion).filter(
            StorageDeletion.id == deletion_id, StorageDeletion.claim_token == token
        )
        if error_type:
            delay = min(3600, 60 * 2 ** min(prior_attempts, 6))
            owned.update({
                "last_error_type": error_type,
                "claim_token": None,
                "next_attempt_at": now + timedelta(seconds=delay),
            }, synchronize_session=False)
        else:
            completed += owned.delete(synchronize_session=False)
        db.commit()
    return completed


def cleanup_after_commit(ids: Sequence[str], *, bind: Engine | Connection | None = None) -> None:
    """Local fast path only. Worker retries survive any failure of this best effort."""
    if not ids:
        return
    try:
        settings = get_settings()
        if settings.storage_backend.lower() != "local":
            return  # Do not make API deletion latency depend on a remote storage service.
        with (SessionLocal() if bind is None else Session(bind=bind)) as db:
            process_due_storage_deletions(db, ids=ids[:MAX_BATCH_SIZE], settings=settings)
    except Exception as exc:
        # The business transaction is already committed; do not turn success into a 500.
        logger.warning("Post-commit storage cleanup deferred (%s)", type(exc).__name__)
