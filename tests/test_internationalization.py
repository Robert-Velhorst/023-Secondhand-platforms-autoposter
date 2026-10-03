import re
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
    assert locales["nl"]["complete"] is False


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


def test_frontend_catalog_keys_are_synchronized_between_supported_locales():
    script = Path("public/app.js").read_text(encoding="utf-8")
    english = re.search(r"\n  en: \{(.*?)\n  \},\n  nl: \{", script, re.DOTALL)
    dutch = re.search(r"\n  nl: \{(.*?)\n  \},\n\};", script, re.DOTALL)

    assert english is not None
    assert dutch is not None
    english_keys = set(re.findall(r'^\s*"([^"]+)":', english.group(1), re.MULTILINE))
    dutch_keys = set(re.findall(r'^\s*"([^"]+)":', dutch.group(1), re.MULTILINE))
    assert english_keys == dutch_keys


def test_static_ui_translation_hooks_exist_in_both_catalogs():
    index = Path("public/index.html").read_text(encoding="utf-8")
    script = Path("public/app.js").read_text(encoding="utf-8")
    english = re.search(r"\n  en: \{(.*?)\n  \},\n  nl: \{", script, re.DOTALL)
    dutch = re.search(r"\n  nl: \{(.*?)\n  \},\n\};", script, re.DOTALL)
    assert english is not None and dutch is not None
    references = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', index))
    references.update(re.findall(r'\bt\("([^"]+)"\)', script))
    for locale_block in (english.group(1), dutch.group(1)):
        keys = set(re.findall(r'^\s*"([^"]+)":', locale_block, re.MULTILINE))
        assert references <= keys


def test_common_dynamic_ui_copy_uses_localized_catalog_values():
    script = Path("public/app.js").read_text(encoding="utf-8")

    assert "function localizedStatus(status)" in script
    assert 'localizedStatus(listing.status)' in script
    assert 'localizedStatus(job.status)' in script
    assert 'localizedStatus(account.status)' in script
    assert 't("review.notChecked")' in script
    assert 't("empty.assistedPackages")' in script
