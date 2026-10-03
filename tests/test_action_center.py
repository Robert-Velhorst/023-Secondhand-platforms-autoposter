from app.database import Base, engine
from tests.factories import create_listing, register_user
from tests.test_api import client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_action_center_guides_first_run_without_external_notifications():
    headers = register_user(client, "onboarding")

    response = client.get("/api/action-center", headers=headers)

    assert response.status_code == 200, response.text
    center = response.json()
    assert center["source"] == "derived_local"
    assert center["onboarding_complete"] is False
    assert [step["complete"] for step in center["onboarding_steps"]] == [False] * 5
    assert center["reminders"] == []


def test_action_center_is_owner_scoped_and_surfaces_listing_reminders():
    owner_headers = register_user(client, "action-owner")
    other_headers = register_user(client, "action-other")
    listing = create_listing(client, owner_headers, title="Needs a photo")

    owner_center = client.get("/api/action-center", headers=owner_headers).json()
    other_center = client.get("/api/action-center", headers=other_headers).json()

    assert owner_center["onboarding_steps"][0]["complete"] is True
    assert any(item["resource_id"] == listing["id"] for item in owner_center["reminders"])
    assert other_center["reminders"] == []
    assert all(step["complete"] is False for step in other_center["onboarding_steps"])
