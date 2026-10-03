from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ListingImage, StorageDeletion
from app.services.image_writes import image_write_scope
from app.storage import ValidatedUpload, store_validated_image
from tests.test_api import PNG_BYTES
from tests.test_job_claim_safety import job_engine as _job_engine

job_engine = _job_engine


@pytest.mark.parametrize("committed", [False, True])
def test_image_recovery_uses_the_business_database_and_preserves_uncertain_commit(
    job_engine, tmp_path, monkeypatch, committed,
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    upload = ValidatedUpload("image.png", PNG_BYTES, "image/png", len(PNG_BYTES), "a" * 64, ".png")
    with Session(job_engine) as db:
        real_commit = db.commit

        def fail_commit():
            if committed:
                real_commit()
            raise OperationalError("COMMIT", {}, RuntimeError("injected acknowledgment failure"))

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(OperationalError, match="injected acknowledgment failure"):
            with image_write_scope(db) as track:
                stored = store_validated_image(upload, 1, on_planned=track)
                db.add(ListingImage(listing_id=1, filename=stored.original_filename, storage_path=stored.storage_path))
                db.commit()
    assert Path(stored.storage_path).exists() is committed
    with Session(job_engine) as db:
        assert db.query(ListingImage).count() == int(committed)
        assert db.query(StorageDeletion).count() == 0


def test_recovery_database_failure_preserves_original_exception_and_avoids_blind_delete(
    job_engine, tmp_path, monkeypatch, caplog,
):
    from app.services import image_writes

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    upload = ValidatedUpload("image.png", PNG_BYTES, "image/png", len(PNG_BYTES), "a" * 64, ".png")

    def unavailable_session(**kwargs):
        raise OperationalError("CONNECT", {}, RuntimeError("sensitive-connection-details"))

    with Session(job_engine) as db:
        monkeypatch.setattr(image_writes, "Session", unavailable_session)
        with pytest.raises(ValueError, match="original write error"):
            with image_write_scope(db) as track:
                stored = store_validated_image(upload, 1, on_planned=track)
                raise ValueError("original write error")
    # No reference check was possible: do not risk deleting a possibly committed object.
    assert Path(stored.storage_path).is_file()
    assert "could not be persisted (OperationalError)" in caplog.text
    assert "sensitive-connection-details" not in caplog.text
