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

The standalone profile uses SQLite and local image storage. It is intended for one Windows operator, including access through a private ngrok tunnel; multi-user production deployments should use PostgreSQL and the production Compose definition.

## Verified Portable Build

The 2026-09-05 worker-recovery build has SHA-256 `68bab4a5d1e371e4a1fd91b8ce367f218ea87a49a2ed427a628450fafc5f9416`. Its clean-directory HTTP workflow passed API/worker health, dashboard, image upload, HAI metadata, malformed-cursor rejection, repeated-failure idempotency, and separate-worker retry through `needs_user_action`. See the [verification report](FINAL_VERIFICATION_REPORT.md) for current evidence and limits; the older build below is historical evidence, not the current binary.

The finalized 2026-08-09 local build produced a 43,670,075-byte executable with SHA-256 `6f791859c6bb70101e85b0c5c3ab417f5e962b12b2e52869b1c2df75bcfa1ed2`. A clean-directory runtime test reached Alembic head `20260809_0013`, reported a healthy API and worker, and created the expected database and secret; an exact-source rebuild passed the same API/worker smoke. One-file startup took about 99–130 seconds on this Windows host while Windows extracted/scanned it; later behavior depends on the machine and security software.

## Ngrok

Install and authenticate ngrok, then run:

```powershell
.\scripts\start-ngrok.ps1
```

Use `-Domain your-domain.ngrok.app` when the account has a reserved domain. The script starts its own ngrok process with the inspection API disabled, discovers the URL only from that process's JSON log, sets restrictive bearer/CORS values, waits for local API and worker health, verifies public HTTPS health, and cleans up only the processes it created.

`-VerifyOnly` performs the checks and stops the test services. It fails closed if ngrok cannot allocate an endpoint. Do not enable pooling merely to work around `ERR_NGROK_334`: pooling could route one public address to unrelated local services. Stop the conflicting endpoint in the ngrok account or provide a separate domain/tunnel slot instead.
