"""Compensate handled image-write failures without risking committed references."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.services.storage_cleanup import cleanup_after_commit, queue_storage_deletions

logger = logging.getLogger("autoposter.image_writes")


@contextmanager
def image_write_scope(db: Session) -> Iterator[Callable[[str], None]]:
    """Register each target before storage I/O; caller commits the business rows.

An exception rolls back the business transaction, then a separate session saves
cleanup intent. The cleanup worker rechecks references, including a commit whose
acknowledgment was lost. Never unlink directly on an uncertain database outcome.
This handles exceptions, not process termination or an unavailable recovery DB.
"""
    paths: list[str] = []
    bind = db.get_bind()
    try:
        yield paths.append
    except Exception:
        try:
            db.rollback()
        except Exception as exc:
            logger.warning("Image transaction rollback failed (%s)", type(exc).__name__)
        if paths:
            try:
                with Session(bind=bind) as recovery:
                    ids = queue_storage_deletions(recovery, paths)
                    recovery.commit()
                cleanup_after_commit(ids, bind=bind)
            except Exception as exc:
                # Never replace the original failure or expose provider/path details.
                logger.error("Image cleanup intent could not be persisted (%s)", type(exc).__name__)
        raise
