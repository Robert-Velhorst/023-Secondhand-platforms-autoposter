import io
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import duplicate_listing, upload_image
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Listing, ListingImage, StorageDeletion, User, now_utc
from app.services.storage_cleanup import process_due_storage_deletions
from app.storage import LocalStorage
from tests.test_api import PNG_BYTES, client
from tests.test_data_portability import auth_headers, create_account_deletion_image


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_duplicate_preserves_all_editable_listing_details():
    headers = auth_headers("copy-details")
    response = client.post("/api/listings", headers=headers, json={
        "title": "Detailed cabinet", "description": "Details", "price_cents": 4321, "currency": "USD",
        "condition": "used", "category": "Furniture", "location": "Arnhem",
        "delivery_options": {"pickup": True}, "pickup_allowed": True, "shipping_allowed": True,
        "shipping_cost_cents": 123, "dimensions": {"width": 10}, "weight_grams": 500,
        "brand": "Brand", "model": "Model", "color": "Blue", "material": "Oak",
        "category_attributes": {"style": "vintage"}, "notes": "Note", "internal_notes": "Private note",
        "tags": ["cabinet"], "status": "published",
    })
    assert response.status_code == 200, response.text
    source = response.json()
    response = client.post(f"/api/listings/{source['id']}/duplicate", headers=headers)
    assert response.status_code == 200, response.text
    clone = response.json()
    for key in source:
        if key not in {"id", "title", "created_at", "updated_at", "revision", "status", "images", "platform_mappings"}:
            assert clone[key] == source[key], key
    assert clone["status"] == "draft" and clone["revision"] == 1
    assert clone["title"].endswith(" copy") and len(clone["title"]) <= 160


def test_duplicate_refuses_silent_loss_of_missing_source_image():
    headers = auth_headers("copy-missing")
    _, listing_id, _, path = create_account_deletion_image(headers)
    path.unlink()
    response = client.post(f"/api/listings/{listing_id}/duplicate", headers=headers)
    assert response.status_code == 409, response.text
    assert "image" in response.text.lower() and str(path) not in response.text
    with SessionLocal() as db:
        assert db.query(Listing).count() == 1


@pytest.mark.parametrize("operation", ["upload", "duplicate"])
def test_failed_image_commit_cleans_written_objects_without_losing_source(monkeypatch, operation):
    headers = auth_headers(f"write-failure-{operation}")
    owner_id, listing_id, image_id, source_path = create_account_deletion_image(headers)
    before = set(get_settings().upload_path.rglob("*.*"))

    def fail_commit():
        raise OperationalError("COMMIT", {}, RuntimeError("injected image commit failure"))

    with SessionLocal() as db:
        user = db.get(User, owner_id)
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", fail_commit)
            with pytest.raises(OperationalError, match="injected image commit failure"):
                if operation == "duplicate":
                    duplicate_listing(listing_id, user, db)
                else:
                    file = UploadFile(io.BytesIO(PNG_BYTES + b"second"), filename="new.png")
                    upload_image(listing_id, file, user, db)
        db.rollback()
    assert source_path.read_bytes() == PNG_BYTES
    assert set(get_settings().upload_path.rglob("*.*")) == before, "Failed writes must not leak image objects"
    with SessionLocal() as db:
        assert db.query(Listing).count() == 1
        assert db.query(ListingImage).one().id == image_id


def test_duplicate_long_title_remains_valid_and_editable():
    headers = auth_headers("copy-long-title")
    response = client.post("/api/listings", headers=headers, json={"title": "x" * 160})
    assert response.status_code == 200, response.text
    response = client.post(f"/api/listings/{response.json()['id']}/duplicate", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "x" * 155 + " copy"
    saved = client.patch(f"/api/listings/{response.json()['id']}", headers=headers,
                         json={"title": response.json()["title"]})
    assert saved.status_code == 200, saved.text


def test_missing_later_image_rolls_back_clone_and_removes_earlier_copies():
    headers = auth_headers("copy-later-missing")
    _, listing_id, _, source_path = create_account_deletion_image(headers)
    response = client.post(f"/api/listings/{listing_id}/images", headers=headers,
                           files={"file": ("second.png", PNG_BYTES + b"second", "image/png")})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        second = db.query(ListingImage).filter_by(listing_id=listing_id).order_by(ListingImage.id.desc()).first()
        Path(second.storage_path).unlink()
    before = set(get_settings().upload_path.rglob("*.*"))
    response = client.post(f"/api/listings/{listing_id}/duplicate", headers=headers)
    assert response.status_code == 409, response.text
    assert set(get_settings().upload_path.rglob("*.*")) == before
    assert source_path.read_bytes() == PNG_BYTES
    with SessionLocal() as db:
        assert db.query(Listing).count() == 1
        assert db.query(ListingImage).count() == 2


@pytest.mark.parametrize("operation", ["upload", "duplicate"])
def test_partial_storage_write_is_tracked_before_provider_raises(monkeypatch, operation):
    headers = auth_headers(f"partial-{operation}")
    _, listing_id, _, source_path = create_account_deletion_image(headers)
    before = set(get_settings().upload_path.rglob("*.*"))
    real_save = LocalStorage.save_listing_image

    def write_then_fail(self, listing_id, filename, upload):
        real_save(self, listing_id, filename, upload)
        raise OSError("sensitive-provider-details")

    with monkeypatch.context() as patch:
        patch.setattr(LocalStorage, "save_listing_image", write_then_fail)
        http = TestClient(app, raise_server_exceptions=False)
        if operation == "upload":
            response = http.post(f"/api/listings/{listing_id}/images", headers=headers,
                                 files={"file": ("new.png", PNG_BYTES + b"new", "image/png")})
        else:
            response = http.post(f"/api/listings/{listing_id}/duplicate", headers=headers)
    assert response.status_code == 500 and "sensitive-provider-details" not in response.text
    assert set(get_settings().upload_path.rglob("*.*")) == before
    assert source_path.read_bytes() == PNG_BYTES


@pytest.mark.parametrize("operation", ["upload", "duplicate"])
def test_uncertain_commit_preserves_newly_committed_image(monkeypatch, operation):
    headers = auth_headers(f"uncertain-{operation}")
    owner_id, listing_id, _, source_path = create_account_deletion_image(headers)
    with SessionLocal() as db:
        user = db.get(User, owner_id)
        real_commit = db.commit

        def commit_then_fail():
            real_commit()
            raise OperationalError("COMMIT", {}, RuntimeError("lost acknowledgment"))

        monkeypatch.setattr(db, "commit", commit_then_fail)
        with pytest.raises(OperationalError, match="lost acknowledgment"):
            if operation == "upload":
                upload_image(listing_id, UploadFile(io.BytesIO(PNG_BYTES + b"new"), filename="new.png"),
                             user, db)
            else:
                duplicate_listing(listing_id, user, db)
    with SessionLocal() as db:
        images = db.query(ListingImage).all()
        assert len(images) == 2
        assert all(Path(image.storage_path).is_file() for image in images)
        assert db.query(StorageDeletion).count() == 0
    assert source_path.read_bytes() == PNG_BYTES


def test_s3_uncertain_put_is_queued_and_retried_without_exposing_provider_details(monkeypatch):
    import boto3

    headers = auth_headers("s3-uncertain-put")
    created = client.post("/api/listings", headers=headers, json={"title": "S3 upload"})
    assert created.status_code == 200, created.text
    listing_id = created.json()["id"]
    objects = {}

    class FakeS3:
        def put_object(self, **kwargs):
            objects[kwargs["Key"]] = kwargs["Body"]
            raise OSError("sensitive-provider-response")

        def delete_object(self, **kwargs):
            objects.pop(kwargs["Key"], None)

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: FakeS3())
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "private-test-bucket")
    get_settings.cache_clear()
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            f"/api/listings/{listing_id}/images", headers=headers,
            files={"file": ("photo.png", PNG_BYTES, "image/png")},
        )
        assert response.status_code == 500 and "sensitive-provider-response" not in response.text
        assert len(objects) == 1
        with SessionLocal() as db:
            assert db.query(ListingImage).count() == 0
            assert db.query(StorageDeletion).one().storage_path.startswith("s3://private-test-bucket/uploads/")
            assert process_due_storage_deletions(db) == 1
            assert db.query(StorageDeletion).count() == 0
        assert objects == {}
    finally:
        get_settings.cache_clear()


def test_failed_write_keeps_durable_retry_when_local_cleanup_is_locked(monkeypatch):
    headers = auth_headers("write-cleanup-locked")
    _, listing_id, _, _ = create_account_deletion_image(headers)
    real_save = LocalStorage.save_listing_image

    def write_then_fail(self, listing_id, filename, upload):
        real_save(self, listing_id, filename, upload)
        raise OSError("original write failure")

    def deny_cleanup(self, path):
        raise PermissionError("locked")

    with monkeypatch.context() as patch:
        patch.setattr(LocalStorage, "save_listing_image", write_then_fail)
        patch.setattr(LocalStorage, "delete", deny_cleanup)
        with pytest.raises(OSError, match="original write failure"):
            client.post(f"/api/listings/{listing_id}/images", headers=headers,
                        files={"file": ("new.png", PNG_BYTES + b"new", "image/png")})
    with SessionLocal() as db:
        pending = db.query(StorageDeletion).one()
        assert pending.last_error_type == "PermissionError"
        assert process_due_storage_deletions(db, now=now_utc() + timedelta(hours=2)) == 1
        assert db.query(StorageDeletion).count() == 0
