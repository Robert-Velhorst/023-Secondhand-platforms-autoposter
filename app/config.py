from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.feature_flags import FeatureFlag, build_feature_flags, unsafe_production_feature_flags


class Settings(BaseSettings):
    app_name: str = "Secondhand Platforms Autoposter"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    database_url: str = "sqlite:///./data/autoposter.db"
    public_base_url: str = "http://127.0.0.1:8000"
    upload_dir: str = "./data/uploads"
    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_key_prefix: str = "uploads"
    max_upload_size_mb: int = 10
    allowed_image_types: str = "image/jpeg,image/png,image/gif,image/webp"
    cors_origins: str = "*"
    log_level: str = "INFO"
    log_format: str = "text"
    dev_auto_login: bool = False
    auth_transport: str = "bearer"
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    api_rate_limit_requests: int = 300
    api_rate_limit_window_seconds: int = 60
    auto_create_tables: bool = True
    job_process_inline: bool = True
    job_worker_poll_seconds: int = 5
    job_worker_batch_size: int = 10
    worker_heartbeat_timeout_seconds: int = 30
    job_stale_running_seconds: int = 1800
    platform_rate_limit_seconds: int = 60
    platform_rate_limit_overrides: str = ""
    session_expire_hours: int = 168
    audit_retention_days: int = 365
    suggestion_provider: str = "deterministic_local"
    default_locale: str = "en"
    supported_locales: str = "en,nl"
    ebay_oauth_client_id: str = ""
    ebay_oauth_client_secret: str = ""
    ebay_oauth_redirect_uri: str = ""
    ebay_oauth_environment: str = "sandbox"
    ebay_oauth_scopes: str = (
        "https://api.ebay.com/oauth/api_scope/sell.inventory "
        "https://api.ebay.com/oauth/api_scope/sell.account"
    )
    ebay_oauth_state_ttl_seconds: int = 600
    ebay_token_secret_ref_prefix: str = "secret://ebay/oauth"
    token_secret_dir: str = "./data/secrets"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def token_secret_path(self) -> Path:
        return Path(self.token_secret_dir)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_image_type_set(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_image_types.split(",") if item.strip()}

    @property
    def platform_rate_limit_seconds_by_platform(self) -> dict[str, int]:
        overrides: dict[str, int] = {}
        for raw_item in self.platform_rate_limit_overrides.split(","):
            item = raw_item.strip()
            if not item:
                continue
            if "=" not in item:
                raise ValueError("PLATFORM_RATE_LIMIT_OVERRIDES entries must use platform=seconds")
            platform, raw_seconds = item.split("=", 1)
            platform_key = platform.strip().lower()
            if not platform_key:
                raise ValueError("PLATFORM_RATE_LIMIT_OVERRIDES platform cannot be empty")
            try:
                seconds = int(raw_seconds.strip())
            except ValueError as exc:
                raise ValueError("PLATFORM_RATE_LIMIT_OVERRIDES seconds must be integers") from exc
            if seconds < 0:
                raise ValueError("PLATFORM_RATE_LIMIT_OVERRIDES seconds must be non-negative")
            overrides[platform_key] = seconds
        return overrides

    def platform_rate_limit_for(self, platform: str) -> int:
        return self.platform_rate_limit_seconds_by_platform.get(platform.lower(), self.platform_rate_limit_seconds)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def feature_flags(self) -> tuple[FeatureFlag, ...]:
        return build_feature_flags(self)

    @property
    def supported_locale_list(self) -> list[str]:
        return [locale.strip().lower() for locale in self.supported_locales.split(",") if locale.strip()]

    @property
    def ebay_oauth_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.ebay_oauth_scopes.split() if scope.strip()]

    @property
    def ebay_oauth_authorize_url(self) -> str:
        if self.ebay_oauth_environment.lower() == "production":
            return "https://auth.ebay.com/oauth2/authorize"
        return "https://auth.sandbox.ebay.com/oauth2/authorize"

    @property
    def ebay_oauth_token_url(self) -> str:
        if self.ebay_oauth_environment.lower() == "production":
            return "https://api.ebay.com/identity/v1/oauth2/token"
        return "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

    @property
    def ebay_inventory_api_base_url(self) -> str:
        if self.ebay_oauth_environment.lower() == "production":
            return "https://api.ebay.com/sell/inventory/v1"
        return "https://api.sandbox.ebay.com/sell/inventory/v1"

    @property
    def ebay_oauth_configured(self) -> bool:
        return bool(self.ebay_oauth_client_id.strip() and self.ebay_oauth_redirect_uri.strip())

    @property
    def ebay_oauth_token_exchange_configured(self) -> bool:
        return bool(
            self.ebay_oauth_client_id.strip()
            and self.ebay_oauth_client_secret.strip()
            and self.ebay_oauth_redirect_uri.strip()
        )


def validate_startup_safety(settings: Settings) -> None:
    problems: list[str] = []
    if settings.auth_transport.lower() != "bearer":
        problems.append("AUTH_TRANSPORT must be bearer")
    if settings.storage_backend.lower() not in {"local", "s3"}:
        problems.append("STORAGE_BACKEND must be local or s3")
    if settings.storage_backend.lower() == "s3" and not settings.s3_bucket.strip():
        problems.append("S3_BUCKET must be set when STORAGE_BACKEND=s3")
    if settings.log_format.lower() not in {"text", "json"}:
        problems.append("LOG_FORMAT must be text or json")
    if settings.max_upload_size_mb <= 0:
        problems.append("MAX_UPLOAD_SIZE_MB must be positive")
    if settings.login_rate_limit_attempts <= 0:
        problems.append("LOGIN_RATE_LIMIT_ATTEMPTS must be positive")
    if settings.login_rate_limit_window_seconds <= 0:
        problems.append("LOGIN_RATE_LIMIT_WINDOW_SECONDS must be positive")
    if settings.api_rate_limit_requests <= 0:
        problems.append("API_RATE_LIMIT_REQUESTS must be positive")
    if settings.api_rate_limit_window_seconds <= 0:
        problems.append("API_RATE_LIMIT_WINDOW_SECONDS must be positive")
    if settings.job_worker_poll_seconds <= 0:
        problems.append("JOB_WORKER_POLL_SECONDS must be positive")
    if settings.job_worker_batch_size <= 0:
        problems.append("JOB_WORKER_BATCH_SIZE must be positive")
    if settings.worker_heartbeat_timeout_seconds <= 0:
        problems.append("WORKER_HEARTBEAT_TIMEOUT_SECONDS must be positive")
    if settings.job_stale_running_seconds < 0:
        problems.append("JOB_STALE_RUNNING_SECONDS must be non-negative")
    if settings.platform_rate_limit_seconds < 0:
        problems.append("PLATFORM_RATE_LIMIT_SECONDS must be non-negative")
    if settings.session_expire_hours <= 0:
        problems.append("SESSION_EXPIRE_HOURS must be positive")
    if settings.audit_retention_days < 0:
        problems.append("AUDIT_RETENTION_DAYS must be non-negative")
    if settings.suggestion_provider.lower() != "deterministic_local":
        problems.append("SUGGESTION_PROVIDER must be deterministic_local until an approved provider is implemented")
    if not settings.default_locale.strip():
        problems.append("DEFAULT_LOCALE must not be empty")
    if not settings.supported_locale_list:
        problems.append("SUPPORTED_LOCALES must contain at least one locale")
    if settings.default_locale.lower() not in settings.supported_locale_list:
        problems.append("DEFAULT_LOCALE must be included in SUPPORTED_LOCALES")
    if settings.ebay_oauth_environment.lower() not in {"sandbox", "production"}:
        problems.append("EBAY_OAUTH_ENVIRONMENT must be sandbox or production")
    if settings.ebay_oauth_state_ttl_seconds <= 0:
        problems.append("EBAY_OAUTH_STATE_TTL_SECONDS must be positive")
    if not settings.ebay_oauth_scope_list:
        problems.append("EBAY_OAUTH_SCOPES must contain at least one scope")
    if settings.ebay_oauth_environment.lower() == "production" and not settings.ebay_oauth_configured:
        problems.append("EBAY OAuth production mode requires EBAY_OAUTH_CLIENT_ID and EBAY_OAUTH_REDIRECT_URI")
    if settings.ebay_oauth_environment.lower() == "production" and not settings.ebay_oauth_client_secret.strip():
        problems.append("EBAY OAuth production mode requires EBAY_OAUTH_CLIENT_SECRET")

    if problems:
        detail = "; ".join(problems)
        raise RuntimeError(f"Invalid configuration: {detail}")

    if not settings.is_production:
        return

    problems = []
    if settings.secret_key in {"", "change-me-in-production", "replace-with-a-long-random-value"}:
        problems.append("SECRET_KEY must be set to a strong non-default value")
    elif len(settings.secret_key) < 32:
        problems.append("SECRET_KEY must be at least 32 characters in production")
    for flag in unsafe_production_feature_flags(settings):
        problems.append(flag.production_error)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if not origins or "*" in origins:
        problems.append("CORS_ORIGINS must be restricted in production")
    elif any(urlparse(origin).scheme not in {"http", "https"} or not urlparse(origin).netloc for origin in origins):
        problems.append("CORS_ORIGINS entries must be absolute http(s) origins in production")
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        problems.append("DATABASE_URL must use PostgreSQL in production")
    if not settings.public_base_url.startswith("https://"):
        problems.append("PUBLIC_BASE_URL must use https in production")

    if problems:
        detail = "; ".join(problems)
        raise RuntimeError(f"Unsafe production configuration: {detail}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
