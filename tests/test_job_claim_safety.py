import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, local

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.adapters import get_adapter
from app.config import get_settings
from app.database import Base
from app.models import Listing, ListingImage, PlatformAccount, PublicationAttempt, PublishingJob, PublishingJobLog, User
from app.services.jobs import (
    PublishingAccountError,
    claim_due_queued_job_ids,
    claim_job_for_processing,
    enqueue_publish_job,
    process_due_jobs,
    process_job,
    recover_stale_running_jobs,
    retry_job,
)
from app.services.operator_controls import set_job_processing_paused


@pytest.fixture
def job_engine(tmp_path, request):
    postgres_url = request.config.getoption("--job-postgres-url")
    admin = None
    if postgres_url:
        url = make_url(postgres_url)
        if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("autoposter_job_test_"):
            raise pytest.UsageError("Job integration tests require a disposable autoposter_job_test_* database")
        admin = create_engine(url)
        schema = f"jobtest_{uuid.uuid4().hex}"
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
        engine = create_engine(isolated_url)
    else:
        engine = create_engine(f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}")

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _record):
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        if postgres_url:
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            migration_url = isolated_url.render_as_string(hide_password=False).replace("%", "%%")
            config.set_main_option("sqlalchemy.url", migration_url)
            command.upgrade(config, "head")
        else:
            Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.execute(User.__table__.insert(), {"email": "claims@example.com", "password_hash": "unused"})
            db.execute(Listing.__table__.insert(), {"id": 1, "owner_id": 1, "title": "Claim safety"})
            db.execute(PublishingJob.__table__.insert(), {
                "listing_id": 1, "platform": "marktplaats", "idempotency_key": "claim-test",
            })
            db.commit()
        yield engine
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            admin.dispose()
        get_settings.cache_clear()


def test_another_request_cannot_execute_a_worker_claim(job_engine):
    with Session(job_engine) as worker:
        assert claim_due_queued_job_ids(worker, 1) == [1]
    with Session(job_engine) as request:
        result = process_job(request, 1)
        assert result.status == "running"
        assert result.attempts == 0
        assert request.query(PublicationAttempt).count() == 0


@pytest.mark.parametrize("batch_claim", [False, True])
def test_reclaimed_job_is_not_immediately_recovered_again(job_engine, batch_claim):
    with Session(job_engine) as db:
        job = db.get(PublishingJob, 1)
        job.status = "running"
        job.started_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
        assert recover_stale_running_jobs(db, 60) == 1
        if batch_claim:
            assert claim_due_queued_job_ids(db, 1) == [1]
        else:
            assert claim_job_for_processing(db, 1)
    with Session(job_engine) as other_worker:
        assert recover_stale_running_jobs(other_worker, 60) == 0
        assert other_worker.get(PublishingJob, 1).status == "running"


@pytest.mark.parametrize("new_state", ["published", "failed", "needs_user_action", "reclaimed", "updated"])
@pytest.mark.parametrize("started", [False, True])
def test_stale_recovery_cannot_overwrite_a_newer_job_version(job_engine, new_state, started):
    old = datetime.now(UTC) - timedelta(hours=1)
    newer = datetime.now(UTC)
    with Session(job_engine) as db:
        db.execute(update(PublishingJob).where(PublishingJob.id == 1).values(
            status="running", started_at=old if started else None, updated_at=old,
        ))
        db.commit()
    observed = False
    expected_status = "running" if new_state in {"reclaimed", "updated"} else new_state

    def change_after_stale_selection(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal observed
        if (not observed and statement.lstrip().upper().startswith("SELECT")
                and "publishing_jobs.started_at <" in statement):
            observed = True
            # Commit after the recovery SELECT has run, but before its stale rows are used.
            with job_engine.begin() as connection:
                values = {"status": expected_status, "updated_at": newer,
                          "result": {"newer_result": True}, "attempts": 2}
                if new_state == "reclaimed":
                    values["started_at"] = newer
                elif new_state not in {"updated"}:
                    values["finished_at"] = newer
                connection.execute(update(PublishingJob).where(PublishingJob.id == 1).values(**values))

    event.listen(job_engine, "after_cursor_execute", change_after_stale_selection)
    try:
        with Session(job_engine) as recovery:
            recovered = recover_stale_running_jobs(recovery, 60)
    finally:
        event.remove(job_engine, "after_cursor_execute", change_after_stale_selection)
    assert observed, "The test must interleave after the real stale-row query"
    with Session(job_engine) as db:
        job = db.get(PublishingJob, 1)
        assert job.status == expected_status
        assert job.result == {"newer_result": True}
        assert job.attempts == 2
        assert db.query(PublishingJobLog).count() == 0
    assert recovered == 0


def test_simultaneous_recovery_records_one_transition_and_log(job_engine):
    old = datetime.now(UTC) - timedelta(hours=1)
    with Session(job_engine) as db:
        db.execute(update(PublishingJob).where(PublishingJob.id == 1).values(
            status="running", started_at=old, updated_at=old,
        ))
        db.commit()
    selected = Barrier(2)

    def synchronize_stale_selection(_connection, _cursor, statement, _parameters, _context, _many):
        if (statement.lstrip().upper().startswith("SELECT")
                and "publishing_jobs.started_at <" in statement):
            selected.wait(timeout=20)

    def recover():
        with Session(job_engine) as db:
            return recover_stale_running_jobs(db, 60)

    event.listen(job_engine, "after_cursor_execute", synchronize_stale_selection)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: recover(), range(2)))
    finally:
        event.remove(job_engine, "after_cursor_execute", synchronize_stale_selection)
    assert sorted(results) == [0, 1]
    with Session(job_engine) as db:
        assert db.get(PublishingJob, 1).status == "queued"
        assert db.query(PublishingJobLog).count() == 1


@pytest.mark.parametrize("batch_size", [0, 2])
def test_worker_cycle_bounds_stale_recovery_to_its_batch(job_engine, batch_size):
    old = datetime.now(UTC) - timedelta(hours=1)
    with Session(job_engine) as db:
        for job_id in range(2, 7):
            db.add(PublishingJob(id=job_id, listing_id=1, platform="marktplaats",
                                 idempotency_key=f"stale-batch-{job_id}"))
        db.flush()
        db.query(PublishingJob).update({
            PublishingJob.status: "running", PublishingJob.started_at: old, PublishingJob.updated_at: old,
        }, synchronize_session=False)
        db.commit()
        assert process_due_jobs(db, batch_size) == batch_size
    with Session(job_engine) as db:
        assert db.query(PublishingJobLog).filter(
            PublishingJobLog.message == "Recovered stale running job and returned it to the queue."
        ).count() == batch_size
        assert db.query(PublishingJob).filter_by(status="running").count() == 6 - batch_size
        assert db.query(PublicationAttempt).count() == batch_size
    if batch_size:
        with Session(job_engine) as db:
            assert process_due_jobs(db, batch_size) == 2
            assert process_due_jobs(db, batch_size) == 2
        with Session(job_engine) as db:
            assert db.query(PublishingJob).filter_by(status="failed").count() == 6
            assert db.query(PublicationAttempt).count() == 6


@pytest.mark.parametrize("control", ["paused", "disabled"])
def test_worker_recovery_preserves_operator_controls(job_engine, monkeypatch, control):
    old = datetime.now(UTC) - timedelta(hours=1)
    with Session(job_engine) as db:
        db.execute(update(PublishingJob).where(PublishingJob.id == 1).values(
            status="running", started_at=old, updated_at=old,
        ))
        db.commit()
        if control == "paused":
            set_job_processing_paused(db, paused=True, reason="Recovery must remain paused")
        else:
            monkeypatch.setenv("JOB_STALE_RUNNING_SECONDS", "0")
            get_settings.cache_clear()
        assert process_due_jobs(db, 2) == 0
    with Session(job_engine) as db:
        assert db.get(PublishingJob, 1).status == "running"
        assert db.query(PublishingJobLog).count() == 0
        assert db.query(PublicationAttempt).count() == 0


def test_recovery_state_rolls_back_if_its_log_cannot_be_saved(job_engine):
    old = datetime.now(UTC) - timedelta(hours=1)
    with Session(job_engine) as db:
        db.execute(update(PublishingJob).where(PublishingJob.id == 1).values(
            status="running", started_at=old, updated_at=old, next_retry_at=old,
        ))
        db.commit()

    def break_log_foreign_key(_mapper, _connection, log):
        log.job_id = 999999

    event.listen(PublishingJobLog, "before_insert", break_log_foreign_key)
    try:
        with Session(job_engine) as db:
            with pytest.raises(IntegrityError):
                recover_stale_running_jobs(db, 60)
            db.rollback()
    finally:
        event.remove(PublishingJobLog, "before_insert", break_log_foreign_key)
    with Session(job_engine) as db:
        job = db.get(PublishingJob, 1)
        assert job.status == "running" and job.next_retry_at is not None
        assert db.query(PublishingJobLog).count() == 0


@pytest.mark.parametrize("status", ["queued", "running"])
def test_retry_does_not_restart_active_work(job_engine, status):
    with Session(job_engine) as db:
        job = db.get(PublishingJob, 1)
        job.status = status
        job.next_retry_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()
        retry_at = job.next_retry_at
        result = retry_job(db, job)
        assert result.status == status
        assert result.attempts == 0
        assert result.next_retry_at == retry_at
        assert db.query(PublicationAttempt).count() == 0


def test_retry_queues_for_separate_worker_when_inline_is_disabled(job_engine, monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    get_settings.cache_clear()
    with Session(job_engine) as db:
        job = db.get(PublishingJob, 1)
        job.status = "failed"
        job.error_message = "Previous failure"
        db.commit()
        result = retry_job(db, job)
        assert result.status == "queued"
        assert result.attempts == 0
        assert result.error_message is None
        assert db.query(PublicationAttempt).count() == 0


def test_inline_processing_preserves_scheduled_backoff(job_engine):
    with Session(job_engine) as db:
        job = db.get(PublishingJob, 1)
        job.next_retry_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()
        result = process_job(db, 1)
        assert result.status == "queued"
        assert result.attempts == 0
        assert result.next_retry_at is not None


@pytest.mark.parametrize("ready", [False, True])
def test_simultaneous_workers_process_each_job_once(job_engine, ready):
    # Real sessions/connections and the real local adapter; no marketplace calls.
    with Session(job_engine) as db:
        for job_id in range(2, 25):
            db.execute(Listing.__table__.insert(), {"id": job_id, "owner_id": 1, "title": f"Job {job_id}"})
            db.execute(PublishingJob.__table__.insert(), {
                "id": job_id, "listing_id": job_id, "platform": "marktplaats",
                "idempotency_key": f"parallel-{job_id}",
            })
        if ready:
            db.query(Listing).update({
                Listing.description: "A synthetic concurrency test listing.", Listing.price_cents: 1000,
                Listing.category: "Home and furniture", Listing.location: "Arnhem",
                Listing.delivery_options: {"pickup": True},
            }, synchronize_session=False)
            db.execute(ListingImage.__table__.insert(), [
                {"listing_id": job_id, "filename": "item.png", "storage_path": "synthetic/item.png",
                 "content_type": "image/png", "file_size": 1, "position": 0}
                for job_id in range(1, 25)
            ])
        db.commit()
    start = Barrier(4)

    def worker():
        start.wait(timeout=20)
        with Session(job_engine) as db:
            # SQLite workers may initially lose a conditional claim and return
            # zero; subsequent passes still drain the queue without duplicates.
            for _ in range(24):
                process_due_jobs(db, 2)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker) for _ in range(4)]
        for future in futures:
            future.result(timeout=60)
    with Session(job_engine) as db:
        jobs = db.query(PublishingJob).order_by(PublishingJob.id).all()
        assert len(jobs) == 24
        expected_status = "needs_user_action" if ready else "failed"
        assert all(job.status == expected_status and job.attempts == 1 for job in jobs), [
            (job.id, job.status, job.attempts, job.error_message) for job in jobs
        ]
        if ready:
            assert all(job.result["automation_mode"] == "assisted" for job in jobs)
        attempts = db.query(PublicationAttempt.job_id).all()
        assert sorted(row.job_id for row in attempts) == list(range(1, 25))


@pytest.mark.parametrize("finished", [False, True])
def test_stale_retry_request_cannot_restart_newer_work(job_engine, monkeypatch, finished):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    get_settings.cache_clear()
    with Session(job_engine) as db:
        db.get(PublishingJob, 1).status = "failed"
        db.commit()
    with Session(job_engine) as first, Session(job_engine) as delayed:
        first_job = first.get(PublishingJob, 1)
        delayed_job = delayed.get(PublishingJob, 1)
        assert retry_job(first, first_job).status == "queued"
        if finished:
            assert process_due_jobs(first, 1) == 1
        else:
            assert claim_due_queued_job_ids(first, 1) == [1]
        assert retry_job(delayed, delayed_job).status == ("failed" if finished else "running")
        assert delayed_job.attempts == (1 if finished else 0)


@pytest.mark.parametrize("status", ["queued", "running", "failed", "skipped", "needs_user_action", "published"])
def test_repeated_enqueue_preserves_existing_job_in_every_state(job_engine, status):
    with Session(job_engine) as db:
        listing = db.get(Listing, 1)
        first = enqueue_publish_job(db, listing, "marktplaats")
        first.status = status
        first.attempts = 2
        db.commit()
        job_id = first.id
        repeated = enqueue_publish_job(db, listing, "marktplaats")
        assert repeated.id == job_id
        assert repeated.status == status
        assert repeated.attempts == 2
        assert db.query(PublishingJob).filter_by(idempotency_key=first.idempotency_key).count() == 1
        assert db.query(PublishingJobLog).filter_by(job_id=job_id).count() == 1


def test_simultaneous_enqueue_returns_one_job_and_one_queue_log(job_engine):
    looked_up = Barrier(2)
    thread_state = local()

    def synchronize_missing_lookup(_connection, _cursor, statement, _parameters, _context, _many):
        # Pause only after each real initial lookup has executed, forcing both
        # callers to observe the absent key before either is allowed to insert.
        if (statement.lstrip().upper().startswith("SELECT")
                and "publishing_jobs.idempotency_key =" in statement
                and not getattr(thread_state, "observed", False)):
            thread_state.observed = True
            looked_up.wait(timeout=20)

    event.listen(job_engine, "after_cursor_execute", synchronize_missing_lookup)

    def enqueue(request_id):
        with Session(job_engine, autoflush=False) as db:
            listing = db.get(Listing, 1)
            db.add(User(email=f"caller-{request_id}@example.com", password_hash="unused"))
            job = enqueue_publish_job(db, listing, "marktplaats")
            job_id = job.id
            db.commit()
            return job_id

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(enqueue, request_id) for request_id in range(2)]
            job_ids = [future.result(timeout=30) for future in futures]
    finally:
        event.remove(job_engine, "after_cursor_execute", synchronize_missing_lookup)
    assert job_ids[0] == job_ids[1]
    with Session(job_engine) as db:
        assert db.query(PublishingJobLog).filter_by(job_id=job_ids[0]).count() == 1
        assert db.query(PublishingJob).count() == 2  # Fixture job plus the single new job.
        assert db.query(User).filter(User.email.in_([
            "caller-0@example.com", "caller-1@example.com",
        ])).count() == 2, "Collision recovery must preserve both callers' pending changes"


def test_enqueue_does_not_hide_integrity_errors_or_discard_prior_changes(job_engine):
    def invalidate_insert(_mapper, _connection, job):
        # Simulate an independent database integrity failure after admission checks.
        job.account_id = 999999

    event.listen(PublishingJob, "before_insert", invalidate_insert)
    try:
        with Session(job_engine) as db:
            listing = db.get(Listing, 1)
            listing.title = "Keep this caller change"
            with pytest.raises(IntegrityError):
                enqueue_publish_job(db, listing, "marktplaats")
            assert db.is_active
            assert db.query(PublishingJob).count() == 1
            db.commit()
    finally:
        event.remove(PublishingJob, "before_insert", invalidate_insert)
    with Session(job_engine) as db:
        assert db.get(Listing, 1).title == "Keep this caller change"


@pytest.mark.parametrize("entrypoint", ["duplicate-enqueue", "worker"])
@pytest.mark.parametrize("changed_field", ["owner_id", "platform"])
def test_changed_account_is_revalidated_on_real_connections(job_engine, monkeypatch, entrypoint, changed_field):
    received = []
    adapter = get_adapter("marktplaats")
    publish = adapter.publish_listing

    def capture_account(listing, account=None, overrides=None):
        received.append(account.id if account else None)
        return publish(listing, account, overrides)

    monkeypatch.setattr(adapter, "publish_listing", capture_account)
    with Session(job_engine) as db:
        db.add(User(id=2, email="other-account-owner@example.com", password_hash="unused"))
        account = PlatformAccount(owner_id=1, platform="marktplaats", display_name="Selected account")
        db.add(account)
        db.commit()
        listing = db.get(Listing, 1)
        job = enqueue_publish_job(db, listing, "marktplaats", account.id)
        assert enqueue_publish_job(db, listing, "marktplaats", account.id).id == job.id
        with job_engine.begin() as connection:
            connection.execute(update(PlatformAccount).where(PlatformAccount.id == account.id).values(
                **{changed_field: 2 if changed_field == "owner_id" else "ebay"}
            ))
        assert account.owner_id == 1 and account.platform == "marktplaats"
        if entrypoint == "duplicate-enqueue":
            with pytest.raises(PublishingAccountError):
                enqueue_publish_job(db, listing, "marktplaats", account.id)
            assert job.status == "queued" and job.attempts == 0
        else:
            result = process_job(db, job.id)
            assert result.status == "failed" and result.attempts == 1
            assert "account" in result.error_message.lower()
        assert received == []
