# Secondhand Platforms Autoposter

A full-stack listing manager for preparing one reusable secondhand product listing and publishing or preparing it across multiple secondhand platforms from one dashboard.

The current production-safe implementation uses assisted-posting adapters for Marktplaats, Koopplein, Nextdoor, eBay, and Tweedehands. It validates listings, stores platform-specific overrides, queues publishing jobs, records logs and attempts, and produces a prepared posting package for the account owner to complete on each platform. It does not bypass login checks, CAPTCHAs, paid placement flows, rate limits, or platform security systems.

## Stack

- FastAPI backend
- SQLAlchemy models
- SQLite by default
- Static HTML/CSS/JavaScript dashboard
- Pytest API tests
- Docker Compose for local deployment

Legacy Selenium scripts remain in the repository as reference/manual tooling, but they are not part of the default web app startup path.

Install `requirements-legacy.txt` only if you need to run the old Selenium scripts in a compatible Python environment.

See `docs/ARCHITECTURE.md` for the current backend route/module layout.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

On Linux/macOS, activate with `source .venv/bin/activate` and copy the env file with `cp .env.example .env`.

## Docker

```bash
copy .env.example .env
docker compose up --build
```

The app is available at `http://127.0.0.1:8000`. SQLite data and uploads are stored in `./data`.

The Compose stack also starts a worker service that runs queued publishing jobs:

```bash
python -m app.worker
```

For local development, `JOB_PROCESS_INLINE=true` keeps publish jobs immediately processed in the API request. For production-style operation, set `JOB_PROCESS_INLINE=false` and run the worker process.

## Production deployment

Use the separate production Compose definition; it deliberately has no bundled database and runs Alembic before the API and worker can start.

```bash
copy .env.production.example .env.production
# Set secret-manager-backed values in .env.production and a persistent upload location.
set UPLOAD_VOLUME=C:\path\to\persistent\autoposter-uploads
docker compose -f docker-compose.production.yml up --build
```

`DATABASE_URL` must point to target PostgreSQL, `APP_ENV=production`, `AUTH_TRANSPORT=bearer`, `AUTO_CREATE_TABLES=false`, and `JOB_PROCESS_INLINE=false`. The stack exposes `GET /api/health` for liveness and `GET /api/worker-status` for worker-heartbeat readiness. A container start is not final release evidence: record the deployed SHA, migration head, backup/restore result, edge rate-limit policy, user walkthrough, accessibility QA, and acceptance in `docs/RELEASE_EVIDENCE_RECORD.md`.

## Environment variables

- `SECRET_KEY`: set to a long random value in production.
- `DATABASE_URL`: SQLAlchemy database URL. Default: `sqlite:///./data/autoposter.db`.
- `UPLOAD_DIR`: image upload directory. Default: `./data/uploads`.
- `STORAGE_BACKEND`: storage adapter. Supported values: `local`, `s3`.
- `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, `S3_KEY_PREFIX`: optional S3-compatible object storage settings used when `STORAGE_BACKEND=s3`.
- `MAX_UPLOAD_SIZE_MB`: maximum image upload size.
- `ALLOWED_IMAGE_TYPES`: comma-separated accepted image MIME types.
- `CORS_ORIGINS`: comma-separated allowed origins or `*` for local development.
- `DEV_AUTO_LOGIN`: creates a reserved local demo session only when `APP_ENV=development`.
- `AUTH_TRANSPORT`: supported value is `bearer`; cookie sessions are not enabled.
- `LOGIN_RATE_LIMIT_ATTEMPTS`: failed login attempts allowed per email/IP window.
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS`: failed login throttle window.
- `API_RATE_LIMIT_REQUESTS`: API requests allowed per bearer token or client IP window.
- `API_RATE_LIMIT_WINDOW_SECONDS`: API throttle window.
- `AUTO_CREATE_TABLES`: local development helper. Must be `false` in production.
- `JOB_PROCESS_INLINE`: processes queued jobs in the request for local simplicity.
- `JOB_WORKER_POLL_SECONDS`: worker polling interval.
- `JOB_WORKER_BATCH_SIZE`: maximum queued jobs processed per worker pass.
- `WORKER_HEARTBEAT_TIMEOUT_SECONDS`: age after which a worker is reported unavailable by `GET /api/worker-status`.
- `JOB_STALE_RUNNING_SECONDS`: age after which a stuck running job is returned to the queue.
- `PLATFORM_RATE_LIMIT_SECONDS`: cooldown per platform between job attempts.
- `PLATFORM_RATE_LIMIT_OVERRIDES`: optional comma-separated per-platform cooldowns such as `marktplaats=120,ebay=300`.
- `SESSION_EXPIRE_HOURS`: bearer session lifetime.
- `AUDIT_RETENTION_DAYS`: age after which sanitized audit events can be purged by `python -m app.audit_retention`; `0` disables purging.
- `DEFAULT_LOCALE`: default UI/API locale contract. Default: `en`.
- `SUPPORTED_LOCALES`: comma-separated supported locale codes. Default: `en,nl`.
- `EBAY_OAUTH_CLIENT_ID`: optional eBay developer App ID for the official API consent foundation.
- `EBAY_OAUTH_REDIRECT_URI`: optional eBay OAuth redirect URI/RuName callback configured in the eBay developer application.
- `EBAY_OAUTH_ENVIRONMENT`: `sandbox` by default; `production` requires client ID and redirect URI.
- `EBAY_OAUTH_SCOPES`: space-separated eBay OAuth scopes requested during consent.
- `EBAY_OAUTH_STATE_TTL_SECONDS`: lifetime for one-use OAuth state values.
- `EBAY_TOKEN_SECRET_REF_PREFIX`: secret-manager reference prefix used after consent; raw tokens are not stored in app tables.
- `PUBLIC_BASE_URL`: public URL used for future generated links and diagnostics.
- `LOG_LEVEL`: desired logging verbosity for deployment.
- `LOG_FORMAT`: `text` for local logs or `json` for production log aggregation.
- `SUGGESTION_PROVIDER`: supported value is `deterministic_local`; listing content is not sent externally.

Legacy Selenium variables are documented in `.env.example` and should only be filled locally.

## Database

In development, tables can be created automatically when `AUTO_CREATE_TABLES=true`.

For production, set `AUTO_CREATE_TABLES=false` and run Alembic migrations explicitly:

```bash
alembic upgrade head
```

The schema includes:

- users and user sessions
- listings/products
- listing images
- platform accounts
- platform listing mappings
- category mappings
- publishing jobs
- publishing job logs
- listing drafts
- description templates
- publication attempts
- persistent operator controls

SQLite is the default for quick local development. PostgreSQL is supported through SQLAlchemy by setting `DATABASE_URL`, for example:

```bash
DATABASE_URL=postgresql+psycopg://autoposter:autoposter@postgres:5432/autoposter
docker compose --profile postgres up --build
```

## Verification

Run the local verification gate before pushing changes:

```bash
python scripts/verify.py
```

The script runs Ruff lint, Python compile checks, the full pytest suite, and the doctor command.

You can also run the test suite directly:

```bash
pytest
```

The test suite uses an isolated temporary SQLite database and validates the core create-listing-to-publish-job flow, adapter validation, auth, and image upload.

GitHub Actions runs the same verification gate on pushes and pull requests to `main`.

## Diagnostics

Run the doctor command to verify local configuration, database connectivity, migration state, upload storage, platform adapters, and legacy-script isolation:

```bash
python -m app.doctor
python -m app.doctor --json
```

The API also exposes `GET /api/diagnostics`, which includes the same doctor summary plus basic record counts.

## Image storage

Image uploads are validated before storage:

- filenames are sanitized
- upload size is bounded by `MAX_UPLOAD_SIZE_MB`
- MIME type and file signature are checked
- SHA-256 checksum is stored
- duplicate images on the same listing are ignored
- local storage is isolated under `UPLOAD_DIR/{listing_id}/`
- S3-compatible storage can be enabled with `STORAGE_BACKEND=s3`

Only JPEG, PNG, GIF, and WebP are enabled by default.

See `docs/IMAGE_STORAGE.md` for the storage backend and image policy details.

## Platform support

| Platform | Mode | Notes |
| --- | --- | --- |
| Marktplaats | Assisted | Prepares mapped fields. User completes login, verification, category/payment choices, and final submission. |
| Koopplein | Assisted | Prepares fields and tracks status. User confirms final post manually. |
| Nextdoor | Assisted | Keeps neighborhood/account confirmations user-controlled. |
| eBay | Assisted by default | OAuth/token foundations exist for future official API work, but credential-dependent publishing is not enabled. |
| Tweedehands | Assisted | Legacy import/posting scripts are separate and must be run only in compliant user-controlled sessions. |

See `docs/PLATFORM_COMPLETION_CONTRACTS.md` for the tested per-platform completion contract.

## Adding a platform adapter

1. Add a class implementing `PlatformAdapter` in `app/adapters/`.
2. Implement `validate_listing`, `map_listing_to_platform_fields`, `publish_listing`, `get_required_fields`, `get_supported_categories`, and honest `PlatformCapabilities` metadata.
3. Register it in `app/adapters/registry.py`.
4. Add adapter tests that prove assisted adapters do not fake external success; use fake local API responses only for future official API test suites.
5. Document the automation mode and compliance limits here.

`GET /api/platforms` exposes each adapter's capabilities, including prepared fields, supported category mapping, official API status, account requirements, manual steps, blocked actions, and whether final marketplace submission remains user-controlled.

## API highlights

For a seller-facing workflow guide, see `docs/USER_GUIDE.md`. For endpoint-level details, see `docs/API_REFERENCE.md`.

- `POST /api/auth/register`
- `POST /api/auth/login`
- `DELETE /api/auth/me`
- `GET /api/analytics`
- `GET /api/action-center`
- `GET /api/localization`
- `GET /api/listings`
- `POST /api/listings`
- `PATCH /api/listings/{id}`
- `POST /api/listings/{id}/images`
- `GET /api/listings/{id}/validate`
- `GET /api/listings/{id}/quality`
- `POST /api/listings/{id}/publish`
- `GET /api/jobs`
- `POST /api/jobs/{id}/retry`
- `GET /api/platforms`
- `GET /api/diagnostics`
- `POST /api/accounts`
- `POST /api/templates`
- `GET /api/category-mappings`
- `POST /api/category-mappings`
- `GET /api/export`
- `POST /api/import`

Interactive API docs are available at `http://127.0.0.1:8000/docs`.

Listings include revision tracking. Editing a listing increments its `revision`, and publishing job idempotency includes user, listing, revision, platform, action type, account, and operation mode. Re-queuing the same listing revision returns the existing job; editing the listing allows a fresh platform package/job.

The listing editor also exposes an explicit regenerate package action. It creates a new listing revision before queueing, so the user can intentionally produce a fresh assisted package without implying automatic marketplace submission.

Category mappings let a user translate a master listing category into a platform-specific category. Validation and publishing jobs apply these mappings unless a platform-specific override already supplies a category. Listings also support bounded `category_attributes` for item-specific details such as vehicle mileage, furniture style, clothing size, or electronics accessories.

The listing editor includes a local quality assistant. It scores buyer-readiness, flags missing or weak fields, and offers deterministic title, description, and tag suggestions from the listing data already entered. It does not call an external AI service or invent product facts.

The dashboard includes local-first Insights from `GET /api/analytics`: inventory value, average price, listing quality, platform coverage, and job outcomes. These are derived from the authenticated user's local records and do not use an external analytics provider.

The dashboard also includes an owner-scoped onboarding/action center. Listing edits are debounced
and autosaved with visible pending, success, and retry states; the explicit Save action remains
available. Quality guidance identifies the deterministic local provider and confirms that no
listing data was transmitted externally.

List endpoints support bounded pagination with `limit` and `offset`. Core list endpoints also expose focused filtering/sorting parameters, such as `/api/listings?search=chair&status=draft&sort=-updated_at`. The Listings screen uses those query parameters for search, status filtering, sorting, and previous/next paging.

Data portability is available through Settings and the API. `GET /api/export` returns a JSON bundle with listings, platform override drafts, templates, category mappings, and sanitized platform account metadata. `POST /api/import` recreates that business data for the authenticated user. `DELETE /api/auth/me` removes the authenticated user's account, sessions, owned listings, jobs, templates, mappings, platform accounts, and uploaded image files. Password hashes, sessions, job history, platform secret references, and image binaries are not included in the JSON export.

Export, import, and account deletion write sanitized local audit events with aggregate counts only. Account deletion keeps a hashed-email audit record after the user row is removed.

API errors use a consistent envelope:

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

Every response includes `X-Request-ID`; callers may provide their own `X-Request-ID` header for traceability.

## Worker

Publishing jobs are persisted in the database. The worker command processes due queued jobs and can run independently from the web process:

```bash
python -m app.worker
```

Jobs with `next_retry_at` in the future remain queued until their retry time. This keeps assisted posting preparation and future official API publishing out of fragile blocking requests.

Operators can persistently pause or resume new job claims with `python -m app.operator_control`.
Use `python -m app.reconcile` for a check-only consistency audit and
`python -m app.support_bundle --output support-bundle.zip` for a sanitized diagnostic archive.

## Security and compliance

- No raw platform passwords are stored by the web app.
- New user passwords are hashed with Argon2.
- Older PBKDF2 hashes are still accepted and upgraded on successful login.
- Bearer sessions can be revoked with `POST /api/auth/logout`.
- Authentication is bearer-only: send tokens in the `Authorization` header. The app does not set session cookies.
- Failed login attempts are rate-limited per email/IP window.
- External calls are isolated behind adapter interfaces.
- The default integrations are assisted-only where official automation credentials are absent.
- Jobs are idempotent per listing/platform and include platform cooldowns.
- Use official APIs when converting an assisted adapter into a fully automated adapter.
- Do not bypass CAPTCHAs, anti-bot protections, login protections, payment prompts, or platform rate limits.

## Project phase documentation

- Product definition: `docs/PRODUCT_DEFINITION.md`
- Repository provenance: `docs/REPOSITORY_PROVENANCE.md`
- Platform reality review: `docs/PLATFORM_REALITY_REVIEW.md`
- Legacy script quarantine: `docs/LEGACY_SCRIPT_QUARANTINE.md`
- Rate limits: `docs/RATE_LIMITS.md`
- API usage audit: `docs/API_USAGE_AUDIT.md`
- UI action audit: `docs/UI_ACTION_AUDIT.md`
- Technical debt register: `docs/TECHNICAL_DEBT_REGISTER.md`
- Testing strategy: `docs/TESTING_STRATEGY.md`
- Browser and accessibility QA: `docs/BROWSER_ACCESSIBILITY_QA.md`
- Automated accessibility audit: `docs/ACCESSIBILITY_AUDIT.md`
- Operator runbook: `docs/OPERATOR_RUNBOOK.md`
- Product analytics local-first: `docs/PRODUCT_ANALYTICS_LOCAL_FIRST.md`
- SaaS readiness without billing: `docs/SAAS_READINESS.md`
- Requirements traceability: `docs/REQUIREMENTS_TRACEABILITY.md`
- Task graph and execution: `docs/TASK_GRAPH_AND_EXECUTION.md`
- Progressive stabilization gates: `docs/PROGRESSIVE_STABILIZATION_GATES.md`
- False completion prevention: `docs/FALSE_COMPLETION_PREVENTION.md`
- Autonomy-first design: `docs/AUTONOMY_FIRST_DESIGN.md`
- Workspaces optional review: `docs/WORKSPACES_OPTIONAL_REVIEW.md`
- Internationalization: `docs/INTERNATIONALIZATION.md`
- Product value review: `docs/PRODUCT_VALUE_REVIEW.md`
- Product realism review: `docs/PRODUCT_REALISM_REVIEW.md`
- Non-technical user simulation: `docs/NON_TECHNICAL_USER_SIMULATION.md`
- Fresh-clone dry run: `docs/FRESH_CLONE_DRY_RUN.md`
- Final no-excuses search: `docs/FINAL_NO_EXCUSES_SEARCH.md`
- Backup and restore: `docs/BACKUP_RESTORE.md`
- Official API credential checklist: `docs/OFFICIAL_API_CREDENTIAL_CHECKLIST.md`
- Auth deployment posture: `docs/AUTH_SECURITY_POSTURE.md`
- Performance and scale basics: `docs/PERFORMANCE_SCALE_BASICS.md`
- Release readiness: `docs/RELEASE_READINESS.md`
- Supply chain and dependencies: `docs/SUPPLY_CHAIN.md`
- State machines: `docs/STATE_MACHINES.md`
- Domain model: `docs/DOMAIN_MODEL.md`
- Acceptance tests: `docs/ACCEPTANCE_TESTS.md`
- Feature flags: `docs/FEATURE_FLAGS.md`
- Demo mode: `docs/DEMO_MODE.md`
- Fake provider lab: `docs/FAKE_PROVIDER_LAB.md`
- No mocks in production audit: `docs/NO_MOCKS_PRODUCTION_AUDIT.md`
- Privacy audit events: `docs/PRIVACY_AUDIT_EVENTS.md`
- Canonical 116-phase completion matrix: `docs/GOAL_COMPLETION_MATRIX.md`

## Production notes

- Set a strong `SECRET_KEY`.
- Use a managed database by changing `DATABASE_URL`.
- Place uploads on persistent storage.
- Put the app behind HTTPS.
- Restrict `CORS_ORIGINS`.
- Run Alembic migrations before production startup.
- Use `docker-compose.production.yml` only with a separately managed PostgreSQL database and persistent upload storage.
- Configure platform OAuth/API credentials only through environment variables or a proper secret manager.
- Keep the security headers middleware enabled. HTTPS deployments also receive HSTS.
