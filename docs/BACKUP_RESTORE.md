# Backup, Restore, And Disaster Recovery

This runbook defines the minimum backup set and restore procedure for production operation.

## Backup Scope

Back up these items together:

- production database, including pending `storage_deletions` cleanup intent
- upload directory configured by `UPLOAD_DIR`
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
4. Record current git SHA and Alembic revision.
5. Run the migration.
6. Run `python -m app.doctor --json`.
7. Start the API and worker only after diagnostics are acceptable.

## Restore Order

1. Stop worker and web processes.
2. Restore database.
3. Restore uploads to the configured `UPLOAD_DIR`, or restore the configured S3-compatible bucket/prefix.
4. Deploy the matching git commit, or a commit known to support the restored schema.
5. Run `alembic upgrade head`.
6. Run `python -m app.doctor --json`.
7. Review `python -m app.reconcile`, including pending storage cleanup, against the matching restored image snapshot and configured root/bucket/prefix. Resolve any mismatch before permitting cleanup.
8. Start web and worker processes. Both can perform cleanup: API deletions have a local post-commit fast path, and the worker resumes durable pending requests.

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
