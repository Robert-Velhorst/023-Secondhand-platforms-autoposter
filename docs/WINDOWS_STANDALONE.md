# Windows 11 Standalone And Ngrok

## Build

Install Python 3.13 for packaging; the script creates its own build environment.
For source-mode execution, follow the [README setup](../README.md#local-development-setup).
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

The standalone profile uses SQLite and local image storage. It is intended for one Windows operator; multi-user production deployments should use PostgreSQL and the production Compose definition. Use a free local port and stop previous instances before running migrations against the same data directory. The revised ngrok lifecycle has local regression evidence, but still needs real-agent and access-policy acceptance; a reserved URL is not private access control.

### Startup ownership and shutdown

The current launcher reserves its IPv4 loopback socket and acquires an OS file lock on `.launcher.lock` **before** creating a secret, running migrations, or starting a worker. A duplicate launch fails without those side effects. The original socket remains reserved even if the API server closes its duplicate, and is released only after worker cleanup.

On Windows, the worker starts suspended, is assigned to a private Job Object, and only then runs. Descendants inherit that ownership; closing the job or crashing its owner terminates the owned tree. Cleanup does not enumerate all processes sharing an executable name. This is forced termination, not graceful completion of an in-flight job; the existing stale-job recovery rules still apply.

The data lock covers cooperating launchers using the same directory. It cannot stop an older build, a separately started API/worker, another application, or a different data directory sharing the same configured database. Stop those processes before upgrading. Keep `.launcher.lock` in place: deleting it is not a safe unlock procedure. Windows can briefly delay releasing locks after a crash; retry startup after the prior processes have stopped. See [Microsoft's file-lock lifecycle documentation](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfile).

The revised `start-ngrok.ps1` delegates to this launcher. In tunnel mode it first
owns the port and data lock, then starts owned ngrok, worker, and API process
trees. The separate API child receives the already-owned socket through an
owned stdin pipe (Windows socket sharing targets the actual interpreter PID,
not an assumed bootloader PID). The supervisor holds data ownership until all
request threads have been terminated with their process tree. If the API server
returns while request threads survive, a stop marker triggers cleanup; failure
to write that marker forces the dedicated API interpreter to exit. Normal local
mode retains its previous Uvicorn graceful-drain policy.

## Verified Portable Build

The latest 2026-09-13 browser-auth recovery build has SHA-256
`d5bedcb438ec7909c70fd223098f2373f278c391cb4d700a4afdd7a2f58bde73`.
Six Chromium flows passed against its actual loopback API at desktop
1366×900 and mobile 390×844: temporary session failure/retry, single-flight
sign-in, browser registration validation, mobile recovery layout, logout
availability during slow dashboard reads, and failed/retried logout. The
last flow verified the old token was rejected by the backend after retry.
Page identity, meaningful content, absence of framework overlays, screenshots,
and console checks passed; deliberately injected HTTP 503 errors were expected.
See [browser session recovery](AUTH_SECURITY_POSTURE.md#browser-session-recovery).

The packaged API/worker, registration, login, image/CSV, static-asset, and local
read-only HAI checks passed on the final run. An initial HAI consumer attempt
failed before its detailed output was captured; the wrapper now retains those
details, and a fresh isolated rerun passed. The first failure's cause remains
unresolved, so this is not evidence of fully stable or installed HAI operation.
Doctor passed all six checks against the isolated database. Owned test
processes and the disposable PostgreSQL container were stopped afterward.
Schema head remains `20260913_0016`. This is an unsigned review executable,
not production deployment or live-ngrok/manual-accessibility acceptance.
Earlier hashes below are historical.

The latest 2026-09-13 atomic-registration build has SHA-256
`107a5a85c71a6384ec62e372f2410cdbbbd66ff779054be5bbd149b65d606eea`.
Its real API passed a forced initial-session failure with no account left
behind, successful retry, authenticated profile access, and duplicate-email
conflict. Existing API/worker, migration, login, storage, CSV, assisted-job,
account-boundary, static-delivery, and producer-to-local-review-HAI checks
also passed. See the [registration verification record](FINAL_VERIFICATION_REPORT.md#atomic-registration-and-retry-recovery--2026-09-13)
and [uncertain-commit recovery guidance](AUTH_SECURITY_POSTURE.md#registration-transactions-and-recovery).
Schema head remains `20260913_0016`; no new migration was added. This unsigned
local review executable is not a production deployment, public ngrok
acceptance, or installed HAI release. Earlier hashes below are historical.

The latest 2026-09-13 login-account-state build has SHA-256
`cbc609cb5c95ac34d8465801cd55dc40b6989b5b164483dd42ea69bebb7f45e9`.
Its real API rejected a disabled synthetic account without issuing a session,
then accepted the re-enabled fixture and upgraded its legacy password hash.
The existing API/worker, migration, login-quota cleanup, storage, CSV, assisted
jobs, account-boundary, static-delivery, and producer-to-local-review-HAI
checks also passed. See the [account-state verification record](FINAL_VERIFICATION_REPORT.md#login-account-state-and-connection-lifetime--2026-09-13).
Schema head remains `20260913_0016`; this checkpoint adds no migration.
This is an unsigned local review executable, not a production or installed
HAI release, and no public ngrok acceptance is implied. Earlier hashes below
are historical.

The latest 2026-09-13 atomic-login build has SHA-256
`869f2039f3b7ee1b540c9e71c7dead8cd83824988ec5324a3ba27e1877a63788`.
Its real API/worker at head `20260913_0016` passed login quota enforcement,
worker cleanup after deliberately expiring an isolated test reservation, and
subsequent successful login/clear. Existing API/worker/image/CSV/rate-limit and
real producer-to-local-review-HAI checks also passed. See the
[atomic-login verification](FINAL_VERIFICATION_REPORT.md#atomic-login-admission-and-expiry-maintenance--2026-09-13)
and [coordinated upgrade procedure](OPERATOR_RUNBOOK.md#login-admission-upgrade).
This is an unsigned local review executable, not production deployment or
live ngrok/installed-HAI acceptance. Earlier hashes below are historical.

The latest 2026-09-13 bounded API-limiter build has SHA-256
`b8c886d480a2d1a15e425d2129bb076818343ae37511e9fd119afdcf0ded9d59`.
Its actual API accepted the configured 300 requests for a new synthetic
identity, then returned HTTP 429 with Retry-After while health/static remained
available. API/worker, CSV, image cleanup, and real producer-to-local-review-HAI
checks also passed. See the [bounded-limiter verification](FINAL_VERIFICATION_REPORT.md#bounded-api-rate-limit-state--2026-09-13)
for test scope and capacity tradeoffs. This is an unsigned local review build,
not production deployment, edge enforcement, live ngrok acceptance, or an
installed HAI release. The following hashes describe earlier builds.

The newer 2026-09-13 upload/CSV responsiveness build has SHA-256
`862ff9dd4ada2cccb7ac1a03653566f7468de185209c8a5c2b2e14abe75dd461`.
Its actual API/worker passed existing workflows, image-write compensation,
locked-file cleanup retry, and CSV size/encoding rejection without partial
imports. The real producer-to-local-review-HAI test also passed on disposable
PostgreSQL. Source regressions prove health can finish while storage/CSV work
is paused; this is not a saturated-load benchmark. See the
[request-isolation verification](FINAL_VERIFICATION_REPORT.md#upload-and-csv-event-loop-isolation--2026-09-13).
This remains an unsigned local review build, not a published release or live
ngrok/production/installed-HAI acceptance. Hashes below describe earlier builds.

The latest 2026-09-13 image-write recovery build has SHA-256
`4b5a7bf4c7ca1fe9a40af9b24e724659fd64e1bedbdfc07d3882f9929e7977f0`.
The real executable passed cleanup after a rejected database image insert,
complete duplication details, bounded copy titles, missing-source-image
conflicts, locked-file retry, and the existing API/worker/HAI workflow. It also
includes the migration environment's application-logger preservation fix.
See [image-write verification](FINAL_VERIFICATION_REPORT.md#image-write-compensation-and-duplication-integrity--2026-09-13)
for evidence and the remaining pre-write crash-recovery gap. This is an unsigned
local review executable; it is not production deployment or live ngrok acceptance.

The earlier 2026-09-13 storage-cleanup build has SHA-256
`bd264a834b214a058f9f04239c64d7a89b70e20269557e32103af323220db03c`.
The real executable passed API/worker workflows at Alembic head
`20260913_0015`, including account deletion while a Windows file handle blocked
image removal and successful retry by the separate worker after release. It
also passed the separate local HAI consumer integration against disposable
PostgreSQL. See the [cleanup verification record](FINAL_VERIFICATION_REPORT.md#transactional-image-cleanup-and-recovery--2026-09-13)
for counts, the initial launcher-test failure and passing reruns, and limitations.
This remains a local review build, not a signed release, production deployment,
installed HAI integration, or live ngrok acceptance. Earlier hashes are historical.

The earlier 2026-09-13 listener follow-up build has SHA-256
`ba4339d08f8eb844f4928e0f61324584d91cf8692a2bb44995fcbf8a414639a0`.
The isolated full HTTP workflow, owner-crash/occupied-resource drill, and
packaged API/worker socket-handoff drill all passed again. The additional
source change enables POSIX restart after closed TCP connections; Windows
retains exclusive-address protection. See the
[cross-platform follow-up](FINAL_VERIFICATION_REPORT.md#posix-listener-restart-follow-up--2026-09-13).
This is a local review build, not a signed release or live ngrok acceptance.

The 2026-09-13 managed-lifecycle build has SHA-256
`380a09e1a69161ba293a4fcb060e34ff35b882f12d0481694a690c536c94832a`.
Its isolated executable workflow passed API/worker health, migrations, uploads,
account isolation, retries/recovery, HAI downloads, and source-matching frontend
assets/cache checks. A separate drill passed packaged API socket sharing and
exact packaged-worker identity under the source supervisor, including cleanup
with an unfinished request. Occupied resources and actual launcher-owner crash
cleanup also passed. These are local packaging checks, **not a real public
ngrok session or a signed release**. See the
[managed lifecycle evidence](FINAL_VERIFICATION_REPORT.md#managed-ngrok-lifecycle--2026-09-13).
Earlier hashes below are historical.

The 2026-09-06 launcher-ownership build has SHA-256 `3bffa5882044b5a5c01ecc43e67199dc1e2c5489abd2ba85b9e0bc1b41fe3d4c`. It passed the isolated API/worker, migration, upload, account-isolation, retry/recovery, HAI-download, and frontend-byte/cache checks. See the [launcher verification record](FINAL_VERIFICATION_REPORT.md#launcher-port-data-and-process-ownership--2026-09-06) for process-ownership evidence and limits. This remains a locally built review executable, not a signed production release or proof of safe ngrok use. The hashes below describe earlier builds.

The 2026-09-06 frontend-delivery build has SHA-256 `abb2501ee4f0daca16bb32d0368c408ca5a5ad907d9aca1abc8b4aa5a10e4124`. The isolated executable passed API/worker health, migration head `20260905_0014`, uploads, account isolation, retry/recovery, and HAI-download checks. All four frontend assets, including the icon, matched source bytes and passed cache revalidation with body-free HTTP 304 responses. Test processes were stopped afterward. This verifies the local package, not production deployment or safe ngrok operation. Earlier build hashes below are historical.

The 2026-09-06 HAI-download build has SHA-256 `0d5daa88f4bd7bcbc2cf8380cfc96cff16a0cbbba8c8c143df62294bd4a2fe13`. A fresh isolated runtime passed API/worker health, migration head `20260905_0014`, the existing retry/account/recovery workflow, and the owner-only generic HAI download. Served frontend assets matched current source bytes. This build adds a manual file handoff, not automatic HAI synchronization or a signed production release. See the [current verification report](FINAL_VERIFICATION_REPORT.md#manual-hai-file-handoff-verification--2026-09-06).

The 2026-09-05 claim-fencing build has SHA-256 `ddb3c47b4fdc8b7f01f6a4ea63e27bac8fec0af053ba61b28683230cb7cfd635`. Its isolated runtime reached Alembic head `20260905_0014` and passed API/worker health, dashboard, uploads/HAI metadata, cursor rejection, account isolation, explicit retry, and recovery of an abandoned running job. Terminal claim identifiers were cleared and not exposed in the job API. Before upgrading an existing installation, stop every old executable/API/worker and back up its data; see the [upgrade procedure](OPERATOR_RUNBOOK.md#claim-fencing-upgrade). The following build records are historical.

The 2026-09-05 worker-recovery build has SHA-256 `68bab4a5d1e371e4a1fd91b8ce367f218ea87a49a2ed427a628450fafc5f9416`. Its clean-directory HTTP workflow passed API/worker health, dashboard, image upload, HAI metadata, malformed-cursor rejection, repeated-failure idempotency, and separate-worker retry through `needs_user_action`. See the [verification report](FINAL_VERIFICATION_REPORT.md) for current evidence and limits; the older build below is historical evidence, not the current binary.

The finalized 2026-08-09 local build produced a 43,670,075-byte executable with SHA-256 `6f791859c6bb70101e85b0c5c3ab417f5e962b12b2e52869b1c2df75bcfa1ed2`. A clean-directory runtime test reached Alembic head `20260809_0013`, reported a healthy API and worker, and created the expected database and secret; an exact-source rebuild passed the same API/worker smoke. One-file startup took about 99–130 seconds on this Windows host while Windows extracted/scanned it; later behavior depends on the machine and security software.

## Ngrok

**Starting ngrok is an explicit public action.** Local tests use a substitute
agent and do not open a public tunnel. The revised implementation addresses the
earlier port-ownership, process-selection, shared-log, worker-readiness, and
PowerShell-environment gaps. Neither these tests nor older successful public
health checks prove acceptance of the revised path against the real provider.

After operator approval and installing/authenticating ngrok:

```powershell
.\scripts\start-ngrok.ps1
```

The wrapper prefers `dist/SecondhandAutoposter.exe`; **rebuild it after a source
update**, or pass `-FromSource` to select `.venv/Scripts/python.exe`. Other options
are `-Domain your-domain.ngrok.app`, `-Port 8010`, `-NgrokPath "C:\Tools\ngrok.exe"`,
and `-NoBrowser`. Caller environment values and working directory are preserved.

`-VerifyOnly` opens the endpoint, checks both local/public API health **and this
launch's exact worker heartbeat**, then tears down the owned session. HTTP
responses must have the generated instance marker and matching worker ID. It
does not accept another worker's recent heartbeat as startup proof. The marker
is not a credential. The public-origin profile forces bearer authentication,
restrictive CORS, no development auto-login, explicit migrations, and a separate
worker. Account registration remains available: review edge access controls
before exposing sensitive data.

Agent arguments disable inspection and pooling. Logs are isolated under
`AUTOPOSTER_DATA_DIR/runtime/ngrok-<unique-id>/`, rotating at approximately 64 KiB
with three backups. Malformed endpoint values, a changed/unexpected endpoint,
log EOF, and read/write/close failures stop the run with fixed lifecycle errors.
Logs are not served by the app; OS permissions and retention across runs still
need operator management. Do not share raw logs without reviewing their content.

After initial HTTP readiness, monitoring checks process/log liveness, not
continuous public connectivity or heartbeat freshness. Ctrl+C, process death,
or a failed readiness/logging check cleans up the owned session. Forced cleanup
can interrupt requests and jobs; check state before retrying. Endpoint discovery
has a 30-second deadline, API bootstrap and readiness each have 180 seconds;
these do not bound every migration, DNS, or OS failure. Thread-cleanup failures
are reported, not silently accepted.

Do not enable pooling to work around `ERR_NGROK_334`; resolve the endpoint
conflict through an authorised operator. A reserved address is not private
access, and a temporary tunnel is not production hosting. Sleeping, shutting
down, or disconnecting the Windows host makes the app unavailable. See the
[README ngrok section](../README.md#access-through-ngrok) for the complete
operational boundary.
