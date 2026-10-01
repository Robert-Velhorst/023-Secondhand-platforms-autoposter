from urllib.parse import parse_qs, urlparse

import httpx

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import PlatformAccount, PlatformOAuthState
from app.services.oauth import (
    consume_ebay_authorization_callback,
    refresh_ebay_access_token,
    verify_ebay_inventory_api_access,
)
from tests.test_api import auth_headers, client


def setup_function():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_function():
    get_settings.cache_clear()


def configure_ebay_oauth(monkeypatch):
    monkeypatch.setenv("EBAY_OAUTH_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setenv("EBAY_OAUTH_REDIRECT_URI", "https://app.example.com/api/accounts/ebay/oauth/callback")
    monkeypatch.setenv("EBAY_OAUTH_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("EBAY_TOKEN_SECRET_REF_PREFIX", "vault://platform-tokens/ebay")
    get_settings.cache_clear()


class MemoryTokenSecretStore:
    def __init__(self):
        self.payloads = {}

    def read_json(self, secret_ref):
        return self.payloads[secret_ref]

    def write_json(self, secret_ref, payload):
        self.payloads[secret_ref] = payload

    def delete_json(self, secret_ref):
        self.payloads.pop(secret_ref, None)


def test_ebay_oauth_start_fails_closed_without_config():
    headers = auth_headers()

    response = client.post("/api/accounts/ebay/oauth/start", headers=headers)

    assert response.status_code == 503
    assert "not configured" in response.json()["error"]["message"]


def test_ebay_oauth_start_creates_hashed_state_and_authorization_url(monkeypatch):
    configure_ebay_oauth(monkeypatch)
    headers = auth_headers()

    response = client.post("/api/accounts/ebay/oauth/start", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    parsed = urlparse(payload["authorization_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "auth.sandbox.ebay.com"
    assert query["client_id"] == ["sandbox-client-id"]
    assert query["redirect_uri"] == ["https://app.example.com/api/accounts/ebay/oauth/callback"]
    assert query["response_type"] == ["code"]
    assert "https://api.ebay.com/oauth/api_scope/sell.inventory" in query["scope"][0]
    assert query["state"][0]

    db = SessionLocal()
    try:
        oauth_state = db.query(PlatformOAuthState).one()
        assert oauth_state.platform == "ebay"
        assert oauth_state.state_hash != query["state"][0]
        assert oauth_state.redirect_uri == "https://app.example.com/api/accounts/ebay/oauth/callback"
    finally:
        db.close()


def test_ebay_oauth_callback_consumes_state_without_storing_tokens(monkeypatch):
    configure_ebay_oauth(monkeypatch)
    headers = auth_headers()
    start_response = client.post("/api/accounts/ebay/oauth/start", headers=headers)
    state = parse_qs(urlparse(start_response.json()["authorization_url"]).query)["state"][0]

    callback_response = client.get(
        "/api/accounts/ebay/oauth/callback",
        params={"state": state, "code": "authorization-code-from-ebay"},
    )

    assert callback_response.status_code == 200, callback_response.text
    account = callback_response.json()
    assert account["platform"] == "ebay"
    assert account["display_name"] == "eBay official API"
    assert account["mode"] == "official_api"
    assert account["status"] == "needs_token_exchange"
    assert "secret_ref" not in account
    assert "authorization-code-from-ebay" not in str(account)
    assert account["connection_data"]["oauth"]["token_exchange"] == "pending_secret_manager"

    db = SessionLocal()
    try:
        oauth_state = db.query(PlatformOAuthState).one()
        assert oauth_state.consumed_at is not None
        stored_account = db.query(PlatformAccount).one()
        assert stored_account.secret_ref.startswith("vault://platform-tokens/ebay/user-1/consent-")
        assert "authorization-code-from-ebay" not in str(stored_account.connection_data)
    finally:
        db.close()

    replay_response = client.get(
        "/api/accounts/ebay/oauth/callback",
        params={"state": state, "code": "second-code"},
    )
    assert replay_response.status_code == 400
    assert "already been used" in replay_response.json()["error"]["message"]


def test_ebay_oauth_callback_can_exchange_and_store_tokens_without_exposing_them(monkeypatch):
    configure_ebay_oauth(monkeypatch)
    monkeypatch.setenv("EBAY_OAUTH_CLIENT_SECRET", "sandbox-client-secret")
    get_settings.cache_clear()
    headers = auth_headers()
    start_response = client.post("/api/accounts/ebay/oauth/start", headers=headers)
    state = parse_qs(urlparse(start_response.json()["authorization_url"]).query)["state"][0]
    store = MemoryTokenSecretStore()

    def fake_post(url, data, auth, headers, timeout):
        assert url == "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        assert data["grant_type"] == "authorization_code"
        assert data["code"] == "authorization-code-from-ebay"
        assert auth == ("sandbox-client-id", "sandbox-client-secret")
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert timeout == 15
        return httpx.Response(
            200,
            json={
                "access_token": "access-token-secret",
                "refresh_token": "refresh-token-secret",
                "expires_in": 7200,
                "refresh_token_expires_in": 47304000,
                "token_type": "Bearer",
            },
        )

    db = SessionLocal()
    try:
        account = consume_ebay_authorization_callback(
            db,
            state,
            "authorization-code-from-ebay",
            get_settings(),
            http_post=fake_post,
            secret_store=store,
        )

        assert account.status == "connected"
        assert account.secret_ref.startswith("vault://platform-tokens/ebay/user-1/consent-")
        assert store.payloads[account.secret_ref]["access_token"] == "access-token-secret"
        serialized = str(account.connection_data)
        assert "access-token-secret" not in serialized
        assert "refresh-token-secret" not in serialized
        assert "sandbox-client-secret" not in serialized
        assert "authorization-code-from-ebay" not in serialized
        assert account.secret_ref not in serialized
        assert account.connection_data["oauth"]["token_exchange"] == "stored"
        assert account.connection_data["oauth"]["access_token_expires_in"] == 7200
    finally:
        db.close()

    response = client.get("/api/accounts", headers=headers)
    assert response.status_code == 200, response.text
    serialized_response = str(response.json())
    assert "access-token-secret" not in serialized_response
    assert "refresh-token-secret" not in serialized_response
    assert "sandbox-client-secret" not in serialized_response
    assert account.secret_ref not in serialized_response
    assert response.json()[0]["status"] == "connected"


def test_ebay_token_refresh_and_inventory_probe_use_secret_store(monkeypatch):
    configure_ebay_oauth(monkeypatch)
    monkeypatch.setenv("EBAY_OAUTH_CLIENT_SECRET", "sandbox-client-secret")
    get_settings.cache_clear()
    store = MemoryTokenSecretStore()
    store.write_json(
        "vault://platform-tokens/ebay/user-1/consent-test",
        {
            "access_token": "old-access-token",
            "refresh_token": "refresh-token-secret",
            "expires_in": 1,
            "token_type": "Bearer",
        },
    )

    def fake_post(url, data, auth, headers, timeout):
        assert url == "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "refresh-token-secret"
        assert "sell.inventory" in data["scope"]
        assert auth == ("sandbox-client-id", "sandbox-client-secret")
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert timeout == 15
        return httpx.Response(200, json={"access_token": "new-access-token", "expires_in": 7200})

    refresh_summary = refresh_ebay_access_token(
        "vault://platform-tokens/ebay/user-1/consent-test",
        settings=get_settings(),
        http_post=fake_post,
        secret_store=store,
    )

    assert refresh_summary["token_refresh"] == "stored"
    assert store.payloads["vault://platform-tokens/ebay/user-1/consent-test"]["access_token"] == "new-access-token"
    assert store.payloads["vault://platform-tokens/ebay/user-1/consent-test"]["refresh_token"] == "refresh-token-secret"

    def fake_get(url, headers, params, timeout):
        assert url == "https://api.sandbox.ebay.com/sell/inventory/v1/inventory_item"
        assert headers == {"Authorization": "Bearer new-access-token"}
        assert params == {"limit": 1}
        assert timeout == 15
        return httpx.Response(200, json={"inventoryItems": []})

    probe = verify_ebay_inventory_api_access(
        "vault://platform-tokens/ebay/user-1/consent-test",
        settings=get_settings(),
        http_get=fake_get,
        secret_store=store,
    )

    assert probe == {
        "inventory_api": "reachable",
        "environment": "sandbox",
        "url": "https://api.sandbox.ebay.com/sell/inventory/v1/inventory_item",
        "status_code": 200,
    }


def test_ebay_oauth_callback_rejects_invalid_state(monkeypatch):
    configure_ebay_oauth(monkeypatch)

    response = client.get(
        "/api/accounts/ebay/oauth/callback",
        params={"state": "unknown", "code": "authorization-code-from-ebay"},
    )

    assert response.status_code == 400
    assert "Invalid eBay OAuth state" in response.json()["error"]["message"]
