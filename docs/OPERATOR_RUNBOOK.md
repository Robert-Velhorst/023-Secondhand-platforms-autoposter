# Operator Runbook

This runbook covers deployment and operation of the assisted-posting app. It is not production approval: resolve the [implementation gaps and launch requirements](../README.md#current-launch-blockers) and record target-environment evidence before launch.

## Pre-Deploy Checks

1. Set production environment values:
   - `APP_ENV=production`
   - strong `SECRET_KEY`
   - production `DATABASE_URL`
   - persistent `UPLOAD_DIR`
   - restrictive `CORS_ORIGINS`
   - `AUTH_TRANSPORT=bearer`
   - `AUTO_CREATE_TABLES=false`
   - `JOB_PROCESS_INLINE=false`
   - `LOG_LEVEL=INFO`
   - `LOG_FORMAT=json` when logs are collected by a structured log system
2. Install runtime dependencies from `requirements.txt`. Contributors and reviewers should install `requirements-dev.txt` instead.
3. Run migrations:

```bash
alembic upgrade head
```

4. Run the verification gate:

```bash
python scripts/verify.py
```

Doctor warnings must be understood before release; doctor errors block release.

## Claim-fencing upgrade

Revision `20260905_0014` adds nullable `publishing_jobs.claim_token`. This is an internal worker ownership identifier, not an API credential. Existing rows and their history are retained; queued jobs receive an identifier when claimed. Legacy running jobs cannot be executed by the new worker until normal stale recovery returns them to the queue.

1. Pause job processing and stop **all** old API/worker processes, including standalone executables and API processes that can execute jobs inline. Wait for in-flight work to finish where possible; reconcile any uncertain external outcome before retrying it.
2. Back up the target database and verify the recovery procedure. The automated disposable migration tests are not a backup for your target data.
3. Install the new release, run `alembic upgrade head`, and check `python -m app.doctor --json` reports head `20260905_0014`.
4. Start the API and worker from the same release, verify health, and resume processing. Check an assisted job reaches `needs_user_action` and its history is retained.

Do not perform a mixed-version rolling deployment: old workers ignore claim identifiers and can still overwrite newer results. Claim fencing prevents stale **local writes**; it cannot cancel an already-started external request, renew a lease, or guarantee exactly-once marketplace publication. Current adapters prepare assisted packages only.

For rollback, stop every process again and preserve a backup before `alembic downgrade 20260809_0013`. The downgrade removes only the claim column using native `DROP COLUMN`; SQLite requires version 3.35 or later. Do not substitute a table-rebuild/drop operation with foreign keys enabled: it can cascade-delete job logs and attempts. See [SQLite ALTER TABLE](https://www.sqlite.org/lang_altertable.html#alter_table_drop_column). Reverting code also removes claim-fencing protection; reconcile running jobs before restarting an older release.

## Start Services

Web process:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Worker process:

```bash
python -m app.worker
```

Docker Compose:

```bash
docker compose up --build
```

Production Compose runs migrations as a one-shot service before API and worker startup. For a new deployment, prepare `.env.production` from `.env.production.example` outside version control and replace every placeholder first. Do not overwrite an existing configured file. For an upgrade, stop all older API and worker processes and back up the target database/uploads before starting the new stack; follow the claim-fencing procedure above.

After configuration and backup, launch from PowerShell:

```powershell
$env:UPLOAD_VOLUME = "C:\path\to\persistent\autoposter-uploads"
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
```

On Linux/macOS, use `export UPLOAD_VOLUME=/path/to/persistent/autoposter-uploads` instead of the PowerShell assignment. `--env-file` supplies Compose interpolation values; the services' `env_file` loads application settings. Keep the published API port behind a reviewed HTTPS proxy/firewall. Compose does not provide TLS, edge rate limiting, backup scheduling, or a managed database.

Do not add a default database password or a bundled database service to this production file. `DATABASE_URL` must be supplied by the deployment secret manager. Confirm `GET /api/worker-status` reports `status: ok` after the worker has completed at least one poll cycle.

## Health Checks

- App health: `GET /api/health`
- Diagnostics: `GET /api/diagnostics`
- Metrics snapshot: `GET /api/metrics`
- Worker heartbeat: `GET /api/worker-status` (returns 503 until a fresh worker heartbeat exists)
- CLI diagnostics: `python -m app.doctor --json`

Expected production status is `ok`. A warning requires operator review. An error requires rollback or repair.

## Worker Database Recovery

Runtime queue or heartbeat failures classified as SQLAlchemy `OperationalError`, `InterfaceError`, or pool `TimeoutError` are retried with a fresh session. The delay starts at `JOB_WORKER_POLL_SECONDS`, doubles on consecutive failed cycles, and caps at the greater of 60 seconds or the configured poll interval. One complete successful queue-and-heartbeat cycle resets the delay. The worker logs a recovery message. Database connection/query timeouts are additional to this sleep; an indefinitely blocked driver call cannot be fixed by the retry loop.

Warnings contain the worker ID, `queue` or `heartbeat` phase, exception class, and delay. They deliberately omit exception messages, SQL parameters, and tracebacks that can contain sensitive data. These exception classes are driver categories, not proof that a fault is temporary; persistent permission/schema/connectivity problems still require investigation. See [SQLAlchemy's exception reference](https://docs.sqlalchemy.org/en/20/core/exceptions.html).

No fallback healthy heartbeat is written after a failed cycle. A previously recorded heartbeat can remain fresh until `WORKER_HEARTBEAT_TIMEOUT_SECONDS` elapses; if the database is unavailable, the health endpoint itself may fail. An ambiguous heartbeat commit can already have reached the database. Treat `processed_jobs` as best-effort operational telemetry and use persisted jobs/attempts for reconciliation; the loop does not replay an uncertain counter increment.

Startup validation, automatic table creation, and unrelated programming/integrity errors remain fail-fast. Configure an appropriate service manager/restart policy and alerting. The Windows launcher does not supervise or restart a child that exits from those failures; investigate the cause before restarting the application.

The retry loop does not release already-claimed jobs or replay an interrupted external operation. Existing stale-job recovery remains responsible for abandoned claims. Long-running leases, crash recovery during provider calls, and exactly-once publication need separate proof; current adapters are assisted/manual only. Do not manually requeue work with an uncertain external outcome without reconciliation.

## Logs

- Web requests are logged on `autoposter.requests` with `request_id`, method, path, status code, and duration.
- Worker lifecycle and batch activity are logged on `autoposter.worker`.
- Set `LOG_FORMAT=json` in production when the process manager or hosting platform collects stdout.
- Use the `X-Request-ID` response header to connect API errors, browser reports, and server logs.
- Poll `GET /api/metrics` for lightweight JSON counters covering users, listings, platform accounts, publishing jobs, listing statuses, and publishing job statuses.

## Auth And CSRF

- The supported auth mode is bearer tokens in the `Authorization` header.
- The app does not set authenticated session cookies, so CSRF token middleware is intentionally not enabled.
- Keep `CORS_ORIGINS` restricted in production and serve the app only over HTTPS.
- Do not enable cookie auth without adding CSRF validation and a new security review.

## Routine Operations

- Check the Queue screen for `failed` and `needs_user_action` jobs.
- Use job retry only after confirming the listing and platform account state.
- eBay OAuth consent can create an account with `status=needs_token_exchange` when `EBAY_OAUTH_CLIENT_SECRET` is absent, or `status=connected` when token exchange succeeds through the configured secret store. Official eBay listing publication remains disabled until live sandbox listing proof and seller-policy checks are added.
- Investigate repeated stale-running recovery logs; they can indicate worker crashes, timeouts, or deployment restarts during publishing work.
- Keep uploads on persistent local storage or private S3-compatible object storage and include that storage in backups.
- Keep database backups separate from application deploy artifacts.
- Run `python -m app.audit_retention` on the chosen retention schedule to purge audit events older than `AUDIT_RETENTION_DAYS`.
- Run `python -m app.reconcile` as a check-only consistency audit. Use `--repair-safe` only after reviewing its image-position-only repair scope.
- Generate a sanitized diagnostic archive with `python -m app.support_bundle --output support-bundle.zip`; review it before sharing.
- Do not run legacy Selenium scripts inside the web or worker process.

## Emergency Job Stop

Pause new job claims without deleting queued work:

```bash
python -m app.operator_control pause --reason "incident reference"
python -m app.operator_control status
```

Resume only after the incident owner approves processing:

```bash
python -m app.operator_control resume --reason "incident resolved"
```

The control is stored in the database, survives process restarts, and is reflected by
`GET /api/worker-status` and `GET /api/diagnostics`. It does not interrupt an adapter call that is
already executing; stop the worker process as well if immediate containment is required.

## Backup And Restore

Minimum backup set:

- production database
- upload directory
- deployed `.env` or secret-manager references
- current git commit SHA

Restore order:

1. Restore database.
2. Restore uploads to `UPLOAD_DIR`.
3. Deploy the matching git commit.
4. Run `alembic upgrade head`.
5. Run `python -m app.doctor --json`.
6. Start web and worker services.

## Incident Checklist

- Capture current git SHA and environment name.
- Run `python -m app.doctor --json`.
- Check app logs, worker logs, and recent failed job logs.
- Pause the worker if duplicate posting risk is suspected.
- Export affected user data before destructive repair when possible.
- Prefer rollback to the last known good commit if startup, auth, or migration safety is uncertain.

## Rollback

1. Stop worker first.
2. Stop web process.
3. Deploy last known good commit.
4. Restore database only if the failed release changed data incompatibly.
5. Run diagnostics.
6. Start web, then worker.
