import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.test_api import PNG_BYTES, app, client


def _register(prefix: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{prefix}-{uuid.uuid4().hex}@example.com",
            "password": "correct-password",
            "name": "HAI owner",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _create_hai_token(headers: dict[str, str]) -> tuple[int, dict[str, str]]:
    response = client.post(
        "/api/hai/tokens",
        headers=headers,
        json={"name": "Local HAI", "expires_days": 30},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["token"].startswith("hai_")
    return payload["id"], {"Authorization": f"Bearer {payload['token']}"}


def test_hai_manifest_is_honest_and_read_only():
    response = client.get("/.well-known/hai-connector.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["connector_key"] == "secondhand-platforms-autoposter"
    assert payload["mode"] == "read_only_pull"
    assert payload["capabilities"]["incremental_sync"] is True
    assert payload["capabilities"]["tombstones"] is True
    assert payload["capabilities"]["write_back"] is False
    assert payload["capabilities"]["credentials_exported"] is False


def test_hai_token_is_scoped_incremental_and_revocable():
    owner_headers = _register("hai-owner")
    foreign_headers = _register("hai-foreign")
    listing_response = client.post(
        "/api/listings",
        headers=owner_headers,
        json={
            "title": "Oak desk",
            "description": "Solid oak desk for a home office.",
            "price_cents": 7500,
            "category": "Furniture",
            "internal_notes": "Never export this private note",
            "tags": ["oak", "desk"],
        },
    )
    listing_id = listing_response.json()["id"]
    token_id, hai_headers = _create_hai_token(owner_headers)
    _, foreign_hai_headers = _create_hai_token(foreign_headers)

    assert client.get("/api/hai/status", headers=owner_headers).status_code == 401
    status = client.get("/api/hai/status", headers=hai_headers)
    assert status.status_code == 200
    assert status.json()["write_back"] is False

    first_page = client.get("/api/hai/records?limit=1", headers=hai_headers)
    assert first_page.status_code == 200, first_page.text
    first_payload = first_page.json()
    record = first_payload["records"][0]
    assert record["id"] == f"listing:{listing_id}"
    assert record["deleted"] is False
    assert "Oak desk" in record["content"]
    assert "Never export" not in record["content"]
    assert record["metadata"]["execution_authority"] is False
    cursor = first_payload["next_cursor"]

    foreign_page = client.get("/api/hai/records", headers=foreign_hai_headers)
    assert foreign_page.status_code == 200
    assert foreign_page.json()["records"] == []

    update = client.patch(
        f"/api/listings/{listing_id}",
        headers=owner_headers,
        json={"title": "Oak writing desk"},
    )
    assert update.status_code == 200
    changed_page = client.get(f"/api/hai/records?cursor={cursor}", headers=hai_headers)
    assert changed_page.status_code == 200
    assert changed_page.json()["records"][-1]["title"] == "Oak writing desk"
    changed_cursor = changed_page.json()["next_cursor"]

    assert client.delete(f"/api/listings/{listing_id}", headers=owner_headers).status_code == 204
    deleted_page = client.get(f"/api/hai/records?cursor={changed_cursor}", headers=hai_headers)
    assert deleted_page.status_code == 200
    assert deleted_page.json()["records"][-1]["deleted"] is True

    listed_tokens = client.get("/api/hai/tokens", headers=owner_headers)
    assert listed_tokens.status_code == 200
    assert "token" not in listed_tokens.json()[0]
    assert client.get("/api/hai/tokens", headers=hai_headers).status_code == 401

    assert client.delete(f"/api/hai/tokens/{token_id}", headers=owner_headers).status_code == 204
    assert client.get("/api/hai/status", headers=hai_headers).status_code == 401


def test_hai_cursor_rejects_invalid_values():
    owner_headers = _register("hai-cursor")
    _, hai_headers = _create_hai_token(owner_headers)

    response = client.get("/api/hai/records?cursor=not-a-cursor", headers=hai_headers)

    assert response.status_code == 422

    invalid_padding = client.get("/api/hai/records?cursor=A", headers=hai_headers)
    assert invalid_padding.status_code == 422


@pytest.mark.parametrize("cursor", [
    base64.urlsafe_b64encode(b"9223372036854775808").decode().rstrip("="),
    base64.urlsafe_b64encode(b"9" * 80).decode().rstrip("="),
    "MQ!!==",  # Invalid base64 characters must not be silently discarded.
    "KzE",  # Signed values are not change identifiers.
    "IDE",  # Whitespace is not part of an identifier.
])
def test_hai_malformed_cursor_returns_validation_error_instead_of_server_error(cursor):
    owner_headers = _register("hai-invalid-cursor")
    _, hai_headers = _create_hai_token(owner_headers)
    with TestClient(app, raise_server_exceptions=False) as requests:
        response = requests.get("/api/hai/records", params={"cursor": cursor}, headers=hai_headers)
    assert response.status_code == 422, response.text


def test_hai_cursor_accepts_database_integer_boundary():
    owner_headers = _register("hai-boundary-cursor")
    _, hai_headers = _create_hai_token(owner_headers)
    cursor = "OTIyMzM3MjAzNjg1NDc3NTgwNw"  # 9223372036854775807
    response = client.get("/api/hai/records", params={"cursor": cursor}, headers=hai_headers)
    assert response.status_code == 200, response.text
    assert response.json()["records"] == []
    assert response.json()["next_cursor"] == cursor
    assert response.json()["has_more"] is False


def test_hai_incremental_feed_observes_image_addition_and_deletion():
    owner_headers = _register("hai-images")
    _, hai_headers = _create_hai_token(owner_headers)
    listing = client.post("/api/listings", headers=owner_headers, json={"title": "Photo item"}).json()
    cursor = client.get("/api/hai/records", headers=hai_headers).json()["next_cursor"]
    uploaded = client.post(
        f"/api/listings/{listing['id']}/images", headers=owner_headers,
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    page = client.get("/api/hai/records", params={"cursor": cursor}, headers=hai_headers).json()
    assert page["records"], "An image addition must invalidate HAI's cached image count"
    assert page["records"][-1]["metadata"]["image_count"] == 1
    deleted = client.delete(
        f"/api/listings/{listing['id']}/images/{uploaded.json()['images'][0]['id']}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200, deleted.text
    page = client.get("/api/hai/records", params={"cursor": page["next_cursor"]}, headers=hai_headers).json()
    assert page["records"], "An image deletion must invalidate HAI's cached image count"
    assert page["records"][-1]["metadata"]["image_count"] == 0


def test_hai_incremental_feed_observes_platform_selection_changes():
    owner_headers = _register("hai-platforms")
    _, hai_headers = _create_hai_token(owner_headers)
    listing = client.post("/api/listings", headers=owner_headers, json={"title": "Platform item"}).json()
    cursor = client.get("/api/hai/records", headers=hai_headers).json()["next_cursor"]
    for selected, expected in [(True, ["marktplaats"]), (False, [])]:
        changed = client.post(
            f"/api/listings/{listing['id']}/platforms", headers=owner_headers,
            json={"platform": "marktplaats", "selected": selected, "overrides": {}},
        )
        assert changed.status_code == 200, changed.text
        page = client.get("/api/hai/records", params={"cursor": cursor}, headers=hai_headers).json()
        assert page["records"], "Platform selection changes must appear in incremental sync"
        assert page["records"][-1]["metadata"]["platforms"] == expected
        cursor = page["next_cursor"]


def test_hai_export_download_has_generic_items_and_only_owner_public_fields():
    owner = _register("hai-export")
    foreign = _register("hai-export-foreign")
    listing = client.post("/api/listings", headers=owner, json={
        "title": "Éiken bureau", "description": "Solid oak desk.", "price_cents": 7500,
        "internal_notes": "PRIVATE OWNER NOTE", "notes": "PRIVATE GENERAL NOTE",
        "tags": ["oak"],
    }).json()
    client.post("/api/listings", headers=foreign, json={"title": "FOREIGN SECRET TITLE"})
    uploaded = client.post(
        f"/api/listings/{listing['id']}/images", headers=owner,
        files={"file": ("PRIVATE_FILENAME.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200
    response = client.get("/api/hai/export", headers=owner)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == 'attachment; filename="autoposter-hai-feed.json"'
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert set(payload) == {"items"}
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["externalId"] == f"secondhand:listing:{listing['id']}"
    assert item["provider"] == "generic_json_feed"
    assert item["itemType"] == "document"
    assert item["title"] == "Éiken bureau"
    assert "Solid oak desk." in item["content"]
    assert "75.00 EUR" in item["content"]
    assert item["metadata"]["image_count"] == 1
    assert item["metadata"]["execution_authority"] is False
    assert item["sourceUri"].endswith(f"/?listing={listing['id']}")
    for excluded in ("PRIVATE OWNER NOTE", "PRIVATE GENERAL NOTE", "FOREIGN SECRET TITLE", "PRIVATE_FILENAME"):
        assert excluded not in response.text


def test_hai_export_requires_owner_session_not_connector_token():
    owner = _register("hai-export-auth")
    _, connector = _create_hai_token(owner)
    for headers in ({}, connector, {"Authorization": "Bearer invalid"}):
        assert client.get("/api/hai/export", headers=headers).status_code == 401
    assert client.get("/api/hai/export", headers=owner).json() == {"items": []}


def test_hai_export_refresh_has_current_content_without_deleted_listings():
    owner = _register("hai-export-refresh")
    listing = client.post("/api/listings", headers=owner, json={"title": "Before"}).json()
    first = client.get("/api/hai/export", headers=owner).json()["items"][0]
    client.patch(f"/api/listings/{listing['id']}", headers=owner, json={"title": "After"})
    second = client.get("/api/hai/export", headers=owner).json()["items"][0]
    assert first["externalId"] == second["externalId"]
    assert second["title"] == "After"
    client.delete(f"/api/listings/{listing['id']}", headers=owner)
    assert client.get("/api/hai/export", headers=owner).json() == {"items": []}


@pytest.mark.parametrize("case", ["content", "metadata", "feed"])
def test_hai_export_refuses_consumer_size_overflow_without_partial_download(case):
    from app.database import SessionLocal
    from app.models import Listing

    owner = _register(f"hai-export-large-{case}")
    owner_id = client.get("/api/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        if case == "content":
            rows = [Listing(owner_id=owner_id, title="Too much Unicode", description="🪑" * 50_001)]
        elif case == "metadata":
            rows = [Listing(owner_id=owner_id, title="Old imported metadata", category="x" * 16_001)]
        else:
            rows = [Listing(owner_id=owner_id, title=f"Bulk {i}", description="x" * 190_000) for i in range(28)]
        db.add_all(rows)
        db.commit()
    response = client.get("/api/hai/export", headers=owner)
    assert response.status_code == 413, response.text[:300]
    assert "content-disposition" not in response.headers
    assert "items" not in response.json()


def test_hai_export_includes_more_than_one_api_page_without_n_plus_one_queries():
    from sqlalchemy import event

    from app.database import SessionLocal, engine
    from app.models import Listing

    owner = _register("hai-export-batches")
    owner_id = client.get("/api/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        db.add_all([Listing(owner_id=owner_id, title=f"Batch item {i}") for i in range(301)])
        db.commit()
    queries = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/hai/export", headers=owner)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 301
    assert len({item["externalId"] for item in items}) == 301
    assert {item["title"] for item in items} == {f"Batch item {i}" for i in range(301)}
    assert len(queries) <= 12, f"Expected batched queries, got {len(queries)}"
    assert all("internal_notes" not in query and "storage_path" not in query for query in queries)


def test_hai_export_never_embeds_credentials_from_a_misconfigured_source_url(monkeypatch):
    from app.config import get_settings

    owner = _register("hai-export-url")
    client.post("/api/listings", headers=owner, json={"title": "Safe item"})
    monkeypatch.setattr(get_settings(), "public_base_url", "https://user:PRIVATE_PASSWORD@example.com/?token=SECRET")
    response = client.get("/api/hai/export", headers=owner)
    assert response.status_code == 200
    assert response.json()["items"][0]["sourceUri"] == ""
    assert "PRIVATE_PASSWORD" not in response.text
    assert "SECRET" not in response.text


@pytest.mark.parametrize("character", ["<", ">", "&", "\u2028", "\u2029"])
def test_hai_export_counts_go_metadata_escaping_before_accepting_a_file(character):
    from app.database import SessionLocal
    from app.models import Listing

    owner = _register("hai-export-escaped")
    owner_id = client.get("/api/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        # Go escapes each character to six ASCII bytes: 2700 * 6 already exceeds 16000.
        db.add(Listing(owner_id=owner_id, title="Escaped metadata", category=character * 2700))
        db.commit()
    response = client.get("/api/hai/export", headers=owner)
    assert response.status_code == 413
    assert "content-disposition" not in response.headers


def test_hai_export_accepts_exact_content_byte_limit_then_rejects_one_more_byte():
    from app.database import SessionLocal
    from app.models import Listing

    owner = _register("hai-export-boundary")
    owner_id = client.get("/api/auth/me", headers=owner).json()["id"]
    empty_content = (
        "Title: Boundary\nDescription: \nCategory: unspecified\nCondition: used\n"
        "Status: draft\nPrice: 0.00 EUR\nLocation: unspecified\nTags: none"
    )
    with SessionLocal() as db:
        listing = Listing(owner_id=owner_id, title="Boundary", description="x" * (200_000 - len(empty_content)))
        db.add(listing)
        db.commit()
        listing_id = listing.id
    response = client.get("/api/hai/export", headers=owner)
    assert response.status_code == 200, response.text[:200]
    assert len(response.json()["items"][0]["content"].encode("utf-8")) == 200_000
    with SessionLocal() as db:
        db.get(Listing, listing_id).description += "x"
        db.commit()
    assert client.get("/api/hai/export", headers=owner).status_code == 413
