# Windows 11 Standalone And Ngrok

## Build

From PowerShell:

```powershell
.\scripts\build-windows.ps1
```

The script creates an isolated build environment, builds `dist\SecondhandAutoposter.exe`, and writes a SHA-256 sidecar. The executable contains the frontend, application, Alembic migrations, and local worker. It does not contain user data or production credentials.

## Run Locally

Start `SecondhandAutoposter.exe`, or run the source launcher during development:

```powershell
.\.venv\Scripts\python.exe -m app.launcher
```

The launcher binds only to `127.0.0.1`, migrates the local database before startup, creates a persistent random secret, starts the API and worker separately, and opens the browser after health succeeds. Data is stored under `%LOCALAPPDATA%\SecondhandAutoposter` by default. Override that location with `AUTOPOSTER_DATA_DIR` for a controlled backup location.

The standalone profile uses SQLite and local image storage. It is intended for one Windows operator; multi-user production deployments should use PostgreSQL and the production Compose definition. Use a free local port and stop previous instances before running migrations against the same data directory. The ngrok helper is experimental and has the unresolved lifecycle risks below; a reserved URL alone is not private access control.

## Verified Portable Build

The 2026-09-06 frontend-delivery build has SHA-256 `abb2501ee4f0daca16bb32d0368c408ca5a5ad907d9aca1abc8b4aa5a10e4124`. The isolated executable passed API/worker health, migration head `20260905_0014`, uploads, account isolation, retry/recovery, and HAI-download checks. All four frontend assets, including the icon, matched source bytes and passed cache revalidation with body-free HTTP 304 responses. Test processes were stopped afterward. This verifies the local package, not production deployment or safe ngrok operation. Earlier build hashes below are historical.

The 2026-09-06 HAI-download build has SHA-256 `0d5daa88f4bd7bcbc2cf8380cfc96cff16a0cbbba8c8c143df62294bd4a2fe13`. A fresh isolated runtime passed API/worker health, migration head `20260905_0014`, the existing retry/account/recovery workflow, and the owner-only generic HAI download. Served frontend assets matched current source bytes. This build adds a manual file handoff, not automatic HAI synchronization or a signed production release. See the [current verification report](FINAL_VERIFICATION_REPORT.md#manual-hai-file-handoff-verification--2026-09-06).

The 2026-09-05 claim-fencing build has SHA-256 `ddb3c47b4fdc8b7f01f6a4ea63e27bac8fec0af053ba61b28683230cb7cfd635`. Its isolated runtime reached Alembic head `20260905_0014` and passed API/worker health, dashboard, uploads/HAI metadata, cursor rejection, account isolation, explicit retry, and recovery of an abandoned running job. Terminal claim identifiers were cleared and not exposed in the job API. Before upgrading an existing installation, stop every old executable/API/worker and back up its data; see the [upgrade procedure](OPERATOR_RUNBOOK.md#claim-fencing-upgrade). The following build records are historical.

The 2026-09-05 worker-recovery build has SHA-256 `68bab4a5d1e371e4a1fd91b8ce367f218ea87a49a2ed427a628450fafc5f9416`. Its clean-directory HTTP workflow passed API/worker health, dashboard, image upload, HAI metadata, malformed-cursor rejection, repeated-failure idempotency, and separate-worker retry through `needs_user_action`. See the [verification report](FINAL_VERIFICATION_REPORT.md) for current evidence and limits; the older build below is historical evidence, not the current binary.

The finalized 2026-08-09 local build produced a 43,670,075-byte executable with SHA-256 `6f791859c6bb70101e85b0c5c3ab417f5e962b12b2e52869b1c2df75bcfa1ed2`. A clean-directory runtime test reached Alembic head `20260809_0013`, reported a healthy API and worker, and created the expected database and secret; an exact-source rebuild passed the same API/worker smoke. One-file startup took about 99–130 seconds on this Windows host while Windows extracted/scanned it; later behavior depends on the machine and security software.

## Ngrok

**Do not use the current helper on a shared host or with sensitive data until lifecycle hardening is implemented and verified.** Source review on 2026-09-06 found:

- The tunnel starts before the application binds the port, without establishing port ownership. A pre-existing local service could be exposed.
- Cleanup selects new processes by matching executable path against a baseline, rather than a verified child-process tree. It can select unrelated concurrent launches and miss children using another executable path.
- Runtime log paths are shared across invocations, so concurrent runs are not isolated.
- Readiness checks call local/public `/api/health`, not `/api/worker-status`. The script's worker-verification message overstates what it checks.
- Environment changes remain in the calling PowerShell session after the script exits.

These findings are from the script's source, not a claim that an accidental exposure or unrelated-process termination was reproduced. Required follow-up is exclusive port ownership before exposure, reliable owned-process cleanup, per-run log isolation, independent worker-health verification, environment restoration, and occupied-port/concurrent-run tests. Do not treat older successful ngrok health checks as proof of those properties.

The current experimental interface, for controlled investigation only, is:

```powershell
.\scripts\start-ngrok.ps1
```

Install/authenticate ngrok and prepare the executable or Python environment first. Use `-Domain your-domain.ngrok.app` when the account has a reserved domain. The script passes `--inspect=false`, reads a URL from its redirected JSON log, sets restrictive bearer/CORS values, and checks local/public API health. Those controls do not resolve the ownership and cleanup gaps above. Use a dedicated PowerShell session for investigation.

`-VerifyOnly` performs those API checks and invokes the same limited cleanup logic; it does not independently prove worker health. The script stops if ngrok cannot allocate an endpoint. Do not enable pooling merely to work around `ERR_NGROK_334`: pooling could route one public address to unrelated local services. Resolve an endpoint conflict through an authorised operator. A temporary tunnel is not a production deployment.
