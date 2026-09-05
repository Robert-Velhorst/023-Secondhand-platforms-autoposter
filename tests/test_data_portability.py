import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import (
    AuditEvent,
    CategoryMapping,
    Listing,
    ListingImage,
    ListingTemplate,
    PlatformAccount,
    PlatformOAuthState,
    PublishingJob,
    User,
)
from app.services.audit import purge_expired_audit_events, record_audit_event
from tests.test_api import PNG_BYTES, client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers(prefix: str):
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{prefix}-{uuid.uuid4().hex}@example.com",
            "password": "correct-password",
            "name": f"{prefix} User",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def create_portable_workspace(headers):
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Portable cabinet",
            "description": "Oak cabinet with two drawers.",
            "price_cents": 11900,
            "condition": "used",
            "category": "Furniture",
            "location": "Arnhem",
            "brand": "Vintage Co",
            "category_attributes": {"style": "mid-century", "doors": 2},
            "shipping_allowed": True,
            "shipping_cost_cents": 1500,
            "tags": ["cabinet", "oak"],
        },
    )
    assert listing_response.status_code == 200, listing_response.text
    listing_id = listing_response.json()["id"]

    override_response = client.post(
        f"/api/listings/{listing_id}/platforms",
        headers=headers,
        json={
            "platform": "marktplaats",
            "overrides": {"description": "Marktplaats specific copy"},
            "selected": True,
        },
    )
    assert override_response.status_code == 200, override_response.text

    account_response = client.post(
        "/api/accounts",
        headers=headers,
        json={
            "platform": "ebay",
            "display_name": "Portable eBay",
            "mode": "assisted",
            "status": "ready",
            "connection_data": {"store": "main", "access_token": "do-not-export"},
        },
    )
    assert account_response.status_code == 200, account_response.text

    db = SessionLocal()
    try:
        account = db.query(PlatformAccount).filter(PlatformAccount.display_name == "Portable eBay").one()
        account.secret_ref = "vault://secret/platform-token"
        db.commit()
    finally:
        db.close()

    template_response = client.post(
        "/api/templates",
        headers=headers,
        json={
            "name": "Pickup",
            "variant": "appointment",
            "platform": None,
            "body": "Pickup is available by appointment.",
        },
    )
    assert template_response.status_code == 200, template_response.text

    mapping_response = client.post(
        "/api/category-mappings",
        headers=headers,
        json={
            "source_category": "Furniture",
            "platform": "marktplaats",
            "platform_category": "Huis en Inrichting",
        },
    )
    assert mapping_response.status_code == 200, mapping_response.text


def test_export_omits_private_and_secret_fields():
    headers = auth_headers("export")
    create_portable_workspace(headers)

    response = client.get("/api/export", headers=headers)

    assert response.status_code == 200, response.text
    bundle = response.json()
    assert bundle["version"] == "1"
    assert bundle["listings"][0]["title"] == "Portable cabinet"
    assert bundle["listings"][0]["platform_mappings"][0]["platform"] == "marktplaats"
    assert bundle["platform_accounts"][0]["connection_data"] == {"store": "main"}
    assert bundle["templates"][0]["variant"] == "appointment"

    serialized = json.dumps(bundle)
    assert "password_hash" not in serialized
    assert "token_hash" not in serialized
    assert "revoked_at" not in serialized
    assert "secret_ref" not in serialized
    assert "vault://secret/platform-token" not in serialized
    assert "do-not-export" not in serialized

    db = SessionLocal()
    try:
        event = db.query(AuditEvent).filter(AuditEvent.action == "data_exported").one()
        assert event.user_email_hash
        assert event.event_data == {
            "listings": 1,
            "platform_accounts": 1,
            "templates": 1,
            "category_mappings": 1,
        }
        assert "export-" not in json.dumps(event.event_data)
    finally:
        db.close()


def test_import_recreates_user_owned_business_data():
    source_headers = auth_headers("source")
    create_portable_workspace(source_headers)
    bundle = client.get("/api/export", headers=source_headers).json()

    target_headers = auth_headers("target")
    import_response = client.post("/api/import", headers=target_headers, json=bundle)

    assert import_response.status_code == 200, import_response.text
    result = import_response.json()
    assert result["listings_created"] == 1
    assert result["platform_mappings_created"] == 1
    assert result["platform_accounts_created"] == 1
    assert result["templates_created"] == 1
    assert result["category_mappings_created"] == 1

    listings = client.get("/api/listings", headers=target_headers).json()
    assert len(listings) == 1
    assert listings[0]["title"] == "Portable cabinet"
    assert listings[0]["platform_mappings"][0]["status"] == "draft"
    assert listings[0]["platform_mappings"][0]["overrides"]["description"] == "Marktplaats specific copy"

    accounts = client.get("/api/accounts", headers=target_headers).json()
    assert accounts[0]["display_name"] == "Portable eBay"
    assert "secret_ref" not in accounts[0]

    templates = client.get("/api/templates", headers=target_headers).json()
    assert templates[0]["name"] == "Pickup"
    assert templates[0]["variant"] == "appointment"

    mappings = client.get("/api/category-mappings", headers=target_headers).json()
    assert mappings[0]["platform_category"] == "Huis en Inrichting"

    db = SessionLocal()
    try:
        event = db.query(AuditEvent).filter(AuditEvent.action == "data_imported").one()
        assert event.event_data["listings_created"] == 1
        assert event.event_data["platform_accounts_created"] == 1
        assert event.event_data["skipped"] == 0
    finally:
        db.close()


def test_listing_csv_export_and_import_round_trip():
    source_headers = auth_headers("csv-source")
    create_portable_workspace(source_headers)

    csv_response = client.get("/api/export/listings.csv", headers=source_headers)

    assert csv_response.status_code == 200, csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")
    csv_text = csv_response.text
    assert "Portable cabinet" in csv_text
    assert "cabinet, oak" in csv_text
    assert "password_hash" not in csv_text

    target_headers = auth_headers("csv-target")
    import_response = client.post(
        "/api/import/listings.csv",
        headers=target_headers,
        files={"file": ("listings.csv", csv_text.encode("utf-8"), "text/csv")},
    )

    assert import_response.status_code == 200, import_response.text
    assert import_response.json()["listings_created"] == 1
    listings = client.get("/api/listings", headers=target_headers).json()
    assert listings[0]["title"] == "Portable cabinet"
    assert listings[0]["tags"] == ["cabinet", "oak"]
    assert listings[0]["shipping_allowed"] is True
    assert listings[0]["category_attributes"]["style"] == "mid-century"

    db = SessionLocal()
    try:
        actions = {event.action for event in db.query(AuditEvent).all()}
        assert "listings_csv_exported" in actions
        assert "listings_csv_imported" in actions
    finally:
        db.close()


def test_image_zip_export_contains_manifest_and_owned_images():
    headers = auth_headers("image-export")
    create_portable_workspace(headers)
    listing = client.get("/api/listings", headers=headers).json()[0]
    image_response = client.post(
        f"/api/listings/{listing['id']}/images",
        headers=headers,
        files={"file": ("cabinet.png", PNG_BYTES, "image/png")},
    )
    assert image_response.status_code == 200, image_response.text

    response = client.get("/api/export/images.zip", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "1"
        assert manifest["missing"] == []
        assert len(manifest["images"]) == 1
        archive_path = manifest["images"][0]["archive_path"]
        assert archive_path in names
        assert archive.read(archive_path) == PNG_BYTES
        assert manifest["images"][0]["filename"] == "cabinet.png"

    db = SessionLocal()
    try:
        event = db.query(AuditEvent).filter(AuditEvent.action == "images_exported").one()
        assert event.event_data == {"images": 1, "missing": 0}
    finally:
        db.close()


def test_image_zip_export_reports_object_storage_images_in_manifest():
    headers = auth_headers("s3-image-export")
    create_portable_workspace(headers)
    listing = client.get("/api/listings", headers=headers).json()[0]
    db = SessionLocal()
    try:
        db.add(
            ListingImage(
                listing_id=listing["id"],
                filename="remote.png",
                storage_path="s3://autoposter-images/uploads/1/remote.png",
                content_type="image/png",
                file_size=123,
                checksum_sha256="b" * 64,
                position=0,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/export/images.zip", headers=headers)

    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["images"] == []
        assert manifest["missing"][0]["filename"] == "remote.png"
        assert manifest["missing"][0]["reason"] == "object_storage_not_exportable"


def test_privacy_audit_events_are_reviewable_and_owner_scoped():
    owner_headers = auth_headers("audit-owner")
    other_headers = auth_headers("audit-other")
    client.get("/api/export", headers=owner_headers)
    client.get("/api/export/listings.csv", headers=owner_headers)
    client.get("/api/export", headers=other_headers)

    response = client.get("/api/audit-events?limit=10", headers=owner_headers)

    assert response.status_code == 200, response.text
    assert response.headers["X-Total-Count"] == "2"
    events = response.json()
    assert {event["action"] for event in events} == {"data_exported", "listings_csv_exported"}
    serialized = json.dumps(events)
    assert "audit-other" not in serialized
    assert "user_email_hash" not in serialized
    assert "user_id" not in serialized

    filtered = client.get("/api/audit-events?action=listings_csv_exported", headers=owner_headers)
    assert filtered.status_code == 200, filtered.text
    assert [event["action"] for event in filtered.json()] == ["listings_csv_exported"]


def test_frontend_exposes_privacy_activity_review():
    html = Path("public/index.html").read_text(encoding="utf-8")
    script = Path("public/app.js").read_text(encoding="utf-8")

    assert 'id="auditEventList"' in html
    assert "/audit-events?limit=8" in script
    assert "state.auditEvents" in script


def test_delete_me_purges_owned_data_and_revokes_session():
    headers = auth_headers("delete")
    create_portable_workspace(headers)
    listing = client.get("/api/listings", headers=headers).json()[0]
    image_response = client.post(
        f"/api/listings/{listing['id']}/images",
        headers=headers,
        files={"file": ("cabinet.png", PNG_BYTES, "image/png")},
    )
    assert image_response.status_code == 200, image_response.text
    image_id = image_response.json()["images"][0]["id"]
    with SessionLocal() as db:
        image_path = db.query(ListingImage.storage_path).filter(ListingImage.id == image_id).scalar()
    assert image_path
    publish_response = client.post(
        f"/api/listings/{listing['id']}/publish",
        headers=headers,
        json={"platforms": ["marktplaats"], "process_now": True},
    )
    assert publish_response.status_code == 200, publish_response.text

    other_headers = auth_headers("keep")
    other_listing = client.post("/api/listings", headers=other_headers, json={"title": "Keep me"})
    assert other_listing.status_code == 200, other_listing.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email.like("delete-%")).one()
        db.add(
            PlatformOAuthState(
                user_id=user.id,
                platform="ebay",
                state_hash="0" * 64,
                redirect_uri="https://app.example.com/callback",
                scopes=["https://api.ebay.com/oauth/api_scope/sell.inventory"],
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        db.commit()
    finally:
        db.close()

    delete_response = client.delete("/api/auth/me", headers=headers)

    assert delete_response.status_code == 204, delete_response.text
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/listings", headers=other_headers).json()[0]["title"] == "Keep me"

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email.like("delete-%")).count() == 0
        assert db.query(Listing).filter(Listing.title == "Portable cabinet").count() == 0
        assert db.query(PublishingJob).count() == 0
        assert db.query(PlatformAccount).filter(PlatformAccount.display_name == "Portable eBay").count() == 0
        assert db.query(PlatformOAuthState).count() == 0
        assert db.query(ListingTemplate).filter(ListingTemplate.name == "Pickup").count() == 0
        assert db.query(CategoryMapping).filter(CategoryMapping.source_category == "Furniture").count() == 0
        event = db.query(AuditEvent).filter(AuditEvent.action == "account_deleted").one()
        assert event.user_id is not None
        assert event.user_email_hash
        assert event.event_data["listings_deleted"] == 1
        assert event.event_data["jobs_deleted"] == 1
        assert event.event_data["images_deleted"] == 1
        assert event.event_data["platform_accounts_deleted"] == 1
        assert "delete-" not in json.dumps(event.event_data)
    finally:
        db.close()
    assert not Path(image_path).exists()


def test_audit_retention_purges_only_expired_events():
    headers = auth_headers("audit-retention")
    client.get("/api/export", headers=headers)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email.like("audit-retention-%")).one()
        old_event = record_audit_event(db, user, "old_event", {"count": 1})
        old_event.created_at = datetime.now(UTC) - timedelta(days=400)
        recent_event = record_audit_event(db, user, "recent_event", {"count": 1})
        recent_event.created_at = datetime.now(UTC)
        db.commit()

        assert purge_expired_audit_events(db, retention_days=365) == 1
        actions = {event.action for event in db.query(AuditEvent).all()}
        assert "old_event" not in actions
        assert "recent_event" in actions
        assert "data_exported" in actions
    finally:
        db.close()


def test_audit_retention_can_be_disabled():
    headers = auth_headers("audit-retention-disabled")
    client.get("/api/export", headers=headers)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email.like("audit-retention-disabled-%")).one()
        event = record_audit_event(db, user, "very_old_event", {})
        event.created_at = datetime.now(UTC) - timedelta(days=4000)
        db.commit()

        assert purge_expired_audit_events(db, retention_days=0) == 0
        assert db.query(AuditEvent).filter(AuditEvent.action == "very_old_event").count() == 1
    finally:
        db.close()
