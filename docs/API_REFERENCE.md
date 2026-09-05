# API Reference

This reference summarizes the implemented FastAPI surface. Interactive OpenAPI docs are available at `/docs` while the app is running.

All authenticated endpoints use bearer tokens returned by `POST /api/auth/register` or `POST /api/auth/login`.

## Error Shape

Errors use a structured envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": {},
    "field_errors": {},
    "retryable": false,
    "request_id": "..."
  }
}
```

Use `request_id` when matching browser reports to server logs. Retry only when `retryable` is true or after correcting user input.

## Public And Diagnostic Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check with current server time and application version. |
| `GET` | `/api/localization` | Current locale metadata and catalog status. |
| `GET` | `/api/metrics` | Authenticated, owner-scoped operational counts. |
| `GET` | `/api/diagnostics` | Authenticated doctor checks plus owner-scoped object counts. |
| `GET` | `/api/account/readiness` | Authenticated personal-account readiness contract with owner-scoped usage counts and no billing requirement. |
| `GET` | `/api/action-center` | Authenticated owner-scoped onboarding steps and actionable reminders. |
| `GET` | `/api/dashboard` | Authenticated combined analytics, action-center, recent-listing, and latest-job payload. |
| `GET` | `/api/worker-status` | Worker heartbeat readiness plus persistent operator-pause state. |

## Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create a user and bearer session. |
| `POST` | `/api/auth/login` | Create a bearer session. |
| `POST` | `/api/auth/logout` | Revoke the current session. |
| `GET` | `/api/auth/me` | Read the current user. |
| `DELETE` | `/api/auth/me` | Delete the current user and owned data. |

## Listings And Images

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/listings` | List owned listings with `search`, `status`, `sort`, `limit`, and `offset`. |
| `POST` | `/api/listings` | Create a listing. |
| `GET` | `/api/listings/{listing_id}` | Read one owned listing. |
| `PATCH` | `/api/listings/{listing_id}` | Update a listing and increment revision when data changes. |
| `DELETE` | `/api/listings/{listing_id}` | Delete a listing. |
| `POST` | `/api/listings/{listing_id}/duplicate` | Duplicate a listing. |
| `POST` | `/api/listings/{listing_id}/images` | Upload a validated image. |
| `GET` | `/api/listings/{listing_id}/images/{image_id}/content` | Read private image content from local or S3 storage as the owner. |
| `PATCH` | `/api/listings/{listing_id}/images/order` | Reorder uploaded images. |
| `DELETE` | `/api/listings/{listing_id}/images/{image_id}` | Delete an image. |

## Platform Preparation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/platforms` | Registered platform metadata, capabilities, required fields, supported categories, and compliance notes. |
| `POST` | `/api/listings/{listing_id}/platforms` | Save platform selection and overrides. |
| `GET` | `/api/listings/{listing_id}/validate` | Validate readiness and return mapped fields. |
| `GET` | `/api/listings/{listing_id}/quality` | Run deterministic local guidance and return provider/data-transfer disclosure. |
| `POST` | `/api/listings/{listing_id}/publish` | Queue assisted package jobs. Use `force_new_revision=true` to intentionally regenerate a fresh package. |

Registered production platforms are assisted-only. A successful assisted job returns `needs_user_action`, not API-confirmed marketplace publication.

`account_ids` is an optional map from a selected platform key to a platform-account ID. Omit a platform's entry to prepare its assisted package without an account. A supplied ID must exist, belong to the listing owner, and match that platform. Unavailable, foreign, wrong-platform, zero, and negative IDs receive the same generic HTTP 404 response without account details. Every selected platform/account is preflighted before `force_new_revision` or queue writes; unused map entries do not select platforms. The service rechecks the account before reusing or inserting a job, on retry, and before passing it to an adapter. A previously queued job whose account no longer matches fails with an account error instead of invoking the adapter. Correct the account/platform association or queue a new package with a suitable account; retry does not replace a job's account ID. Account setup status is metadata, not an additional admission gate for assisted posting.

Listing payloads include `category_attributes`, a bounded JSON object for category-specific item details such as furniture style, vehicle mileage, clothing size, or electronics accessories. These attributes are included in assisted mapped fields and JSON/CSV portability.

Account IDs outside the positive signed-64-bit range are also rejected before a database query, preventing integer-binding errors on SQLite. Existing request parsing of integer-compatible JSON values remains unchanged; authorization always checks the resulting ID.

## Jobs

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/jobs` | List owned jobs with platform/status/sort/page controls. |
| `GET` | `/api/jobs/{job_id}` | Read one owned job. |
| `POST` | `/api/jobs/{job_id}/retry` | Requeue a job after correcting the underlying issue. |
| `POST` | `/api/jobs/{job_id}/manual-completion` | Mark an assisted `needs_user_action` job as user-confirmed published with marketplace URL and optional listing ID. |

Queue idempotency covers every job state. A repeated `publish` request with the same key returns the existing job, including `failed` or `skipped`, without resetting attempts. Concurrent inserts for one key converge on one job and initial queue log. Use `/retry` for an eligible existing job or a new listing revision for a deliberately new package. HTTP 200 means the request was handled, not that preparation or marketplace publication succeeded; inspect each returned job's `status` and logs.

## Accounts, Templates, And Category Mappings

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/accounts` | List platform accounts with platform/status/sort/page controls. |
| `POST` | `/api/accounts` | Create a platform account record. |
| `PATCH` | `/api/accounts/{account_id}` | Update owned platform account metadata, setup status, and sanitized connection metadata. |
| `DELETE` | `/api/accounts/{account_id}` | Delete a platform account record. |
| `POST` | `/api/accounts/ebay/oauth/start` | Start eBay OAuth consent foundation when configured. |
| `GET` | `/api/accounts/ebay/oauth/callback` | Consume eBay OAuth callback state; records setup handoff or stores exchanged tokens through the configured secret store. |
| `GET` | `/api/templates` | List templates with search/platform/variant/sort/page controls. |
| `POST` | `/api/templates` | Create a template with `name`, `variant`, optional `platform`, and `body`. |
| `PATCH` | `/api/templates/{template_id}` | Update a template, including its variant. |
| `DELETE` | `/api/templates/{template_id}` | Delete a template. |
| `GET` | `/api/category-mappings` | List mappings with source/platform/sort/page controls. |
| `POST` | `/api/category-mappings` | Create or upsert a mapping. |
| `PATCH` | `/api/category-mappings/{mapping_id}` | Update a mapping. |
| `DELETE` | `/api/category-mappings/{mapping_id}` | Delete a mapping. |

## Data Portability

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/export` | Export portable JSON data without secrets or image binaries. |
| `POST` | `/api/import` | Import supported portable JSON data. |
| `GET` | `/api/export/listings.csv` | Export owned listings as CSV for spreadsheet workflows. |
| `POST` | `/api/import/listings.csv` | Import owned listings from the supported CSV format. |
| `GET` | `/api/export/images.zip` | Export owned uploaded image binaries as a ZIP with `manifest.json`. |

## Privacy

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/audit-events` | Review the signed-in user's sanitized privacy activity with optional `action`, `limit`, and `offset` controls. |

## HAI Read-Only Connector

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/.well-known/hai-connector.json` | Public discovery metadata and read-only capability declaration. |
| `GET` | `/api/hai/tokens` | List the signed-in user's connector token metadata. |
| `POST` | `/api/hai/tokens` | Create an expiring connector token; plaintext is returned once. |
| `DELETE` | `/api/hai/tokens/{token_id}` | Revoke an owned connector token. |
| `GET` | `/api/hai/status` | Verify an HAI bearer token and owner-scoped feed state. |
| `GET` | `/api/hai/records` | Read incremental owner-scoped listing upserts and deletion tombstones. |
| `GET` | `/api/hai/export` | Download current owner listings as HAI generic JSON (`items`); normal owner bearer session required. |

`/api/hai/status` and `/api/hai/records` require a `hai_...` connector token, not a normal user session. `/api/hai/export` deliberately uses the normal session and rejects connector tokens. It returns a no-store JSON attachment, or HTTP 413 without a partial file if the feed exceeds 5 MiB or HAI's item limits. See [HAI connector](HAI_CONNECTOR.md) for file registration, incremental compatibility gaps, and deletion limitations.

## Pagination

Paginated product collections return `X-Total-Count`, `X-Limit`, and `X-Offset` headers. Use `limit` and `offset` to page through those results. HAI records instead use opaque `cursor`, `next_cursor`, and `has_more` with `limit` from 1 to 250 (default 100). The HAI file export is complete-or-error, not a paginated response.

## Rate Limiting

API requests are throttled per bearer token or client IP using `API_RATE_LIMIT_REQUESTS` and `API_RATE_LIMIT_WINDOW_SECONDS`. Rate-limited responses use the structured error envelope with `code=RATE_LIMITED` and include a `Retry-After` header.
