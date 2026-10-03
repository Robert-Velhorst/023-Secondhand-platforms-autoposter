from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from importlib import import_module
from threading import Barrier

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import DateTime, bindparam, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import rate_limit
from app.config import get_settings
from app.models import LoginThrottle
from tests.test_job_claim_safety import job_engine as _job_engine

job_engine = _job_engine


def test_atomic_login_admission_across_independent_connections(job_engine, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "3")
    get_settings.cache_clear()
    start = Barrier(12)

    def admit(_):
        with Session(job_engine) as db:
            start.wait(timeout=10)
            try:
                return rate_limit.reserve_login_attempt(db, "shared-login")
            except HTTPException as exc:
                assert exc.status_code == 429
                assert int(exc.headers["Retry-After"]) > 0
                return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(admit, range(12)))
    reservations = [result for result in results if result is not None]
    assert len(reservations) == 3
    assert len({result.attempt_token for result in reservations}) == 3
    with Session(job_engine) as db:
        stored = db.query(LoginThrottle).one()
        assert stored.attempts == 3
        assert stored.attempt_token in {result.attempt_token for result in reservations}


def test_stale_identity_map_cannot_overwrite_newer_attempt_count(job_engine):
    with Session(job_engine) as first:
        rate_limit.reserve_login_attempt(first, "stale-session")
        stale = first.query(LoginThrottle).one()
        assert stale.attempts == 1
        with Session(job_engine) as second:
            rate_limit.reserve_login_attempt(second, "stale-session")
        rate_limit.reserve_login_attempt(first, "stale-session")
    with Session(job_engine) as fresh:
        assert fresh.query(LoginThrottle).one().attempts == 3


def test_success_clear_is_fenced_and_commits_with_its_caller(job_engine):
    with Session(job_engine) as db:
        old = rate_limit.reserve_login_attempt(db, "completion-order")
        newer = rate_limit.reserve_login_attempt(db, "completion-order")
        rate_limit.clear_successful_login(db, old)
        db.commit()
        assert db.query(LoginThrottle).one().attempt_token == newer.attempt_token
        rate_limit.clear_successful_login(db, newer)
        db.rollback()
        assert db.query(LoginThrottle).one().attempts == 2
        rate_limit.clear_successful_login(db, newer)
        db.commit()
        assert db.query(LoginThrottle).count() == 0


def test_exact_expiry_starts_new_generation_and_rejects_old_completion(job_engine, monkeypatch):
    instant = [datetime(2026, 9, 13, tzinfo=UTC)]

    class Clock:
        @staticmethod
        def now(tz):
            return instant[0]

    monkeypatch.setattr(rate_limit, "datetime", Clock)
    with Session(job_engine) as db:
        old = rate_limit.reserve_login_attempt(db, "expired-generation")
        instant[0] += timedelta(seconds=get_settings().login_rate_limit_window_seconds)
        fresh = rate_limit.reserve_login_attempt(db, "expired-generation")
        assert fresh.attempt_token != old.attempt_token
        rate_limit.clear_successful_login(db, old)
        db.commit()
        stored = db.query(LoginThrottle).one()
        assert stored.attempts == 1 and stored.attempt_token == fresh.attempt_token


def test_failed_admission_commit_rolls_back_without_a_reserved_slot(job_engine, monkeypatch):
    def fail_commit():
        raise OperationalError("COMMIT", {}, RuntimeError("synthetic admission failure"))

    with Session(job_engine) as db:
        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(OperationalError, match="synthetic admission failure"):
            rate_limit.reserve_login_attempt(db, "failed-admission")
        db.rollback()
    with Session(job_engine) as fresh:
        assert fresh.query(LoginThrottle).count() == 0


def test_cleanup_racing_with_refresh_preserves_the_new_window(job_engine):
    for _ in range(5):
        expired = datetime.now(UTC) - timedelta(seconds=get_settings().login_rate_limit_window_seconds + 1)
        with Session(job_engine) as db:
            db.add(LoginThrottle(identifier_hash=rate_limit._identifier_hash("refresh-race"), attempts=5,
                                 window_started_at=expired, last_failed_at=expired))
            db.commit()
        start = Barrier(2)

        def refresh(start=start):
            with Session(job_engine) as db:
                start.wait(timeout=10)
                return rate_limit.reserve_login_attempt(db, "refresh-race")

        def purge(start=start):
            with Session(job_engine) as db:
                start.wait(timeout=10)
                return rate_limit.purge_expired_login_throttles(db)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fresh = pool.submit(refresh)
            cleaned = pool.submit(purge)
            reservation = fresh.result(timeout=10)
            assert cleaned.result(timeout=10) in {0, 1}
        with Session(job_engine) as db:
            assert db.query(LoginThrottle).one().attempt_token == reservation.attempt_token
            rate_limit.clear_successful_login(db, reservation)
            db.commit()


def test_cleanup_batch_size_is_clamped_and_zero_does_no_work(job_engine):
    expired = datetime.now(UTC) - timedelta(seconds=get_settings().login_rate_limit_window_seconds + 1)
    with Session(job_engine) as db:
        db.add_all([LoginThrottle(identifier_hash=f'{index:064x}', attempts=1,
                                 window_started_at=expired, last_failed_at=expired) for index in range(105)])
        db.commit()
        assert rate_limit.purge_expired_login_throttles(db, batch_size=0) == 0
        assert rate_limit.purge_expired_login_throttles(db, batch_size=1000) == 100
        assert db.query(LoginThrottle).count() == 5


def test_additive_migration_preserves_legacy_throttle_records(job_engine):
    migration = import_module("migrations.versions.20260913_0016_login_attempt_tokens")
    with job_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        connection.execute(text(
            "INSERT INTO login_throttles (identifier_hash, attempts, window_started_at, last_failed_at) "
            "VALUES (:identifier, 4, :now, :now)"
        ).bindparams(bindparam("now", type_=DateTime(timezone=True))),
            {"identifier": "a" * 64, "now": datetime.now(UTC)})
        before = dict(connection.execute(text("SELECT * FROM login_throttles")).mappings().one())
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        after = dict(connection.execute(text("SELECT * FROM login_throttles")).mappings().one())
        assert after.pop("attempt_token") is None
        assert after == before
    assert "ix_login_throttles_window_started_at" in {
        index["name"] for index in inspect(job_engine).get_indexes("login_throttles")
    }


def test_downgrade_refuses_to_discard_login_reservations(job_engine):
    migration = import_module("migrations.versions.20260913_0016_login_attempt_tokens")
    with Session(job_engine) as db:
        reservation = rate_limit.reserve_login_attempt(db, "pending-downgrade")
    with job_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="Drain login reservations"):
                migration.downgrade()
    with Session(job_engine) as db:
        assert db.query(LoginThrottle).one().attempt_token == reservation.attempt_token


@pytest.mark.parametrize("scenario", ["burst", "completion-order"])
def test_real_http_login_interleavings_on_selected_database(job_engine, monkeypatch, scenario):
    from app.database import get_db
    from app.main import app
    from tests import test_login_admission
    from tests.test_login_admission import (
        test_concurrent_login_burst_cannot_start_more_password_checks_than_the_limit as check_burst,
    )
    from tests.test_login_admission import test_older_success_cannot_clear_a_newer_failed_login as check_completion

    def isolated_session():
        with Session(job_engine, autoflush=False) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_session)
    monkeypatch.setattr(test_login_admission, "SessionLocal", lambda: Session(job_engine))
    if scenario == "burst":
        check_burst(monkeypatch)
    else:
        check_completion(monkeypatch)
