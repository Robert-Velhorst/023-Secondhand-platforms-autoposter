# Secondhand Platforms Autoposter

Secondhand Platforms Autoposter is a self-hosted listing workspace for preparing one secondhand-product listing for several marketplaces. A seller enters the item once, adds images, checks listing quality, creates platform-specific variations, and tracks the work needed to publish it.

> **Current status:** release candidate `1.0.0-rc.1`. The local listing workflow has automated verification, but the project is **not approved for a final production launch**. The implementation/integration gaps and deployment, backup, accessibility, real-user, and acceptance requirements described below remain open.

> **Important:** every marketplace adapter currently uses **assisted posting**. The app prepares copy-ready data and opens the appropriate marketplace workflow; the seller still signs in, handles verification or CAPTCHA prompts, reviews fees and options, and presses the marketplace's final submit button. The app does not claim automatic publication without official API proof or explicit user confirmation.

### Which version does this describe?

This README describes the **`agent/production-launch-hardening` review branch**, tracked in [draft pull request #2](https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter/pull/2), not an approved production release. At the **2026-09-13** repository check, `main` remained at [`d96b27e`](https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter/commit/d96b27e85b9027db71a61cc003518b998dacff89). This revision adds managed ngrok lifecycle controls after the historical [`3388291`](https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter/commit/33882913d272f1352b782a7066dd6caeac6eca24) application baseline. The previously reported 190 tests refer to the earlier main baseline, not this review branch. Follow the branch-specific clone instructions below to obtain the code described here.

The repository's current GitHub owner is **Robert-Velhorst**. The original `Noodzakelijk-Online/023-Secondhand-platforms-autoposter` link resolves to this repository. Proposed changes, older PR descriptions, and generated executables are not interchangeable with the source revision you checked out. Rebuild after updating source; an older executable does not gain new launcher controls merely because its PowerShell wrapper changed.

In plain language: the local app prepares and organises listings; people still publish them. Windows packaging, a manual HAI file handoff, and managed tunnel lifecycle controls have local verification records. Production launch, live acceptance of the revised ngrok path, automatic HAI synchronization, and acceptance in the target HAI installation remain unfinished milestones. The `1.0.0-rc.1` version string is not launch approval or proof of a downloadable signed release.

## Contents

- [Who this is for](#who-this-is-for)
- [Start here without a technical background](#start-here-without-a-technical-background)
- [Frequently asked questions](#frequently-asked-questions)
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
- [Performance and resource use](#performance-and-resource-use)
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

## Start here without a technical background

Ask your installer or operator for **either** a Windows executable built from the agreed review commit **or** the address of an authorised installation. This README is not a download page for a signed installer, and the repository does not supply an always-on hosted account.

1. Start the Windows app, or open the address supplied by your operator. For a default local installation, the address is `http://127.0.0.1:8000` on that same computer.
2. Register an **Autoposter account**, then sign in. This account is separate from your Marktplaats, eBay, or other marketplace accounts. There is no shared default username/password.
3. Open **Listings → New listing** and enter a real item's description, price, condition, category, location, and images. During a demo, use non-sensitive sample content and do not submit it to a marketplace.
4. Save, check the **Quality assistant**, choose marketplaces, and select **Validate**. Correct the reported omissions before queueing.
5. Select **Queue assisted package** and open **Queue**. `needs_user_action` means the preparation succeeded and your marketplace work remains.
6. Copy the prepared information into the marketplace's own form. Review its rules, visibility, delivery options, and fees before deciding to submit.
7. Only after actual publication, record the resulting marketplace URL in the job's manual-completion action. Do not confirm publication just to clear the queue.

Before closing an editor, confirm that saving succeeded. If it failed, keep the page open and retry **Save**; visible text is not proof that the database stored it. For a fuller walkthrough, read the [User guide](docs/USER_GUIDE.md).

### Words used in the app

| Term | Plain-language meaning |
| --- | --- |
| Master listing | Your reusable description of one item |
| Platform or marketplace | The external site where you intend to advertise the item |
| Platform override | A different field value or description for one marketplace |
| Assisted package | Prepared listing information and guidance; not a submitted advertisement |
| Job / queue / worker | A saved task / the waiting tasks / the background process that prepares them |
| Revision | A saved version used to distinguish changed listing content from repeated requests |
| API | The interface the browser and approved integrations use to communicate with the app |
| Migration | A controlled database-structure upgrade run by the installer or operator |
| HAI connector | A restricted way to share listing records with a separately operated HAI installation |
| Release candidate | A version under review, not a promise that production launch is approved |

## Frequently asked questions

### Does “Autoposter” mean it publishes automatically?

No. All five registered marketplace adapters prepare assisted packages. Final submission remains yours. A `published` job records your explicit confirmation in the current implementation; it is not independent verification that the marketplace still hosts the advertisement. Editing, archiving, or deleting an item in Autoposter does not automatically change or remove its external advertisement. The app also does not synchronize sales, buyer messages, or stock across marketplaces.

### Can I use it without internet or from another device?

With the app running on your computer, SQLite and local storage keep listing preparation local; the quality assistant does not need an external AI service. Marketplace visits, ngrok, remote PostgreSQL/S3 storage, and remote integrations require their respective network connections. This is not an offline browser app: if its API is stopped or unreachable, the page cannot save work.

`127.0.0.1` means **this device**, not your other computer or phone. Another device needs an operator-approved reachable deployment. A tunnel forwards traffic to the running Windows app; it does not move the app into cloud hosting or keep it running while the computer sleeps, shuts down, or loses connectivity. The committed ngrok helper has the [safety limitations below](#access-through-ngrok).

### Is there a subscription, AI bill, or marketplace fee?

There is no billing/subscription implementation or external AI requirement in this app. That is not a free-use licence or a promise of zero operating cost. Hosting, storage, backups, a tunnel account, and marketplace placement can have separate charges under your chosen providers. The app does not purchase marketplace extras for you. Repository licensing is [not yet specified](#license-and-third-party-services).

### Who can see my data?

Application reads and writes are scoped to your signed-in owner account, and uploaded images require authentication. However, the person administering the host, database, storage, and backups can potentially access their contents. This is not end-to-end encrypted storage. The local quality assistant does not send listings to an external AI provider. Marketplace submission and a deliberate HAI export share data with their respective destinations.

### What if I forget my password? Can I invite a team?

There is no implemented self-service password-reset email, email-verification flow, multi-factor authentication, invitation-only registration, or shared team workspace. The repository also does not ship an operator password-reset command or establish a tested account-recovery procedure. Use a password manager and agree a recovery/support plan with the operator before relying on the app; do not assume a recovery service already exists. Do not delete or recreate the database to solve a login problem. The registration endpoint is public: a secret-looking URL or restrictive CORS alone does not limit who can create an account on an internet-accessible installation.

### Will exports or deleting my account undo everything?

No. JSON/CSV exports cover supported business records, not a complete database backup; images need a separate export or storage backup. Account deletion is destructive within this app and is not an undoable archive action. It does not delete marketplace advertisements, files already downloaded or shared with HAI, or copies retained in operator backups. Backups and the sanitised audit-retention policy need separate operator handling. See [Data, storage, and privacy](#data-storage-and-privacy).

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
| ngrok over standalone | Operator-approved remote review of one Windows instance | Local SQLite | Separate owned worker; startup checks its exact heartbeat locally and through the public URL | Lifecycle controls are locally tested; live-provider and access-control acceptance remain open |

## Windows 11 standalone use

The repository contains a PyInstaller build recipe; the generated executable is intentionally ignored by Git and is not a source file. Build it on the Windows machine where it will be reviewed:

```powershell
py -3.13 -m venv .venv-build
.\scripts\build-windows.ps1
```

Run these commands from the repository root after cloning the review branch. The environment-creation command is for a **new** packaging environment; preserve an existing working `.venv-build`. The build script uses that isolated environment and expects Python 3.13 for packaging. Its automatic discovery fallback looks for a uv-managed Python 3.13 installation, so merely having another Python version on `PATH` is not sufficient. It creates:

- `dist\SecondhandAutoposter.exe`
- `dist\SecondhandAutoposter.exe.sha256`

Run the executable by double-clicking it or from PowerShell:

```powershell
.\dist\SecondhandAutoposter.exe
```

The launcher:

- exclusively reserves IPv4 loopback (`127.0.0.1`, also when `localhost` is requested) before changing data;
- locks its data directory against another cooperating launcher before creating secrets or running migrations;
- creates or reuses a strong local secret;
- stores data in `%LOCALAPPDATA%\SecondhandAutoposter` by default;
- upgrades the local database to Alembic head before serving;
- starts the API and worker as separate processes;
- contains the Windows worker and its descendants in an owned process group that is terminated on launcher exit or crash;
- opens the browser after the health endpoint responds;
- trusts forwarded proxy headers only from localhost.

To choose another controlled data/backup location:

```powershell
$env:AUTOPOSTER_DATA_DIR = "D:\AutoposterData"
.\dist\SecondhandAutoposter.exe
```

The standalone profile is designed for one Windows operator using SQLite and local image storage. It is not a substitute for a multi-user PostgreSQL production deployment. See [Windows standalone and ngrok](docs/WINDOWS_STANDALONE.md).

An occupied port or a data directory held by another current launcher causes startup to fail before secrets, migrations, workers, or a tunnel are started. After a forced shutdown, Windows may briefly retain the file lock; retry after the old processes have stopped. Do not delete `.launcher.lock` to bypass it. The lock coordinates this launcher, not older versions, direct worker/API commands, other applications, or two different data directories configured to share one database. Upgrades still require a backup and all older API/worker processes stopped. Local build evidence does not establish Windows code-signing, SmartScreen reputation, an installer, or automatic updates. The ngrok wrapper now delegates lifecycle ownership to the current launcher.

## Local development setup

### Requirements

- Python 3.12 is the supported application/CI target.
- Git.
- A modern browser.
- Optional: Docker Desktop, PostgreSQL, ngrok, and Python 3.13 for Windows packaging.

### Choose and record the version

The review branch can advance. After cloning and entering the repository directory, run `git rev-parse HEAD` to record what you actually obtained, and inspect that revision's verification evidence. Commit `33882913d272f1352b782a7066dd6caeac6eca24` is a historical comparison point, **not** the current managed-ngrok implementation. Do not switch versions in a working installation without checking schema compatibility, stopping processes, and backing up its data.

### Windows PowerShell

```powershell
git clone --branch agent/production-launch-hardening https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter.git
Set-Location 023-Secondhand-platforms-autoposter
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

**Before starting:** review the new `.env` and replace its example secret with a random local value. It is a development profile, not a production configuration. The current example contains only web-app settings; no legacy-section removal is needed for a fresh copy. If an existing `.env` was copied from an older version, remove its legacy-only Selenium/LastPass/marketplace-URL keys while preserving any needed historical values separately. Do not overwrite unrelated settings in an existing installation.

After saving the corrected `.env`:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

### Linux or macOS

```bash
git clone --branch agent/production-launch-hardening https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter.git
cd 023-Secondhand-platforms-autoposter
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Review the new development `.env` and replace its example secret, as described in the Windows instructions. A fresh copy no longer requires legacy-key cleanup. Then run:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

`.env.example` enables development conveniences, including automatic table creation and inline job processing. Run Alembic anyway when validating migrations, and never copy those unsafe conveniences into production.

These commands are for a **new checkout**. Do not overwrite an existing `.env` or recreate a working environment without reviewing it. If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python`; activation is not required. Stop the development server with Ctrl+C. There is no frontend build step or Node.js requirement for the shipped plain-JavaScript interface.

## Docker setup

### Local SQLite stack

```powershell
Copy-Item .env.example .env
```

Review the new development `.env` and replace its example secret, then start the stack:

```powershell
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

Then start the database, wait for it to accept connections, migrate it with a one-off application container, and only then start the API and worker:

```powershell
docker compose --profile postgres up -d postgres
docker compose exec postgres pg_isready -U autoposter -d autoposter
docker compose run --build --rm autoposter alembic upgrade head
docker compose --profile postgres up --build -d autoposter worker
```

Continue past `pg_isready` only after it reports that PostgreSQL is accepting connections; repeat the check if it is still starting. For an existing stack, stop API and worker and back up data before migrating. The local Compose PostgreSQL password is a development value. Do not reuse it outside an isolated local environment. Compose publishes ports on the host; apply host firewall restrictions and do not expose this development stack to the internet.

## Access through ngrok

> **Explicit internet exposure, not cloud hosting or production approval.** The revised launcher owns the port and data lock before starting ngrok, and supervises its own tunnel, API, and worker processes. These controls were tested locally with a substitute agent, real sockets, real API/worker processes, and failure injection. That is not live-provider or public-access-policy acceptance.

A reserved domain does not make the app private. Account registration is available; CORS is a browser-origin control, not a firewall or invitation-only registration. Have an operator approve access controls, exposure duration, and data sensitivity. Keep credentials in the operator's ngrok configuration, not the repository.

With ngrok installed/authenticated and the **current rebuilt** executable or Python environment prepared:

```powershell
.\scripts\start-ngrok.ps1
```

For a reserved domain:

```powershell
.\scripts\start-ngrok.ps1 -Domain "your-domain.ngrok.app"
```

For the script's non-interactive health drill (subject to the same lifecycle limitations):

```powershell
.\scripts\start-ngrok.ps1 -VerifyOnly
```

`-VerifyOnly` checks startup readiness and tears down this run; it still opens a real public endpoint. Use `-FromSource` to bypass an existing executable, `-NoBrowser` to avoid opening a tab, `-Port 8010` for another port, or `-NgrokPath "C:\Tools\ngrok.exe"` for an explicit agent path. Arguments preserve paths with spaces. The wrapper preserves the caller's environment and working directory.

The managed lifecycle provides:

- Exclusive IPv4 loopback binding and an OS data-directory lock **before exposure**. An occupied port or locked directory stops startup before ngrok runs.
- Separate owned ngrok, API, and worker process trees. Windows uses kill-on-close Job Objects; cleanup does not select unrelated processes by executable name. The supervisor retains its socket and data lock until child cleanup finishes.
- Per-run logs under `AUTOPOSTER_DATA_DIR/runtime/ngrok-<unique-id>/`. A log rotates at approximately 64 KiB with three backups; oversized records are omitted rather than parsed in fragments. Failed or ended log observation fails the run. Logs are not served by the app; local filesystem access and cross-run retention remain operator responsibilities.
- Inspection and endpoint pooling disabled with `--inspect=false --pooling-enabled=false`; HTTPS-origin validation and matching the reported endpoint to the requested domain, when supplied.
- Standalone mode, bearer authentication, development auto-login off, explicit migrations, separate job processing, and CORS restricted to the observed public origin.
- Local **and public** `/api/health` and `/api/worker-status?worker_id=...` checks. Both must carry this launch's instance marker; the worker response must identify this launch's fresh heartbeat. Another worker or app cannot satisfy readiness. The marker is diagnostic, not an authentication token.

After readiness, supervision checks process and log-observation liveness; it does **not** continuously retest public HTTP availability or heartbeat freshness. Process death, failed logging, readiness failure, or Ctrl+C tears down the owned session. In tunnel mode, API termination stops unfinished request threads before releasing data ownership. This is forced termination, not a guarantee that requests/jobs completed; inspect state before retrying consequential operations. Ordinary local mode retains its existing API graceful-drain behavior.

Endpoint discovery has a 30-second deadline; API socket bootstrap and startup readiness each have a 180-second deadline. These are not a universal bound for migrations, OS cleanup, DNS resolution, or all infrastructure failures. A failed shutdown is reported rather than counted as successful verification. See [Windows lifecycle details](docs/WINDOWS_STANDALONE.md) and the [verification report](docs/FINAL_VERIFICATION_REPORT.md).

If ngrok reports `ERR_NGROK_334`, that endpoint is already online. Stop the conflicting endpoint in the ngrok account or provide another reserved domain/tunnel slot. Do not enable pooling as an improvised fix: it may route one public address to unrelated local services.

Treat an ngrok URL as internet exposure. Use a strong account password, do not enable development auto-login, revoke the tunnel after review, and do not describe a temporary standalone tunnel as a production deployment.

## HAI connector

The application offers a **HAI-compatible local-file download** and a separate owner-scoped, **read-only** incremental API. **HAI's current HTTP consumer is not directly compatible with the incremental API.**

### Download a file for HAI

Sign in, open **Settings → HAI connection → Download HAI feed**, and save `autoposter-hai-feed.json`. Give the file to your authorised HAI operator to place under HAI's allowlisted feeds directory and register as `local_json_file` / `generic_json_feed`, using a distinct account label for this Autoposter installation and owner. No connector token is needed for this manual download; it uses your normal signed-in session.

The file contains all currently stored owner listings (including archived listings), in HAI's `items` format with stable listing IDs. It excludes private notes, credentials, filenames, and image bytes. Exports over 5 MiB, or listings exceeding HAI's per-item limits, return an error **without a partial file**. Refresh the file to share later changes. An omitted/deleted listing does not remove previously ingested HAI operations. This is a controlled file handoff, not automatic synchronization or production HAI acceptance. The [connector guide](docs/HAI_CONNECTOR.md) explains setup and verification.

### Test the app-side connector

1. Sign in to Secondhand Autoposter.
2. Open **Settings** and create a named HAI token with an expiry period.
3. Copy the `hai_...` value immediately. Only its SHA-256 hash is retained, so the plaintext token cannot be shown again.
4. Use a controlled API client capable of sending `Authorization: Bearer hai_...`; do not put the token in a URL, screenshot, or committed configuration.
5. Read `/.well-known/hai-connector.json`, verify with `GET /api/hai/status`, and pull `GET /api/hai/records`. This verifies Autoposter's API, not ingestion into HAI.

Example with a placeholder token:

```bash
curl -H "Authorization: Bearer hai_REPLACE_ME" \
  "https://autoposter.example/api/hai/records?limit=100"
```

The feed uses opaque cursors, returns listing upserts, and emits deletion tombstones. Each incremental record has a decimal-string `change_id` so a consumer can reject older/equal replays without relying on timestamps. Both feed formats omit unsafe configured source links. The feed excludes internal notes, credentials, secret references, and image binaries. Connector tokens have only `hai:read`, expire, can be revoked, and cannot edit, delete, publish, or mark a marketplace job complete.

### What is still needed on the HAI side?

Source comparison against [HAI's generic-feed parser at commit `91c8620`](https://github.com/Robert-Velhorst/018-HAI/blob/91c8620c557229f1da4ed15fcbb7088c6a6947a7/backend/internal/accountfeed/generic_feed.go), [HTTP fetcher](https://github.com/Robert-Velhorst/018-HAI/blob/91c8620c557229f1da4ed15fcbb7088c6a6947a7/backend/internal/accountfeed/fetcher.go), and [sync registry](https://github.com/Robert-Velhorst/018-HAI/blob/91c8620c557229f1da4ed15fcbb7088c6a6947a7/backend/internal/accountfeed/registry_service.go), refreshed on 2026-09-13 with HAI main still at that revision, found:

| Contract | Autoposter emits/requires | Inspected HAI consumer |
| --- | --- | --- |
| Authentication | A `hai:read` bearer token | HTTP fetcher does not set an Authorization header |
| Envelope | `records`, `next_cursor`, `has_more` | Parses `items` and optional `cursor`, or a bare item array |
| Identity/type fields | `id`, `source_url`, listing metadata | Requires `externalId`, `provider`, and `itemType`; uses `sourceUri` |
| Incremental sync | Caller advances the cursor and applies deletion tombstones | Reports a cursor but does not advance the fetch URL or apply Autoposter tombstones |

Registering the incremental URL alone is therefore insufficient: authenticated fetching fails, and even a manually fetched `records` envelope can be interpreted as zero items by that parser. The new file download handles the generic format for a manual handoff; a compatible authenticated adapter must be installed and accepted in the target HAI environment. Do not remove authentication or claim installed end-to-end automatic HAI completion to work around the mismatch. See [HAI connector](docs/HAI_CONNECTOR.md) for the protocol and acceptance checklist.

A **separate local HAI review branch**, not HAI main or an installed release, now contains a reference-only Autoposter adapter, durable cursor checkpoints, deletion handling, and persistent enable/disable controls. The 2026-09-13 integration test passed against the real Windows Autoposter executable and disposable PostgreSQL, including 101 records, updates/deletion, restart, persisted disable, and zero-replay resume. That HAI work remains uncommitted, unpublished, and uninstalled; it does not establish unattended scheduling or target acceptance. See the [current verification record](docs/FINAL_VERIFICATION_REPORT.md#transactional-image-cleanup-and-recovery--2026-09-13).

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
    U -->|"Authenticated download + operator import"| H["HAI generic local-file consumer"]
    H -.->|"Automatic authenticated adapter still needed"| R["Read-only incremental connector"]
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
| `app/routes/hai.py` | HAI discovery, connector-token lifecycle, status, incremental read feed, and generic file export |
| `app/models.py` | SQLAlchemy domain and operational models |
| `app/storage.py` | Validated local and S3-compatible image persistence/retrieval |
| `app/adapters/` | Honest marketplace capability, validation, mapping, and assisted-package contracts |
| `app/services/` | Jobs, quality, analytics, audit, OAuth, localisation, worker health, and operator controls |
| `app/worker.py` | Due-job processing loop and heartbeat recording |
| `app/launcher.py` | Windows standalone migration, API, worker, browser, and local-data lifecycle |
| `app/ngrok.py` | Owned tunnel process, isolated bounded logs, origin checks, and per-instance API/worker startup verification |
| `migrations/` | Alembic schema history |
| `tests/` | API, ownership, state, frontend-contract, deployment, migration, accessibility, and release-gate coverage |

### Request and data boundaries

- Browser requests use opaque bearer sessions in the `Authorization` header; cookie sessions are not enabled.
- User-owned reads and writes are filtered by authenticated owner ID.
- Image bytes are never served by a public directory mount.
- API requests write persistent jobs; a worker claims and processes due work.
- Assisted adapters produce `needs_user_action`, not invented marketplace success.
- The incremental HAI API uses a separate purpose-limited token and can only read the owner's listing feed. The manual HAI file download instead requires the owner's normal signed-in session.

## Performance and resource use

The shipped browser interface is plain HTML, CSS, and JavaScript: no frontend compilation, Node.js runtime, or external AI request is needed for normal use. The API serves it directly. The queue is stored in the application database; Redis, Celery, and a separate message broker are not required.

- Collection endpoints page results rather than sending the entire inventory. Dashboard data comes from one combined owner-scoped endpoint, and filters refresh their own collection.
- Worker batches and polling are configurable. Image binaries stay outside ordinary JSON responses and exports.
- Worker health uses database aggregates; reminders bound the candidates they load. Exact quality analytics still inspect every owned listing in batches, so bounded memory does **not** mean constant processing time.
- PostgreSQL connection pools are bounded **per process**. With the defaults, one API process and one worker can together allow up to 20 pooled/overflow connections (`2 × (5 + 5)`), before migrations, administration, or additional processes. Size the total against the database's connection budget.
- SQLite uses foreign keys, WAL journaling, a five-second busy timeout, and `synchronous=NORMAL`. These choices support small local workloads; they do not replace tested backups or eliminate contention/power-loss risks.

The [performance guide](docs/PERFORMANCE_SCALE_BASICS.md) records a reproducible synthetic read benchmark and its limits. There is no declared production throughput, maximum concurrent-user count, minimum-RAM guarantee, or uptime SLA. Measure representative inventory, image sizes, query plans, worker latency, and concurrent users on the actual target before increasing deployment scale.

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
- Upload and duplication exceptions roll back their business transaction and queue cleanup of tracked storage targets through a fresh session on the same database. Missing source images block duplication instead of producing an incomplete copy; category attributes are retained and copy titles stay within 160 characters. This does not yet cover a hard crash before recovery intent is saved or an unavailable recovery database. See [write-failure recovery](docs/IMAGE_STORAGE.md#upload-and-duplication-failures).
- S3-backed images can be read by the authenticated application, but the built-in image ZIP exporter currently records them as `object_storage_not_exportable`; use provider tooling for a complete S3 bucket export.

### Portability and deletion

- JSON export contains supported listing, platform-draft, template, category-mapping, and sanitised account data.
- CSV import/export supports the documented master-listing columns. Imports require UTF-8 (an optional BOM is accepted) and are limited to 2,000,000 bytes. Oversized files return HTTP 413; encoding, malformed CSV, oversized parser fields, and invalid listing values return HTTP 422. A rejected import does not save a partial set of listings.
- Image ZIP export contains locally stored binaries plus a manifest.
- Password hashes, sessions, raw OAuth tokens, platform passwords, job history, and image binaries are excluded from the JSON export.
- Account deletion removes owned sessions, listings, jobs, templates, mappings, accounts, and connector tokens in one database transaction. File cleanup is queued in that same transaction and only runs after commit; a rolled-back deletion preserves the images.
- Cleanup checks for remaining image references, retries storage failures across restarts, and rejects paths outside the configured upload directory or S3 bucket/prefix. Small local batches are attempted immediately; the worker completes larger batches and all S3 deletion. A successful deletion response confirms removal from the app, **not** immediate physical erasure from storage, backups, or external copies. See [cleanup and recovery](docs/IMAGE_STORAGE.md#deletion-and-recovery).
- A sanitised audit record with a hashed email may remain for operational accountability until `AUDIT_RETENTION_DAYS` purges it. Production privacy notices must disclose that retention.

User exports are portability tools, not complete operational backups. See [Image storage](docs/IMAGE_STORAGE.md), [Privacy audit events](docs/PRIVACY_AUDIT_EVENTS.md), and [Backup/restore](docs/BACKUP_RESTORE.md).

## Configuration reference

Start from `.env.example` for development or `.env.production.example` for deployment. Never commit a completed secrets file.

`Settings` reads `.env` relative to the process working directory; environment variables override values loaded from that file. Run source commands from the repository root and restart API and worker after changing configuration. The standalone launcher supplies its own controlled profile and data paths. Production Compose explicitly loads `.env.production` for its services. The tables below cover the application's declared settings; provider credentials and launcher/Compose-only values are distinguished separately.

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

The S3 client uses [boto3's credential resolution](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html#configuring-credentials) rather than custom `S3_ACCESS_KEY` settings. Supply an approved runtime identity or securely injected provider credentials to every process that needs storage. Do not put real keys in this README or a committed `.env`. If the optional OAuth token foundation is used, its secret-reference directory also needs durable, access-controlled storage and backup; the supplied production Compose file mounts uploads, not that secrets directory.

### Authentication, sessions, and limits

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEV_AUTO_LOGIN` | `false` | Reserved development-only shortcut; rejected in production/standalone |
| `SESSION_EXPIRE_HOURS` | `168` | Bearer-session lifetime |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | Atomically admitted attempts per email/IP window, including in-flight checks; a still-latest success clears its window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `300` | Login throttle window |
| `API_RATE_LIMIT_REQUESTS` | `300` | Requests per supplied Authorization header (or observed client IP if absent), per process/window |
| `API_RATE_LIMIT_WINDOW_SECONDS` | `60` | API throttle window |
| `AUDIT_RETENTION_DAYS` | `365` | Sanitised audit-event retention; `0` disables automatic age-based purging |

The built-in API limiter is process-local and capped at 10,000 hashed identities, with monotonic expiry and atomic counter updates. It rejects new identities with a retryable 429 when full instead of growing indefinitely or resetting active quotas. Header rotation can still evade a per-identity quota or fill the cap: the supplied Authorization header is not authenticated at this middleware stage. A multi-process or internet-facing deployment still needs independently verified edge/proxy/CDN/WAF rate limiting. See [rate-limit behavior and tradeoffs](docs/RATE_LIMITS.md#general-api-request-limit).

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

Historical marketplace URL, LastPass, and Selenium variables are preserved in [the separate legacy example](legacy/selenium/.env.example), not the root `.env.example`. They are not supported `Settings` fields. Remove them from older web-app `.env` files if startup reports `extra_forbidden`; the application intentionally rejects unknown settings rather than hiding configuration mistakes. This separation does not enable or validate the quarantined scripts.

## API reference

All product endpoints are under `/api` unless noted. Authenticated calls use `Authorization: Bearer <token>`. Interactive OpenAPI documentation is available at `/docs`.

### Public and authentication endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness, server time, and version |
| `GET` | `/api/worker-status` | Worker heartbeat and operator-pause readiness; optional exact `worker_id` filter |
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
| `GET` | `/api/hai/export` | Download a HAI generic JSON file using the owner's normal bearer session; connector tokens cannot call it |

Paginated product collections such as listings and jobs use bounded `limit`/`offset` and return `X-Total-Count`, `X-Limit`, and `X-Offset`. This is not universal: HAI records use `cursor`, `limit` (1–250, default 100), `next_cursor`, and `has_more`; token metadata and platform capabilities have their own response contracts. See [API reference](docs/API_REFERENCE.md) and the running `/docs` schema for payload and error-shape details.

## Jobs and worker operation

For normal production-style operation, set `JOB_PROCESS_INLINE=false` and run:

```powershell
python -m app.worker
```

Job states are:

- `queued`: waiting for a worker or a future cooldown time;
- `running`: claimed for adapter processing;
- `needs_user_action`: a valid assisted package exists and the seller must continue on the marketplace;
- `published`: the seller explicitly recorded manual completion; API-confirmed publication is reserved for a future approved official adapter and is not available today;
- `failed`: processing failed and may be eligible for retry;
- `skipped`: intentionally not processed.

Claims use a conditional queued-to-running update; PostgreSQL query construction includes `FOR UPDATE SKIP LOCKED` for concurrent workers. Idempotency keys include the owner, listing revision, platform, account, action, and operation mode. Platform cooldowns can return work to `queued` without counting an adapter attempt. Stale `running` jobs are recovered after `JOB_STALE_RUNNING_SECONDS`.

Recovery checks the selected job version again before returning it to the queue, so an outdated recovery decision cannot replace a newer completion or claim. Competing recoverers record only one successful transition and recovery log. Each worker cycle considers at most its configured batch size of stale candidates, loading only IDs and timestamps; repeated cycles drain the backlog.

Each claim also carries a random identifier through execution. A delayed worker cannot start a replacement claim or save a late success, error, or quota response after its claim has been replaced. The job result, platform mapping, and attempt/log writes share one guarded transaction. Adapter calls receive detached listing/image/account inputs after the read connection has been released; package preparation does not hold a database transaction open. These safeguards protect local database state, not provider-side effects: lease renewal and exactly-once external publication are not implemented.

Upgrading across Alembic revision `20260905_0014` requires stopping all old API and worker processes first, including inline processing. Current head `20260913_0016` also includes durable storage cleanup and atomic login reservation fencing. Back up the database and uploads, apply migrations, and restart every process with the new code. Do not mix old and new processes: old code does not enforce these protections. See the [claim-fencing upgrade procedure](docs/OPERATOR_RUNBOOK.md#claim-fencing-upgrade), [storage-cleanup upgrade](docs/OPERATOR_RUNBOOK.md#storage-cleanup-upgrade-and-operation), and [login-admission upgrade](docs/OPERATOR_RUNBOOK.md#login-admission-upgrade).

Inline requests must claim due queued work; they do not execute a job already claimed by a worker or bypass its scheduled backoff. Retrying an already queued/running job leaves it unchanged. Retrying terminal work uses a conditional version check and, when `JOB_PROCESS_INLINE=false`, leaves execution to the separate worker. A fresh claim clears the previous attempt's start/finish timestamps so it is not immediately recovered as stale.

Repeating a queue request with the same idempotency key returns the existing job in any state, including `failed` and `skipped`; it does not create a duplicate or implicitly retry a failure. Use the explicit retry action for eligible jobs, or edit/regenerate the listing to create a new revision. Simultaneous requests for the same key are resolved by the database uniqueness constraint, with one job and one initial queue log. A recovered duplicate-key race preserves caller changes made before the enqueue savepoint; unrelated database errors still propagate.

Automated checks exercise four concurrent database sessions on SQLite and migrated PostgreSQL, with 24 jobs per scenario and one attempt per job. These checks are not a guarantee of exactly-once external publication: crash recovery during external calls, long-running jobs exceeding the stale timeout, target-environment load, and provider idempotency require separate proof. Current marketplace adapters still prepare local assisted packages only.

### Database-error recovery

The worker retries runtime database operational/interface errors and connection-pool timeouts instead of exiting after one failure. It closes the cycle's sessions before waiting and doubles the delay from `JOB_WORKER_POLL_SECONDS` up to 60 seconds (or the configured poll interval if longer). A complete successful queue-and-heartbeat cycle restores normal polling. Logs identify the worker, failing phase, exception class, and retry delay without including raw database exception text or SQL parameters.

Startup/configuration errors and unrelated programming/integrity errors still stop the process. Monitor heartbeat freshness and logs; a retrying process is not proof of healthy processing. Heartbeat counters are best-effort telemetry, not an exact job ledger, especially when a database commit's result is uncertain. See the [operator runbook](docs/OPERATOR_RUNBOOK.md#worker-database-recovery) for recovery limits and intervention guidance.

### Emergency controls

```powershell
python -m app.operator_control status
python -m app.operator_control pause --reason "Investigating duplicate-post risk" --actor "operator-name"
python -m app.operator_control resume --actor "operator-name"
```

Pausing prevents new claims; it does not terminate an adapter call already in progress. See [State machines](docs/STATE_MACHINES.md) and [Operator runbook](docs/OPERATOR_RUNBOOK.md).

## Production deployment

Production Compose deliberately does **not** bundle a database. Supply a managed or separately operated PostgreSQL service, durable upload storage, and secret-manager-backed values.

1. For a new deployment only, copy `.env.production.example` to `.env.production` outside version control. Preserve an existing configured file.
2. Replace every placeholder, particularly `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_BASE_URL`, and `CORS_ORIGINS`.
3. Choose private S3-compatible storage or a persistent local upload volume.
4. Back up the target database and uploads before migration.
5. Start the migration-gated stack.

```powershell
$env:UPLOAD_VOLUME = "D:\PersistentData\autoposter-uploads"
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
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

Startup rejects specific unsafe production values rather than silently falling back to development behaviour. These checks are not a security assessment: a long example secret can pass the length check, an allowed CORS origin is not access control, and syntactically valid storage/database settings do not prove availability or backup coverage. Replace **every** example secret with a freshly generated value and verify the target runtime.

The example creates a new environment; do not copy over an existing `.env.production`. For upgrades, stop all older API/worker processes before migration and follow the [operator runbook](docs/OPERATOR_RUNBOOK.md). Compose does not supply TLS certificates, an edge proxy/WAF, backup scheduling, or a managed database. Restrict direct access to the published API port and terminate HTTPS at a reviewed proxy. `--env-file` supplies Compose interpolation values such as `APP_PORT`; service `env_file` supplies the application environment. Neither is a secret manager.

After deployment, record the exact commit, environment, URL, migration head, API/worker health, backup/restore result, edge policy, accessibility evidence, accepted risks, and final decision in [Release evidence record](docs/RELEASE_EVIDENCE_RECORD.md).

## Backups and recovery

A complete operator backup includes:

- the PostgreSQL database or standalone SQLite database;
- the local upload directory or the complete private S3 bucket/prefix;
- the access-controlled `TOKEN_SECRET_DIR` when the optional OAuth token foundation is used, and the standalone installation's local secret file;
- the deployed Git commit and Alembic revision;
- environment/secret references **and an approved way to recover the corresponding secret values**, such as the secret manager's protected recovery procedure; references alone cannot restore a lost secret. Keep plaintext secrets out of ordinary logs and evidence records.

Minimum documented cadence is daily database/uploads backup, an additional pre-migration backup, configuration-reference capture after deployment/rotation, and a monthly restore test.

Restore in this order: stop worker and API, restore database and images, restore required local secrets and secret-manager access through the approved secure procedure, deploy a schema-compatible commit with the intended configuration, run `alembic upgrade head`, run the doctor, start the API, then start the worker. Keep the worker stopped whenever duplicate external action is a concern.

User JSON/CSV/image exports do not contain the full operational history and are not a disaster-recovery substitute. Follow [Backup, restore, and disaster recovery](docs/BACKUP_RESTORE.md).

## Security model and limitations

### Implemented controls

- Argon2 password hashing; successful login upgrades supported older PBKDF2 hashes.
- Opaque session and HAI tokens stored as hashes, with expiry and revocation.
- Owner filtering and dedicated cross-user isolation tests.
- Selected publishing accounts must belong to the listing owner and match its target platform. The API checks all selections before queueing or creating a revision; enqueue, retry, and worker execution recheck the account. Assisted posting without a selected account remains supported.
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

The latest atomic-login checkpoint passed **501 tests with one POSIX-only skip in 139.72 seconds on Windows on 2026-09-13** (502 cases), plus Ruff and compilation. All **85 PostgreSQL subset checks** passed. Sixteen new cases cover concurrent admission, successful-completion fencing, error rollback, expiry cleanup, and migration preservation. See the [current verification record](docs/FINAL_VERIFICATION_REPORT.md#atomic-login-admission-and-expiry-maintenance--2026-09-13). Production deployment and human acceptance remain separate requirements.

The latest API rate-limit resource checkpoint passed **485 tests with one POSIX-only skip in 128.22 seconds on Windows on 2026-09-13** (486 cases), plus Ruff and compilation. Ten new cases cover memory bounds, expiry, capacity behavior, concurrent admission, and real HTTP errors. See the [current verification record](docs/FINAL_VERIFICATION_REPORT.md#bounded-api-rate-limit-state--2026-09-13); these checks do not prove production load capacity or edge enforcement.

The newer upload/CSV responsiveness checkpoint passed **475 tests with one POSIX-only skip in 117.81 seconds on Windows on 2026-09-13** (476 cases), plus Ruff and compilation. Nine new cases cover event-loop isolation, async image helpers, exact CSV size boundaries, and encoding/parser errors without partial imports. See the [current verification record](docs/FINAL_VERIFICATION_REPORT.md#upload-and-csv-event-loop-isolation--2026-09-13). The earlier checkpoints below retain their original evidence; none is production acceptance or a saturated-load guarantee.

The latest image-write recovery checkpoint passed **466 tests with one POSIX-only skip in 114.71 seconds on Windows on 2026-09-13**, along with Ruff, compilation, and an isolated-database doctor check at head `20260913_0015`. The suite collects 467 cases. Coverage includes API behaviour, authentication, owner isolation, publishing-account checks, uploads/storage, listing revisions, adapters, job states/rate limits, concurrent enqueue/claims/retries, stale recovery, claim-fenced results, bounded database reads, migrations, deployment configuration, HAI feeds/downloads, frontend contracts, diagnostics, and release gates. Cleanup tests cover rollback safety, shared files, committed deletion during storage failures, a fresh worker process, crash recovery, concurrent claims, fenced acknowledgments, storage-path boundaries, and pending-work-safe migration rollback. Image-write tests additionally cover partial writes, uncertain commits, same-database recovery, unavailable recovery storage, complete duplication details, missing-image conflicts, and title bounds. A migration regression prevents Alembic from disabling existing application loggers. The HAI regressions cover source-link privacy and monotonic change identifiers for safe consumer replay. Clean-install tests copy the unedited environment example and exercise migrations, real API/worker startup, registration, and a persisted listing. The 41 ngrok-specific cases include occupied resources, exact-worker identity, malformed/oversized logs, EOF/I/O failures, wrapper environment preservation, and shutdown with unfinished or blocked requests. The Windows owner-crash and PowerShell-wrapper cases are skipped on other operating systems; the POSIX connection-reuse case is skipped on Windows. Scripted accessibility/browser-related cases do not replace manual acceptance. The verification report records historical results and an earlier launcher-test startup failure whose cause remains unconfirmed; its targeted and full-suite reruns passed, and startup diagnostics were improved without relaxing the test.

Pytest creates a separate database, upload directory, and secret directory for each process before importing the application. It ignores inherited deployment/storage values and removes its own fixtures after a successful run; failed fixtures remain under `.tmp/test-runs/` for diagnosis. See [Testing strategy](docs/TESTING_STRATEGY.md) for the isolation contract and explicit PostgreSQL integration checks.

GitHub's `postgres-workers` job is configured to run 85 job-safety, storage-cleanup, image-write recovery, and login-admission cases against a disposable PostgreSQL 16 service. All 85 passed locally on 2026-09-13, including eleven login cases for concurrent HTTP/DB admission, completion fencing, rollback, expiry cleanup, and migration preservation. Each case migrates its own newly created schema to Alembic head and removes that schema afterward. These rerun a subset of the product tests against a different database; they are not 85 additional distinct cases or evidence of a deployed production database. Use the checks attached to the exact commit for GitHub CI status.

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

The historical `3388291` baseline was rechecked on GitHub on 2026-09-13: [verification run 33999316498](https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter/actions/runs/33999316498) and [supply-chain run 33999316535](https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter/actions/runs/33999316535) both completed successfully. Verification recorded 368 passed and one Windows-only skip on Linux, plus 61 PostgreSQL job-safety passes. Those 61 checks rerun a subset against a different database; they are not 61 additional distinct product tests. They do not verify the later ngrok patch; each revision requires its own evidence.

On **2026-09-13**, rerunning the release gate still reported **77 missing evidence fields** (36 release, 29 walkthrough, 12 acceptance). That count is a dated template-status snapshot, not the complete count of outstanding engineering tasks. No target deployment, live ngrok session, installed HAI registration, marketplace submission, or human acceptance was performed as part of this README update.

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
| Startup reports `extra_forbidden` for legacy URL/Selenium keys | The web app's `.env` still contains the legacy-only example section | Remove that section from the web app configuration; do not relax configuration validation or print secrets to diagnose it |
| Validation lists missing fields/images | The package is intentionally not ready | Correct each item, save, and validate again |
| Job is `needs_user_action` | The assisted package is ready | Open the platform, complete it deliberately, then record the result |
| Worker is unhealthy | No recent heartbeat | Inspect worker logs, environment, database reachability, migration head, and pause state |
| Worker is paused | Persistent emergency stop is active | Inspect the recorded reason; resume only after the incident is resolved |
| Autosave failed | Visible form changes were not persisted | Keep the page open, inspect the request ID/connectivity, and use **Save** to retry |
| Migration mismatch | Database is behind Alembic head | Back up first, stop all API and worker processes, then run `alembic upgrade head` with the intended database configuration |
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

There are both **unfinished implementation/integration tasks** and **external evidence/signoff requirements**. Filling out the evidence templates does not fix code gaps, and fixing code cannot supply a person's acceptance.

The launch owner must agree the intended product scope. Safe ngrok exposure is required before offering the tunnel route; automatic HAI synchronization needs a compatible consumer before it can be promised. Official marketplace publishing is future work unless it is explicitly made part of the accepted launch scope. An assisted/manual release must say so clearly; it must not be sold as fully automated publishing.

| Remaining work | Responsibility and completion proof |
| --- | --- |
| Revised ngrok path acceptance | Operator: real-agent compatibility, public access policy, target-machine lifecycle checks, and live local/public API plus exact-worker readiness evidence; local adversarial tests are implemented |
| Actual HAI ingestion | Integrator and HAI operator: compatible authenticated transport/format, paging and deletion policy, real create/update/delete ingestion evidence |
| Long-running/external publishing guarantees | Developers and future provider integrator: lease renewal, provider idempotency and ambiguous-outcome reconciliation before enabling official publishing |
| Production environment and human acceptance | Deployment/acceptance owner: the evidence below, including accepted scope and risks |

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

### Client handoff summary

> The review branch provides a locally verified listing-preparation app, a Windows standalone build recipe, and a manual HAI file handoff. Marketplace publication remains assisted/manual. Production launch still needs the agreed implementation scope completed, target deployment details, PostgreSQL migration proof, production secrets/CORS/storage confirmation, API and worker evidence, backup/restore and edge rate-limit evidence, a real-user walkthrough, manual accessibility QA, and named final acceptance. A passing local or CI test run is not that signoff.

## License and third-party services

No repository-level `LICENSE` file is currently present. Do not assume permission to copy, redistribute, sublicense, or commercially reuse the code beyond rights you already have; the repository owner should add an explicit licence before third-party distribution or contribution.

Marktplaats, Koopplein, Nextdoor, eBay, Tweedehands, ngrok, PostgreSQL, S3 providers, and other named services retain their own terms, privacy policies, trademarks, technical restrictions, and account requirements. This repository does not grant provider authorisation. The deployment/acceptance owner must review current dependency licences, marketplace terms, data-processing obligations, storage region/retention, and official API permissions before launch.

---

For a quick product walkthrough, begin with the [User guide](docs/USER_GUIDE.md). For deployment work, begin with [Release readiness](docs/RELEASE_READINESS.md) and [Operator runbook](docs/OPERATOR_RUNBOOK.md). For development, begin with [Architecture](docs/ARCHITECTURE.md) and run `python scripts/verify.py` before submitting changes.
