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
        json={"email": "query-owner@example.com", "password": "correct-password", "name": "Query Owner"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_account_template_and_mapping_endpoints_filter_sort_and_page():
    headers = auth_headers()

    for payload in [
        {"platform": "ebay", "display_name": "Alpha eBay", "status": "connected"},
        {"platform": "marktplaats", "display_name": "Beta Marktplaats", "status": "needs_setup"},
        {"platform": "ebay", "display_name": "Zeta eBay", "status": "disabled"},
    ]:
        assert client.post("/api/accounts", headers=headers, json=payload).status_code == 200

    accounts = client.get("/api/accounts?platform=ebay&sort=display_name&limit=1", headers=headers)
    assert accounts.status_code == 200, accounts.text
    assert accounts.headers["X-Total-Count"] == "2"
    assert [account["display_name"] for account in accounts.json()] == ["Alpha eBay"]

    accounts_page_2 = client.get("/api/accounts?platform=ebay&sort=display_name&limit=1&offset=1", headers=headers)
    assert [account["display_name"] for account in accounts_page_2.json()] == ["Zeta eBay"]

    disabled_accounts = client.get("/api/accounts?status=disabled", headers=headers)
    assert [account["display_name"] for account in disabled_accounts.json()] == ["Zeta eBay"]

    for payload in [
        {"name": "Shipping eBay", "variant": "short", "platform": "ebay", "body": "eBay shipping available."},
        {"name": "Shipping Marktplaats", "variant": "seasonal", "platform": "marktplaats", "body": "Pickup preferred."},
        {"name": "Pickup", "platform": None, "body": "Local pickup only."},
    ]:
        assert client.post("/api/templates", headers=headers, json=payload).status_code == 200

    templates = client.get("/api/templates?search=Shipping&platform=ebay&variant=short&sort=-name", headers=headers)
    assert templates.status_code == 200, templates.text
    assert templates.headers["X-Total-Count"] == "1"
    assert [template["name"] for template in templates.json()] == ["Shipping eBay"]

    for payload in [
        {"source_category": "Home and furniture", "platform": "ebay", "platform_category": "Home"},
        {"source_category": "Home and furniture", "platform": "marktplaats", "platform_category": "Huis"},
        {"source_category": "Electronics", "platform": "ebay", "platform_category": "Consumer electronics"},
    ]:
        assert client.post("/api/category-mappings", headers=headers, json=payload).status_code == 200

    mappings = client.get(
        "/api/category-mappings?source_category=Home&platform=marktplaats&sort=platform_category",
        headers=headers,
    )
    assert mappings.status_code == 200, mappings.text
    assert mappings.headers["X-Total-Count"] == "1"
    assert [mapping["platform_category"] for mapping in mappings.json()] == ["Huis"]


def test_frontend_exposes_extended_query_controls():
    html = Path("public/index.html").read_text(encoding="utf-8")
    script = Path("public/app.js").read_text(encoding="utf-8")

    required_ids = [
        "accountPlatformFilter",
        "accountStatusFilter",
        "accountSort",
        "accountPrevPage",
        "accountNextPage",
        "cancelAccountEditButton",
        "templateSearch",
        "templatePlatformFilter",
        "templateVariantFilter",
        "templateSort",
        "templatePrevPage",
        "templateNextPage",
        "mappingSourceFilter",
        "mappingPlatformFilter",
        "mappingSort",
        "mappingPrevPage",
        "mappingNextPage",
    ]
    for element_id in required_ids:
        assert f'id="{element_id}"' in html
        assert f'$("#{element_id}")' in script

    assert "accountQueryPath()" in script
    assert "data-edit-account" in script
    assert "templateQueryPath()" in script
    assert "mappingQueryPath()" in script
