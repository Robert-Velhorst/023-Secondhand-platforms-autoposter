from app.config import Settings

LANGUAGE_NAMES = {
    "en": "English",
    "nl": "Nederlands",
}


def localization_metadata(settings: Settings) -> dict:
    locales = settings.supported_locale_list
    return {
        "default_locale": settings.default_locale.lower(),
        "supported_locales": [
            {
                "code": locale,
                "name": LANGUAGE_NAMES.get(locale, locale),
                "complete": locale == "en",
            }
            for locale in locales
        ],
        "ui_catalog_status": "frontend_catalog_with_english_fallback",
        "fallback_locale": "en",
    }
