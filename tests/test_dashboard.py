import uuid

from tests.test_api import client


def _auth() -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"dashboard-{uuid.uuid4().hex}@example.com",
            "password": "correct-password",
            "name": "Dashboard owner",
        },
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_dashboard_is_owner_scoped_exact_and_bounded():
    owner_headers = _auth()
    foreign_headers = _auth()
    for index in range(7):
        response = client.post(
            "/api/listings",
            headers=owner_headers,
            json={"title": f"Owner listing {index}", "status": "ready" if index < 3 else "draft"},
        )
        assert response.status_code == 200
    client.post("/api/listings", headers=foreign_headers, json={"title": "Foreign listing"})

    response = client.get("/api/dashboard", headers=owner_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["analytics"]["summary"]["listings_total"] == 7
    assert payload["analytics"]["summary"]["ready_listings"] == 3
    assert len(payload["recent_listings"]) == 5
    assert all(item["title"].startswith("Owner listing") for item in payload["recent_listings"])
    assert payload["latest_jobs"] == []
    assert payload["action_center"]["source"] == "derived_local"


def test_dashboard_requires_authentication():
    assert client.get("/api/dashboard").status_code == 401
