import logging
import sqlite3

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError, TimeoutError
from sqlalchemy.orm import sessionmaker

from app import worker
from app.config import get_settings
from app.database import Base
from app.models import Listing, PublishingJob, User, WorkerHeartbeat


@pytest.fixture
def worker_database(tmp_path, monkeypatch):
    path = tmp_path / "worker.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"timeout": 0})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    settings = get_settings().model_copy(update={
        "auto_create_tables": False,
        "job_worker_poll_seconds": 2,
        "job_process_inline": False,
    })
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    # Keep pytest's logging capture installed; queue/database behavior stays real.
    monkeypatch.setattr(worker, "configure_logging", lambda *_args: None)
    # Alembic's fileConfig in earlier migration tests disables existing loggers.
    monkeypatch.setattr(worker.logger, "disabled", False)
    with sessions() as db:
        user = User(email="worker-resilience@example.com", password_hash="unused")
        db.add(user)
        db.flush()
        db.add(Listing(id=1, owner_id=user.id, title="Incomplete recovery listing"))
        db.commit()
    yield path, engine, sessions, settings
    engine.dispose()


@pytest.mark.parametrize("failure_phase", ["queue", "heartbeat"])
def test_worker_recovers_after_real_database_write_lock(worker_database, monkeypatch, caplog, failure_phase):
    path, engine, sessions, _settings = worker_database

    def queue_job():
        with sessions() as db:
            db.add(PublishingJob(listing_id=1, platform="marktplaats", idempotency_key="lock-recovery"))
            db.commit()

    if failure_phase == "queue":
        queue_job()
    lock = sqlite3.connect(path, timeout=0)
    lock.execute("BEGIN IMMEDIATE")
    waits = []

    def advance(seconds):
        waits.append(seconds)
        assert engine.pool.checkedout() == 0, "Failed cycles must release database sessions before waiting"
        if len(waits) == 1:
            with sessions() as db:
                assert db.query(WorkerHeartbeat).count() == 0, "A failed cycle must not publish a healthy heartbeat"
            lock.rollback()
            if failure_phase == "heartbeat":
                queue_job()
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(worker.time, "sleep", advance)
    caplog.set_level(logging.INFO, logger="autoposter.worker")
    try:
        with pytest.raises(KeyboardInterrupt):
            worker.run_forever()
    finally:
        lock.close()
    assert waits == [2, 2]
    with sessions() as db:
        job = db.query(PublishingJob).one()
        assert job.status == "failed"  # Real missing-field validation, not a mock adapter.
        assert job.attempts == 1
        heartbeat = db.query(WorkerHeartbeat).one()
        assert heartbeat.processed_jobs == 1
    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert "OperationalError" in caplog.text


@pytest.mark.parametrize("error_type", [OperationalError, InterfaceError, TimeoutError])
def test_worker_backs_off_caps_delay_and_resets_after_recovery(worker_database, monkeypatch, caplog, error_type):
    _path, engine, sessions, _settings = worker_database
    waits = []
    secret = "private-sql-parameter-must-not-be-logged"

    def flaky_session():
        # Eight unavailable cycles, a successful cycle, another failure, then recovery.
        if len(waits) < 8 or len(waits) == 9:
            if error_type is TimeoutError:
                raise TimeoutError(secret)
            raise error_type("SELECT private_data", {"secret": secret}, Exception(secret))
        return sessions()

    def advance(seconds):
        waits.append(seconds)
        assert engine.pool.checkedout() == 0
        if len(waits) == 11:
            raise KeyboardInterrupt

    monkeypatch.setattr(worker, "SessionLocal", flaky_session)
    monkeypatch.setattr(worker.time, "sleep", advance)
    caplog.set_level(logging.INFO, logger="autoposter.worker")
    with pytest.raises(KeyboardInterrupt):
        worker.run_forever()
    assert waits == [2, 4, 8, 16, 32, 60, 60, 60, 2, 2, 2]
    with sessions() as db:
        assert db.query(WorkerHeartbeat).count() == 1
    assert secret not in caplog.text
    assert "SELECT private_data" not in caplog.text
    assert sum(record.levelno == logging.WARNING for record in caplog.records) == 9


@pytest.mark.parametrize("error", [
    RuntimeError("programming defect"),
    IntegrityError("invalid write", {}, Exception("invalid data")),
    KeyboardInterrupt(),
    SystemExit(3),
])
def test_worker_does_not_swallow_non_retryable_errors_or_shutdown(worker_database, monkeypatch, error):
    _path, engine, _sessions, _settings = worker_database

    def fail_query(*_args):
        raise error

    def unexpected_wait(_seconds):
        pytest.fail("Non-retryable failures must not enter the retry loop")

    monkeypatch.setattr(worker.time, "sleep", unexpected_wait)
    event.listen(engine, "before_cursor_execute", fail_query)
    try:
        with pytest.raises(type(error)) as caught:
            worker.run_forever()
    finally:
        event.remove(engine, "before_cursor_execute", fail_query)
    assert caught.value is error
    assert engine.pool.checkedout() == 0


def test_worker_backoff_never_shortens_a_long_configured_poll(worker_database, monkeypatch):
    _path, _engine, _sessions, settings = worker_database
    monkeypatch.setattr(worker, "get_settings", lambda: settings.model_copy(update={"job_worker_poll_seconds": 120}))
    waits = []

    def unavailable():
        raise TimeoutError("pool unavailable")

    def advance(seconds):
        waits.append(seconds)
        if len(waits) == 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(worker, "SessionLocal", unavailable)
    monkeypatch.setattr(worker.time, "sleep", advance)
    with pytest.raises(KeyboardInterrupt):
        worker.run_forever()
    assert waits == [120, 120, 120]


def test_worker_rejects_unsafe_startup_before_retrying(worker_database, monkeypatch):
    _path, _engine, _sessions, settings = worker_database
    monkeypatch.setattr(worker, "get_settings", lambda: settings.model_copy(update={"job_worker_poll_seconds": 0}))
    with pytest.raises(RuntimeError, match="JOB_WORKER_POLL_SECONDS"):
        worker.run_forever()
