# Testing Strategy

This strategy defines the current test layers, the verification gate, and the gaps that remain before release.

## Verification Gate

Run the full local gate before pushing:

```bash
python scripts/verify.py
```

The gate runs:

- Ruff lint for `app`, `tests`, `migrations`, and `scripts`
- Python compile checks for `app`, `tests`, and `migrations`
- the full pytest suite
- `python -m app.doctor --json`

Doctor warnings are allowed for local development defaults; doctor errors fail the gate.

GitHub Actions runs the same command on pushes and pull requests to `main` via `.github/workflows/verify.yml`.

The same workflow also runs a `postgres-workers` job against a disposable PostgreSQL 16 service. Its nineteen job-safety tests use real connections and migrations, not merely compiled PostgreSQL SQL.

## Current Test Layers

| Layer | Files | Purpose |
| --- | --- | --- |
| Architecture boundaries | `tests/test_architecture.py` | Verifies auth/system routes and shared request dependencies stay split from product routes. |
| API smoke and route contract | `tests/test_api.py`, `tests/test_api_hardening.py` | Core listing/account/template flow, platform metadata, direct detail/delete routes, request IDs, metrics, pagination, filters, and structured errors. |
| Acceptance workflow | `tests/test_acceptance_workflow.py` | Seller setup-to-portability API acceptance flow covering accounts, templates, mappings, listing/image creation, quality, validation, assisted jobs, analytics, export/import, and audit activity. |
| Owner isolation | `tests/test_owner_isolation.py` | Cross-user visibility and mutation boundaries for owned listings, jobs, accounts, templates, and category mappings. |
| Auth/security | `tests/test_auth_security.py`, `tests/test_api_rate_limit.py` | Password hashing, login/logout/session behavior, token revocation, bearer-only auth posture, database-backed hashed failed-login throttling with expiry/success clearing/`Retry-After`, and general API throttling. |
| SaaS/account readiness | `tests/test_saas_readiness.py` | Personal-account readiness contract, billing-free status, workspace deferral, and owner-scoped usage counts. |
| Storage | `tests/test_storage_uploads.py`, `tests/test_startup_safety.py` | Filename sanitization, MIME/signature validation, duplicate detection, delete/reorder behavior, metadata persistence, local file cleanup, S3-compatible object writes/deletes, and storage config validation. |
| Category mappings | `tests/test_category_mappings.py` | Mapping CRUD/upsert/patch behavior and mapping use in validation/publish output. |
| Official API foundations | `tests/test_ebay_oauth.py`, `tests/test_platform_rate_limits.py` | eBay OAuth state safety, token exchange, token refresh, secret-store redaction, sandbox Inventory API probe shape, and quota-header backoff. |
| Jobs/worker | `tests/test_worker.py`, `tests/test_job_state.py`, `tests/test_platform_rate_limits.py`, `tests/test_config.py` | Database-backed queue processing, worker empty-queue behavior, job detail route, filtering/sorting/pagination, atomic claims, PostgreSQL `SKIP LOCKED` claim SQL, stale-running recovery, state transitions, user-confirmed manual completion, platform cooldown overrides, and official API quota-header backoff. |
| Listing revisions/idempotency | `tests/test_listing_revisions.py` | Revision increments and publish idempotency boundaries. |
| Concurrent job safety | `tests/test_job_claim_safety.py` | Due-only public claims, worker-owned execution, reclaimed timestamps, active and delayed retry safety, inline-worker separation, real concurrent sessions, and optional migrated PostgreSQL fixtures. |
| Domain model | `tests/test_domain_model.py` | Listing aggregate cascade behavior for images, drafts, mappings, jobs, logs, and attempts. |
| Data invariants | `tests/test_data_invariants.py` | Money/weight validation, currency/tag/category-attribute normalization, and listing condition/status choices. |
| Data portability | `tests/test_data_portability.py` | Sanitized JSON export/import, listing CSV round trip including category attributes, image ZIP export, settings, mappings, and account metadata. |
| Diagnostics/startup/migrations | `tests/test_doctor.py`, `tests/test_config.py`, `tests/test_startup_safety.py`, `tests/test_migrations.py` | Doctor checks, `.env.example` runtime-setting synchronization, startup safety guards, production-like config validation, SQLite migration smoke coverage, and PostgreSQL dialect schema rendering. |
| Observability | `tests/test_observability.py` | Structured JSON log formatting and request log metadata. |
| Internationalization | `tests/test_internationalization.py` | Locale metadata, frontend copy catalog presence, Dutch shell copy, locale selector, and English fallback contract. |
| Accessibility | `tests/test_accessibility_audit.py` | Static dashboard smoke checks for labeled controls, named buttons, image alt text, landmarks, headings, and live status regions. |
| Browser workflow evidence | `scripts/browser_e2e_workflow.cjs`, `tests/test_browser_e2e_workflow.py`, `docs/BROWSER_E2E_WORKFLOW.md` | Executed Chromium workflow for registration, listing save, image upload, validation, assisted job queueing, manual completion, JSON export, and account deletion. |
| Release readiness controls | `tests/test_release_readiness.py`, `tests/test_release_gate.py`, `docs/RELEASE_READINESS.md`, `docs/RELEASE_EVIDENCE_RECORD.md`, `scripts/release_gate.py` | Launch evidence gates, explicit missing-evidence placeholders, machine-readable blocked/ready status, section-aware missing-evidence JSON output, missing-evidence counts, and anti-overclaim release blocker language. |
| Final response controls | `tests/test_final_response_check.py`, `docs/FINAL_RESPONSE_REQUIREMENTS.md`, `scripts/final_response_check.py` | Machine-readable preflight for the final release answer, required statement coverage, release-gate status propagation, and blocked response status while launch evidence is incomplete. |
| Verification report controls | `tests/test_final_verification_report.py`, `docs/FINAL_VERIFICATION_REPORT.md` | Local verification report date, test count, and release-gate blocker status stay explicit. |
| Progressive gate controls | `tests/test_progressive_stabilization_gates.py`, `docs/PROGRESSIVE_STABILIZATION_GATES.md` | Stabilization gate status stays aligned with the machine-checkable release gate. |
| External evidence backlog | `tests/test_external_evidence_backlog.py`, `docs/EXTERNAL_EVIDENCE_BACKLOG.md` | Remaining partial phases stay listed with their required external evidence and capture records. |
| Non-technical user evidence controls | `tests/test_non_technical_user_simulation.py`, `docs/NON_TECHNICAL_USER_SIMULATION.md`, `docs/NON_TECHNICAL_USER_WALKTHROUGH_RECORD.md` | Proxy scenario, observed-user record requirements, manual-posting comprehension checks, and explicit external-evidence blocker language. |
| Legacy isolation | `tests/test_legacy_quarantine.py` | Ensures legacy browser automation imports do not leak into the web app path. |

## Data And Isolation

- `tests/conftest.py` selects test configuration before application modules are imported. It replaces inherited runtime/deployment values with known test defaults, including local storage and disabled external credentials.
- Every pytest process receives its own SQLite database, upload directory, and secret directory under `.tmp/test-runs/run-*`. The configured application database and storage paths are ignored by pytest.
- If an application database was preloaded by a plugin, collection aborts before destructive schema fixtures can run.
- Test modules reset SQLAlchemy metadata only in the isolated test database. Successful runs dispose the engine and remove their own verified test directory; failed-run fixtures are retained for diagnosis.
- `tests/test_test_environment.py` launches real pytest subprocesses to verify a sentinel application database remains byte-for-byte unchanged, production/S3 settings are overridden, run paths are unique, successful artifacts are removed, and early application imports fail safely.
- Platform cooldown tests either disable cooldowns with `PLATFORM_RATE_LIMIT_SECONDS=0` or use `PLATFORM_RATE_LIMIT_OVERRIDES` for platform-specific behavior.
- Tests do not require browser automation, external marketplace credentials, or real platform network calls.

The doctor step in `scripts/verify.py` runs separately against the operator's current configuration. A target PostgreSQL integration drill must explicitly select a disposable database; setting `DATABASE_URL` while invoking pytest does not opt out of isolation.

## Coverage Priorities

### PostgreSQL Job Safety Drill

The default suite runs `tests/test_job_claim_safety.py` on isolated SQLite databases. To run the same cases on PostgreSQL, first provision a **disposable** database whose name starts with `autoposter_job_test_`, then run:

```bash
python -m pytest -q tests/test_job_claim_safety.py --job-postgres-url "postgresql+psycopg://USER:PASSWORD@HOST:5432/autoposter_job_test_local"
```

Replace the uppercase connection fields with credentials for the disposable test service only. Do not supply a production database. The fixture rejects other database-name prefixes, creates a random schema with `CREATE SCHEMA` (never reuses one), migrates it from empty to Alembic head, and drops only that schema during cleanup. The account needs permission to create and drop its test schemas. This explicit option does not change the application database selected by the global test-isolation fixture.

Coverage includes another request trying to execute a worker's claim, reclaimed-job timestamp freshness, queued/running retry protection, delayed retry requests, disabled inline processing, scheduled backoff, and four simultaneous sessions draining 24 jobs. Both real assisted-package success and missing-field failure paths assert exactly one attempt per job. Image metadata is synthetic; these concurrency cases do not validate image-file delivery or contact marketplaces.

Enqueue coverage verifies unchanged reuse across all six job states and forces two concurrent sessions to observe the same missing key before inserting. The race must produce one job and one queue log while preserving both callers' pending user records. A separate invalid-account case checks that unrelated integrity errors propagate without invalidating the outer session or discarding earlier listing changes. The API revision suite additionally checks that repeating a publish request after validation failure returns HTTP 200 with the original failed job and unchanged attempt count.

The queue claim transaction remains short and uses PostgreSQL `SKIP LOCKED`; see the [PostgreSQL locking documentation](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE). These cases do not prove exactly-once behavior during external provider calls, lease expiry during unusually long work, distributed cooldown enforcement, or target-host load capacity.

### Ongoing Priorities

1. Idempotency, retries, and worker concurrency for publishing jobs.
2. File safety: upload validation, storage paths, duplicate handling, ordering, and deletion.
3. Data portability and privacy: no password/session/platform secrets in exports.
4. Assisted-posting honesty: tests should verify prepared packages and user-action states instead of fake automated success.

## Remaining Gaps

- Browser-executed accessibility, keyboard navigation, and cross-browser matrix tests.
- Live multi-worker concurrency tests against the target PostgreSQL database.
- Broader PostgreSQL-backed integration coverage beyond the job-safety and dashboard-read drills.
- Frontend state consistency tests for filters, pagination, and edit modes.
- Official API/OAuth sandbox tests when future platform API integrations are added.
