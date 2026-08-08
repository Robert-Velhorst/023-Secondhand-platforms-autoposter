import json
import zipfile

from app.config import Settings
from app.database import Base, SessionLocal, engine
from app.models import ListingImage
from app.reconcile import reconcile_database
from app.support_bundle import build_support_bundle
from tests.factories import create_listing, register_user
from tests.test_api import client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_reconciliation_repairs_only_safe_image_positions():
    headers = register_user(client, "reconcile")
    listing = create_listing(client, headers)
    db = SessionLocal()
    try:
        db.add(
            ListingImage(
                listing_id=listing["id"],
                filename="one.png",
                storage_path="local://one.png",
                content_type="image/png",
                file_size=1,
                checksum_sha256="a" * 64,
                position=4,
            )
        )
        db.commit()
        report = reconcile_database(db, repair_safe=True)
        image = db.query(ListingImage).one()
    finally:
        db.close()

    assert report["status"] == "issues_found"
    assert report["repairs"] == [{"code": "image_positions_reindexed", "listing_id": listing["id"]}]
    assert image.position == 0


def test_support_bundle_contains_only_sanitized_operational_evidence(tmp_path):
    db = SessionLocal()
    settings = Settings(
        database_url="sqlite:///./data/test_autoposter.db",
        secret_key="super-secret-value-that-must-not-appear",
        ebay_oauth_client_secret="ebay-secret-that-must-not-appear",
    )
    try:
        path = build_support_bundle(tmp_path / "support.zip", settings, db)
    finally:
        db.close()

    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        contents = "\n".join(archive.read(name).decode("utf-8") for name in names)
        runtime = json.loads(archive.read("runtime-summary.json"))

    assert names >= {"metadata.json", "runtime-summary.json", "doctor.json", "operator-control.json"}
    assert runtime["database_backend"] == "sqlite"
    assert runtime["secrets_present"]["ebay_client_secret"] is True
    assert "super-secret-value" not in contents
    assert "ebay-secret" not in contents
