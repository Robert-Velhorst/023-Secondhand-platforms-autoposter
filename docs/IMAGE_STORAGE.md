# Image Storage

Uploaded listing images are validated before storage and are represented in the database by metadata only.

## Validation Policy

- Supported image types are controlled by `ALLOWED_IMAGE_TYPES`.
- The service verifies both declared MIME type and file signature.
- `MAX_UPLOAD_SIZE_MB` bounds upload size before storage.
- Filenames are sanitized and stored objects receive UUID-suffixed names.
- SHA-256 checksums are stored and used to avoid duplicate images on the same listing.
- Image content is returned only from the owner-authenticated content endpoint; raw storage paths are not exposed in normal listing responses.
- Image deletes queue removal of a local file or S3-compatible object after its final database reference is removed and the transaction commits.
- Listing duplication creates an independent stored object instead of sharing a destructible path.

## Backends

`STORAGE_BACKEND=local` stores files under `UPLOAD_DIR/{listing_id}/`.

`STORAGE_BACKEND=s3` stores files through a boto3 S3-compatible client. Required configuration:

- `S3_BUCKET`
- optional `S3_REGION`
- optional `S3_ENDPOINT_URL` for S3-compatible providers
- optional `S3_KEY_PREFIX`, defaulting to `uploads`

Stored S3 paths use `s3://bucket/key` internally. Raw object data is not included in JSON exports. The owner-authenticated `GET /api/listings/{listing_id}/images/{image_id}/content` endpoint reads either backend. The separate image ZIP export includes local files directly; S3-backed images are listed in the manifest as `object_storage_not_exportable` so operators can export them from object storage using provider tooling.

## Deletion and recovery

### Upload and duplication failures

Uploads and listing duplication register each planned, uniquely named storage
target before writing its bytes. If a handled storage or database exception
occurs, the shared image-write scope rolls back the business transaction and
uses a fresh session on the **same database** to record cleanup intent. This
also tracks local partial writes and an S3 upload that may have succeeded before
the provider response was lost. Cleanup then uses the reference checks and
retry mechanism below; a database commit whose acknowledgment was lost must
not cause its successfully referenced image to be deleted.

Duplication copies category attributes with the other master-listing details,
starts the copy as a draft, and bounds its suffixed title to 160 characters.
It creates independent image objects. If a source image is missing, it returns
an actionable conflict instead of silently creating an incomplete copy; any
earlier copies in that failed operation are queued for cleanup. Source images
and source metadata are not removed by this recovery.

This exception recovery is **not a pre-write durable journal**. A process killed
before recovery intent is saved, or an unavailable recovery database, can still
leave an unreferenced object. In the latter case the original failure is
preserved and a sanitized error is logged; no blind deletion is attempted when
the committed reference state cannot be checked. Closing this crash window and
reconciling historical orphans remain hardening work. The queue does not scan
storage or infer ownership from filenames.

### Post-commit cleanup

Account, listing, and individual-image deletion record file-cleanup intent in
`storage_deletions` within the same database transaction as the deleted records.
A failed or rolled-back transaction does not delete files. The outbox has no
account foreign key: it must survive account deletion until cleanup finishes.
It retains the internal storage path (which can contain a filename), creation and
retry times, attempt count, claim identifier, and exception class, not image
binaries or exception messages. Include this temporary retention in the privacy
notice and protect the database like the original image metadata.

After commit, API requests attempt at most five **local** objects. Remaining work
and all S3 work are handled by the separate worker. Each worker poll handles at
most five local objects or one S3 object after its publishing-job batch. These
limits bound each batch; they are not guarantees about filesystem, credential
resolution, or network latency. The S3 client uses 3-second connection and
5-second read timeouts with at most two SDK attempts per request.

The worker rechecks that no `listing_images` row references the exact stored
path. Referenced objects are preserved and that cleanup request is retired;
deleting their final reference creates new cleanup intent. Normal uploads and
duplicates use unique object names. Operators/importers must not reuse old
object paths or concurrently recreate references to an object being deleted.

Cleanup claims are committed before storage I/O, have a five-minute recovery
lease, and use unique claim tokens to fence acknowledgments. A crash before or
after deletion can therefore cause an idempotent retry, not lost cleanup intent.
This is at-least-once processing, not exactly-once storage execution. Ordinary
failures retry after one minute, doubling to at most one hour, without silently
discarding the request. Missing local files are already cleaned up. Local
unlink failures and rejected targets are retained for review/retry.

Local cleanup resolves paths and only unlinks within `UPLOAD_DIR`; it does not
remove that root directory. S3 cleanup requires the configured bucket and key
prefix. An empty prefix means the entire configured bucket. Keep upload roots
and their parent directories private to trusted operators. If storage settings
change, stop the API and worker and reconcile old pending paths before resuming;
unknown/out-of-scope paths fail closed rather than being treated as erased.

Run `python -m app.reconcile` to see `pending_storage_cleanup` and the count of
pending entries with previous failures. It reports counts without exposing file
paths, and exits nonzero while work remains. `--repair-safe` does not force or
discard cleanup. A healthy worker heartbeat alone does not prove erasure.
Investigate storage permissions, configured roots/bucket/prefix, and worker
operation; keep pending records until their disposition is proven.

A successful API response confirms the database deletion, not completed physical
erasure. Already downloaded/shared copies, marketplace advertisements, backups,
and S3 historical object versions are outside this queue. In a versioned bucket,
an ordinary object delete may create a delete marker; provider lifecycle and
version-retention rules require separate operator handling and evidence. See
[Amazon S3 delete-marker behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeleteMarker.html).

See the [operator procedure](OPERATOR_RUNBOOK.md#storage-cleanup-upgrade-and-operation)
and [backup/restore instructions](BACKUP_RESTORE.md).

## Production Notes

Use bucket policies, private objects, server-side encryption, lifecycle rules, and backups according to the deployment target. The application does not mount `UPLOAD_DIR` as a public static directory.
