import base64
import binascii
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import HaiConnectorToken, HaiListingChange, Listing, ListingImage, PlatformListingMapping, User
from app.schemas import HaiRecord, HaiRecordPage, HaiTokenCreate, HaiTokenCreated, HaiTokenOut
from app.security import hash_token
from app.services.audit import record_audit_event

router = APIRouter(tags=["HAI connector"])

HAI_EXPORT_MAX_BYTES = 5 * 1024 * 1024
HAI_CONTENT_MAX_BYTES = 200_000
HAI_METADATA_MAX_BYTES = 16_000


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _encode_cursor(change_id: int) -> str:
    return base64.urlsafe_b64encode(str(change_id).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        if not decoded.isdigit():
            raise ValueError("HAI cursor must contain an unsigned decimal identifier")
        value = int(decoded)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid HAI cursor") from exc
    # Reject values that cannot be bound as a database integer before querying.
    if value > 2**63 - 1:
        raise HTTPException(status_code=422, detail="Invalid HAI cursor")
    return value


def get_hai_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing HAI bearer token")
    raw_token = authorization.split(" ", 1)[1].strip()
    if not raw_token.startswith("hai_"):
        raise HTTPException(status_code=401, detail="Invalid or expired HAI token")
    credential = (
        db.query(HaiConnectorToken)
        .options(selectinload(HaiConnectorToken.user))
        .filter(HaiConnectorToken.token_hash == hash_token(raw_token))
        .one_or_none()
    )
    now = datetime.now(UTC)
    if (
        credential is None
        or credential.scope != "hai:read"
        or credential.revoked_at is not None
        or _utc(credential.expires_at) <= now
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired HAI token")
    if not credential.user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")
    if credential.last_used_at is None or now - _utc(credential.last_used_at) >= timedelta(hours=1):
        credential.last_used_at = now
        db.commit()
    return credential.user


@router.get("/.well-known/hai-connector.json")
def hai_manifest() -> dict:
    settings = get_settings()
    return {
        "schema_version": "1.0",
        "connector_key": "secondhand-platforms-autoposter",
        "name": settings.app_name,
        "mode": "read_only_pull",
        "authentication": {"type": "bearer", "token_prefix": "hai_", "scope": "hai:read"},
        "endpoints": {
            "status": "/api/hai/status",
            "records": "/api/hai/records",
        },
        "record_types": ["secondhand_listing"],
        "cursor": {"parameter": "cursor", "opaque": True},
        "capabilities": {
            "incremental_sync": True,
            "tombstones": True,
            "write_back": False,
            "credentials_exported": False,
            "image_binaries_exported": False,
        },
    }


@router.get("/api/hai/tokens", response_model=list[HaiTokenOut])
def list_hai_tokens(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(HaiConnectorToken)
        .filter(HaiConnectorToken.user_id == user.id, HaiConnectorToken.revoked_at.is_(None))
        .order_by(HaiConnectorToken.created_at.desc())
        .all()
    )


@router.post("/api/hai/tokens", response_model=HaiTokenCreated)
def create_hai_token(
    payload: HaiTokenCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_token = f"hai_{secrets.token_urlsafe(36)}"
    credential = HaiConnectorToken(
        user_id=user.id,
        name=payload.name.strip(),
        token_hash=hash_token(raw_token),
        scope="hai:read",
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_days),
    )
    db.add(credential)
    db.flush()
    record_audit_event(
        db,
        user,
        "hai_token_created",
        {"token_id": credential.id, "expires_days": payload.expires_days},
    )
    db.commit()
    db.refresh(credential)
    return HaiTokenCreated(
        id=credential.id,
        name=credential.name,
        scope=credential.scope,
        expires_at=credential.expires_at,
        last_used_at=credential.last_used_at,
        revoked_at=credential.revoked_at,
        created_at=credential.created_at,
        token=raw_token,
    )


@router.delete("/api/hai/tokens/{token_id}", status_code=204)
def revoke_hai_token(
    token_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credential = (
        db.query(HaiConnectorToken)
        .filter(HaiConnectorToken.id == token_id, HaiConnectorToken.user_id == user.id)
        .one_or_none()
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="HAI token not found")
    if credential.revoked_at is None:
        credential.revoked_at = datetime.now(UTC)
        record_audit_event(db, user, "hai_token_revoked", {"token_id": credential.id})
        db.commit()
    return Response(status_code=204)


@router.get("/api/hai/status")
def hai_status(user: User = Depends(get_hai_user)) -> dict:
    return {
        "status": "ok",
        "connector": "secondhand-platforms-autoposter",
        "owner": str(user.id),
        "mode": "read_only_pull",
        "write_back": False,
    }


def _listing_record(listing: Listing, changed_at: datetime, *, image_count: int | None = None) -> HaiRecord:
    settings = get_settings()
    tags = ", ".join(str(tag) for tag in listing.tags if str(tag).strip()) or "none"
    content = "\n".join(
        [
            f"Title: {listing.title}",
            f"Description: {listing.description}",
            f"Category: {listing.category or 'unspecified'}",
            f"Condition: {listing.condition}",
            f"Status: {listing.status}",
            f"Price: {listing.price_cents / 100:.2f} {listing.currency}",
            f"Location: {listing.location or 'unspecified'}",
            f"Tags: {tags}",
        ]
    )
    return HaiRecord(
        id=f"listing:{listing.id}",
        title=listing.title or f"Listing {listing.id}",
        content=content,
        source_url=f"{settings.public_base_url.rstrip('/')}/?listing={listing.id}",
        updated_at=changed_at,
        metadata={
            "listing_id": listing.id,
            "revision": listing.revision,
            "status": listing.status,
            "category": listing.category,
            "price_cents": listing.price_cents,
            "currency": listing.currency,
            "image_count": len(listing.images) if image_count is None else image_count,
            "platforms": sorted(
                mapping.platform for mapping in listing.platform_mappings if mapping.status != "skipped"
            ),
            "authority": "owner_record",
            "execution_authority": False,
        },
    )


@router.get("/api/hai/records", response_model=HaiRecordPage)
def hai_records(
    cursor: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(get_hai_user),
    db: Session = Depends(get_db),
) -> HaiRecordPage:
    after_id = _decode_cursor(cursor)
    changes = (
        db.query(HaiListingChange)
        .filter(HaiListingChange.owner_id == user.id, HaiListingChange.id > after_id)
        .order_by(HaiListingChange.id.asc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(changes) > limit
    page = changes[:limit]
    listing_ids = {change.listing_id for change in page if change.action != "delete"}
    listings = {}
    if listing_ids:
        listings = {
            listing.id: listing
            for listing in db.query(Listing)
            .options(selectinload(Listing.images), selectinload(Listing.platform_mappings))
            .filter(Listing.owner_id == user.id, Listing.id.in_(listing_ids))
            .all()
        }

    records: list[HaiRecord] = []
    for change in page:
        listing = listings.get(change.listing_id)
        if change.action == "delete" or listing is None:
            records.append(
                HaiRecord(
                    id=f"listing:{change.listing_id}",
                    title=f"Deleted listing {change.listing_id}",
                    content="",
                    source_url="",
                    updated_at=change.changed_at,
                    deleted=True,
                    metadata={"listing_id": change.listing_id},
                )
            )
        else:
            records.append(_listing_record(listing, change.changed_at))

    return HaiRecordPage(
        records=records,
        next_cursor=_encode_cursor(page[-1].id) if page else cursor,
        has_more=has_more,
    )


@router.get("/api/hai/export", response_class=Response)
def hai_export(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """Download current owner listings in HAI's generic local-file format."""
    image_count_query = (
        select(func.count(ListingImage.id)).where(ListingImage.listing_id == Listing.id).scalar_subquery()
    )
    listings = (
        db.query(Listing, image_count_query)
        .options(
            load_only(
                Listing.title, Listing.description, Listing.price_cents, Listing.currency,
                Listing.condition, Listing.category, Listing.location, Listing.tags,
                Listing.status, Listing.revision, Listing.updated_at,
            ),
            selectinload(Listing.platform_mappings).load_only(
                PlatformListingMapping.platform, PlatformListingMapping.status,
            ),
        )
        .filter(Listing.owner_id == user.id)
        .order_by(Listing.id.asc())
        .yield_per(100)
    )
    body = bytearray(b'{"items":[')
    for index, (listing, image_count) in enumerate(listings):
        record = _listing_record(listing, listing.updated_at, image_count=image_count)
        # HAI validates decoded content bytes and Go's JSON-encoded metadata.
        metadata_json = json.dumps(record.metadata, ensure_ascii=False, separators=(",", ":"))
        for character, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                                   ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
            metadata_json = metadata_json.replace(character, escaped)
        if (len(record.content.encode("utf-8")) > HAI_CONTENT_MAX_BYTES
                or len(metadata_json.encode("utf-8")) > HAI_METADATA_MAX_BYTES):
            raise HTTPException(413, "A listing exceeds HAI's content or metadata limit; no feed was exported.")
        source_uri = record.source_url
        try:
            base = urlsplit(get_settings().public_base_url)
            if (base.scheme not in {"http", "https"} or not base.hostname
                    or base.username or base.password or base.query or base.fragment
                    or re.search(r"(token|auth|api[_-]?key|secret|password|bearer)=", source_uri, re.I)):
                source_uri = ""
        except ValueError:
            source_uri = ""
        item = {
            "externalId": f"secondhand:listing:{listing.id}",
            "provider": "generic_json_feed",
            "itemType": "document",
            "title": record.title,
            "content": record.content,
            "sourceUri": source_uri,
            "metadata": record.metadata,
        }
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) + bool(index) + len(encoded) + 2 > HAI_EXPORT_MAX_BYTES:
            raise HTTPException(413, "HAI feed exceeds 5 MiB; no partial file was exported. Use a managed connector.")
        if index:
            body.extend(b",")
        body.extend(encoded)
    body.extend(b"]}")
    return Response(
        bytes(body), media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="autoposter-hai-feed.json"',
            "Cache-Control": "no-store",
        },
    )
