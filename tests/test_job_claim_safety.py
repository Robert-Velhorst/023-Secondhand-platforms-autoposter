import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import get_settings
from app.database import Base
from app.models import Listing, ListingImage, PublicationAttempt, PublishingJob, User
from app.services.jobs import (
    claim_due_queued_job_ids,
    claim_job_for_processing,
    process_due_jobs,
    process_job,
    recover_stale_running_jobs,
    retry_job,
)


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
            db.execute(User.__table__.insert(), {"id": 1, "email": "claims@example.com", "password_hash": "unused"})
            db.execute(Listing.__table__.insert(), {"id": 1, "owner_id": 1, "title": "Claim safety"})
            db.execute(PublishingJob.__table__.insert(), {
                "id": 1, "listing_id": 1, "platform": "marktplaats", "idempotency_key": "claim-test",
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
