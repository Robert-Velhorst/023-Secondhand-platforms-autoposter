from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def register_user(client: TestClient, prefix: str = "factory") -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{prefix}-{uuid.uuid4().hex}@example.com",
            "password": "correct-password",
            "name": f"{prefix.title()} User",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def create_listing(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {
        "title": "Factory oak table",
        "description": "Reusable listing created by the test-data factory.",
        "price_cents": 4500,
        "condition": "good",
        "category": "Home and furniture",
        "location": "Utrecht",
        "delivery_options": {"pickup": True},
    }
    payload.update(overrides)
    response = client.post("/api/listings", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()
