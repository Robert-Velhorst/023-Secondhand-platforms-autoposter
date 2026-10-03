import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import ListingImage, StorageDeletion, User, now_utc
from app.reconcile import reconcile_database
from app.services.storage_cleanup import process_due_storage_deletions
from app.storage import LocalStorage, S3Storage
from tests.test_data_portability import auth_headers, create_account_deletion_image


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.mark.parametrize("scope", ["account", "listing", "image"])
def test_committed_deletion_survives_storage_failure_and_retries_after_restart(monkeypatch, caplog, scope):
    headers = auth_headers(f"cleanup-{scope}")
    owner_id, listing_id, image_id, path = create_account_deletion_image(headers)
    urls = {
        "account": "/api/auth/me",
        "listing": f"/api/listings/{listing_id}",
        "image": f"/api/listings/{listing_id}/images/{image_id}",
    }

    def fail_delete(self, storage_path):
        raise PermissionError("sensitive-filename-must-not-be-logged")

    with monkeypatch.context() as patch:
        patch.setattr(LocalStorage, "delete", fail_delete)
        response = TestClient(app, raise_server_exceptions=False).delete(urls[scope], headers=headers)
    assert response.status_code == (200 if scope == "image" else 204), response.text
    with SessionLocal() as db:
        assert db.get(ListingImage, image_id) is None
        if scope == "account":
            assert db.get(User, owner_id) is None
    assert Path(path).is_file()
    with SessionLocal() as db:
        pending = db.query(StorageDeletion).one()
        assert pending.storage_path == str(path)
        assert pending.last_error_type == "PermissionError"
        assert pending.attempts == 1
        assert pending.claim_token is None
        assert process_due_storage_deletions(db) == 0  # Backoff, not a tight retry loop.
        report = reconcile_database(db)
        assert report["issues"] == [{
            "code": "pending_storage_cleanup", "count": 1, "failed_attempts_pending": 1,
            "safe_to_auto_repair": False,
        }]
        pending.next_attempt_at = now_utc() - timedelta(seconds=1)
        db.commit()
    assert "sensitive-filename-must-not-be-logged" not in caplog.text
    # Real fresh Python process reads the committed outbox and runs the actual worker.
    result = subprocess.run(
        [sys.executable, "-c", "from app.worker import run_once; run_once(); print('CLEANUP_WORKER_FINISHED')"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "CLEANUP_WORKER_FINISHED" in result.stdout
    assert not path.exists()
    with SessionLocal() as db:
        assert db.query(StorageDeletion).count() == 0


def test_local_cleanup_rejects_paths_outside_configured_root(tmp_path):
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "keep.txt"
    outside.write_bytes(b"unrelated data")
    storage = LocalStorage(root)
    for path in [outside, root / ".." / outside.name, root]:
        with pytest.raises(ValueError, match="outside the configured upload directory"):
            storage.delete(str(path))
    assert outside.read_bytes() == b"unrelated data"
    assert root.is_dir()


def test_local_cleanup_preserves_root_and_propagates_unlink_failure(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    target = root / "image.png"
    target.write_bytes(b"image")
    storage = LocalStorage(root)
    with monkeypatch.context() as patch:
        def denied(self, missing_ok=False):
            raise PermissionError("busy file")
        patch.setattr(Path, "unlink", denied)
        with pytest.raises(PermissionError):
            storage.delete(str(target))
    assert target.is_file()
    storage.delete(str(target))
    storage.delete(str(target))  # Retry after delete-before-ack crash is harmless.
    assert not target.exists()
    assert root.is_dir()


def test_s3_cleanup_rejects_other_bucket_and_prefix(monkeypatch):
    import boto3

    calls = []

    class FakeClient:
        def delete_object(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: FakeClient())
    storage = S3Storage(Settings(s3_bucket="owned", s3_key_prefix="private/uploads"))
    for path in ["local.png", "s3://other/private/uploads/1/x.png", "s3://owned/private/uploads-else/x.png",
                 "s3://owned/private/uploads", "s3://owned/other/x.png"]:
        with pytest.raises(ValueError):
            storage.delete(path)
    assert calls == []
    storage.delete("s3://owned/private/uploads/1/x.png")
    assert calls == [{"Bucket": "owned", "Key": "private/uploads/1/x.png"}]


def test_s3_account_deletion_defers_network_work_until_worker(monkeypatch):
    import boto3

    headers = auth_headers("s3-cleanup")
    owner_id, _, image_id, _ = create_account_deletion_image(headers)
    uri = "s3://owned/uploads/1/image.png"
    with SessionLocal() as db:
        db.get(ListingImage, image_id).storage_path = uri
        db.commit()
    calls = []

    class FakeClient:
        def delete_object(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "owned")
    get_settings.cache_clear()
    try:
        response = TestClient(app).delete("/api/auth/me", headers=headers)
        assert response.status_code == 204, response.text
        assert calls == []
        with SessionLocal() as db:
            assert db.get(User, owner_id) is None
            pending = db.query(StorageDeletion).one()
            assert pending.storage_path == uri and pending.attempts == 0
            assert process_due_storage_deletions(db) == 1
            assert db.query(StorageDeletion).count() == 0
        assert calls == [{"Bucket": "owned", "Key": "uploads/1/image.png"}]
    finally:
        get_settings.cache_clear()
