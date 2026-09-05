from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

LISTING_CONDITIONS = frozenset({"new", "as_new", "good", "used", "fair", "damaged", "for_parts", "other"})
LISTING_STATUSES = frozenset({"draft", "ready", "published", "archived"})


def _non_negative(value: int | None) -> int | None:
    if value is not None and value < 0:
        raise ValueError("must be greater than or equal to 0")
    return value


def _normalize_currency(value: str | None) -> str | None:
    if value is None:
        return value
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return normalized


def _normalize_choice(value: str | None, allowed: frozenset[str], field_name: str) -> str | None:
    if value is None:
        return value
    normalized = value.strip().lower()
    if normalized not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {allowed_values}")
    return normalized


def _normalize_tags(value: list[str] | None) -> list[str] | None:
    if value is None:
        return value
    normalized: list[str] = []
    seen = set()
    for raw_tag in value:
        tag = raw_tag.strip()
        if not tag:
            continue
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(tag)
    if len(normalized) > 20:
        raise ValueError("tags cannot contain more than 20 values")
    long_tags = [tag for tag in normalized if len(tag) > 40]
    if long_tags:
        raise ValueError("tags cannot be longer than 40 characters")
    return normalized


def _normalize_category_attributes(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return value
    if len(value) > 30:
        raise ValueError("category_attributes cannot contain more than 30 fields")
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("category_attributes keys cannot be blank")
        if len(key) > 80:
            raise ValueError("category_attributes keys cannot be longer than 80 characters")
        normalized[key] = raw_value
    return normalized


class AuthRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = ""


class AuthLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str


class AccountUsage(BaseModel):
    listings: int = 0
    publishing_jobs: int = 0
    platform_accounts: int = 0
    templates: int = 0
    category_mappings: int = 0


class AccountReadiness(BaseModel):
    user: UserOut
    scope: str = "personal_account"
    billing_required: bool = False
    billing_status: str = "not_configured"
    workspaces_enabled: bool = False
    data_isolation: str = "owner_id"
    usage: AccountUsage


class AuthToken(BaseModel):
    token: str
    user: UserOut


class HaiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_days: int = Field(default=90, ge=1, le=365)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class HaiTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: str
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class HaiTokenCreated(HaiTokenOut):
    token: str


class HaiRecord(BaseModel):
    id: str
    type: str = "secondhand_listing"
    title: str
    content: str
    source_url: str
    updated_at: datetime
    deleted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class HaiRecordPage(BaseModel):
    connector: str = "secondhand-platforms-autoposter"
    read_only: bool = True
    records: list[HaiRecord] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class ListingBase(BaseModel):
    title: str = ""
    description: str = ""
    price_cents: int = 0
    currency: str = "EUR"
    condition: str = "used"
    category: str = ""
    location: str = ""
    delivery_options: dict[str, Any] = Field(default_factory=dict)
    pickup_allowed: bool = True
    shipping_allowed: bool = False
    shipping_cost_cents: int = 0
    dimensions: dict[str, Any] = Field(default_factory=dict)
    weight_grams: int = 0
    brand: str = ""
    model: str = ""
    color: str = ""
    material: str = ""
    category_attributes: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    internal_notes: str = ""
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"

    @field_validator("price_cents", "shipping_cost_cents", "weight_grams")
    @classmethod
    def validate_non_negative_numbers(cls, value: int) -> int:
        return _non_negative(value) or 0

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value) or "EUR"

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        return _normalize_choice(value, LISTING_CONDITIONS, "condition") or "used"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _normalize_choice(value, LISTING_STATUSES, "status") or "draft"

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tags(value) or []

    @field_validator("category_attributes")
    @classmethod
    def validate_category_attributes(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalize_category_attributes(value) or {}


class ListingCreate(ListingBase):
    pass


class ListingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price_cents: int | None = None
    currency: str | None = None
    condition: str | None = None
    category: str | None = None
    location: str | None = None
    delivery_options: dict[str, Any] | None = None
    pickup_allowed: bool | None = None
    shipping_allowed: bool | None = None
    shipping_cost_cents: int | None = None
    dimensions: dict[str, Any] | None = None
    weight_grams: int | None = None
    brand: str | None = None
    model: str | None = None
    color: str | None = None
    material: str | None = None
    category_attributes: dict[str, Any] | None = None
    notes: str | None = None
    internal_notes: str | None = None
    tags: list[str] | None = None
    status: str | None = None

    @field_validator("price_cents", "shipping_cost_cents", "weight_grams")
    @classmethod
    def validate_non_negative_numbers(cls, value: int | None) -> int | None:
        return _non_negative(value)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        return _normalize_currency(value)

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, value: str | None) -> str | None:
        return _normalize_choice(value, LISTING_CONDITIONS, "condition")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        return _normalize_choice(value, LISTING_STATUSES, "status")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_tags(value)

    @field_validator("category_attributes")
    @classmethod
    def validate_category_attributes(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _normalize_category_attributes(value)


class ListingImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    file_size: int
    checksum_sha256: str
    position: int
    created_at: datetime


class PlatformMappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    platform_listing_id: str | None
    status: str
    platform_url: str | None
    overrides: dict[str, Any]
    validation_errors: list[Any]
    last_published_at: datetime | None


class ListingOut(ListingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    revision: int
    created_at: datetime
    updated_at: datetime
    images: list[ListingImageOut] = Field(default_factory=list)
    platform_mappings: list[PlatformMappingOut] = Field(default_factory=list)


class PlatformAccountCreate(BaseModel):
    platform: str
    display_name: str
    mode: str = "assisted"
    status: str = "needs_setup"
    connection_data: dict[str, Any] = Field(default_factory=dict)


class PlatformAccountUpdate(BaseModel):
    platform: str | None = None
    display_name: str | None = None
    mode: str | None = None
    status: str | None = None
    connection_data: dict[str, Any] | None = None


class PlatformAccountOut(PlatformAccountCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime


class OAuthStartResponse(BaseModel):
    authorization_url: str
    expires_at: datetime
    platform: str = "ebay"
    mode: str = "official_api"


class PlatformOverrideUpdate(BaseModel):
    platform: str
    overrides: dict[str, Any] = Field(default_factory=dict)
    selected: bool = True


class ImageOrderUpdate(BaseModel):
    image_ids: list[int]


class PublishRequest(BaseModel):
    platforms: list[str]
    account_ids: dict[str, int] = Field(default_factory=dict)
    process_now: bool = True
    force_new_revision: bool = False


class ManualCompletionRequest(BaseModel):
    platform_url: str = Field(min_length=8, max_length=500)
    platform_listing_id: str | None = Field(default=None, max_length=255)

    @field_validator("platform_url")
    @classmethod
    def validate_platform_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not (cleaned.startswith("https://") or cleaned.startswith("http://")):
            raise ValueError("platform_url must start with http:// or https://")
        return cleaned


class JobLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    message: str
    data: dict[str, Any]
    created_at: datetime


class PublishingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    platform: str
    account_id: int | None
    listing_revision: int
    action_type: str
    operation_mode: str
    status: str
    attempts: int
    max_attempts: int
    scheduled_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    next_retry_at: datetime | None
    error_message: str | None
    result: dict[str, Any]
    logs: list[JobLogOut] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    name: str
    body: str
    variant: str = "default"
    platform: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    variant: str | None = None
    platform: str | None = None


class TemplateOut(TemplateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime


class CategoryMappingCreate(BaseModel):
    source_category: str
    platform: str
    platform_category: str


class CategoryMappingUpdate(BaseModel):
    source_category: str | None = None
    platform: str | None = None
    platform_category: str | None = None


class CategoryMappingOut(CategoryMappingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime


class ExportListingImage(BaseModel):
    filename: str
    storage_path: str
    content_type: str
    file_size: int
    checksum_sha256: str
    position: int


class ExportPlatformMapping(BaseModel):
    platform: str
    platform_listing_id: str | None = None
    status: str = "draft"
    platform_url: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)
    validation_errors: list[Any] = Field(default_factory=list)
    last_published_at: datetime | None = None


class ExportListing(ListingBase):
    revision: int = 1
    images: list[ExportListingImage] = Field(default_factory=list)
    platform_mappings: list[ExportPlatformMapping] = Field(default_factory=list)


class DataExportBundle(BaseModel):
    version: str = "1"
    exported_at: datetime
    user: UserOut
    listings: list[ExportListing] = Field(default_factory=list)
    platform_accounts: list[PlatformAccountCreate] = Field(default_factory=list)
    templates: list[TemplateCreate] = Field(default_factory=list)
    category_mappings: list[CategoryMappingCreate] = Field(default_factory=list)


class ImportPlatformMapping(BaseModel):
    platform: str
    overrides: dict[str, Any] = Field(default_factory=dict)


class ImportListing(ListingCreate):
    platform_mappings: list[ImportPlatformMapping] = Field(default_factory=list)


class DataImportBundle(BaseModel):
    version: str | None = None
    listings: list[ImportListing] = Field(default_factory=list)
    platform_accounts: list[PlatformAccountCreate] = Field(default_factory=list)
    templates: list[TemplateCreate] = Field(default_factory=list)
    category_mappings: list[CategoryMappingCreate] = Field(default_factory=list)


class DataImportResult(BaseModel):
    listings_created: int = 0
    platform_mappings_created: int = 0
    platform_accounts_created: int = 0
    platform_accounts_updated: int = 0
    templates_created: int = 0
    templates_updated: int = 0
    category_mappings_created: int = 0
    category_mappings_updated: int = 0
    skipped: int = 0


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    event_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ValidationResult(BaseModel):
    platform: str
    ready: bool
    missing_fields: list[str]
    warnings: list[str] = Field(default_factory=list)
    mapped_fields: dict[str, Any] = Field(default_factory=dict)


class ListingQualityIssue(BaseModel):
    field: str
    severity: str
    message: str
    action: str


class ListingQualitySuggestion(BaseModel):
    field: str
    value: Any
    rationale: str


class ListingQualityResult(BaseModel):
    provider: str = "deterministic_local"
    deterministic: bool = True
    external_data_sent: bool = False
    score: int = Field(ge=0, le=100)
    grade: str
    summary: str
    issues: list[ListingQualityIssue] = Field(default_factory=list)
    suggestions: list[ListingQualitySuggestion] = Field(default_factory=list)
    checklist: dict[str, bool] = Field(default_factory=dict)


class ActionItem(BaseModel):
    id: str
    kind: str
    severity: str
    title: str
    detail: str
    next_action: str
    target_view: str
    resource_type: str | None = None
    resource_id: int | None = None


class OnboardingStep(BaseModel):
    id: str
    label: str
    complete: bool
    target_view: str


class ActionCenterResult(BaseModel):
    source: str = "derived_local"
    generated_at: datetime
    onboarding_complete: bool
    onboarding_steps: list[OnboardingStep] = Field(default_factory=list)
    reminders: list[ActionItem] = Field(default_factory=list)


class AnalyticsIssueCount(BaseModel):
    field: str
    count: int


class AnalyticsQualitySummary(BaseModel):
    grade_counts: dict[str, int] = Field(default_factory=dict)
    top_issue_fields: list[AnalyticsIssueCount] = Field(default_factory=list)
    listings_missing_images: int = 0
    average_images_per_listing: float = 0


class AnalyticsResult(BaseModel):
    source: str
    external_tracking: bool
    summary: dict[str, int | float] = Field(default_factory=dict)
    listing_statuses: dict[str, int] = Field(default_factory=dict)
    job_statuses: dict[str, int] = Field(default_factory=dict)
    job_platforms: dict[str, int] = Field(default_factory=dict)
    selected_platforms: dict[str, int] = Field(default_factory=dict)
    quality: AnalyticsQualitySummary


class DashboardResult(BaseModel):
    analytics: AnalyticsResult
    action_center: ActionCenterResult
    recent_listings: list[ListingOut] = Field(default_factory=list)
    latest_jobs: list[PublishingJobOut] = Field(default_factory=list)
