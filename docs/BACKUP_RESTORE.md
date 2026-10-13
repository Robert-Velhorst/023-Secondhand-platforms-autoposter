# Backup, Restore, And Disaster Recovery

This runbook defines the minimum backup set and restore procedure for production operation.

## Backup Scope

Back up these items together:

- production database, including pending `storage_deletions` and `token_secret_deletions` cleanup intent
- upload directory configured by `UPLOAD_DIR`
- private `TOKEN_SECRET_DIR` when OAuth token exchange is enabled; token files cannot be recreated from database references alone
- deployed git commit SHA
- environment/secret references, excluding raw secret values from ordinary backup logs
- Alembic revision at backup time

User JSON exports are useful for portability, but they are not a replacement for operator backups because image binaries and job history are intentionally excluded.

## Backup Cadence

- Database: at least daily, plus before migrations.
- Uploads: at least daily and after large import/upload batches.
- Configuration references: after every deployment or secret rotation.
- Test restore: monthly, and before major releases.

## Pre-Migration Backup

Before `alembic upgrade head` in production:

1. Stop both API and worker processes, including standalone executables. Pausing publishing jobs does not pause file cleanup or API writes.
2. Take a database backup.
3. Snapshot/copy uploads or export the configured S3-compatible image bucket/prefix.
4. Back up the private token-secret directory, if present, using an access-controlled encrypted backup procedure.
5. Record current git SHA and Alembic revision.
6. Run the migration.
7. Run `python -m app.doctor --json`.
8. Start the API and worker only after diagnostics are acceptable.

## Restore Order

1. Stop worker and web processes.
2. Restore database.
3. Restore uploads to the configured `UPLOAD_DIR`, or restore the configured S3-compatible bucket/prefix.
4. Restore the private token-secret directory and its access controls if OAuth tokens are used.
5. Deploy the matching git commit, or a commit known to support the restored schema.
6. Run `alembic upgrade head`.
7. Run `python -m app.doctor --json`.
8. Review `python -m app.reconcile`, including pending image and token-secret cleanup, against the matching restored snapshots and configured roots. Resolve any mismatch before permitting cleanup.
9. Start web and worker processes. The worker resumes durable pending image and token-secret erasures.

## Reconciliation Checks

After restore, verify:

- `GET /api/health` returns `ok`.
- `GET /api/diagnostics` has no `error` status.
- Listing image tiles load for a restored listing.
- Queue counts are plausible and no duplicate worker is running.
- A test export for a non-sensitive account returns sanitized JSON.

## Disaster Recovery Notes

- If duplicate posting risk is suspected, keep the worker stopped until queue state is reviewed.
- If uploads or the storage snapshot do not match the restored database, keep API and worker stopped while investigating backups. Cleanup removes unreferenced objects, not image metadata, but resumed historical requests must not be applied to an unrelated/newer storage snapshot.
- If migration state is uncertain, prefer restoring to the recorded backup commit and revision instead of forcing schema changes.
- Keep legacy Selenium scripts out of production recovery paths.
