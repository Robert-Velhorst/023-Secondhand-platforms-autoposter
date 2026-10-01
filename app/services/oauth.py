import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PlatformAccount, PlatformOAuthState, User
from app.security import hash_token
from app.services.secrets import TokenSecretStore, get_token_secret_store
from app.services.token_secret_cleanup import cleanup_token_secrets_after_commit, queue_token_secret_deletions

HttpPost = Callable[..., httpx.Response]
HttpGet = Callable[..., httpx.Response]


def create_ebay_authorization_url(db: Session, user: User, settings: Settings) -> tuple[str, datetime]:
    if not settings.ebay_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail="eBay OAuth is not configured. Set EBAY_OAUTH_CLIENT_ID and EBAY_OAUTH_REDIRECT_URI.",
        )

    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.ebay_oauth_state_ttl_seconds)
    db.add(
        PlatformOAuthState(
            user_id=user.id,
            platform="ebay",
            state_hash=hash_token(state),
            redirect_uri=settings.ebay_oauth_redirect_uri,
            scopes=settings.ebay_oauth_scope_list,
            expires_at=expires_at,
        )
    )
    db.commit()
    query = urlencode(
        {
            "client_id": settings.ebay_oauth_client_id,
            "redirect_uri": settings.ebay_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(settings.ebay_oauth_scope_list),
            "state": state,
        }
    )
    return f"{settings.ebay_oauth_authorize_url}?{query}", expires_at


def consume_ebay_authorization_callback(
    db: Session,
    state: str,
    code: str,
    settings: Settings,
    *,
    http_post: HttpPost | None = None,
    secret_store: TokenSecretStore | None = None,
) -> PlatformAccount:
    if not state or not code:
        raise HTTPException(status_code=400, detail="Missing eBay OAuth state or authorization code")

    oauth_state = (
        db.query(PlatformOAuthState)
        .filter(
            PlatformOAuthState.platform == "ebay",
            PlatformOAuthState.state_hash == hash_token(state),
        )
        .with_for_update()
        .one_or_none()
    )
    if not oauth_state:
        raise HTTPException(status_code=400, detail="Invalid eBay OAuth state")
    if oauth_state.consumed_at is not None:
        raise HTTPException(status_code=400, detail="eBay OAuth state has already been used")

    expires_at = oauth_state.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="eBay OAuth state has expired")

    oauth_state.consumed_at = datetime.now(UTC)
    secret_ref = (
        f"{settings.ebay_token_secret_ref_prefix}/user-{oauth_state.user_id}/consent-{oauth_state.state_hash}"
    )
    account = (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.owner_id == oauth_state.user_id,
            PlatformAccount.platform == "ebay",
            PlatformAccount.display_name == "eBay official API",
        )
        .one_or_none()
    )
    connection_data = {
        "oauth": {
            "environment": settings.ebay_oauth_environment.lower(),
            "redirect_uri": oauth_state.redirect_uri,
            "scopes": oauth_state.scopes,
            "authorization_code_received": True,
            "token_exchange": "pending_secret_manager",
            "authorized_at": oauth_state.consumed_at.isoformat(),
        }
    }
    if settings.ebay_oauth_token_exchange_configured:
        token_summary = exchange_ebay_authorization_code(
            code,
            secret_ref=secret_ref,
            settings=settings,
            http_post=http_post,
            secret_store=secret_store,
        )
        connection_data["oauth"].update(token_summary)
    old_secret_ref = account.secret_ref if account else None
    if account:
        account.mode = "official_api"
        account.status = _oauth_account_status(connection_data)
        account.connection_data = connection_data
        account.secret_ref = secret_ref
    else:
        account = PlatformAccount(
            owner_id=oauth_state.user_id,
            platform="ebay",
            display_name="eBay official API",
            mode="official_api",
            status=_oauth_account_status(connection_data),
            connection_data=connection_data,
            secret_ref=secret_ref,
        )
        db.add(account)
    cleanup_ids = queue_token_secret_deletions(
        db, [old_secret_ref] if old_secret_ref and old_secret_ref != secret_ref else []
    )
    db.commit()
    db.refresh(account)
    cleanup_token_secrets_after_commit(cleanup_ids)
    return account


def _oauth_account_status(connection_data: dict[str, Any]) -> str:
    return "connected" if connection_data["oauth"]["token_exchange"] == "stored" else "needs_token_exchange"


def exchange_ebay_authorization_code(
    code: str,
    *,
    secret_ref: str,
    settings: Settings,
    http_post: HttpPost | None = None,
    secret_store: TokenSecretStore | None = None,
) -> dict[str, Any]:
    if not settings.ebay_oauth_token_exchange_configured:
        raise HTTPException(status_code=503, detail="eBay OAuth token exchange is not configured")

    post = http_post or httpx.post
    try:
        response = post(
            settings.ebay_oauth_token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.ebay_oauth_redirect_uri,
            },
            auth=(settings.ebay_oauth_client_id, settings.ebay_oauth_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="eBay OAuth token exchange failed") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="eBay OAuth token exchange was rejected")

    try:
        token_payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="eBay OAuth token response was not JSON") from exc
    if not token_payload.get("access_token") or not token_payload.get("refresh_token"):
        raise HTTPException(status_code=502, detail="eBay OAuth token response was incomplete")

    store = secret_store or get_token_secret_store(settings)
    store.write_json(secret_ref, token_payload)
    return {
        "token_exchange": "stored",
        "token_type": token_payload.get("token_type", "Bearer"),
        "access_token_expires_in": token_payload.get("expires_in"),
        "refresh_token_expires_in": token_payload.get("refresh_token_expires_in"),
        "token_url": settings.ebay_oauth_token_url,
    }


def refresh_ebay_access_token(
    secret_ref: str,
    *,
    settings: Settings,
    http_post: HttpPost | None = None,
    secret_store: TokenSecretStore | None = None,
) -> dict[str, Any]:
    if not settings.ebay_oauth_token_exchange_configured:
        raise HTTPException(status_code=503, detail="eBay OAuth token refresh is not configured")

    store = secret_store or get_token_secret_store(settings)
    current_payload = store.read_json(secret_ref)
    refresh_token = current_payload.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=503, detail="Stored eBay token payload has no refresh token")

    post = http_post or httpx.post
    try:
        response = post(
            settings.ebay_oauth_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": " ".join(settings.ebay_oauth_scope_list),
            },
            auth=(settings.ebay_oauth_client_id, settings.ebay_oauth_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="eBay OAuth token refresh failed") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="eBay OAuth token refresh was rejected")
    try:
        refreshed_payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="eBay OAuth refresh response was not JSON") from exc
    if not refreshed_payload.get("access_token"):
        raise HTTPException(status_code=502, detail="eBay OAuth refresh response was incomplete")

    updated_payload = {**current_payload, **refreshed_payload, "refresh_token": refresh_token}
    store.write_json(secret_ref, updated_payload)
    return {
        "token_refresh": "stored",
        "token_type": updated_payload.get("token_type", "Bearer"),
        "access_token_expires_in": updated_payload.get("expires_in"),
        "token_url": settings.ebay_oauth_token_url,
    }


def verify_ebay_inventory_api_access(
    secret_ref: str,
    *,
    settings: Settings,
    http_get: HttpGet | None = None,
    secret_store: TokenSecretStore | None = None,
) -> dict[str, Any]:
    store = secret_store or get_token_secret_store(settings)
    token_payload = store.read_json(secret_ref)
    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=503, detail="Stored eBay token payload has no access token")

    get = http_get or httpx.get
    url = f"{settings.ebay_inventory_api_base_url}/inventory_item"
    try:
        response = get(url, headers={"Authorization": f"Bearer {access_token}"}, params={"limit": 1}, timeout=15)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="eBay Inventory API verification failed") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="eBay Inventory API verification was rejected")
    return {
        "inventory_api": "reachable",
        "environment": settings.ebay_oauth_environment.lower(),
        "url": url,
        "status_code": response.status_code,
    }
