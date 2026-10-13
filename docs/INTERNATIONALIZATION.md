# Internationalization

The app now has an explicit localization foundation and a frontend copy catalog for the primary dashboard shell.

## Current Decision

- Default locale: `en`.
- Supported locale codes: configured by `SUPPORTED_LOCALES`, defaulting to `en,nl`.
- Fallback locale: `en`.
- UI catalog status: English is the complete catalog; Dutch has translated primary dashboard chrome and metrics, onboarding steps, forms, filter and sort choices, condition choices, common listing/job/account statuses, known field labels, the prepublish review, and common empty states. Catalog keys stay synchronized across both locales.
- `GET /api/localization` marks Dutch as incomplete while any visible UI copy still relies on the English fallback.
- `GET /api/localization` exposes the locale contract to clients.
- The sidebar language selector stores the user's locale in browser local storage.
- English remains the fallback for untranslated dynamic API or operational messages.

## Current Limits

- API validation and operational messages are English-first.
- User language preference is stored in browser local storage, not yet on the user account.
- API validation messages, provider-supplied warnings, action-center reminder details, unknown data-driven field names, and diagnostics details remain English-first; unknown status values also fall back to their server-provided wording.
- No translated marketplace category catalogs are included yet.

## Rules

- Do not claim server-side/API messages or marketplace catalogs are fully translated.
- Any new locale must appear in `SUPPORTED_LOCALES`.
- `DEFAULT_LOCALE` must be included in `SUPPORTED_LOCALES`.
- English remains the fallback for missing translated strings.

## Future Implementation

To complete internationalization:

- Localize validation messages, quality-assistant explanations, provider-supplied warnings, and remaining operational copy.
- Add locale-aware number, currency, and date formatting where user-visible.
- Add browser walkthrough evidence for each supported locale.
