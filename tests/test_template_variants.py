from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers():
    response = client.post(
        "/api/auth/register",
        json={
            "email": "template-variants@example.com",
            "password": "correct-password",
            "name": "Template Variants",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_template_variants_filter_search_sort_and_update():
    headers = auth_headers()
    for payload in [
        {"name": "Pickup", "variant": "default", "platform": None, "body": "Pickup available."},
        {"name": "Pickup", "variant": "short", "platform": "ebay", "body": "Short pickup note."},
        {"name": "Pickup", "variant": "seasonal", "platform": "marktplaats", "body": "Seasonal pickup note."},
    ]:
        response = client.post("/api/templates", headers=headers, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["variant"] == payload["variant"]

    short_templates = client.get("/api/templates?variant=short", headers=headers)
    assert short_templates.status_code == 200, short_templates.text
    assert short_templates.headers["X-Total-Count"] == "1"
    assert [template["variant"] for template in short_templates.json()] == ["short"]

    searched_templates = client.get("/api/templates?search=seasonal", headers=headers)
    assert searched_templates.status_code == 200, searched_templates.text
    assert [template["variant"] for template in searched_templates.json()] == ["seasonal"]

    sorted_templates = client.get("/api/templates?sort=variant", headers=headers)
    assert sorted_templates.status_code == 200, sorted_templates.text
    assert [template["variant"] for template in sorted_templates.json()] == ["default", "seasonal", "short"]

    template_id = short_templates.json()[0]["id"]
    update_response = client.patch(
        f"/api/templates/{template_id}",
        headers=headers,
        json={"variant": "compact"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["variant"] == "compact"


def test_frontend_exposes_template_variant_controls():
    html = Path("public/index.html").read_text(encoding="utf-8")
    script = Path("public/app.js").read_text(encoding="utf-8")

    assert 'id="templateVariantFilter"' in html
    assert 'id="templateVariant"' in html
    assert "$(\"#templateVariantFilter\")" in script
    assert "$(\"#templateVariant\")" in script
    assert 'params.set("variant", state.templateQuery.variant.trim())' in script
    assert 'variant: $("#templateVariant").value || "default"' in script
