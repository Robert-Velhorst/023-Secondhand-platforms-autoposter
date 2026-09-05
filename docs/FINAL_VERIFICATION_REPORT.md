# Final Verification Report

## Repeated and concurrent enqueue verification — 2026-09-05

Target: working checkout based on `d90d95e53f97c5d9e9bca67c33267481c9055ec7`, with enqueue idempotency and transaction-isolation repairs.

- Five failing regression cases reproduced duplicate-key errors for existing failed/skipped jobs, a simultaneous enqueue race, an invalid-account error invalidating the caller's session, and an actual repeated publish API request after validation failure.
- Enqueue now reuses the exact existing key in every state. New job and initial log insertion share a savepoint; a concurrent duplicate returns the persisted winner, while unrelated integrity errors still propagate. Caller-owned pending work is flushed outside the savepoint and preserved when the duplicate is recovered. Repeating a failed request is not an implicit retry.
- Final full local gate passed: Ruff, compilation, **262 tests in 50.69 seconds**, and doctor. The development default-secret warning remains; the local database is at Alembic head `20260809_0013`.
- All **19 job-safety tests passed on PostgreSQL 16.15 in 51.51 seconds**, each using a newly created schema migrated from empty to Alembic head. The final cases include a forced two-connection missing-key race, one resulting job/log, and preservation of both callers' pending records, alongside the earlier worker/retry concurrency coverage. The same cases passed on isolated SQLite in the full suite.
- Independent read-only review found no introduced blocker. Its suggested coverage improvement—preserving caller work specifically on the recovered duplicate-key path—was added to the forced-race case before the final SQLite and PostgreSQL runs.
- PostgreSQL cleanup confirmed zero `jobtest_*` schemas. The dedicated disposable container was stopped and confirmed absent; no production database was used.
- Windows executable rebuilt with SHA-256 `02573cfac5ce7333427255a0295b70bd743902bd2e8805bf6ebdbb946602f863`. Fresh isolated executable HTTP checks passed: API and separate-worker health, dashboard HTTP 200, private image upload, HAI metadata, and malformed-cursor HTTP 422.
- The executable's worker processed an incomplete listing to `failed`. Repeating the publish request returned HTTP 200 with the same failed job and one attempt. After correcting the listing, explicit retry returned `queued`, and the separate worker produced `needs_user_action` with two attempts. The test processes were stopped afterward.
- This verifies local and disposable-database behavior, not exactly-once external publication, long-running lease/crash recovery, target-environment load or deployment, a real HAI consumer installation, manual accessibility, or client acceptance. Those requirements remain open.

## Job-claim and concurrent-worker verification — 2026-09-05

Target: working checkout based on `97f8b88baf90040b2dda0e52425fc6f5c7ffa433`, with job-claim and retry repairs.

- Seven failing regression cases reproduced unwanted execution of another worker's running job, immediate stale recovery after reclaiming an old attempt, active-job retries restarting work, retries bypassing `JOB_PROCESS_INLINE=false`, and inline execution bypassing scheduled backoff.
- Public job processing now requires a successful due-job claim; worker execution uses its already-claimed IDs. Claims clear old attempt timestamps. Retries preserve active work, use a conditional status/version update, and respect the separate-worker setting.
- Final full local gate passed: Ruff, compilation, **253 tests in 91.13 seconds**, and doctor. The development default-secret warning remains; the local database is at Alembic head `20260809_0013`.
- The initial **10 job-safety checks passed on PostgreSQL 16.15 in 91.83 seconds**. Each case ran Alembic migrations from empty in a fresh isolated schema. Two scenarios used four simultaneous database sessions to process 24 jobs each: missing-field failures and valid assisted packages, with exactly one recorded attempt per job. The same scenarios passed on SQLite. These are real database/session checks, not separate OS worker-process stress tests.
- Independent read-only review found no introduced blockers and identified a version-guard coverage gap. An eleventh case now verifies that a delayed retry cannot restart newer work which has already returned to the same terminal status. It failed with the timestamp predicate temporarily removed and passed after restoration; the final full local gate includes it. The CI PostgreSQL job runs all eleven cases.
- Added a dedicated `postgres-workers` GitHub Actions job to retain the migrated PostgreSQL regression coverage. Test credentials are confined to its disposable service. No production credentials or existing application database were used.
- PostgreSQL cleanup confirmed zero `jobtest_*` schemas, then the dedicated container was stopped and confirmed absent.
- Windows executable rebuilt with SHA-256 `0440e8994706825fa6dbba2674cc7800e34bfe85d65245084441b65e927ca69a`. Fresh isolated Windows 11 executable HTTP checks passed: API/worker health, dashboard, private image upload, HAI incremental metadata, and malformed-cursor HTTP 422.
- The executable's actual separate worker processed an incomplete listing once to `failed`; after correcting the listing, the retry API returned `queued` without increasing attempts, and the worker subsequently produced `needs_user_action` with two total attempts. Test processes were stopped afterward.
- This does not prove exactly-once external publication, long-running lease-expiry safety, target-environment load, production deployment, a real HAI consumer installation, manual accessibility, or client acceptance. Those requirements remain open.

## Test-data isolation verification — 2026-09-05

Target: working checkout based on `f8e765275621fdc2fe5583fc97b5d16332adc9a8`, with centralized pytest configuration and process-specific storage.

- Reproduced a test collection-order bug using a disposable sentinel database: an inherited `DATABASE_URL` could select application data before individual test modules installed their test settings. The worker test fixtures then changed that database. No real application data was used for this reproduction.
- Pytest now selects isolated SQLite, upload, and secret paths before application database imports, resets inherited deployment/storage settings to test defaults, and stops collection if the database module was already loaded.
- Real subprocess regression checks passed: the sentinel database remained byte-for-byte unchanged, existing uploads were preserved, production/S3 settings were overridden, two runs used different paths, successful fixtures were removed, and preloaded database imports stopped safely. Failed-run fixtures remain available for diagnosis.
- Final full local gate passed: Ruff, compilation, **242 tests in 109.55 seconds**, and doctor. The local development default-secret warning remains; the database is at Alembic head `20260809_0013`.
- Removed the obsolete shared test-database setting from CI. The doctor step remains separate from pytest and checks the operator's current configuration.
- Application runtime code did not change in this pass; the Windows executable was not rebuilt. Target deployment, live concurrent workers, HAI consumer integration, manual accessibility, and client acceptance remain separate outstanding checks.

## Read-path resource verification — 2026-09-05

Target: working checkout based on `62c52f7438d1dbb28f9d348f6b57f872dbc56673`, with worker health, analytics, and action-center read optimizations.

- Full local gate passed: Ruff, compilation, **240 tests**, and doctor. The development default-secret warning remains expected.
- All six new resource/behavior checks passed on SQLite and on a real, disposable PostgreSQL **16.15** server. The PostgreSQL database migrated from empty to Alembic head `20260809_0013`. Tests cover bounded object loading, exact counts, owner scope, stale/paused worker reporting, all reminder types, priority, and the top-20 limit.
- Synthetic before/after benchmark returned identical normalized responses for all three paths. Peak Python allocations decreased by 90.4% for worker health, 95.5% for analytics, and 99.2% for action-center reminders. See [Performance and scale](PERFORMANCE_SCALE_BASICS.md) for fixture, timings, method, and limitations.
- Windows executable rebuilt and exercised through actual HTTP requests with fresh isolated SQLite data: API, separate worker, dashboard aggregates/action center, image upload, HAI incremental metadata, and malformed-cursor handling passed.
- Executable SHA-256: `a3f1071f9c291bec989700cbe96f5904769d585566a9e8756af8d0dc75ada93f`.
- Target deployment, concurrent PostgreSQL query/worker measurements, real HAI consumer integration, manual accessibility, and client acceptance are still outside this local verification result. The full product goal remains open.

## HAI integration regression verification — 2026-09-05

Target: working checkout based on `111bff6926316bd0d2c56be34b6800796ff5ce00`, with the HAI cursor and related-record feed fixes described below.

- Reproduced HTTP 500 for oversized HAI cursor integers and incorrect acceptance of malformed cursor content before the fix. Invalid cursors now return HTTP 422; the maximum supported integer remains accepted.
- Reproduced missing incremental events after image uploads and marketplace selection changes. Image addition/deletion and marketplace selection/deselection now update HAI metadata through transactional change records.
- `python scripts/verify.py`: passed, including Ruff, compilation, **234 tests**, and doctor. The development default-secret warning remains expected; migrations are at `20260809_0013`.
- Focused HAI regression suite: **11 passed**.
- Windows executable rebuilt using Python 3.13.14/PyInstaller 6.22.0. SHA-256: `e7ca55217033b4ec13a169862fd2af711ad563f0e3d533c67ddf8fe338a74113`.
- Fresh isolated executable run on Windows 11: API and separate worker healthy; browser entry point served; SQLite and persistent secret created; registration, HAI token creation, private image upload, marketplace selection, incremental HAI metadata, and oversized-cursor HTTP 422 all passed through actual HTTP requests.
- `scripts/start-ngrok.ps1 -VerifyOnly -Port 18762`, with an isolated data directory: passed local API/worker startup and public HTTPS health, then stopped its test services. The earlier endpoint-allocation blocker did not recur in this run. This proves temporary tunnel access; production hosting and HAI-side registration remain separate requirements.
- Release gate: still blocked, **77 missing evidence fields**. This regression verification does not supply target PostgreSQL deployment proof, a real HAI installation's consumer results, or manual accessibility/client acceptance.

The earlier evidence below is retained as a dated historical record. Its test count and executable hash refer to that earlier build.

## Earlier verification — 2026-08-09

Date: 2026-08-09

Verification target: `agent/production-launch-hardening` working checkout based on starting commit
`0fa6d381a47139038d68b857537a02070740efae`. The exact release commit is recorded after the verified
changes are committed and pushed to the existing draft PR.

## Verification Command

```bash
python scripts/verify.py
```

Result: passed from the working checkout in one complete gate run.

## Gate Results

- Ruff lint: passed.
- Python compile checks: passed.
- Pytest suite: passed, 226 tests in one run.
- Focused HAI, private storage, Windows, deployment, architecture, and documentation suite: passed, 21 tests.
- Alembic CLI from an empty database: passed at head `20260809_0013`.
- Doctor: database, migrations, uploads, adapters, and legacy isolation passed at head `20260809_0013`; local default-secret warning expected.
- Windows executable: clean build and clean-data launch passed, followed by an exact-source rebuild after the cursor edge fix; API and worker healthy, database and persistent secret created, final executable size 43,670,075 bytes, SHA-256 `6f791859c6bb70101e85b0c5c3ab417f5e962b12b2e52869b1c2df75bcfa1ed2`.
- HAI connector: discovery, hashed/expiring/revocable token lifecycle, owner isolation, cursor feed, tombstones, malformed-cursor handling, and read-only contract passed.
- Image privacy: raw storage paths removed from listing responses; owner-authenticated local/S3 reads, independent duplicate storage, reference-safe deletion, and account purge passed.
- Dependency audit: installed-environment strict audit found no known vulnerabilities. The local Python 3.14 requirements-file resolver timed out; the Python 3.12 GitHub supply-chain job remains the authoritative requirements-file check.
- Ngrok launcher: process/log isolation and fail-closed cleanup passed; live allocation is externally blocked by the account's existing endpoint (`ERR_NGROK_334`).
- Docker engine: read-only version/config query timed out on this host, so a current image build and target PostgreSQL container drill remain unverified locally.
- Reconciliation: passed with zero issues on the fresh migrated database.
- Operator control: status healthy and job processing not paused.
- Sanitized support bundle: generated successfully.
- Production Compose configuration: passed when supplied the required external env file and upload volume.
- Earlier browser workflow evidence covers registration, onboarding, listing creation, autosave, action-center refresh, and a 390 x 844 responsive check. The requested in-app Browser runtime failed to initialize during this hardening pass, so the new HAI settings and private-image flow still require fresh manual visual/accessibility evidence.
- Release gate: blocked as expected until external evidence records are complete.
- Final response preflight: blocked as expected until release gate and final acceptance are ready.

## Expected Local Warning

Doctor reports that development uses the default `SECRET_KEY`. This is correct for this isolated
local run and does not weaken the production guard, which rejects default or short secrets,
unrestricted CORS, non-PostgreSQL databases, non-HTTPS public URLs, or unsafe feature flags.

## Release Gate Snapshot

`python scripts/release_gate.py --json` reports `blocked` with a total missing evidence count of 77.
`python scripts/final_response_check.py --json` also reports `blocked` because:

- release readiness still says not release-ready yet;
- deployment and security evidence contains `Not captured` fields;
- the real non-technical user walkthrough contains `Not captured` fields;
- final acceptance is not accepted.

## Current Release Assessment

The repository passes its local implementation and automated verification components. It is ready
for a demo/hardening review and for deployment into a supplied staging environment.

It is not yet a final client launch release. Remaining external gates are target deployment access,
PostgreSQL migration proof, production secret/CORS/storage confirmation, API and worker process
evidence, backup/restore proof, edge rate-limit evidence, a real-user walkthrough, manual keyboard/
zoom/screen-reader QA, acceptance of assisted marketplace posting, and named final signoff.
