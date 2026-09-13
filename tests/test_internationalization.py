from pathlib import Path

from app.config import Settings
from app.services.localization import localization_metadata


def test_internationalization_doc_keeps_translation_status_honest():
    content = Path("docs/INTERNATIONALIZATION.md").read_text(encoding="utf-8")

    required_phrases = [
        "frontend copy catalog",
        "Default locale: `en`",
        "defaulting to `en,nl`",
        "GET /api/localization",
        "Do not claim server-side/API messages or marketplace catalogs are fully translated",
        "English remains the fallback",
    ]
    for phrase in required_phrases:
        assert phrase in content


def test_localization_metadata_reports_frontend_catalog_status():
    metadata = localization_metadata(Settings())

    assert metadata["default_locale"] == "en"
    assert metadata["fallback_locale"] == "en"
    assert metadata["ui_catalog_status"] == "frontend_catalog_with_english_fallback"
    locales = {locale["code"]: locale for locale in metadata["supported_locales"]}
    assert locales["en"]["complete"] is True
    assert locales["nl"]["complete"] is True


def test_frontend_has_locale_selector_and_copy_catalogs():
    index = Path("public/index.html").read_text(encoding="utf-8")
    script = Path("public/app.js").read_text(encoding="utf-8")

    assert 'id="localeSelect"' in index
    assert 'data-i18n="nav.dashboard"' in index
    assert 'data-i18n-label="auth.email"' in index
    assert "COPY_CATALOG" in script
    assert "frontend_catalog_with_english_fallback" not in script
    assert "Tweedehands Autoposter" in script
    assert "Assistentiepakket in wachtrij" in script
    assert 'localStorage.setItem("autoposterLocale"' in script
    assert 'authApi("/localization"' in script
