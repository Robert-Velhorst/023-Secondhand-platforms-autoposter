# Image Storage

Uploaded listing images are validated before storage and are represented in the database by metadata only.

## Validation Policy

- Supported image types are controlled by `ALLOWED_IMAGE_TYPES`.
- The service verifies both declared MIME type and file signature.
- `MAX_UPLOAD_SIZE_MB` bounds upload size before storage.
- Filenames are sanitized and stored objects receive UUID-suffixed names.
- SHA-256 checksums are stored and used to avoid duplicate images on the same listing.
- Image content is returned only from the owner-authenticated content endpoint; raw storage paths are not exposed in normal listing responses.
- Image deletes remove a local file or S3-compatible object after its final database reference is removed.
- Listing duplication creates an independent stored object instead of sharing a destructible path.

## Backends

`STORAGE_BACKEND=local` stores files under `UPLOAD_DIR/{listing_id}/`.

`STORAGE_BACKEND=s3` stores files through a boto3 S3-compatible client. Required configuration:

- `S3_BUCKET`
- optional `S3_REGION`
- optional `S3_ENDPOINT_URL` for S3-compatible providers
- optional `S3_KEY_PREFIX`, defaulting to `uploads`

Stored S3 paths use `s3://bucket/key` internally. Raw object data is not included in JSON exports. The owner-authenticated `GET /api/listings/{listing_id}/images/{image_id}/content` endpoint reads either backend. The separate image ZIP export includes local files directly; S3-backed images are listed in the manifest as `object_storage_not_exportable` so operators can export them from object storage using provider tooling.

## Production Notes

Use bucket policies, private objects, server-side encryption, lifecycle rules, and backups according to the deployment target. The application does not mount `UPLOAD_DIR` as a public static directory.
