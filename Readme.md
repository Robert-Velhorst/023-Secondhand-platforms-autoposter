# Secondhand Platforms Autoposter

A self-hosted workspace for preparing and managing secondhand-product listings across multiple marketplaces. Enter an item once, add photos, improve the listing, prepare platform-specific versions, and track the steps needed to publish it.

> **Project status: review/demo software, not approved for production launch.** Local features and automated checks do not prove a production deployment is secure, backed up, accessible, accepted by real users, or ready for customer data.

> **Marketplace posting is assisted/manual.** The app prepares copy-ready listing information and opens a marketplace workflow. You sign in to that marketplace, complete its verification and policy steps, review fees and options, and press its final submit button yourself. The app does not currently provide proven automatic marketplace publishing.

## For sellers and reviewers

You do not need to know how to program to use the browser interface once an operator has installed or deployed the app. You do need an operator to run the service; this repository does not provide an always-on hosted account or a signed installer.

A typical workflow is:

1. Register an Autoposter account and sign in. This is separate from your marketplace accounts.
2. Create a listing with the item's facts, price, condition, category, location, and description.
3. Upload product images and save the listing.
4. Use the local Quality assistant and choose which suggestions to apply.
5. Select one or more marketplaces, review their field requirements, then validate.
6. Queue an assisted package and open the Queue. A `needs_user_action` status means the app prepared information; marketplace work remains.
7. Copy or review the information in the marketplace's own form and submit only when you are satisfied.
8. After actual publication, record the marketplace URL in the app. Do not mark a job complete just to clear the queue.

The Autoposter account does not create, verify, or manage your marketplace account. Use non-sensitive sample information for demos.

## What the app includes

- A browser dashboard served by a FastAPI application.
- Accounts and bearer-token sign-in; owner-scoped listing and image access.
- Reusable listings, revisions, images, category mappings, templates, and per-marketplace overrides.
- Listing validation and a deterministic, local quality assistant.
- Persistent assisted-posting jobs, attempt history, logs, retries, and a separate background worker.
- Dashboard analytics based on the signed-in owner's app data.
- JSON/CSV data portability and authenticated API endpoints.
- SQLite for local development and PostgreSQL support for deployments.
- Alembic database migrations, Docker Compose, local/S3-compatible image-storage support, diagnostics, and operational documentation.
- English and Dutch interface/localization support.

### Marketplace support

The registered adapters cover Marktplaats, Koopplein, Nextdoor, eBay, and Tweedehands. They are assisted workflows: final marketplace submission remains under your control. The presence of a platform in the interface is not evidence of a partnership, provider approval, or an enabled official publishing API. Legacy Selenium scripts are historical/manual reference material, not the supported app publishing path.

The app does not bypass CAPTCHA, two-factor authentication, login checks, anti-bot protections, rate limits, payment prompts, or marketplace policy screens. It does not store raw marketplace passwords or claim success just because a package was prepared.

## For developers

### Technology

- Python, FastAPI, Pydantic, SQLAlchemy, and Alembic
- Static HTML, CSS, and JavaScript under `public/`
- SQLite for local use; PostgreSQL supported through SQLAlchemy
- A web/API process and a separate worker process
- Local filesystem or optional S3-compatible image storage
- Pytest and Ruff
- Docker Compose for local development

See [Architecture](docs/ARCHITECTURE.md), [API reference](docs/API_REFERENCE.md), and [Platform completion contracts](docs/PLATFORM_COMPLETION_CONTRACTS.md) for the authoritative design and behavior details.

### Local development setup

Requirements: a supported Python version compatible with the pinned dependencies. From PowerShell at the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/verify.py
python -m uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Register through the interface; there is no shared default username or password. Stop the development server with Ctrl+C.

On macOS/Linux, create and activate the virtual environment with `python -m venv .venv` and `source .venv/bin/activate`, install requirements, copy `.env.example` to `.env`, then run the same Python commands.

Inspect `.env.example` before starting. Keep local credentials out of Git. Development convenience settings must not be carried into a production deployment.

### Docker Compose

For local use, prepare `.env` from `.env.example`, then run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The Compose file starts the application and a separate worker and persists local data through mounted storage. The optional `postgres` Compose profile is for local development/testing only. Its example credentials are not suitable for a public or production environment.

### Database and migrations

SQLite is suitable for local single-operator development. PostgreSQL is supported for deployment. Set `DATABASE_URL` to the intended database and use Alembic migrations; do not rely on automatic table creation in production:

```bash
python -m alembic upgrade head
python -m alembic current
```

Back up the database and uploads together using the operator's documented procedure before a migration or upgrade. A user-facing JSON export is not a complete database or image backup.

### Useful commands and endpoints

```bash
python scripts/verify.py
python -m app.doctor
python -m app.doctor --json
python -m alembic current
python scripts/release_gate.py --json
```

- `GET /api/health` — liveness check.
- `GET /api/worker-status` — worker heartbeat and pause-state readiness.
- `GET /api/platforms` — platform capability descriptions.
- `GET /api/diagnostics` — authenticated diagnostics.
- `/docs` — interactive OpenAPI documentation while the server is running.

The verification script runs automated checks; consult its output for the current test count. Tests use isolated test data. A passing local suite is not a production deployment, security assessment, accessibility sign-off, or marketplace-publishing proof. The release gate is expected to remain blocked until required external evidence is supplied.

## Configuration and security

The main settings are documented in `.env.example` and the operator documentation. Important values include:

- `APP_ENV`: runtime profile.
- `SECRET_KEY`: a strong, unique secret for the environment; never commit it.
- `DATABASE_URL`: database connection URL.
- `UPLOAD_DIR`, `STORAGE_BACKEND`, and optional S3 settings: image-storage configuration.
- `CORS_ORIGINS`: explicitly allowed browser origins; avoid wildcard origins in production.
- `AUTH_TRANSPORT`: bearer authentication is supported; do not put tokens in URLs.
- `AUTO_CREATE_TABLES`: local development convenience only; disable for production.
- `JOB_PROCESS_INLINE`: local convenience versus a separately supervised worker.
- `MAX_UPLOAD_SIZE_MB` and `ALLOWED_IMAGE_TYPES`: upload constraints.
- Worker, session-expiry, audit-retention, logging, locale, and rate-limit settings.

Use HTTPS, a production secret manager, restrictive CORS, a protected PostgreSQL service, persistent and backed-up image storage, and edge/proxy rate limits before exposing an installation. Review [Security and privacy](docs/SECURITY.md), [Authentication security posture](docs/AUTH_SECURITY_POSTURE.md), [Rate limits](docs/RATE_LIMITS.md), and the [Operator runbook](docs/OPERATOR_RUNBOOK.md). CORS is not authentication or access control. The registration endpoint must also be considered when an installation is internet-accessible.

## Data and privacy

The application scopes ordinary reads and writes to the authenticated owner. This does not prevent a host, database, storage, or backup administrator from accessing data. The app is not end-to-end encrypted. The local quality assistant does not require an external AI service.

JSON/CSV portability exports are not full disaster-recovery backups. Images and database state require operator-managed backup and restore procedures. Account deletion affects data in the app; it cannot retract marketplace posts, previously exported/shared copies, or operator backups. Review the [backup and restore guide](docs/BACKUP_RESTORE.md) before using real customer data.

## Production readiness

Do not treat this repository as launch-ready merely because it starts or tests pass. Before serving real users, the responsible owner must review the code and current platform terms, provide deployment access/details, configure and verify production secrets/CORS/storage, migrate the target PostgreSQL database, confirm API and worker health, test backup restoration, verify edge rate limits, complete a real non-technical user walkthrough and manual accessibility checks, and record final acceptance and accepted risks.

Marketplace posting must be presented as assisted/manual unless an official provider API integration is implemented, approved, and proven end to end. A local or containerized smoke test cannot supply deployment, provider, accessibility, backup, legal/compliance, or customer acceptance evidence.

Run `python scripts/release_gate.py --json` for the machine-readable blockers. See [Release readiness](docs/RELEASE_READINESS.md), [Release evidence record](docs/RELEASE_EVIDENCE_RECORD.md), [Non-technical user walkthrough record](docs/NON_TECHNICAL_USER_WALKTHROUGH_RECORD.md), and [Final acceptance record](docs/FINAL_ACCEPTANCE_RECORD.md).

## Repository map

```text
app/                 API, domain models, adapters, services, and worker
public/              Browser interface assets
migrations/          Alembic migration history
tests/               Automated tests
scripts/             Verification, diagnostics, and release-gate scripts
docs/                Product, architecture, operations, security, and acceptance docs
legacy/              Quarantined historical/manual scripts
docker-compose.yml   Local application, worker, and optional PostgreSQL
requirements.txt     Python dependencies
```

## Contributing

1. Read the product and architecture documentation before changing behavior.
2. Work on a feature branch.
3. Preserve owner isolation, assisted/manual marketplace boundaries, and honest job states.
4. Add migrations for schema changes and tests for success, error, authorization, idempotency, and recovery paths.
5. Run `python scripts/verify.py` and relevant focused checks.
6. Update the authoritative documentation and release evidence. Never replace missing external proof with assumptions.

Do not switch an assisted adapter to automatic publishing without provider approval, real API credentials, sandbox/live verification, rate and retry handling, idempotency, ambiguous-outcome recovery, and platform compliance review.

## Documentation

- [User guide](docs/USER_GUIDE.md)
- [Product definition](docs/PRODUCT_DEFINITION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API_REFERENCE.md)
- [Platform completion contracts](docs/PLATFORM_COMPLETION_CONTRACTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Operator runbook](docs/OPERATOR_RUNBOOK.md)
- [Backup and restore](docs/BACKUP_RESTORE.md)
- [Release readiness](docs/RELEASE_READINESS.md)
- [Security and privacy](docs/SECURITY.md)
- [Testing strategy](docs/TESTING_STRATEGY.md)

No repository-level LICENSE file is present. Until the owner adds a licence, do not assume third parties have permission to redistribute or commercially reuse the code. Marketplace names and provider services retain their own terms and requirements; this repository does not grant authorization to automate them.
