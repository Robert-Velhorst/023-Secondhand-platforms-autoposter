# Final Verification Report

## Stale-recovery race and resource-bound verification — 2026-09-05

Target: working checkout based on `02e17572f679a1bcdae797327f88e097a16bae78`, with conditional stale recovery, bounded worker recovery, and 16 additional job-safety cases.

- The initial race reproduction produced **11 failures in 4.14 seconds**. A second connection committed a newer completion, reclaim, or update after the real stale-selection query; recovery overwrote every newer state with `queued`. Two simultaneous recoverers also both reported success. Both null and non-null start timestamps were exercised. Two additional failing cases showed one worker cycle recovering all six stale rows even with batch sizes zero and two.
- Recovery now selects only IDs and update/start timestamps. Each update must still match the observed running version; only a winning update records a recovery log, in the same transaction. The worker passes its batch limit into recovery. Direct helper callers retain the optional unbounded mode for compatibility. No schema migration, claim-token lease, or external-adapter behavior change is included.
- Focused job, worker, and resilience checks passed **56 tests in 36.48 seconds**. The extended bounded-backlog cases passed **2 tests in 4.06 seconds**, including repeated cycles draining the remaining jobs. Independent read-only review found no blocking defect. Its suggested paused/disabled-recovery and log-failure rollback controls were added and passed **3 tests in 14.02 seconds**, with a real database foreign-key failure for the rollback case.
- The final full gate passed Ruff, compilation, **312 tests in 150.49 seconds**, and doctor, including the three final review controls. The local database is at Alembic head `20260809_0013`; the development default-secret warning remains.
- The Windows executable rebuilt successfully with SHA-256 `ceff830691a098145cfbb453c89eb5792368af1f5b5eb829535c516cab6af92f`. Its isolated HTTP workflow passed API/worker health, dashboard, private image upload, HAI incremental metadata and malformed-cursor handling, account-isolation checks, idempotent failed-job reuse, and explicit retry. A deliberately abandoned running row in the harness's fresh database was recovered by the executable's separate worker to `needs_user_action`, with two total attempts and exactly one recovery log. No marketplace calls were made.
- The local migrated PostgreSQL **16.15** run completed **36 tests in 439.39 seconds**, including all recovery-race and batch cases. It began before the three final review-control tests were added. Despite slow local fixture migrations, the same run was preserved to completion. A separate query confirmed zero remaining `jobtest_*` schemas afterward.
- On code commit `21d3717045ed3eb88fe03127cd01866b8a241554`, [GitHub verification](https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter/actions/runs/33992291382) passed the final **312-test suite in 22.98 seconds** and all **39 migrated PostgreSQL cases in 20.63 seconds**, including the three review controls. The dependency audit also passed. This is disposable-database and CI evidence, not target-production proof.
- Cleanup: the packaged application's test processes exited, and no `SecondhandAutoposter` process remained. The disposable PostgreSQL service's stop request returned a Docker Desktop HTTP 500 error; container/volume removal is not confirmed. Only the dedicated test service was targeted; unrelated Docker services were not restarted or changed.
- Limits: returned candidates, Python memory, writes, and logs are bounded per worker cycle; total database scan/sort work is not guaranteed to be bounded. Large-running-set query-plan/index measurements remain a scaling follow-up. This fix does not renew/fence long-running external calls or establish exactly-once external publication. Target deployment, real HAI consumer integration, manual accessibility/user walkthroughs, and final acceptance remain open.

## Publishing-account boundary verification — 2026-09-05

Target: working checkout based on `e011d7891cc6566410f2735ccd7363623f4f7bdb`, with the publishing-account boundary fix and 23 additional tests.

- Before the fix, the focused regression run produced **14 failures and 2 legitimate-control passes**. It reproduced foreign-owner account IDs accepted in integer, numeric-string, and integral-float forms, invalid later selections causing partial request effects, and missing account checks in direct enqueue/retry/worker paths. A separate four-case worker/stale-recovery run captured the unauthorized account object actually reaching the adapter. Current assisted adapters ignore account credentials; these results do not show credential misuse or marketplace publication.
- `app/services/jobs.py` now resolves selected accounts with both the listing owner and target platform in the database query. Enqueue validates before idempotency lookup, retry validates before state changes, and execution validates before the adapter call. `app/api.py` preflights all selected accounts before revision/queue writes and returns a generic HTTP 404 for unavailable selections. Existing invalid jobs fail with a recorded attempt rather than reaching an adapter. No schema migration or historical-row rewrite is included.
- An additional adversarial case reproduced an SQLite `OverflowError` for account ID `2**63`. The shared helper now rejects out-of-range IDs before database binding. The final `tests/test_publishing_account_boundary.py` run passed **19 tests in 14.32 seconds**, including unchanged no-account and matching-account assisted packages and repeated-request idempotency. The nearest original job/revision/ownership/worker suites passed **35 cases in 14.01 seconds**.
- Four additional cases in `tests/test_job_claim_safety.py` use separate connections to change account owner/platform after valid enqueue and duplicate reuse, then verify rejection at duplicate enqueue or worker execution. The existing transaction-integrity test still exercises a real foreign-key failure after admission checks and preserves caller changes. These tests use the same session expiration behavior as the application.
- The final `python scripts/verify.py` run passed Ruff, compilation, **296 tests in 122.15 seconds**, and doctor. The development default-secret warning remains; the local database is at Alembic head `20260809_0013`. The no-account helper path adds no account lookup; selected-account lookups use the primary key plus owner/platform predicates.
- The final `scripts/build-windows.ps1` completed on Windows 11 with Python 3.13.14. Executable SHA-256: `36689a9eac563cc84451bfac28ed894f2eb7f01295a13dc3f43313d635c65de8`.
- Isolated HTTP checks against that executable passed API/worker health, dashboard, private image upload, HAI incremental metadata, malformed-cursor HTTP 422, repeated failed-job reuse, and explicit retry processed by the separate worker to `needs_user_action`. Two fresh users verified generic HTTP 404 for foreign and wrong-platform accounts with unchanged revision and no partial queue. The oversized account also returned HTTP 404; a matching account supplied as a numeric string produced an assisted package with one attempt. The test process tree exited; a process check found no remaining `SecondhandAutoposter.exe` process. These checks do not contact marketplaces or install a consumer in HAI.
- All **23 job-safety tests passed on disposable PostgreSQL 16 in 187.65 seconds**, with each case migrating a new schema to Alembic head. This run preceded the final oversized-ID guard; the guard does not affect these cases. Independent read-only review found no concrete surviving bypass or introduced legitimate-flow regression in the candidate source. A later standalone schema-count query timed out during local Docker delays, so that extra zero-schema observation was not obtained; the suite itself completed fixture cleanup successfully. The dedicated container stop completed, and subsequent inspection confirmed both the container and its anonymous data volume no longer existed. No production database was used.
- `python scripts/release_gate.py --json` still returns the expected blocked status with **77 missing evidence fields**. This is a deployment/acceptance gate, not a failure of the automated application suite.
- Remaining full-goal requirements include target deployment, long-running lease/crash safety for external actions, a real HAI consumer installation, manual accessibility/user walkthroughs, and client acceptance. This account-boundary repair does not establish final production readiness or automatic marketplace publishing.

## Worker database-error recovery verification — 2026-09-05

Target: working checkout based on `6d777a8cf577c391f5a5536ddf3d71f80c1fad41`, with runtime worker recovery and eleven new resilience tests.

- Five regression failures reproduced worker termination at real SQLite queue-claim and heartbeat-write locks, plus missing recovery for operational/interface/pool-timeout errors. The fixed loop closes sessions before waiting, uses capped exponential backoff, resets after a complete successful cycle, and logs only safe diagnostic fields. Startup/configuration, programming/integrity errors, and shutdown signals still propagate.
- Final full local gate passed: Ruff, compilation, **273 tests in 79.02 seconds**, and doctor. The local development default-secret warning remains; the local database is at Alembic head `20260809_0013`.
- A full-suite test-order failure was traced to Alembic logging configuration disabling existing loggers. The resilience fixture explicitly restores its logger for each test; migration tests followed by resilience tests passed **14 cases in 23.97 seconds**, and the final full gate includes that repair.
- Independent read-only review found no introduced runtime blocker. Its suggested long-poll and open-session cleanup cases were added before the final full gate. The tests verify actual database effects, released connections, bounded delays, reset after recovery, and suppression of raw SQL/error details in warning logs.
- Windows executable rebuilt with SHA-256 `68bab4a5d1e371e4a1fd91b8ce367f218ea87a49a2ed427a628450fafc5f9416`. Isolated Windows HTTP workflow passed API/worker health, dashboard, image upload, HAI incremental metadata, malformed-cursor HTTP 422, repeated failed publish HTTP 200, and explicit retry followed by separate-worker `needs_user_action` with two attempts. Test processes were stopped afterward.
- Separate source-worker and Windows-executable processes each survived a real stop/start of disposable PostgreSQL 16.15 on a fixed local port, resumed with the same process and worker identity, and processed a new incomplete listing once to `failed` with a recorded heartbeat count of one. Docker's delayed restart in the Windows case extended the outage enough to reach the 60-second retry cap; after the database actually returned, the same executable worker recovered. The final drill returned `status: passed` for both runtimes. This is not target-deployment or external-publication evidence.
- The drill's process trees exited, and the dedicated PostgreSQL container and its disposable volume were removed. Container and process checks confirmed they were absent. No existing application database, production credentials, or marketplace calls were used.
- This does not establish production deployment, driver-call timeout guarantees, long-running lease/crash safety, exactly-once external publication, real HAI consumer installation, manual accessibility, or final acceptance. Heartbeat counts remain best-effort telemetry, especially after an ambiguous commit. These limits and intervention steps are documented in the operator runbook.

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
