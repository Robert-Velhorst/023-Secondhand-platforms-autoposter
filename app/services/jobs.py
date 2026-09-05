import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, desc, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.adapters import get_adapter
from app.config import get_settings
from app.models import (
    CategoryMapping,
    Listing,
    PlatformAccount,
    PlatformListingMapping,
    PublicationAttempt,
    PublishingJob,
    PublishingJobLog,
)
from app.services.job_state import (
    FAILED,
    NEEDS_USER_ACTION,
    PUBLISHED,
    QUEUED,
    RUNNING,
    is_terminal_status,
    transition_job,
)
from app.services.operator_controls import job_processing_is_paused
from app.services.platform_rate_limits import quota_backoff_payload, quota_retry_at_from_outcome


class PublishingAccountError(ValueError):
    """The selected account is not available to this listing/platform pair."""


def load_publishing_account(
    db: Session, owner_id: int, platform: str, account_id: int | None
) -> PlatformAccount | None:
    if account_id is None:
        return None
    message = "Selected platform account is unavailable for this listing and platform."
    # Reject values outside the supported databases' integer range before binding.
    if not isinstance(account_id, int) or not 0 < account_id < 2**63:
        raise PublishingAccountError(message)
    account = (
        db.query(PlatformAccount)
        .filter(PlatformAccount.id == account_id, PlatformAccount.owner_id == owner_id,
                PlatformAccount.platform == platform)
        .populate_existing()
        .one_or_none()
    )
    if account is None:
        raise PublishingAccountError(message)
    return account


def idempotency_key(
    *,
    user_id: int,
    listing_id: int,
    listing_revision: int,
    platform: str,
    action_type: str,
    account_id: int | None,
    operation_mode: str,
) -> str:
    raw = (
        f"user={user_id}:listing={listing_id}:revision={listing_revision}:platform={platform}:"
        f"action={action_type}:account={account_id or 'none'}:mode={operation_mode}"
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def add_log(db: Session, job: PublishingJob, level: str, message: str, data: dict | None = None) -> None:
    db.add(PublishingJobLog(job_id=job.id, level=level, message=message, data=data or {}))
    db.flush()


def get_or_create_mapping(db: Session, listing_id: int, platform: str) -> PlatformListingMapping:
    mapping = (
        db.query(PlatformListingMapping)
        .filter(PlatformListingMapping.listing_id == listing_id, PlatformListingMapping.platform == platform)
        .one_or_none()
    )
    if mapping:
        return mapping
    mapping = PlatformListingMapping(listing_id=listing_id, platform=platform, status="draft")
    db.add(mapping)
    db.flush()
    return mapping


def enqueue_publish_job(
    db: Session, listing: Listing, platform: str, account_id: int | None = None
) -> PublishingJob:
    load_publishing_account(db, listing.owner_id, platform, account_id)
    adapter = get_adapter(platform)
    action_type = "publish"
    operation_mode = adapter.automation_mode
    key = idempotency_key(
        user_id=listing.owner_id,
        listing_id=listing.id,
        listing_revision=listing.revision,
        platform=platform,
        action_type=action_type,
        account_id=account_id,
        operation_mode=operation_mode,
    )
    existing = (
        db.query(PublishingJob)
        .filter(PublishingJob.idempotency_key == key)
        .one_or_none()
    )
    if existing:
        return existing

    job = PublishingJob(
        listing_id=listing.id,
        platform=platform,
        account_id=account_id,
        status=QUEUED,
        idempotency_key=key,
        listing_revision=listing.revision,
        action_type=action_type,
        operation_mode=operation_mode,
    )
    # Flush caller-owned work outside the savepoint so its failures cannot be
    # mistaken for a competing enqueue and its changes survive a key collision.
    db.flush()
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
            add_log(db, job, "info", "Publishing job queued.")
    except IntegrityError:
        # The unique key arbitrates concurrent requests which both saw no job.
        # Only a persisted winner for this exact key is a successful duplicate.
        existing = db.query(PublishingJob).filter(PublishingJob.idempotency_key == key).one_or_none()
        if existing is None:
            raise
        return existing
    db.commit()
    db.refresh(job)
    return job


def process_job(db: Session, job_id: int) -> PublishingJob:
    """Claim due work; never execute a claim held by another request or worker."""
    if not claim_job_for_processing(db, job_id, due_only=True):
        return db.query(PublishingJob).filter(PublishingJob.id == job_id).one()
    return _process_claimed_job(db, job_id)


def _process_claimed_job(db: Session, job_id: int) -> PublishingJob:
    """Execute only IDs obtained by this caller's successful claim operation."""
    job = (
        db.query(PublishingJob)
        .filter(PublishingJob.id == job_id)
        .one()
    )
    if job.status != RUNNING:
        return job

    job = (
        db.query(PublishingJob)
        .options(selectinload(PublishingJob.listing).selectinload(Listing.images), selectinload(PublishingJob.logs))
        .filter(PublishingJob.id == job_id)
        .one()
    )

    settings = get_settings()
    cooldown_seconds = settings.platform_rate_limit_for(job.platform)
    cooldown_cutoff = datetime.now(UTC) - timedelta(seconds=cooldown_seconds)
    recent_job = (
        db.query(PublishingJob)
        .filter(
            PublishingJob.platform == job.platform,
            PublishingJob.id != job.id,
            PublishingJob.started_at.is_not(None),
        )
        .order_by(desc(PublishingJob.started_at))
        .first()
    )
    recent_started_at = recent_job.started_at if recent_job else None
    if recent_started_at and recent_started_at.tzinfo is None:
        recent_started_at = recent_started_at.replace(tzinfo=UTC)
    if recent_job and recent_started_at and recent_started_at > cooldown_cutoff:
        transition_job(job, QUEUED)
        job.started_at = None
        job.next_retry_at = datetime.now(UTC) + timedelta(seconds=cooldown_seconds)
        add_log(db, job, "info", "Rate limit cooldown applied.", {"next_retry_at": job.next_retry_at.isoformat()})
        db.commit()
        db.refresh(job)
        return job

    job.started_at = datetime.now(UTC)
    job.attempts += 1
    add_log(db, job, "info", "Publishing job started.")
    db.commit()

    listing = job.listing
    adapter = get_adapter(job.platform)

    try:
        account = load_publishing_account(db, listing.owner_id, job.platform, job.account_id)
        mapping = get_or_create_mapping(db, listing.id, job.platform)
        overrides = effective_platform_overrides(db, listing, job.platform, mapping.overrides)
        outcome = adapter.publish_listing(listing, account=account, overrides=overrides)
        quota_retry_at = quota_retry_at_from_outcome(outcome.data)
        if quota_retry_at:
            transition_job(job, QUEUED)
            job.error_message = None
            job.next_retry_at = quota_retry_at
            job.result = {
                **outcome.data,
                "rate_limit": quota_backoff_payload(
                    quota_retry_at,
                    outcome.data.get("rate_limit_headers")
                    or outcome.data.get("quota_headers")
                    or outcome.data.get("response_headers")
                    or outcome.data.get("headers")
                    or {},
                ),
            }
            add_log(
                db,
                job,
                "warning",
                "Official API quota backoff applied.",
                job.result["rate_limit"],
            )
            db.commit()
            db.refresh(job)
            return job
        transition_job(job, outcome.status)
        job.error_message = None if outcome.status != FAILED else outcome.message
        job.result = outcome.data
        job.finished_at = datetime.now(UTC)

        mapping.status = outcome.status
        mapping.platform_listing_id = outcome.platform_listing_id
        mapping.platform_url = outcome.platform_url
        mapping.validation_errors = outcome.data.get("missing_fields", [])
        if outcome.status == PUBLISHED:
            mapping.last_published_at = datetime.now(UTC)

        db.add(
            PublicationAttempt(
                job_id=job.id,
                platform=job.platform,
                status=outcome.status,
                error_message=job.error_message,
                payload_snapshot=outcome.data.get("mapped_fields", outcome.data),
            )
        )
        add_log(db, job, "info", outcome.message or f"Job finished with status {outcome.status}.", outcome.data)
    except Exception as exc:  # pragma: no cover - defensive boundary around external adapters
        transition_job(job, FAILED)
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        db.add(
            PublicationAttempt(
                job_id=job.id,
                platform=job.platform,
                status=FAILED,
                error_message=str(exc),
                payload_snapshot={},
            )
        )
        add_log(db, job, "error", "Publishing job failed.", {"error": str(exc)})

    db.commit()
    db.refresh(job)
    return job


def claim_job_for_processing(db: Session, job_id: int, due_only: bool = False) -> bool:
    now = datetime.now(UTC)
    query = db.query(PublishingJob).filter(PublishingJob.id == job_id, PublishingJob.status == QUEUED)
    if due_only:
        query = (
            query.filter(PublishingJob.scheduled_at <= now)
            .filter((PublishingJob.next_retry_at.is_(None)) | (PublishingJob.next_retry_at <= now))
        )
    claimed = query.update({
        PublishingJob.status: RUNNING,
        PublishingJob.started_at: None,
        PublishingJob.finished_at: None,
        PublishingJob.updated_at: now,
    }, synchronize_session=False)
    db.commit()
    return claimed == 1


def retry_job(db: Session, job: PublishingJob) -> PublishingJob:
    load_publishing_account(db, job.listing.owner_id, job.platform, job.account_id)
    if not is_terminal_status(job.status):
        db.refresh(job)
        return job
    # Compare the observed version as well as status: two retry requests must
    # not reset work that the other request has already queued or completed.
    queued = db.query(PublishingJob).filter(
        PublishingJob.id == job.id,
        PublishingJob.status == job.status,
        PublishingJob.updated_at == job.updated_at,
    ).update({
        PublishingJob.status: QUEUED,
        PublishingJob.error_message: None,
        PublishingJob.next_retry_at: None,
        PublishingJob.started_at: None,
        PublishingJob.finished_at: None,
        PublishingJob.updated_at: datetime.now(UTC),
        PublishingJob.max_attempts: case(
            (PublishingJob.attempts >= PublishingJob.max_attempts, PublishingJob.max_attempts + 1),
            else_=PublishingJob.max_attempts,
        ),
    }, synchronize_session=False)
    db.refresh(job)
    if not queued:
        db.commit()
        return job
    add_log(db, job, "info", "Publishing job queued for retry.")
    db.commit()
    db.refresh(job)
    if get_settings().job_process_inline:
        return process_job(db, job.id)
    return job


def confirm_manual_completion(
    db: Session,
    job: PublishingJob,
    *,
    platform_url: str,
    platform_listing_id: str | None = None,
) -> PublishingJob:
    if job.status != NEEDS_USER_ACTION:
        raise ValueError("Only jobs waiting for user action can be manually completed")
    if job.operation_mode != "assisted":
        raise ValueError("Manual completion is only supported for assisted jobs")

    mapping = get_or_create_mapping(db, job.listing_id, job.platform)
    now = datetime.now(UTC)
    transition_job(job, PUBLISHED)
    job.error_message = None
    job.finished_at = now
    job.result = {
        **(job.result or {}),
        "manual_completion": {
            "confirmed_by_user": True,
            "platform_url": platform_url,
            "platform_listing_id": platform_listing_id,
            "confirmed_at": now.isoformat(),
        },
    }

    mapping.status = PUBLISHED
    mapping.platform_url = platform_url
    mapping.platform_listing_id = platform_listing_id
    mapping.last_published_at = now
    mapping.validation_errors = []

    db.add(
        PublicationAttempt(
            job_id=job.id,
            platform=job.platform,
            status=PUBLISHED,
            error_message=None,
            payload_snapshot=job.result["manual_completion"],
        )
    )
    add_log(db, job, "info", "User confirmed manual marketplace completion.", job.result["manual_completion"])
    db.commit()
    db.refresh(job)
    return job


def effective_platform_overrides(db: Session, listing: Listing, platform: str, overrides: dict) -> dict:
    effective = dict(overrides or {})
    if "category" in effective and effective["category"]:
        return effective
    category_mapping = (
        db.query(CategoryMapping)
        .filter(
            CategoryMapping.owner_id == listing.owner_id,
            CategoryMapping.source_category == listing.category,
            CategoryMapping.platform == platform,
        )
        .one_or_none()
    )
    if category_mapping:
        effective["category"] = category_mapping.platform_category
    return effective


def get_due_queued_jobs(db: Session, limit: int) -> list[PublishingJob]:
    return due_queued_jobs_query(db, datetime.now(UTC), limit).all()


def due_queued_jobs_query(db: Session, now: datetime, limit: int, *, lock: bool = False):
    query = (
        db.query(PublishingJob)
        .filter(PublishingJob.status == QUEUED)
        .filter(PublishingJob.scheduled_at <= now)
        .filter((PublishingJob.next_retry_at.is_(None)) | (PublishingJob.next_retry_at <= now))
        .order_by(PublishingJob.scheduled_at.asc(), PublishingJob.id.asc())
    )
    if lock:
        query = query.with_for_update(skip_locked=True)
    return query.limit(limit)


def claim_due_queued_job_ids(db: Session, limit: int) -> list[int]:
    if supports_skip_locked(db):
        return claim_due_queued_job_ids_with_locks(db, limit)

    due_job_ids = [job.id for job in get_due_queued_jobs(db, limit)]
    claimed_job_ids = []
    for job_id in due_job_ids:
        if claim_job_for_processing(db, job_id, due_only=True):
            claimed_job_ids.append(job_id)
    return claimed_job_ids


def supports_skip_locked(db: Session) -> bool:
    bind = db.get_bind()
    return bind.dialect.name in {"postgresql", "mysql", "mariadb", "oracle"}


def claim_due_queued_job_ids_with_locks(db: Session, limit: int) -> list[int]:
    now = datetime.now(UTC)
    jobs = due_queued_jobs_query(db, now, limit, lock=True).all()
    job_ids = [job.id for job in jobs]
    for job in jobs:
        transition_job(job, RUNNING)
        job.started_at = None
        job.finished_at = None
        job.updated_at = now
    if jobs:
        db.commit()
    return job_ids


def recover_stale_running_jobs(db: Session, stale_after_seconds: int, *, limit: int | None = None) -> int:
    if stale_after_seconds <= 0 or (limit is not None and limit <= 0):
        return 0
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    stale_query = (
        db.query(PublishingJob.id, PublishingJob.updated_at, PublishingJob.started_at)
        .filter(PublishingJob.status == RUNNING)
        .filter(
            or_(
                and_(PublishingJob.started_at.is_not(None), PublishingJob.started_at < cutoff),
                and_(PublishingJob.started_at.is_(None), PublishingJob.updated_at < cutoff),
            )
        )
        .order_by(PublishingJob.updated_at.asc(), PublishingJob.id.asc())
    )
    if limit is not None:
        stale_query = stale_query.limit(limit)
    stale_jobs = stale_query.all()
    recovered = 0
    for job in stale_jobs:
        # The SELECT is only a candidate snapshot. A completion, renewed claim,
        # or another recovery must win over this outdated observation.
        changed = db.query(PublishingJob).filter(
            PublishingJob.id == job.id,
            PublishingJob.status == RUNNING,
            PublishingJob.updated_at == job.updated_at,
            PublishingJob.started_at == job.started_at,
        ).update({
            PublishingJob.status: QUEUED,
            PublishingJob.next_retry_at: None,
            PublishingJob.updated_at: datetime.now(UTC),
        }, synchronize_session=False)
        if changed:
            recovered += 1
            db.add(PublishingJobLog(
                job_id=job.id, level="warning",
                message="Recovered stale running job and returned it to the queue.",
                data={"stale_after_seconds": stale_after_seconds},
            ))
    if stale_jobs:
        db.commit()
    return recovered


def process_due_jobs(db: Session, limit: int) -> int:
    if job_processing_is_paused(db):
        return 0
    recover_stale_running_jobs(db, get_settings().job_stale_running_seconds, limit=limit)
    job_ids = claim_due_queued_job_ids(db, limit)
    processed = 0
    for job_id in job_ids:
        _process_claimed_job(db, job_id)
        processed += 1
    return processed
