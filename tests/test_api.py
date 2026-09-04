from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers():
    response = client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "correct-password", "name": "Owner"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_platform_metadata_contract():
    response = client.get("/api/platforms")

    assert response.status_code == 200
    platforms = response.json()
    assert {platform["key"] for platform in platforms} >= {"marktplaats", "koopplein", "nextdoor", "ebay"}
    for platform in platforms:
        assert platform["name"]
        assert platform["automation_mode"] == "assisted"
        assert isinstance(platform["required_fields"], list)
        assert isinstance(platform["supported_categories"], list)
        assert platform["capabilities"]["publish_mode"] == "assisted_package"
        assert platform["capabilities"]["requires_user_final_submission"] is True
        assert platform["capabilities"]["prepared_fields"]
        assert "final_submission" in platform["capabilities"]["blocked_actions"]
        assert isinstance(platform["compliance_notes"], list)
    ebay = next(platform for platform in platforms if platform["key"] == "ebay")
    assert ebay["capabilities"]["official_api_candidate"] is True
    assert ebay["capabilities"]["supports_official_api"] is False


def test_create_validate_and_publish_listing_flow():
    headers = auth_headers()
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Vintage desk lamp",
            "description": "Adjustable metal desk lamp in good working condition.",
            "price_cents": 2500,
            "condition": "used",
            "category": "Home and furniture",
            "location": "Arnhem",
            "delivery_options": {"pickup": True, "shipping": False},
            "tags": ["lamp", "desk"],
        },
    )
    assert listing_response.status_code == 200, listing_response.text
    listing_id = listing_response.json()["id"]

    image_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("lamp.png", PNG_BYTES, "image/png")},
    )
    assert image_response.status_code == 200, image_response.text
    assert len(image_response.json()["images"]) == 1

    validation_response = client.get(f"/api/listings/{listing_id}/validate?platform=marktplaats", headers=headers)
    assert validation_response.status_code == 200, validation_response.text
    validation = validation_response.json()[0]
    assert validation["ready"] is True
    assert validation["missing_fields"] == []

    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["marktplaats"], "process_now": True},
    )
    assert publish_response.status_code == 200, publish_response.text
    job = publish_response.json()[0]
    assert job["status"] == "needs_user_action"
    assert job["result"]["automation_mode"] == "assisted"
    assert job["logs"]

    complete_response = client.post(
        f"/api/jobs/{job['id']}/manual-completion",
        headers=headers,
        json={
            "platform_url": "https://www.marktplaats.nl/v/huis-en-inrichting/lampen/m123456-desk-lamp",
            "platform_listing_id": "m123456",
        },
    )
    assert complete_response.status_code == 200, complete_response.text
    completed_job = complete_response.json()
    assert completed_job["status"] == "published"
    assert completed_job["result"]["manual_completion"]["confirmed_by_user"] is True
    assert completed_job["result"]["manual_completion"]["platform_listing_id"] == "m123456"
    assert any("User confirmed manual marketplace completion" in log["message"] for log in completed_job["logs"])

    detail_response = client.get(f"/api/listings/{listing_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["title"] == "Vintage desk lamp"
    mapping = next(item for item in detail_response.json()["platform_mappings"] if item["platform"] == "marktplaats")
    assert mapping["status"] == "published"
    assert mapping["platform_url"] == "https://www.marktplaats.nl/v/huis-en-inrichting/lampen/m123456-desk-lamp"
    assert mapping["platform_listing_id"] == "m123456"
    assert mapping["last_published_at"]


def test_manual_completion_requires_user_action_job_and_platform_url():
    headers = auth_headers()
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Manual completion guard",
            "description": "Valid listing.",
            "price_cents": 1200,
            "condition": "used",
            "category": "Other",
            "location": "Arnhem",
        },
    )
    listing_id = listing_response.json()["id"]
    image_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("guard.png", PNG_BYTES, "image/png")},
    )
    assert image_response.status_code == 200, image_response.text
    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["koopplein"], "process_now": False},
    )
    job_id = publish_response.json()[0]["id"]

    invalid_url_response = client.post(
        f"/api/jobs/{job_id}/manual-completion",
        headers=headers,
        json={"platform_url": "not-a-url"},
    )
    assert invalid_url_response.status_code == 422

    premature_response = client.post(
        f"/api/jobs/{job_id}/manual-completion",
        headers=headers,
        json={"platform_url": "https://koopplein.nl/item/123"},
    )
    assert premature_response.status_code == 409
    assert "waiting for user action" in premature_response.json()["error"]["message"]


def test_validation_reports_missing_fields():
    headers = auth_headers()
    listing_response = client.post("/api/listings", headers=headers, json={"title": "Incomplete"})
    listing_id = listing_response.json()["id"]

    validation_response = client.get(f"/api/listings/{listing_id}/validate?platform=nextdoor", headers=headers)

    assert validation_response.status_code == 200
    validation = validation_response.json()[0]
    assert validation["ready"] is False
    assert "description" in validation["missing_fields"]
    assert "images" in validation["missing_fields"]


def test_accounts_and_templates():
    headers = auth_headers()
    account_response = client.post(
        "/api/accounts",
        headers=headers,
        json={"platform": "ebay", "display_name": "Personal eBay", "status": "needs_setup"},
    )
    assert account_response.status_code == 200, account_response.text

    template_response = client.post(
        "/api/templates",
        headers=headers,
        json={"name": "Default", "variant": "pickup", "platform": None, "body": "Available for pickup in Arnhem."},
    )
    assert template_response.status_code == 200, template_response.text

    assert client.get("/api/accounts", headers=headers).json()[0]["platform"] == "ebay"
    template = client.get("/api/templates", headers=headers).json()[0]
    assert template["name"] == "Default"
    assert template["variant"] == "pickup"

    account = client.get("/api/accounts", headers=headers).json()[0]
    delete_response = client.delete(f"/api/accounts/{account['id']}", headers=headers)
    assert delete_response.status_code == 204
    assert client.get("/api/accounts", headers=headers).json() == []


def test_accounts_can_be_updated_and_scrub_secret_connection_data():
    owner_headers = auth_headers()
    create_response = client.post(
        "/api/accounts",
        headers=owner_headers,
        json={
            "platform": "ebay",
            "display_name": "Draft eBay",
            "status": "needs_setup",
            "connection_data": {"store": "main", "access_token": "do-not-store"},
        },
    )
    assert create_response.status_code == 200, create_response.text
    account = create_response.json()
    assert account["connection_data"] == {"store": "main"}

    update_response = client.patch(
        f"/api/accounts/{account['id']}",
        headers=owner_headers,
        json={
            "display_name": "Ready eBay",
            "status": "ready",
            "connection_data": {"store": "main", "refresh_token": "do-not-store-either"},
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["display_name"] == "Ready eBay"
    assert updated["status"] == "ready"
    assert updated["connection_data"] == {"store": "main"}

    other_headers = {
        "Authorization": "Bearer "
        + client.post(
            "/api/auth/register",
            json={"email": "account-other@example.com", "password": "correct-password", "name": "Other"},
        ).json()["token"]
    }
    other_update_response = client.patch(
        f"/api/accounts/{account['id']}",
        headers=other_headers,
        json={"display_name": "Stolen"},
    )
    assert other_update_response.status_code == 404


def test_templates_can_be_updated_deleted_and_are_owner_scoped():
    owner_headers = auth_headers()
    template_response = client.post(
        "/api/templates",
        headers=owner_headers,
        json={"name": "Pickup", "platform": None, "body": "Pickup only."},
    )
    assert template_response.status_code == 200, template_response.text
    template_id = template_response.json()["id"]

    update_response = client.patch(
        f"/api/templates/{template_id}",
        headers=owner_headers,
        json={"name": "Shipping", "variant": "seasonal", "platform": "ebay", "body": "Shipping available."},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "Shipping"
    assert update_response.json()["variant"] == "seasonal"
    assert update_response.json()["platform"] == "ebay"
    assert update_response.json()["body"] == "Shipping available."

    other_headers = {
        "Authorization": "Bearer "
        + client.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "correct-password", "name": "Other"},
        ).json()["token"]
    }
    other_update_response = client.patch(
        f"/api/templates/{template_id}",
        headers=other_headers,
        json={"name": "Stolen"},
    )
    assert other_update_response.status_code == 404
    assert client.delete(f"/api/templates/{template_id}", headers=other_headers).status_code == 404

    delete_response = client.delete(f"/api/templates/{template_id}", headers=owner_headers)
    assert delete_response.status_code == 204
    assert client.get("/api/templates", headers=owner_headers).json() == []


def test_listing_detail_and_delete_are_owner_scoped():
    headers = auth_headers()
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={"title": "Delete me", "status": "draft"},
    )
    assert listing_response.status_code == 200, listing_response.text
    listing_id = listing_response.json()["id"]

    detail_response = client.get(f"/api/listings/{listing_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["id"] == listing_id

    delete_response = client.delete(f"/api/listings/{listing_id}", headers=headers)
    assert delete_response.status_code == 204
    assert client.get(f"/api/listings/{listing_id}", headers=headers).status_code == 404
