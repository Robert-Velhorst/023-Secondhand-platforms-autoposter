# Final Verification Report

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
