import uuid

from app.database import Base, engine
from tests.test_api import PNG_BYTES, client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers(prefix: str = "quality"):
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


def test_quality_assistant_flags_incomplete_listing_and_suggests_copy():
    headers = auth_headers()
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={"title": "Lamp", "brand": "Ikea", "condition": "used", "shipping_allowed": True},
    )
    assert listing_response.status_code == 200, listing_response.text
    listing_id = listing_response.json()["id"]

    response = client.get(f"/api/listings/{listing_id}/quality", headers=headers)

    assert response.status_code == 200, response.text
    quality = response.json()
    assert quality["provider"] == "deterministic_local"
    assert quality["deterministic"] is True
    assert quality["external_data_sent"] is False
    assert quality["score"] < 70
    assert quality["grade"] in {"needs_work", "blocked"}
    issue_fields = {issue["field"] for issue in quality["issues"]}
    assert {"description", "price_cents", "category", "location", "images"} <= issue_fields
    suggestion_fields = {suggestion["field"] for suggestion in quality["suggestions"]}
    assert {"title", "description"} <= suggestion_fields
    assert quality["checklist"]["has_title"] is True
    assert quality["checklist"]["has_images"] is False


def test_quality_assistant_scores_ready_listing():
    headers = auth_headers()
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Vintage adjustable brass desk lamp",
            "description": (
                "Vintage adjustable brass desk lamp in used but working condition. "
                "Tested today, with light wear as pictured and no known electrical issues."
            ),
            "price_cents": 3500,
            "condition": "used",
            "category": "Home and furniture",
            "location": "Arnhem",
            "brand": "Vintage Co",
            "color": "Brass",
            "material": "Metal",
            "pickup_allowed": True,
            "shipping_allowed": True,
            "shipping_cost_cents": 750,
            "weight_grams": 1200,
        },
    )
    listing_id = listing_response.json()["id"]
    image_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("lamp.png", PNG_BYTES, "image/png")},
    )
    assert image_response.status_code == 200, image_response.text

    response = client.get(f"/api/listings/{listing_id}/quality", headers=headers)

    assert response.status_code == 200, response.text
    quality = response.json()
    assert quality["score"] >= 85
    assert quality["grade"] == "ready"
    assert quality["checklist"]["has_images"] is True
    assert all(issue["severity"] != "critical" for issue in quality["issues"])


def test_quality_assistant_adds_category_specific_guidance():
    headers = auth_headers()
    listing_response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Sony mirrorless camera body",
            "description": (
                "Sony mirrorless camera body in used condition with light wear on the grip. "
                "Includes body cap and strap, with no known sensor damage."
            ),
            "price_cents": 42500,
            "condition": "used",
            "category": "Electronics",
            "location": "Arnhem",
            "brand": "Sony",
            "pickup_allowed": True,
        },
    )
    assert listing_response.status_code == 200, listing_response.text
    listing_id = listing_response.json()["id"]

    response = client.get(f"/api/listings/{listing_id}/quality", headers=headers)

    assert response.status_code == 200, response.text
    quality = response.json()
    assert quality["checklist"]["has_electronics_details"] is False
    messages = {issue["message"] for issue in quality["issues"]}
    assert "Electronics listings work better with brand and model details." in messages
    assert "Electronics testing and included accessories are unclear." in messages
    description_suggestion = next(
        suggestion for suggestion in quality["suggestions"] if suggestion["field"] == "description"
    )
    assert "Testing/accessories" in description_suggestion["value"]

    update_response = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={
            "model": "A6000",
            "description": (
                "Sony mirrorless camera body in used condition with light wear on the grip. "
                "Tested working today and includes charger, body cap, and strap."
            ),
        },
    )
    assert update_response.status_code == 200, update_response.text

    updated_quality = client.get(f"/api/listings/{listing_id}/quality", headers=headers).json()
    assert updated_quality["checklist"]["has_electronics_details"] is True
    updated_messages = {issue["message"] for issue in updated_quality["issues"]}
    assert "Electronics testing and included accessories are unclear." not in updated_messages


def test_quality_assistant_is_owner_scoped():
    owner_headers = auth_headers("owner")
    listing_response = client.post("/api/listings", headers=owner_headers, json={"title": "Private listing"})
    listing_id = listing_response.json()["id"]
    other_headers = auth_headers("other")

    response = client.get(f"/api/listings/{listing_id}/quality", headers=other_headers)

    assert response.status_code == 404
