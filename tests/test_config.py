import pytest

from app.config import Settings, validate_startup_safety


def env_example_keys() -> set[str]:
    keys = set()
    for line in open(".env.example", encoding="utf-8"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _ = stripped.split("=", 1)
        keys.add(key)
    return keys


def test_env_example_documents_all_runtime_settings():
    expected_keys = {field_name.upper() for field_name in Settings.model_fields}

    assert expected_keys - env_example_keys() == set()


def test_production_like_configuration_profile_passes_startup_safety():
    settings = Settings(
        app_env="production",
        secret_key="production-secret-with-enough-entropy-32chars",
        database_url="postgresql+psycopg://autoposter:secret@db.example.com:5432/autoposter",
        public_base_url="https://autoposter.example.com",
        cors_origins="https://autoposter.example.com",
        auto_create_tables=False,
        dev_auto_login=False,
        job_process_inline=False,
        log_format="json",
        storage_backend="s3",
        s3_bucket="autoposter-prod-images",
    )

    validate_startup_safety(settings)


def test_standalone_profile_allows_loopback_sqlite_with_secure_defaults():
    settings = Settings(
        app_env="standalone",
        secret_key="standalone-secret-with-enough-entropy-32chars",
        database_url="sqlite:///./data/standalone.db",
        public_base_url="http://127.0.0.1:8000",
        cors_origins="http://127.0.0.1:8000",
        auto_create_tables=False,
        dev_auto_login=False,
        job_process_inline=False,
    )

    validate_startup_safety(settings)


def test_standalone_profile_rejects_insecure_non_loopback_public_url():
    settings = Settings(
        app_env="standalone",
        secret_key="standalone-secret-with-enough-entropy-32chars",
        database_url="sqlite:///./data/standalone.db",
        public_base_url="http://example.test",
        cors_origins="http://example.test",
        auto_create_tables=False,
        dev_auto_login=False,
        job_process_inline=False,
    )

    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        validate_startup_safety(settings)


def test_platform_rate_limit_overrides_are_platform_specific():
    settings = Settings(platform_rate_limit_seconds=60, platform_rate_limit_overrides="marktplaats=120, ebay=300")

    assert settings.platform_rate_limit_for("marktplaats") == 120
    assert settings.platform_rate_limit_for("EBAY") == 300
    assert settings.platform_rate_limit_for("nextdoor") == 60


def test_platform_rate_limit_overrides_reject_invalid_entries():
    settings = Settings(platform_rate_limit_overrides="marktplaats")

    with pytest.raises(ValueError, match="platform=seconds"):
        _ = settings.platform_rate_limit_seconds_by_platform


def test_ebay_oauth_uses_sandbox_authorize_url_by_default():
    settings = Settings()

    assert settings.ebay_oauth_authorize_url == "https://auth.sandbox.ebay.com/oauth2/authorize"
    assert settings.ebay_oauth_token_url == "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    assert settings.ebay_inventory_api_base_url == "https://api.sandbox.ebay.com/sell/inventory/v1"
    assert "https://api.ebay.com/oauth/api_scope/sell.inventory" in settings.ebay_oauth_scope_list


def test_ebay_oauth_production_requires_client_and_redirect_config():
    settings = Settings(
        app_env="development",
        ebay_oauth_environment="production",
        ebay_oauth_client_id="",
        ebay_oauth_client_secret="",
        ebay_oauth_redirect_uri="",
    )

    with pytest.raises(RuntimeError, match="EBAY OAuth production mode"):
        validate_startup_safety(settings)


def test_ebay_oauth_production_requires_client_secret():
    settings = Settings(
        app_env="development",
        ebay_oauth_environment="production",
        ebay_oauth_client_id="client-id",
        ebay_oauth_client_secret="",
        ebay_oauth_redirect_uri="https://app.example.com/api/accounts/ebay/oauth/callback",
    )

    with pytest.raises(RuntimeError, match="EBAY_OAUTH_CLIENT_SECRET"):
        validate_startup_safety(settings)


def test_default_locale_must_be_supported():
    settings = Settings(default_locale="nl", supported_locales="en,de")

    with pytest.raises(RuntimeError, match="DEFAULT_LOCALE"):
        validate_startup_safety(settings)


def test_supported_locale_list_is_normalized():
    settings = Settings(supported_locales="en, NL, de")

    assert settings.supported_locale_list == ["en", "nl", "de"]


def test_api_rate_limit_config_must_be_positive():
    settings = Settings(api_rate_limit_requests=0, api_rate_limit_window_seconds=0)

    with pytest.raises(RuntimeError) as exc:
        validate_startup_safety(settings)

    message = str(exc.value)
    assert "API_RATE_LIMIT_REQUESTS must be positive" in message
    assert "API_RATE_LIMIT_WINDOW_SECONDS must be positive" in message
