# Secondhand Platforms Autoposter

Secondhand Platforms Autoposter is a self-hosted listing workspace for preparing one secondhand-product listing for several marketplaces. A seller enters the item once, adds images, checks listing quality, creates platform-specific variations, and tracks the work needed to publish it.

> **Current status:** release candidate `1.0.0-rc.1`. The application is locally implemented and automatically verified, but it is **not approved for a final production launch** until the deployment, backup, accessibility, real-user, and acceptance evidence described below has been completed.

> **Important:** every marketplace adapter currently uses **assisted posting**. The app prepares copy-ready data and opens the appropriate marketplace workflow; the seller still signs in, handles verification or CAPTCHA prompts, reviews fees and options, and presses the marketplace's final submit button. The app does not claim automatic publication without official API proof or explicit user confirmation.

## Contents

- [Who this is for](#who-this-is-for)
- [What the application does](#what-the-application-does)
- [What it deliberately does not do](#what-it-deliberately-does-not-do)
- [How the workflow works](#how-the-workflow-works)
- [Marketplace support](#marketplace-support)
- [Ways to run the application](#ways-to-run-the-application)
- [Windows 11 standalone use](#windows-11-standalone-use)
- [Local development setup](#local-development-setup)
- [Docker setup](#docker-setup)
- [Access through ngrok](#access-through-ngrok)
- [HAI connector](#hai-connector)
- [Architecture](#architecture)
- [Data, storage, and privacy](#data-storage-and-privacy)
- [Configuration reference](#configuration-reference)
- [API reference](#api-reference)
- [Jobs and worker operation](#jobs-and-worker-operation)
- [Production deployment](#production-deployment)
- [Backups and recovery](#backups-and-recovery)
- [Security model and limitations](#security-model-and-limitations)
- [Verification and quality gates](#verification-and-quality-gates)
- [Operations and troubleshooting](#operations-and-troubleshooting)
- [Repository structure](#repository-structure)
- [Development and contribution guidance](#development-and-contribution-guidance)
- [Documentation map](#documentation-map)
- [Current launch blockers](#current-launch-blockers)
- [License and third-party services](#license-and-third-party-services)

## Who this is for

The primary user is a non-technical seller, volunteer, reseller, or small operator who needs to describe the same item on several secondhand marketplaces without repeatedly rebuilding the listing from scratch.

The repository is also intended for:

- developers who maintain the FastAPI service, browser interface, storage layer, or platform adapters;
- operators who deploy the API and worker, run migrations, monitor health, and manage backups;
- reviewers who need an evidence-based view of security, privacy, accessibility, marketplace boundaries, and release readiness;
- HAI integrators who need an owner-scoped, read-only listing feed.

No programming knowledge is required to use the browser interface after an operator has installed or deployed the application. Running from source, building the Windows executable, and deploying production infrastructure do require technical administration.

## What the application does

### Seller-facing capabilities

- Register, sign in, sign out, and delete an account.
- Create, edit, autosave, duplicate, archive, search, sort, filter, and page through listings.
- Store a reusable master listing with title, description, price, currency, condition, category, location, delivery choices, dimensions, weight, brand, model, colour, material, tags, notes, internal notes, and bounded category-specific attributes.
- Upload, reorder, view, and delete JPEG, PNG, GIF, or WebP images.
- Keep images private behind the owner's bearer session; normal API responses do not expose filesystem or S3 object paths.
- Detect duplicate images on the same listing by SHA-256 checksum.
- Create independent image objects when duplicating a listing, so deleting one copy does not break another.
- Select marketplaces and save platform-specific field overrides.
- Define reusable description templates and platform category mappings.
- Validate required fields before creating a posting package.
- Run a deterministic local quality assistant that flags weak or missing content and proposes edits without sending listing data to an external AI provider.
- Queue assisted posting packages, review job logs, retry eligible failures, and regenerate a package as a new listing revision.
- Record a marketplace URL and optional listing ID after the seller has manually confirmed publication.
- View an owner-scoped dashboard, onboarding steps, actionable reminders, inventory insights, listing quality, platform coverage, and job outcomes.
- Export and import supported business data as JSON or CSV, export locally stored images as ZIP, review privacy audit events, and delete owned data.
- Use the interface in English or Dutch.

### Developer and operator capabilities

- FastAPI OpenAPI documentation at `/docs` while the server is running.
- SQLAlchemy persistence with SQLite for local/standalone use and PostgreSQL for production.
- Alembic migrations with an explicit production migration service.
- A separate worker process with due-job claiming, idempotency, retry limits, platform cooldowns, stale-job recovery, and heartbeats.
- Persistent emergency pause/resume controls for worker job claiming.
- Local or S3-compatible image storage.
- Structured request IDs, security headers, JSON logging, diagnostics, reconciliation, and sanitized support bundles.
- Owner-scoped, expiring, revocable HAI connector tokens and an incremental change feed.
- Docker development and production definitions.
- A reproducible PyInstaller recipe for a single-file Windows executable.
- GitHub Actions verification, dependency auditing, pinned action revisions, and Dependabot updates.
- Automated release gates that refuse to describe the project as launch-ready while required external evidence is missing.

## What it deliberately does not do

The current product does **not**:

- log in to marketplaces on a user's behalf;
- store raw marketplace passwords;
- bypass CAPTCHA, two-factor authentication, anti-bot controls, rate limits, policy screens, or payment prompts;
- silently purchase featured placement or other paid services;
- automatically submit listings through browser automation;
- report an assisted job as published merely because a package was prepared;
- provide proven live marketplace publishing through an official API;
- register itself automatically inside a separate HAI deployment;
- use Gmail, Google Drive, analytics trackers, or an external generative-AI service;
- include billing, subscriptions, teams, or organisation workspaces;
- replace operator-level database, upload, and secret backups with a user export;
- prove production readiness solely because local tests pass.

Legacy Selenium scripts are retained under `legacy/` for historical/manual reference. They are isolated from normal application startup, excluded from the production dependency set, and must not be treated as the supported publishing implementation.

## How the workflow works

1. **Create an account.** Register with an email address, name, and password, or sign in to an existing account.
2. **Create one master listing.** Enter the item facts once instead of rewriting them per marketplace.
3. **Add images.** Files are validated for size, declared MIME type, detected signature, and safe storage name.
4. **Improve the listing.** Run the local quality assistant and decide whether to apply its deterministic suggestions.
5. **Choose marketplaces.** Add category mappings or description overrides when a platform needs different wording.
6. **Validate.** The app reports missing fields and platform-specific requirements before a package can look ready.
7. **Queue packages.** A background worker—or optional inline development path—creates an assisted package for each chosen platform.
8. **Complete the marketplace steps.** The seller opens the platform, signs in, reviews categories, delivery, fees, policies, and verification prompts, then submits deliberately.
9. **Record confirmed completion.** The seller adds the resulting marketplace URL and optional external listing ID. Only this explicit action may move an assisted job from `needs_user_action` to `published`.
10. **Monitor or export.** Review job history, analytics, audit activity, and portable exports from the dashboard.

Master listing status values are `draft`, `ready`, `published`, and `archived`. Normalised condition values are `new`, `as_new`, `good`, `used`, `fair`, `damaged`, `for_parts`, and `other`.

## Marketplace support

| Marketplace | Current mode | What the app prepares | What the seller still controls |
| --- | --- | --- | --- |
| Marktplaats | Assisted | Title, description, price, currency, condition, category, location, delivery/shipping details, item attributes, tags, and image filenames | Login, verification, category/payment choices, paid placement, and final submission |
| Koopplein | Assisted | Listing fields, category, location, delivery details, item attributes, tags, and image filenames | Account prompts, category and price-type confirmation, and final submission |
| Nextdoor | Assisted | Title, description, price, category, location, tags, and image filenames | Neighbourhood access, visibility choices, anti-abuse prompts, and final submission |
| eBay | Assisted; official-API candidate | Listing fields and an OAuth/secret-reference foundation for future work | Developer approval, OAuth token exchange, seller policies, shipping/payment/return settings, fees, and final submission |
| Tweedehands | Assisted/manual reference | Listing fields, delivery details, item attributes, tags, and image filenames | Account session, platform-rule compliance, and final submission |

Marketplace names and links identify destinations selected by the user. They do not imply partnership, endorsement, API approval, or permission to automate those services. See [Platform completion contracts](docs/PLATFORM_COMPLETION_CONTRACTS.md) and [Platform reality review](docs/PLATFORM_REALITY_REVIEW.md).

## Ways to run the application

| Route | Best for | Database | Worker | Notes |
| --- | --- | --- | --- | --- |
| Windows standalone | One operator on Windows 11 | Local SQLite | Started automatically | Builds a single executable; data stays under the user's local application-data folder |
| Python from source | Developers and local review | SQLite by default; PostgreSQL optional | Inline by default or separate process | Fastest path for development and debugging |
| Docker Compose | Repeatable local environments | SQLite by default; optional local PostgreSQL profile | Separate container | Edit `.env` to select PostgreSQL and disable inline processing when testing worker behaviour |
| Production Compose | A supplied staging/production host | External PostgreSQL required | Separate container | Migration-gated and requires persistent uploads plus production secrets |
| ngrok over standalone | Temporary remote/private review of one Windows instance | Local SQLite | Started automatically | Requires an authenticated ngrok installation and an available tunnel/domain |

## Windows 11 standalone use

The repository contains a PyInstaller build recipe; the generated executable is intentionally ignored by Git and is not a source file. Build it on the Windows machine where it will be reviewed:

```powershell
.\scripts\build-windows.ps1
```

The build script uses an isolated `.venv-build` environment and expects Python 3.13 for packaging. It creates:

- `dist\SecondhandAutoposter.exe`
- `dist\SecondhandAutoposter.exe.sha256`

Run the executable by double-clicking it or from PowerShell:

```powershell
.\dist\SecondhandAutoposter.exe
```

The launcher:

- binds only to `127.0.0.1`/`localhost`;
- creates or reuses a strong local secret;
- stores data in `%LOCALAPPDATA%\SecondhandAutoposter` by default;
- upgrades the local database to Alembic head before serving;
- starts the API and worker as separate processes;
- opens the browser after the health endpoint responds;
- trusts forwarded proxy headers only from localhost.

To choose another controlled data/backup location:

```powershell
$env:AUTOPOSTER_DATA_DIR = "D:\AutoposterData"
.\dist\SecondhandAutoposter.exe
```

The standalone profile is designed for one Windows operator using SQLite and local image storage. It is not a substitute for a multi-user PostgreSQL production deployment. See [Windows standalone and ngrok](docs/WINDOWS_STANDALONE.md).

## Local development setup

### Requirements

- Python 3.12 is the supported application/CI target.
- Git.
- A modern browser.
- Optional: Docker Desktop, PostgreSQL, ngrok, and Python 3.13 for Windows packaging.

### Windows PowerShell

```powershell
git clone https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter.git
Set-Location 023-Secondhand-platforms-autoposter
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

### Linux or macOS

```bash
git clone https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter.git
cd 023-Secondhand-platforms-autoposter
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

`.env.example` enables development conveniences, including automatic table creation and inline job processing. Run Alembic anyway when validating migrations, and never copy those unsafe conveniences into production.

## Docker setup

### Local SQLite stack

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The API is available at <http://127.0.0.1:8000>. The `./data` directory is mounted into both API and worker containers. With the default `JOB_PROCESS_INLINE=true`, jobs are processed during the API request and the worker will normally remain idle. Set `JOB_PROCESS_INLINE=false` in `.env` to exercise the separate worker.

### Local PostgreSQL profile

Set this value in `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://autoposter:autoposter@postgres:5432/autoposter
AUTO_CREATE_TABLES=false
JOB_PROCESS_INLINE=false
```

Then start the optional database profile and migrate it:

```powershell
docker compose --profile postgres up --build -d
docker compose exec autoposter alembic upgrade head
```

The local Compose PostgreSQL password is a development value. Do not reuse it outside an isolated local environment.

## Access through ngrok

After installing and authenticating ngrok, either build the portable executable or prepare the Python environment, then run:

```powershell
.\scripts\start-ngrok.ps1
```

For a reserved domain:

```powershell
.\scripts\start-ngrok.ps1 -Domain "your-domain.ngrok.app"
```

For a non-interactive health drill that stops its own test processes:

```powershell
.\scripts\start-ngrok.ps1 -VerifyOnly
```

The script disables ngrok's local inspection API, reads the public URL only from the JSON log of the process it started, restricts CORS to that URL, uses bearer authentication, waits for local API/worker health, verifies public HTTPS health, and cleans up only its own processes.

If ngrok reports `ERR_NGROK_334`, that endpoint is already online. Stop the conflicting endpoint in the ngrok account or provide another reserved domain/tunnel slot. Do not enable pooling as an improvised fix: it may route one public address to unrelated local services.

Treat an ngrok URL as internet exposure. Use a strong account password, do not enable development auto-login, revoke the tunnel after review, and do not describe a temporary standalone tunnel as a production deployment.

## HAI connector

The application exposes an app-side, owner-scoped, **read-only** connector that HAI can consume without receiving the user's normal login token.

### Connect

1. Sign in to Secondhand Autoposter.
2. Open **Settings** and create a named HAI token with an expiry period.
3. Copy the `hai_...` value immediately. Only its SHA-256 hash is retained, so the plaintext token cannot be shown again.
4. In HAI, configure an HTTP source using the Autoposter base URL and `Authorization: Bearer hai_...`.
5. Read `/.well-known/hai-connector.json`, verify with `GET /api/hai/status`, and pull `GET /api/hai/records`.

Example with a placeholder token:

```bash
curl -H "Authorization: Bearer hai_REPLACE_ME" \
  "https://autoposter.example/api/hai/records?limit=100"
```

The feed uses opaque cursors, returns listing upserts, and emits deletion tombstones. It excludes internal notes, credentials, secret references, and image binaries. Connector tokens have only `hai:read`, expire, can be revoked, and cannot edit, delete, publish, or mark a marketplace job complete.

This repository provides the Autoposter protocol and token/feed implementation. An administrator must still register or configure the source in the target HAI installation. See [HAI connector](docs/HAI_CONNECTOR.md).

## Architecture

```mermaid
flowchart LR
    U["Seller in browser"] -->|"Bearer-authenticated HTTPS/API"| A["FastAPI application"]
    A --> DB["SQLite local / PostgreSQL production"]
    A --> FS["Private local or S3-compatible image storage"]
    A --> Q["Persistent publishing-job queue"]
    W["Worker process"] --> Q
    W --> P["Assisted platform adapters"]
    P --> M["Copy-ready package + marketplace link"]
    M -->|"Seller signs in and submits"| X["External marketplace"]
    H["HAI"] -->|"Expiring hai:read token"| R["Read-only incremental connector"]
    R --> A
```

### Main components

| Component | Responsibility |
| --- | --- |
| `public/` | Dependency-free HTML, CSS, and JavaScript dashboard |
| `app/main.py` | FastAPI construction, middleware, CORS, routes, and static frontend mount |
| `app/api.py` | Listings, images, platform mappings, jobs, accounts, templates, category mappings, audit events, and import/export routes |
| `app/routes/auth.py` | Registration, login, logout, current user, and account deletion |
| `app/routes/system.py` | Health, worker status, diagnostics, metrics, localisation, analytics, action centre, dashboard, and account readiness |
| `app/routes/hai.py` | HAI discovery, connector-token lifecycle, status, and incremental read feed |
| `app/models.py` | SQLAlchemy domain and operational models |
| `app/storage.py` | Validated local and S3-compatible image persistence/retrieval |
| `app/adapters/` | Honest marketplace capability, validation, mapping, and assisted-package contracts |
| `app/services/` | Jobs, quality, analytics, audit, OAuth, localisation, worker health, and operator controls |
| `app/worker.py` | Due-job processing loop and heartbeat recording |
| `app/launcher.py` | Windows standalone migration, API, worker, browser, and local-data lifecycle |
| `migrations/` | Alembic schema history |
| `tests/` | API, ownership, state, frontend-contract, deployment, migration, accessibility, and release-gate coverage |

### Request and data boundaries

- Browser requests use opaque bearer sessions in the `Authorization` header; cookie sessions are not enabled.
- User-owned reads and writes are filtered by authenticated owner ID.
- Image bytes are never served by a public directory mount.
- API requests write persistent jobs; a worker claims and processes due work.
- Assisted adapters produce `needs_user_action`, not invented marketplace success.
- HAI uses a separate purpose-limited token and can only read the owner's listing feed.

## Data, storage, and privacy

### Core stored records

- users, bearer sessions, and persistent login-throttle state;
- listings, listing revisions/drafts, images, templates, and category mappings;
- platform-account metadata and one-use OAuth state;
- platform listing mappings;
- publishing jobs, logs, attempts, retry/cooldown state, and worker heartbeats;
- privacy audit events and persistent operator controls;
- HAI connector token hashes and listing-change cursors.

### Image handling

- Maximum size is controlled by `MAX_UPLOAD_SIZE_MB` (10 MB by default).
- The declared MIME type and detected byte signature are checked.
- Filenames are sanitised and stored objects receive UUID-suffixed names.
- Duplicate images on one listing are ignored by checksum.
- Normal listing JSON contains image metadata but not raw storage paths.
- `GET /api/listings/{listing_id}/images/{image_id}/content` checks ownership before returning bytes.
- Local and S3-compatible backends are supported.
- S3-backed images can be read by the authenticated application, but the built-in image ZIP exporter currently records them as `object_storage_not_exportable`; use provider tooling for a complete S3 bucket export.

### Portability and deletion

- JSON export contains supported listing, platform-draft, template, category-mapping, and sanitised account data.
- CSV import/export supports the documented master-listing columns.
- Image ZIP export contains locally stored binaries plus a manifest.
- Password hashes, sessions, raw OAuth tokens, platform passwords, job history, and image binaries are excluded from the JSON export.
- Account deletion removes owned sessions, listings, jobs, templates, mappings, accounts, connector tokens, and uploaded files.
- A sanitised audit record with a hashed email may remain for operational accountability until `AUDIT_RETENTION_DAYS` purges it. Production privacy notices must disclose that retention.

User exports are portability tools, not complete operational backups. See [Image storage](docs/IMAGE_STORAGE.md), [Privacy audit events](docs/PRIVACY_AUDIT_EVENTS.md), and [Backup/restore](docs/BACKUP_RESTORE.md).

## Configuration reference

Start from `.env.example` for development or `.env.production.example` for deployment. Never commit a completed secrets file.

### Application and database

| Variable | Default/example | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Secondhand Platforms Autoposter` | Display/service name |
| `APP_ENV` | `development` | `development`, `test`, `standalone`, or `production` |
| `SECRET_KEY` | insecure placeholder | Session/OAuth signing secret; production/standalone require a strong non-default value of at least 32 characters |
| `DATABASE_URL` | `sqlite:///./data/autoposter.db` | SQLAlchemy URL; production requires PostgreSQL (`postgresql+psycopg://...`) |
| `DB_POOL_SIZE` | `5` | PostgreSQL persistent pool size |
| `DB_MAX_OVERFLOW` | `5` | PostgreSQL overflow connections |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | Pool checkout timeout |
| `DB_POOL_RECYCLE_SECONDS` | `1800` | Connection recycle interval |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8000` | Base URL for source links and diagnostics; production requires HTTPS |
| `CORS_ORIGINS` | `*` in development | Comma-separated absolute origins; wildcard is rejected in production/standalone |
| `AUTH_TRANSPORT` | `bearer` | Only supported session transport |
| `AUTO_CREATE_TABLES` | `true` in development | Development convenience; must be `false` in production/standalone so Alembic owns schema changes |

### Storage and uploads

| Variable | Default | Purpose |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `UPLOAD_DIR` | `./data/uploads` | Local image directory |
| `MAX_UPLOAD_SIZE_MB` | `10` | Per-image size limit |
| `ALLOWED_IMAGE_TYPES` | JPEG, PNG, GIF, WebP | Comma-separated accepted MIME types |
| `S3_BUCKET` | empty | Required when `STORAGE_BACKEND=s3` |
| `S3_REGION` | empty | Optional S3 region |
| `S3_ENDPOINT_URL` | empty | Optional S3-compatible provider endpoint |
| `S3_KEY_PREFIX` | `uploads` | Bucket key prefix |
| `TOKEN_SECRET_DIR` | `./data/secrets` | Local secret-reference storage used by the eBay OAuth foundation |

### Authentication, sessions, and limits

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEV_AUTO_LOGIN` | `false` | Reserved development-only shortcut; rejected in production/standalone |
| `SESSION_EXPIRE_HOURS` | `168` | Bearer-session lifetime |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | Failed attempts per email/IP window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `300` | Login throttle window |
| `API_RATE_LIMIT_REQUESTS` | `300` | Requests per bearer token or client IP per process/window |
| `API_RATE_LIMIT_WINDOW_SECONDS` | `60` | API throttle window |
| `AUDIT_RETENTION_DAYS` | `365` | Sanitised audit-event retention; `0` disables automatic age-based purging |

The built-in API limiter is process-local. A multi-process or internet-facing deployment still needs independently verified edge/proxy/CDN/WAF rate limiting.

### Worker and platform processing

| Variable | Default | Purpose |
| --- | --- | --- |
| `JOB_PROCESS_INLINE` | `true` | Development convenience; production normally sets `false` and runs the worker |
| `JOB_WORKER_POLL_SECONDS` | `5` | Worker polling interval |
| `JOB_WORKER_BATCH_SIZE` | `10` | Maximum due jobs per pass |
| `WORKER_HEARTBEAT_TIMEOUT_SECONDS` | `30` | Age after which worker health is stale |
| `JOB_STALE_RUNNING_SECONDS` | `1800` | Age after which an interrupted running job returns to the queue |
| `PLATFORM_RATE_LIMIT_SECONDS` | `60` | Default cooldown between attempts per platform |
| `PLATFORM_RATE_LIMIT_OVERRIDES` | empty | Comma-separated overrides, such as `marktplaats=120,ebay=300` |

### Local guidance, language, and logging

| Variable | Default | Purpose |
| --- | --- | --- |
| `SUGGESTION_PROVIDER` | `deterministic_local` | Only implemented quality provider; listing content is not sent externally |
| `DEFAULT_LOCALE` | `en` | Default locale |
| `SUPPORTED_LOCALES` | `en,nl` | Comma-separated locale contract |
| `LOG_LEVEL` | `INFO` | Application log level |
| `LOG_FORMAT` | `text` | `text` locally or `json` for aggregation |

### Optional eBay OAuth foundation

| Variable | Default | Purpose |
| --- | --- | --- |
| `EBAY_OAUTH_CLIENT_ID` | empty | eBay developer application ID |
| `EBAY_OAUTH_CLIENT_SECRET` | empty | Secret-manager supplied client secret for token exchange |
| `EBAY_OAUTH_REDIRECT_URI` | empty | Registered callback/RuName |
| `EBAY_OAUTH_ENVIRONMENT` | `sandbox` | `sandbox` or `production` |
| `EBAY_OAUTH_SCOPES` | inventory/account scopes | Requested OAuth scopes |
| `EBAY_OAUTH_STATE_TTL_SECONDS` | `600` | One-use state lifetime |
| `EBAY_TOKEN_SECRET_REF_PREFIX` | `secret://ebay/oauth` | Reference prefix for stored tokens |

These variables enable only the consent/token foundation. They do not change the eBay adapter from assisted mode or prove official API publishing.

### Launcher and Compose-only values

| Variable | Used by | Purpose |
| --- | --- | --- |
| `AUTOPOSTER_DATA_DIR` | Windows launcher | Overrides `%LOCALAPPDATA%\SecondhandAutoposter` |
| `APP_PORT` | Production Compose | Host port mapped to container port 8000 |
| `UPLOAD_VOLUME` | Production Compose | Required persistent host path/managed volume mounted at `/app/data/uploads` |

The legacy marketplace URL, LastPass, and Selenium variables in `.env.example` are for quarantined scripts only and are not loaded by the supported web workflow.

## API reference

All product endpoints are under `/api` unless noted. Authenticated calls use `Authorization: Bearer <token>`. Interactive OpenAPI documentation is available at `/docs`.

### Public and authentication endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness, server time, and version |
| `GET` | `/api/worker-status` | Worker heartbeat and operator-pause readiness |
| `GET` | `/api/localization` | Supported locale metadata |
| `GET` | `/.well-known/hai-connector.json` | HAI read-only discovery contract |
| `POST` | `/api/auth/register` | Create a user and bearer session |
| `POST` | `/api/auth/login` | Create a bearer session |
| `POST` | `/api/auth/logout` | Revoke the current session |
| `GET` | `/api/auth/me` | Read the current user |
| `DELETE` | `/api/auth/me` | Delete the current account and owned data |

### Listings, images, and preparation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`, `POST` | `/api/listings` | Search/page owned listings or create one |
| `GET`, `PATCH`, `DELETE` | `/api/listings/{listing_id}` | Read, update, or delete one owned listing |
| `POST` | `/api/listings/{listing_id}/duplicate` | Duplicate listing data and image objects |
| `POST` | `/api/listings/{listing_id}/images` | Upload a validated image |
| `GET` | `/api/listings/{listing_id}/images/{image_id}/content` | Read private image content |
| `PATCH` | `/api/listings/{listing_id}/images/order` | Reorder images |
| `DELETE` | `/api/listings/{listing_id}/images/{image_id}` | Delete an image |
| `POST` | `/api/listings/{listing_id}/platforms` | Save platform selection/overrides |
| `GET` | `/api/listings/{listing_id}/validate` | Validate one or all platforms |
| `GET` | `/api/listings/{listing_id}/quality` | Run deterministic local quality guidance |
| `POST` | `/api/listings/{listing_id}/publish` | Queue assisted packages; optionally force a new revision |
| `GET` | `/api/platforms` | Platform capabilities and compliance boundaries |

### Jobs, accounts, and reusable configuration

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/jobs` and `/api/jobs/{job_id}` | Page jobs or inspect one job and its logs |
| `POST` | `/api/jobs/{job_id}/retry` | Retry an eligible job |
| `POST` | `/api/jobs/{job_id}/manual-completion` | Record user-confirmed marketplace completion |
| `GET`, `POST` | `/api/accounts` | Page or create platform-account metadata |
| `PATCH`, `DELETE` | `/api/accounts/{account_id}` | Update or remove an owned account record |
| `POST` | `/api/accounts/ebay/oauth/start` | Begin configured eBay OAuth consent |
| `GET` | `/api/accounts/ebay/oauth/callback` | Consume one-use OAuth state and store a secret reference |
| `GET`, `POST` | `/api/templates` | Page or create description templates |
| `PATCH`, `DELETE` | `/api/templates/{template_id}` | Update or remove a template |
| `GET`, `POST` | `/api/category-mappings` | Page or create/upsert platform category mappings |
| `PATCH`, `DELETE` | `/api/category-mappings/{mapping_id}` | Update or remove a mapping |

### Dashboard, privacy, portability, and HAI

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/dashboard` | Combined owner-scoped analytics, action centre, recent listings, and latest jobs |
| `GET` | `/api/analytics` | Owner-scoped local analytics |
| `GET` | `/api/action-center` | Onboarding and exception-driven actions |
| `GET` | `/api/account/readiness` | Personal-account readiness and usage |
| `GET` | `/api/diagnostics` | Authenticated doctor summary plus owner counts |
| `GET` | `/api/metrics` | Authenticated owner-scoped operational counts |
| `GET` | `/api/audit-events` | Page sanitised privacy events |
| `GET`, `POST` | `/api/export`, `/api/import` | Portable JSON export/import |
| `GET`, `POST` | `/api/export/listings.csv`, `/api/import/listings.csv` | Listing CSV export/import |
| `GET` | `/api/export/images.zip` | Local image archive and manifest |
| `GET`, `POST` | `/api/hai/tokens` | List token metadata or create a one-time plaintext HAI token |
| `DELETE` | `/api/hai/tokens/{token_id}` | Revoke a connector token |
| `GET` | `/api/hai/status` | Verify a `hai_...` token |
| `GET` | `/api/hai/records` | Pull owner-scoped incremental listing changes |

List endpoints use bounded `limit`/`offset` pagination and return `X-Total-Count`, `X-Limit`, and `X-Offset`. See [API reference](docs/API_REFERENCE.md) for payload and error-shape details.

## Jobs and worker operation

For normal production-style operation, set `JOB_PROCESS_INLINE=false` and run:

```powershell
python -m app.worker
```

Job states are:

- `queued`: waiting for a worker or a future cooldown time;
- `running`: claimed for adapter processing;
- `needs_user_action`: a valid assisted package exists and the seller must continue on the marketplace;
- `published`: an official API eventually confirmed publication, or the seller explicitly recorded manual completion;
- `failed`: processing failed and may be eligible for retry;
- `skipped`: intentionally not processed.

Claims use a conditional queued-to-running update; PostgreSQL query construction includes `FOR UPDATE SKIP LOCKED` for concurrent workers. Idempotency keys include the owner, listing revision, platform, account, action, and operation mode. Platform cooldowns can return work to `queued` without counting an adapter attempt. Stale `running` jobs are recovered after `JOB_STALE_RUNNING_SECONDS`.

Inline requests must claim due queued work; they do not execute a job already claimed by a worker or bypass its scheduled backoff. Retrying an already queued/running job leaves it unchanged. Retrying terminal work uses a conditional version check and, when `JOB_PROCESS_INLINE=false`, leaves execution to the separate worker. A fresh claim clears the previous attempt's start/finish timestamps so it is not immediately recovered as stale.

Automated checks exercise four concurrent database sessions on SQLite and migrated PostgreSQL, with 24 jobs per scenario and one attempt per job. These checks are not a guarantee of exactly-once external publication: crash recovery during external calls, long-running jobs exceeding the stale timeout, target-environment load, and provider idempotency require separate proof. Current marketplace adapters still prepare local assisted packages only.

### Emergency controls

```powershell
python -m app.operator_control status
python -m app.operator_control pause --reason "Investigating duplicate-post risk" --actor "operator-name"
python -m app.operator_control resume --actor "operator-name"
```

Pausing prevents new claims; it does not terminate an adapter call already in progress. See [State machines](docs/STATE_MACHINES.md) and [Operator runbook](docs/OPERATOR_RUNBOOK.md).

## Production deployment

Production Compose deliberately does **not** bundle a database. Supply a managed or separately operated PostgreSQL service, durable upload storage, and secret-manager-backed values.

1. Copy `.env.production.example` to `.env.production` outside version control.
2. Replace every placeholder, particularly `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_BASE_URL`, and `CORS_ORIGINS`.
3. Choose private S3-compatible storage or a persistent local upload volume.
4. Back up the target database and uploads before migration.
5. Start the migration-gated stack.

```powershell
Copy-Item .env.production.example .env.production
$env:UPLOAD_VOLUME = "D:\PersistentData\autoposter-uploads"
docker compose -f docker-compose.production.yml up --build -d
```

The `migrate` service must complete `alembic upgrade head` before the API and worker start. Required production posture includes:

- `APP_ENV=production`;
- a strong non-default `SECRET_KEY` of at least 32 characters;
- a PostgreSQL `DATABASE_URL`;
- an HTTPS `PUBLIC_BASE_URL`;
- explicit `CORS_ORIGINS` without `*`;
- `AUTH_TRANSPORT=bearer`;
- `DEV_AUTO_LOGIN=false`;
- `AUTO_CREATE_TABLES=false`;
- normally `JOB_PROCESS_INLINE=false` with a healthy worker;
- writable, persistent, private, and backed-up uploads;
- production-appropriate JSON logging and independently verified edge rate limits.

Startup rejects unsafe production values rather than silently falling back to development behaviour.

After deployment, record the exact commit, environment, URL, migration head, API/worker health, backup/restore result, edge policy, accessibility evidence, accepted risks, and final decision in [Release evidence record](docs/RELEASE_EVIDENCE_RECORD.md).

## Backups and recovery

A complete operator backup includes:

- the PostgreSQL database or standalone SQLite database;
- the local upload directory or the complete private S3 bucket/prefix;
- the deployed Git commit and Alembic revision;
- environment/secret references without copying plaintext secrets into normal logs.

Minimum documented cadence is daily database/uploads backup, an additional pre-migration backup, configuration-reference capture after deployment/rotation, and a monthly restore test.

Restore in this order: stop worker and API, restore database, restore images, deploy a schema-compatible commit, run `alembic upgrade head`, run the doctor, start the API, then start the worker. Keep the worker stopped whenever duplicate external action is a concern.

User JSON/CSV/image exports do not contain the full operational history and are not a disaster-recovery substitute. Follow [Backup, restore, and disaster recovery](docs/BACKUP_RESTORE.md).

## Security model and limitations

### Implemented controls

- Argon2 password hashing; successful login upgrades supported older PBKDF2 hashes.
- Opaque session and HAI tokens stored as hashes, with expiry and revocation.
- Owner filtering and dedicated cross-user isolation tests.
- Bearer-only authentication; the app does not set session cookies.
- Failed-login throttling and API request throttling.
- Request IDs, structured error envelopes, sanitised logs, audit events, and support bundles.
- Content Security Policy, framing denial, MIME sniffing prevention, referrer/permissions policy, and HSTS on HTTPS deployments.
- Upload size, signature, MIME, filename, path, and ownership controls.
- Private S3 guidance; no public upload mount.
- Idempotent jobs, bounded attempts, cooldown handling, and an operator emergency stop.
- Secret references and configuration-presence booleans instead of token disclosure.
- Non-root, digest-pinned production container and minimal runtime dependencies.
- Pinned GitHub Actions, least-privilege workflow permissions, dependency audit, and Dependabot.
- Production startup validation for database, CORS, HTTPS, secrets, storage, auth, flags, worker limits, upload limits, locales, logging, and OAuth configuration.

### Residual risks and deployment responsibilities

- The browser stores its bearer token in local storage, so same-origin script compromise could expose it; keep the CSP strict and avoid unreviewed third-party JavaScript.
- The built-in API rate limiter is in-memory and per process; internet deployments need edge/proxy enforcement.
- File validation is not malware scanning or image transcoding; operators may need scanning according to their threat model.
- Private S3 bucket policy, encryption, lifecycle rules, region, retention, backups, and service agreements belong to the deployment owner.
- Production secret-manager, rotation, monitoring, alerting, restore, WAF/CDN, and incident-response proof cannot be supplied by source code alone.
- Future official API adapters require provider approval, sandbox/live proof, quota handling, idempotency, ambiguous-outcome reconciliation, and legal/terms review.

Review [Security and privacy](docs/SECURITY.md), [Auth posture](docs/AUTH_SECURITY_POSTURE.md), [Red-team review](docs/RED_TEAM_REVIEW.md), and [Adversarial test report](docs/ADVERSARIAL_TEST_REPORT.md).

## Verification and quality gates

Install development dependencies, then run the complete local gate:

```powershell
python scripts\verify.py
```

The gate runs:

1. Ruff over `app`, `tests`, `migrations`, and `scripts`;
2. Python bytecode compilation;
3. the complete pytest suite;
4. `python -m app.doctor --json`.

The current suite contains 253 tests spanning API behaviour, authentication, owner isolation, uploads, storage, listing revisions, adapters, platform contracts, job states, rate limits, concurrent worker claims/retries/health, migrations, deployment configuration, bounded dashboard reads, HAI, frontend state/contracts, accessibility structure, browser workflows, data portability, diagnostics, release gates, and false-completion prevention.

Pytest creates a separate database, upload directory, and secret directory for each process before importing the application. It ignores inherited deployment/storage values and removes its own fixtures after a successful run; failed fixtures remain under `.tmp/test-runs/` for diagnosis. See [Testing strategy](docs/TESTING_STRATEGY.md) for the isolation contract and explicit PostgreSQL integration checks.

GitHub's `postgres-workers` job also runs the 11 job-safety checks against a disposable PostgreSQL 16 service. Each case migrates its own newly created schema to Alembic head and removes that schema afterward. This is CI integration evidence, not evidence of a deployed production database.

Additional checks:

```powershell
python scripts\audit_dependencies.py
python -m alembic current
python -m app.reconcile
python scripts\release_gate.py --json
python scripts\final_response_check.py --json
```

GitHub Actions runs the verification gate on pushes and pull requests to `main`. The supply-chain workflow audits runtime requirements on pushes, pull requests, a weekly schedule, and manual dispatch.

`release_gate.py` and `final_response_check.py` are expected to return a non-zero blocked result until real deployment, walkthrough, accessibility, and acceptance records are complete. That is a truthful release control, not an automated-test failure.

For the latest recorded evidence, see [Final verification report](docs/FINAL_VERIFICATION_REPORT.md). Browser and accessibility records must be refreshed after UI-affecting changes; static or scripted checks do not replace a real keyboard, zoom, and screen-reader walkthrough.

## Operations and troubleshooting

### Health and diagnostics

```powershell
python -m app.doctor
python -m app.doctor --json
python -m app.reconcile
python -m app.support_bundle --output .tmp\autoposter-support.zip
```

- `GET /api/health` is the public liveness endpoint.
- `GET /api/worker-status` reports heartbeat freshness and pause state.
- `/api/diagnostics` and `/api/metrics` require an authenticated user and return owner-scoped counts.
- The support bundle contains sanitised runtime/configuration summaries, doctor output, operator state, and job-status counts—not listing content, user emails, raw database URLs, tokens, or secret values.

### Common symptoms

| Symptom | Meaning | Safe response |
| --- | --- | --- |
| Registration rejects input | Email or password failed schema validation | Use a valid deliverable-format email and at least eight password characters |
| Validation lists missing fields/images | The package is intentionally not ready | Correct each item, save, and validate again |
| Job is `needs_user_action` | The assisted package is ready | Open the platform, complete it deliberately, then record the result |
| Worker is unhealthy | No recent heartbeat | Inspect worker logs, environment, database reachability, migration head, and pause state |
| Worker is paused | Persistent emergency stop is active | Inspect the recorded reason; resume only after the incident is resolved |
| Autosave failed | Visible form changes were not persisted | Keep the page open, inspect the request ID/connectivity, and use **Save** to retry |
| Migration mismatch | Database is behind Alembic head | Back up first, stop the worker, and run `alembic upgrade head` |
| ngrok reports `ERR_NGROK_334` | The requested endpoint is already online | Stop the conflicting endpoint or allocate another domain; do not pool unrelated services |
| Image metadata exists but bytes do not load | Storage object/path is missing or inaccessible | Stop destructive cleanup, inspect storage credentials/mounts, and reconcile against backups |

See [Troubleshooting](docs/TROUBLESHOOTING.md) for the maintained error catalogue.

## Repository structure

```text
.
├── app/                         FastAPI application, domain, services, adapters, worker
│   ├── adapters/                Marketplace contracts and assisted implementations
│   ├── routes/                  Auth, system, and HAI route modules
│   └── services/                Jobs, quality, analytics, audit, OAuth, and operations
├── public/                      Browser UI (plain HTML, CSS, JavaScript)
├── migrations/                 Alembic migrations
├── tests/                      Automated product, security, UI-contract, and release tests
├── scripts/                    Verification, browser evidence, release gates, Windows/ngrok tools
├── packaging/                  PyInstaller specification
├── docs/                       Product, technical, operational, security, and acceptance records
├── legacy/                     Quarantined historical Selenium/manual scripts
├── Dockerfile                  Non-root application image
├── docker-compose.yml          Local API, worker, and optional PostgreSQL
├── docker-compose.production.yml  Migration-gated API and worker using external PostgreSQL
├── requirements.txt            Production runtime dependencies
├── requirements-dev.txt        Runtime plus pytest/Ruff
└── requirements-build.txt      Runtime plus PyInstaller
```

## Development and contribution guidance

1. Read [Product definition](docs/PRODUCT_DEFINITION.md), [Architecture](docs/ARCHITECTURE.md), and [Platform completion contracts](docs/PLATFORM_COMPLETION_CONTRACTS.md).
2. Create a branch; do not work directly on `main`.
3. Preserve assisted/manual boundaries unless an official integration has provider approval and real proof.
4. Add migrations for schema changes; never rely on production auto-create.
5. Add owner-isolation tests for every new owner-controlled resource.
6. Add tests for error states, idempotency, retries, and truthful completion language.
7. Keep external actions review-gated and fail closed when credentials/configuration are incomplete.
8. Run `python scripts/verify.py` and relevant browser/security checks.
9. Update documentation and release evidence without replacing missing external proof with assumptions.

### Adding a marketplace adapter

Implement the `PlatformAdapter` contract under `app/adapters/`, register the adapter in `app/adapters/registry.py`, expose honest `PlatformCapabilities`, and test validation, mapping, categories, warnings, status transitions, and incomplete inputs.

An assisted adapter must return `needs_user_action`. Changing to `official_api` requires real OAuth/credential setup, sandbox and live provider tests, quota/backoff handling, idempotency, ambiguous-outcome reconciliation, marketplace compliance review, and proof that the API—not a mock or the user—confirmed publication.

### Dependency boundaries

- Add runtime packages to `requirements.txt` only when the shipped app needs them.
- Put test/lint tooling in `requirements-dev.txt`.
- Put Windows packaging tooling in `requirements-build.txt`.
- Keep quarantined browser-automation dependencies in `requirements-legacy.txt`.
- Do not add a frontend package manager unless the static UI genuinely requires a reviewed build pipeline.

## Documentation map

### Start here

- [User guide](docs/USER_GUIDE.md) — seller workflow and UI concepts.
- [Product definition](docs/PRODUCT_DEFINITION.md) — scope, users, supported states, and non-goals.
- [Architecture](docs/ARCHITECTURE.md) — backend boundaries and data flow.
- [API reference](docs/API_REFERENCE.md) — route-level contract.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common symptoms and safe recovery.

### Installation and operation

- [Windows standalone and ngrok](docs/WINDOWS_STANDALONE.md)
- [Operator runbook](docs/OPERATOR_RUNBOOK.md)
- [Backup, restore, and disaster recovery](docs/BACKUP_RESTORE.md)
- [Image storage](docs/IMAGE_STORAGE.md)
- [Performance and scale basics](docs/PERFORMANCE_SCALE_BASICS.md)
- [Rate limits](docs/RATE_LIMITS.md)
- [HAI connector](docs/HAI_CONNECTOR.md)

### Security, privacy, and integration boundaries

- [Security and privacy](docs/SECURITY.md)
- [Authentication security posture](docs/AUTH_SECURITY_POSTURE.md)
- [Privacy audit events](docs/PRIVACY_AUDIT_EVENTS.md)
- [Supply chain](docs/SUPPLY_CHAIN.md)
- [Official API credential checklist](docs/OFFICIAL_API_CREDENTIAL_CHECKLIST.md)
- [No mocks in production audit](docs/NO_MOCKS_PRODUCTION_AUDIT.md)
- [Legacy script quarantine](docs/LEGACY_SCRIPT_QUARANTINE.md)
- [License and third-party services](docs/LICENSE_AND_THIRD_PARTY_SERVICES.md)

### Verification and release governance

- [Testing strategy](docs/TESTING_STRATEGY.md)
- [Browser and accessibility QA](docs/BROWSER_ACCESSIBILITY_QA.md)
- [Final verification report](docs/FINAL_VERIFICATION_REPORT.md)
- [Release readiness](docs/RELEASE_READINESS.md)
- [Release evidence record](docs/RELEASE_EVIDENCE_RECORD.md)
- [Non-technical user walkthrough record](docs/NON_TECHNICAL_USER_WALKTHROUGH_RECORD.md)
- [Final acceptance record](docs/FINAL_ACCEPTANCE_RECORD.md)
- [Goal completion matrix](docs/GOAL_COMPLETION_MATRIX.md)
- [Requirements traceability](docs/REQUIREMENTS_TRACEABILITY.md)

The `docs/` directory also contains detailed audit history, design reviews, task graphs, UI reviews, feature flags, state machines, roadmaps, and evidence templates. Those files preserve review provenance; this README is the orientation layer, not a replacement for the authoritative records.

## Current launch blockers

The codebase can be installed and reviewed locally, but a final client production decision still requires evidence that cannot honestly be manufactured in the repository:

- staging/production deployment access or complete deployment details;
- the target PostgreSQL `DATABASE_URL` and permission to run Alembic;
- proof that the target database is at the expected migration head;
- confirmed production `APP_ENV`, strong secret, HTTPS URL, restrictive CORS, bearer auth, and upload/storage settings;
- deployed API and worker health evidence;
- a successful backup and restore test or formally accepted plan;
- edge/proxy/CDN/WAF rate-limit evidence;
- a real non-technical user walkthrough;
- manual keyboard, 200% zoom/reflow, and screen-reader checks;
- explicit acceptance that marketplace posting remains assisted/manual;
- an acceptance owner, date, accepted risks, deferred blockers, and final launch decision.

Run `python scripts/release_gate.py --json` for the machine-readable missing-evidence list. Do not mark the project production-launch-ready while that gate is blocked.

## License and third-party services

No repository-level `LICENSE` file is currently present. Do not assume permission to copy, redistribute, sublicense, or commercially reuse the code beyond rights you already have; the repository owner should add an explicit licence before third-party distribution or contribution.

Marktplaats, Koopplein, Nextdoor, eBay, Tweedehands, ngrok, PostgreSQL, S3 providers, and other named services retain their own terms, privacy policies, trademarks, technical restrictions, and account requirements. This repository does not grant provider authorisation. The deployment/acceptance owner must review current dependency licences, marketplace terms, data-processing obligations, storage region/retention, and official API permissions before launch.

---

For a quick product walkthrough, begin with the [User guide](docs/USER_GUIDE.md). For deployment work, begin with [Release readiness](docs/RELEASE_READINESS.md) and [Operator runbook](docs/OPERATOR_RUNBOOK.md). For development, begin with [Architecture](docs/ARCHITECTURE.md) and run `python scripts/verify.py` before submitting changes.
