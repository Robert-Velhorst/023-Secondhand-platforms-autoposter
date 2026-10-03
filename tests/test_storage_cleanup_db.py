"""Run against SQLite by default and migrated disposable PostgreSQL in CI."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from importlib import import_module
from threading import Barrier, local

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ListingImage, StorageDeletion, now_utc
from app.services.storage_cleanup import CLAIM_SECONDS, process_due_storage_deletions, queue_storage_deletions
from app.storage import LocalStorage
from tests.test_job_claim_safety import job_engine as _job_engine

job_engine = _job_engine  # Reuse the guarded, per-test SQLite/PostgreSQL fixture.


def pending_file(job_engine, tmp_path):
    root = tmp_path / "uploads"
    root.mkdir(exist_ok=True)
    path = root / "cleanup.png"
    path.write_bytes(b"disposable image")
    with Session(job_engine) as db:
        [deletion_id] = queue_storage_deletions(db, [str(path)])
        db.commit()
    return path, deletion_id, Settings(storage_backend="local", upload_dir=str(root))


def test_cleanup_intent_rolls_back_with_business_transaction(job_engine, tmp_path):
    path = tmp_path / "retained.png"
    path.write_bytes(b"keep")
    with Session(job_engine) as db:
        queue_storage_deletions(db, [str(path)])
        db.flush()
        db.rollback()
    with Session(job_engine) as db:
        assert db.query(StorageDeletion).count() == 0
    assert path.read_bytes() == b"keep"


def test_failed_claim_commit_cannot_delete_file(job_engine, tmp_path, monkeypatch):
    path, deletion_id, settings = pending_file(job_engine, tmp_path)

    def fail_commit():
        raise OperationalError("COMMIT", {}, RuntimeError("injected"))

    with Session(job_engine) as db:
        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(OperationalError):
            process_due_storage_deletions(db, settings=settings)
    assert path.is_file()
    with Session(job_engine) as db:
        pending = db.get(StorageDeletion, deletion_id)
        assert pending.claim_token is None and pending.attempts == 0


@pytest.mark.parametrize("unlink_first", [False, True])
def test_cleanup_recovers_crash_before_or_after_unlink(job_engine, tmp_path, monkeypatch, unlink_first):
    path, deletion_id, settings = pending_file(job_engine, tmp_path)
    start = now_utc()
    real_delete = LocalStorage.delete

    class ProcessCrash(BaseException):
        pass

    def crash(self, storage_path):
        if unlink_first:
            real_delete(self, storage_path)
        raise ProcessCrash()

    with monkeypatch.context() as patch:
        patch.setattr(LocalStorage, "delete", crash)
        with Session(job_engine) as db, pytest.raises(ProcessCrash):
            process_due_storage_deletions(db, settings=settings, now=start)
    assert path.exists() is not unlink_first
    with Session(job_engine) as db:
        pending = db.get(StorageDeletion, deletion_id)
        assert pending.claim_token and pending.attempts == 1
        assert process_due_storage_deletions(db, settings=settings, now=start) == 0
    with Session(job_engine) as restarted:
        assert process_due_storage_deletions(
            restarted, settings=settings, now=start + timedelta(seconds=CLAIM_SECONDS + 1)
        ) == 1
        assert restarted.get(StorageDeletion, deletion_id) is None
    assert not path.exists()


def test_cleanup_preserves_still_referenced_file(job_engine, tmp_path):
    path, deletion_id, settings = pending_file(job_engine, tmp_path)
    with Session(job_engine) as db:
        db.add(ListingImage(listing_id=1, filename="shared.png", storage_path=str(path)))
        db.commit()
        assert process_due_storage_deletions(db, settings=settings) == 1
        assert db.get(StorageDeletion, deletion_id) is None
    assert path.is_file()


def test_competing_workers_claim_cleanup_once(job_engine, tmp_path, monkeypatch):
    path, _, settings = pending_file(job_engine, tmp_path)
    barrier = Barrier(2)
    entered = local()
    deletions = []
    real_delete = LocalStorage.delete

    def before_select(connection, cursor, statement, parameters, context, executemany):
        if (statement.lstrip().startswith("SELECT") and "storage_deletions" in statement
                and not getattr(entered, "yes", False)):
            entered.yes = True
            barrier.wait(timeout=10)

    def delete(self, storage_path):
        deletions.append(storage_path)
        real_delete(self, storage_path)

    def run():
        with Session(job_engine) as db:
            return process_due_storage_deletions(db, settings=settings)

    monkeypatch.setattr(LocalStorage, "delete", delete)
    event.listen(job_engine, "before_cursor_execute", before_select)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(run), pool.submit(run)]
            assert sorted(task.result(timeout=20) for task in tasks) == [0, 1]
    finally:
        event.remove(job_engine, "before_cursor_execute", before_select)
    assert deletions == [str(path)]
    assert not path.exists()
    with Session(job_engine) as db:
        assert db.query(StorageDeletion).count() == 0


@pytest.mark.parametrize("fail", [False, True])
def test_late_cleanup_ack_cannot_overwrite_newer_claim(job_engine, tmp_path, monkeypatch, fail):
    path, deletion_id, settings = pending_file(job_engine, tmp_path)
    new_due = now_utc() + timedelta(hours=1)

    def newer_claim(self, storage_path):
        # Separate connection proves no write lock is held over storage I/O.
        with Session(job_engine) as other:
            other.query(StorageDeletion).filter_by(id=deletion_id).update({
                "claim_token": "b" * 32, "last_error_type": "NewerClaim", "next_attempt_at": new_due,
            })
            other.commit()
        if fail:
            raise PermissionError("late failure")

    monkeypatch.setattr(LocalStorage, "delete", newer_claim)
    with Session(job_engine) as db:
        assert process_due_storage_deletions(db, settings=settings) == 0
    with Session(job_engine) as db:
        pending = db.get(StorageDeletion, deletion_id)
        assert pending.claim_token == "b" * 32
        assert pending.last_error_type == "NewerClaim"
    assert path.exists()


def test_cleanup_batch_is_bounded_and_unknown_path_is_retained(job_engine, tmp_path):
    settings = Settings(upload_dir=str(tmp_path / "owned"), storage_backend="local")
    outside = tmp_path / "not-owned.png"
    outside.write_bytes(b"keep")
    with Session(job_engine) as db:
        queue_storage_deletions(db, [str(outside)])
        for i in range(7):
            queue_storage_deletions(db, [str(tmp_path / "owned" / f"missing-{i}.png")])
        db.commit()
        process_due_storage_deletions(db, settings=settings, limit=999)
        # Exactly five claims, with a path outside the root retained if attempted.
        remaining = db.query(StorageDeletion).all()
        assert len(remaining) in (3, 4)
        attempted = [row for row in remaining if row.attempts]
        assert all(row.last_error_type == "ValueError" for row in attempted)
        process_due_storage_deletions(db, settings=settings, now=now_utc() + timedelta(hours=2))
        remaining = db.query(StorageDeletion).all()
        assert len(remaining) == 1 and remaining[0].storage_path == str(outside)
        assert remaining[0].last_error_type == "ValueError"
    assert outside.read_bytes() == b"keep"


def test_cleanup_migration_roundtrip_preserves_business_rows_and_refuses_pending_work(job_engine, tmp_path):
    migration = import_module("migrations.versions.20260913_0015_storage_deletions")
    with job_engine.connect() as connection:
        before = dict(connection.execute(text("SELECT * FROM publishing_jobs WHERE id = 1")).mappings().one())
    with job_engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert not inspect(connection).has_table("storage_deletions")
        migration.upgrade()
        migration.upgrade()  # Compatible with the historical metadata bootstrap.
    _, deletion_id, _ = pending_file(job_engine, tmp_path)
    with pytest.raises(RuntimeError, match="Drain storage_deletions"):
        with job_engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    with Session(job_engine) as db:
        assert db.get(StorageDeletion, deletion_id) is not None
    with job_engine.connect() as connection:
        assert dict(connection.execute(text("SELECT * FROM publishing_jobs WHERE id = 1")).mappings().one()) == before
