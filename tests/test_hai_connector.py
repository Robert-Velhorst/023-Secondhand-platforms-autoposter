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
