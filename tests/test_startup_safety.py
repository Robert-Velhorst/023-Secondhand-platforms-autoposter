import pytest

from app.config import Settings, validate_startup_safety


def test_production_rejects_unsafe_defaults():
    settings = Settings(app_env="production")

    with pytest.raises(RuntimeError) as exc:
        validate_startup_safety(settings)

    message = str(exc.value)
    assert "SECRET_KEY" in message
    assert "AUTO_CREATE_TABLES" in message
    assert "CORS_ORIGINS" in message


def test_production_accepts_safe_startup_configuration():
    settings = Settings(
        app_env="production",
        secret_key="production-secret-with-enough-entropy-32chars",
        cors_origins="https://example.com",
        database_url="postgresql+psycopg://autoposter:secret@db.example.com:5432/autoposter",
        public_base_url="https://example.com",
        auto_create_tables=False,
        dev_auto_login=False,
        job_process_inline=False,
    )

    validate_startup_safety(settings)


def test_unsupported_auth_transport_is_rejected():
    settings = Settings(auth_transport="cookie")

    with pytest.raises(RuntimeError) as exc:
        validate_startup_safety(settings)

    assert "AUTH_TRANSPORT must be bearer" in str(exc.value)


def test_supported_runtime_configuration_modes_are_accepted():
    settings = Settings(storage_backend="local", log_format="json", platform_rate_limit_seconds=0)

    validate_startup_safety(settings)


def test_s3_storage_configuration_mode_is_accepted():
    settings = Settings(storage_backend="s3", s3_bucket="autoposter-images")

    validate_startup_safety(settings)


def test_invalid_runtime_configuration_values_are_rejected():
    settings = Settings(
        storage_backend="ftp",
        log_format="xml",
        max_upload_size_mb=0,
        login_rate_limit_attempts=0,
        login_rate_limit_window_seconds=0,
        api_rate_limit_requests=0,
        api_rate_limit_window_seconds=0,
        job_worker_poll_seconds=0,
        job_worker_batch_size=0,
        job_stale_running_seconds=-1,
        platform_rate_limit_seconds=-1,
        session_expire_hours=0,
        audit_retention_days=-1,
    )

    with pytest.raises(RuntimeError) as exc:
        validate_startup_safety(settings)

    message = str(exc.value)
    assert "STORAGE_BACKEND must be local or s3" in message
    assert "LOG_FORMAT must be text or json" in message
    assert "MAX_UPLOAD_SIZE_MB must be positive" in message
    assert "LOGIN_RATE_LIMIT_ATTEMPTS must be positive" in message
    assert "LOGIN_RATE_LIMIT_WINDOW_SECONDS must be positive" in message
    assert "API_RATE_LIMIT_REQUESTS must be positive" in message
    assert "API_RATE_LIMIT_WINDOW_SECONDS must be positive" in message
    assert "JOB_WORKER_POLL_SECONDS must be positive" in message
    assert "JOB_WORKER_BATCH_SIZE must be positive" in message
    assert "JOB_STALE_RUNNING_SECONDS must be non-negative" in message
    assert "PLATFORM_RATE_LIMIT_SECONDS must be non-negative" in message
    assert "SESSION_EXPIRE_HOURS must be positive" in message
    assert "AUDIT_RETENTION_DAYS must be non-negative" in message


def test_s3_storage_requires_bucket():
    settings = Settings(storage_backend="s3", s3_bucket="")

    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        validate_startup_safety(settings)


def test_production_rejects_short_secret_non_postgresql_and_inline_processing():
    settings = Settings(
        app_env="production",
        secret_key="too-short",
        cors_origins="https://example.com",
        auto_create_tables=False,
        public_base_url="http://example.com",
    )

    with pytest.raises(RuntimeError) as exc:
        validate_startup_safety(settings)

    message = str(exc.value)
    assert "SECRET_KEY must be at least 32 characters" in message
    assert "DATABASE_URL must use PostgreSQL" in message
    assert "PUBLIC_BASE_URL must use https" in message
    assert "JOB_PROCESS_INLINE must be false" in message


def test_production_rejects_invalid_cors_origin():
    settings = Settings(
        app_env="production",
        secret_key="production-secret-with-enough-entropy-32chars",
        cors_origins="autoposter.example.com",
        database_url="postgresql+psycopg://autoposter:secret@db.example.com:5432/autoposter",
        public_base_url="https://autoposter.example.com",
        auto_create_tables=False,
        job_process_inline=False,
    )

    with pytest.raises(RuntimeError, match="CORS_ORIGINS entries must be absolute"):
        validate_startup_safety(settings)


def test_feature_flags_are_reported_from_settings():
    settings = Settings(dev_auto_login=True, auto_create_tables=False, job_process_inline=False)

    flags = {flag.name: flag for flag in settings.feature_flags}

    assert flags["dev_auto_login"].enabled is True
    assert flags["dev_auto_login"].production_allowed is False
    assert flags["auto_create_tables"].enabled is False
    assert flags["inline_job_processing"].enabled is False


def test_unimplemented_external_suggestion_provider_is_rejected():
    settings = Settings(suggestion_provider="external-ai")

    with pytest.raises(RuntimeError, match="SUGGESTION_PROVIDER must be deterministic_local"):
        validate_startup_safety(settings)
