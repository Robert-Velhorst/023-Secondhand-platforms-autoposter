from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    literal,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["UserSession"]] = relationship(
        cascade="all, delete-orphan", back_populates="user"
    )
    listings: Mapped[list["Listing"]] = relationship(cascade="all, delete-orphan", back_populates="owner")


class HaiConnectorToken(Base):
    """Owner-scoped, read-only credential used only by the HAI export API."""

    __tablename__ = "hai_connector_tokens"
    __table_args__ = (
        Index("ix_hai_connector_tokens_user_created_at", "user_id", "created_at"),
        Index("ix_hai_connector_tokens_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(80), default="hai:read")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped[User] = relationship()


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped[User] = relationship(back_populates="sessions")


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    __table_args__ = (
        UniqueConstraint("identifier_hash"),
        Index("ix_login_throttles_identifier_hash", "identifier_hash"),
        Index("ix_login_throttles_window_started_at", "window_started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Listing(Base, TimestampMixin):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_owner_updated_at", "owner_id", "updated_at"),
        Index("ix_listings_owner_status_updated_at", "owner_id", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    condition: Mapped[str] = mapped_column(String(40), default="used")
    category: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    delivery_options: Mapped[dict] = mapped_column(JSON, default=dict)
    pickup_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    shipping_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    shipping_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    weight_grams: Mapped[int] = mapped_column(Integer, default=0)
    brand: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    color: Mapped[str] = mapped_column(String(80), default="")
    material: Mapped[str] = mapped_column(String(120), default="")
    category_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=1)

    owner: Mapped[User] = relationship(back_populates="listings")
    images: Mapped[list["ListingImage"]] = relationship(
        cascade="all, delete-orphan", back_populates="listing", order_by="ListingImage.position"
    )
    platform_mappings: Mapped[list["PlatformListingMapping"]] = relationship(
        cascade="all, delete-orphan", back_populates="listing"
    )
    jobs: Mapped[list["PublishingJob"]] = relationship(cascade="all, delete-orphan", back_populates="listing")
    drafts: Mapped[list["ListingDraft"]] = relationship(
        cascade="all, delete-orphan", back_populates="listing"
    )


class HaiListingChange(Base):
    """Append-only cursor source so HAI can observe updates and deletions."""

    __tablename__ = "hai_listing_changes"
    __table_args__ = (Index("ix_hai_listing_changes_owner_id_id", "owner_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ListingImage(Base, TimestampMixin):
    __tablename__ = "listing_images"
    __table_args__ = (Index("ix_listing_images_listing_position", "listing_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    listing: Mapped[Listing] = relationship(back_populates="images")


class PlatformAccount(Base, TimestampMixin):
    __tablename__ = "platform_accounts"
    __table_args__ = (
        UniqueConstraint("owner_id", "platform", "display_name"),
        Index("ix_platform_accounts_owner_platform_status", "owner_id", "platform", "status"),
        Index("ix_platform_accounts_owner_created_at", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(80), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(40), default="assisted")
    status: Mapped[str] = mapped_column(String(40), default="needs_setup")
    connection_data: Mapped[dict] = mapped_column(JSON, default=dict)
    secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PlatformOAuthState(Base):
    __tablename__ = "platform_oauth_states"
    __table_args__ = (
        UniqueConstraint("state_hash"),
        Index("ix_platform_oauth_states_user_platform_created_at", "user_id", "platform", "created_at"),
        Index("ix_platform_oauth_states_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(80), index=True)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    redirect_uri: Mapped[str] = mapped_column(String(500))
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PlatformListingMapping(Base, TimestampMixin):
    __tablename__ = "platform_listing_mappings"
    __table_args__ = (UniqueConstraint("listing_id", "platform"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(80), index=True)
    platform_listing_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    platform_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    listing: Mapped[Listing] = relationship(back_populates="platform_mappings")


class CategoryMapping(Base, TimestampMixin):
    __tablename__ = "category_mappings"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_category", "platform"),
        Index("ix_category_mappings_owner_platform_source", "owner_id", "platform", "source_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_category: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str] = mapped_column(String(80))
    platform_category: Mapped[str] = mapped_column(String(120))


class PublishingJob(Base, TimestampMixin):
    __tablename__ = "publishing_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index("ix_publishing_jobs_listing_created_at", "listing_id", "created_at"),
        Index("ix_publishing_jobs_listing_platform_status", "listing_id", "platform", "status"),
        Index("ix_publishing_jobs_due_queue", "status", "scheduled_at", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(80), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("platform_accounts.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    claim_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    listing_revision: Mapped[int] = mapped_column(Integer, default=1)
    action_type: Mapped[str] = mapped_column(String(40), default="publish")
    operation_mode: Mapped[str] = mapped_column(String(40), default="assisted")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)

    listing: Mapped[Listing] = relationship(back_populates="jobs")
    logs: Mapped[list["PublishingJobLog"]] = relationship(
        cascade="all, delete-orphan", back_populates="job", order_by="PublishingJobLog.created_at"
    )
    publication_attempts: Mapped[list["PublicationAttempt"]] = relationship(
        cascade="all, delete-orphan", back_populates="job"
    )


class PublishingJobLog(Base):
    __tablename__ = "publishing_job_logs"
    __table_args__ = (Index("ix_publishing_job_logs_job_created_at", "job_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("publishing_jobs.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    job: Mapped[PublishingJob] = relationship(back_populates="logs")


class ListingDraft(Base, TimestampMixin):
    __tablename__ = "listing_drafts"
    __table_args__ = (Index("ix_listing_drafts_listing_created_at", "listing_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(40), default="manual")

    listing: Mapped[Listing] = relationship(back_populates="drafts")


class ListingTemplate(Base, TimestampMixin):
    __tablename__ = "listing_templates"
    __table_args__ = (
        Index("ix_listing_templates_owner_platform_name", "owner_id", "platform", "name"),
        Index("ix_listing_templates_owner_variant", "owner_id", "variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    variant: Mapped[str] = mapped_column(String(80), default="default")
    platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    body: Mapped[str] = mapped_column(Text)


class PublicationAttempt(Base):
    __tablename__ = "publication_attempts"
    __table_args__ = (Index("ix_publication_attempts_job_created_at", "job_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("publishing_jobs.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    job: Mapped[PublishingJob] = relationship(back_populates="publication_attempts")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_user_created_at", "user_id", "created_at"),
        Index("ix_audit_events_action_created_at", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_email_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (Index("ix_worker_heartbeats_last_seen_at", "last_seen_at"),)

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    processed_jobs: Mapped[int] = mapped_column(Integer, default=0)


class OperatorControl(Base):
    """Singleton operational controls shared by API and worker processes."""

    __tablename__ = "operator_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    job_processing_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(500), default="")
    updated_by: Mapped[str] = mapped_column(String(120), default="operator-cli")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


def _record_hai_listing_change(_mapper, connection, target: Listing, action: str) -> None:
    connection.execute(
        HaiListingChange.__table__.insert().values(
            owner_id=target.owner_id,
            listing_id=target.id,
            action=action,
            changed_at=now_utc(),
        )
    )


@event.listens_for(Listing, "after_insert")
def _record_hai_listing_insert(_mapper, connection, target: Listing) -> None:
    _record_hai_listing_change(_mapper, connection, target, "upsert")


@event.listens_for(Listing, "after_update")
def _record_hai_listing_update(_mapper, connection, target: Listing) -> None:
    _record_hai_listing_change(_mapper, connection, target, "upsert")


@event.listens_for(Listing, "after_delete")
def _record_hai_listing_delete(_mapper, connection, target: Listing) -> None:
    _record_hai_listing_change(_mapper, connection, target, "delete")


def _record_hai_related_change(_mapper, connection, target) -> None:
    # Resolve ownership and append within the same transaction, without loading
    # a listing or its relationships into the worker/API session.
    connection.execute(
        HaiListingChange.__table__.insert().from_select(
            ["owner_id", "listing_id", "action", "changed_at"],
            select(Listing.owner_id, Listing.id, literal("upsert"), literal(now_utc()))
            .where(Listing.id == target.listing_id),
        )
    )


for _related_model in (ListingImage, PlatformListingMapping):
    event.listen(_related_model, "after_insert", _record_hai_related_change)
    event.listen(_related_model, "after_delete", _record_hai_related_change)


@event.listens_for(PlatformListingMapping, "after_update")
def _record_hai_platform_selection_change(mapper, connection, target: PlatformListingMapping) -> None:
    history = inspect(target).attrs.status.history
    if history.has_changes() and ("skipped" in history.deleted or "skipped" in history.added):
        _record_hai_related_change(mapper, connection, target)
