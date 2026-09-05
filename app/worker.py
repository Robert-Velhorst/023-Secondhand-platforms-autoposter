import logging
import time
import uuid

from sqlalchemy.exc import InterfaceError, OperationalError, TimeoutError

from app.config import get_settings, validate_startup_safety
from app.database import SessionLocal, init_db
from app.observability import configure_logging
from app.services.jobs import process_due_jobs
from app.services.worker_health import record_heartbeat

logger = logging.getLogger("autoposter.worker")


def run_once() -> int:
    settings = get_settings()
    db = SessionLocal()
    try:
        return process_due_jobs(db, settings.job_worker_batch_size)
    finally:
        db.close()


def run_forever() -> None:
    settings = get_settings()
    validate_startup_safety(settings)
    configure_logging(settings.log_level, settings.log_format)
    if settings.auto_create_tables:
        init_db()
    worker_id = f"worker-{uuid.uuid4().hex}"
    logger.info("Worker started: %s", worker_id)
    retry_delay = settings.job_worker_poll_seconds
    max_retry_delay = max(60, retry_delay)
    recovering = False
    while True:
        phase = "queue"
        try:
            processed = run_once()
            phase = "heartbeat"
            db = SessionLocal()
            try:
                record_heartbeat(db, worker_id, processed)
            finally:
                db.close()
        except (OperationalError, InterfaceError, TimeoutError) as exc:
            # Driver messages/tracebacks can contain SQL values or credentials.
            # Do not write a fallback heartbeat or reuse the failed session.
            logger.warning(
                "Worker %s %s cycle failed (%s); retrying in %s seconds",
                worker_id, phase, type(exc).__name__, retry_delay,
            )
            recovering = True
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
            continue
        if recovering:
            logger.info("Worker %s recovered after database errors", worker_id)
            recovering = False
        retry_delay = settings.job_worker_poll_seconds
        if processed:
            logger.info("Processed %s queued job(s)", processed)
        time.sleep(settings.job_worker_poll_seconds)


if __name__ == "__main__":
    run_forever()
