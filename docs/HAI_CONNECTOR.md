# HAI Connector

The app exposes an owner-scoped, read-only incremental API and a separate **HAI-compatible local JSON file download**. The download can be ingested by HAI's generic local-file reader. Automatic authenticated synchronization and deletion propagation are not implemented in that reader.

## Manual Local-File Handoff

1. Sign in to Autoposter and open **Settings → HAI connection → Download HAI feed**. This uses the ordinary owner session, not a connector token.
2. Save `autoposter-hai-feed.json` in a controlled location. It contains listing text and safe metadata; treat it as private business data even though private notes, credentials, image filenames, and binaries are excluded.
3. An authorised HAI operator places the file under the installation's allowlisted feeds root and registers a feed with `sourceType=local_json_file`, `provider=generic_json_feed`, a relative `path`, and the correct HAI `ownerUserId` / `workspaceId`. Set a stable, unique `accountLabel` for each Autoposter installation and owner to avoid cross-source identity collisions. Do not point a different owner at someone else's export.
4. Run a sync and inspect the actual item/operation counts. The `items` envelope contains `externalId`, `provider`, `itemType=document`, `title`, `content`, `sourceUri`, and `metadata`. A repeated unchanged file should be deduplicated by HAI.
5. Export/import again when you want to share updates. Deleted listings disappear from subsequent files, but HAI's current registry does not remove older operations. Define and implement an explicit deletion/retention policy before treating this as synchronized storage.

`GET /api/hai/export` returns `application/json`, an attachment filename, and `Cache-Control: no-store`. Unauthenticated requests and `hai:read` tokens receive 401. All current owner listings, including archived ones, are included; the endpoint does not stop at the regular API's first page. It reads batches of 100, counts images in the database, loads only export fields/platform metadata, and caps the serialized file at 5 MiB. This is a current-record export, not a transactionally frozen point-in-time backup while concurrent edits occur.

Content is limited to 200,000 UTF-8 bytes and Go-encoded metadata to 16,000 bytes per item to match the inspected HAI parser. A size overflow produces HTTP 413 and no partial download. A misconfigured source base containing URL credentials, a query/fragment, or secret-looking parameters is omitted from source links. Oversized stored listing fields can still require database work and transient memory before rejection; this is not an unlimited-scale export service.

## Current HAI Compatibility Gap

The 2026-09-06 source comparison used HAI commit `91c8620c557229f1da4ed15fcbb7088c6a6947a7`:

- [Generic parser](https://github.com/Robert-Velhorst/018-HAI/blob/91c8620c557229f1da4ed15fcbb7088c6a6947a7/backend/internal/accountfeed/generic_feed.go): accepts `{cursor, items}` or a bare array. It requires item fields `externalId`, `provider`, and `itemType`, with `sourceUri` for links. Autoposter returns `{records, next_cursor, has_more}` with `id` and `source_url`. An Autoposter envelope can therefore parse as zero items without an error; an HTTP success or empty sync is not ingestion proof.
- [HTTP fetcher](https://github.com/Robert-Velhorst/018-HAI/blob/91c8620c557229f1da4ed15fcbb7088c6a6947a7/backend/internal/accountfeed/fetcher.go): creates GET requests without an Authorization header. Registering the protected Autoposter URL does not supply its required bearer token. HTTP fetching must also be enabled in HAI.
- [Sync registry](https://github.com/Robert-Velhorst/018-HAI/blob/91c8620c557229f1da4ed15fcbb7088c6a6947a7/backend/internal/accountfeed/registry_service.go): returns a parsed cursor in its report but does not advance the fetch URL or apply Autoposter deletion tombstones.

The download above supplies the compatible generic format for a manual local-file handoff. A compatible authenticated adapter is still required for automatic HTTP synchronization. Keep bearer protection in place; do not put tokens in URLs or substitute a public feed. Recheck the target HAI revision when implementing the consumer.

## App-Side API Verification Flow

1. Sign in to Secondhand Autoposter.
2. Open Settings and create a named HAI connector token with an expiry date.
3. Copy the `hai_...` token immediately; only its SHA-256 hash is stored and the plaintext is never shown again.
4. Use a controlled API client that can send `Authorization: Bearer hai_...` to the app base URL.
5. Read the discovery document at `/.well-known/hai-connector.json`, verify the token with `GET /api/hai/status`, then request `GET /api/hai/records`. These steps test this application's API only, not the incompatible HAI consumer above.

The feed is cursor-based. Persist `next_cursor` after each page and pass it as `cursor` on the next request. Upserts contain listing metadata and a source link; deletes are emitted as tombstones. Consumers should deduplicate by record `id` and apply events in cursor order.

Image additions/deletions and marketplace selection changes also emit upserts, so a consumer that has already synced a listing receives updated `image_count` and `platforms` metadata. These changes are recorded in the same database transaction as the underlying edit. Images themselves remain private. Platform status transitions that do not change selection do not add unnecessary connector events.

Cursors are opaque: pass the returned value unchanged. Invalid encoding, signed or non-decimal identifiers, and values outside the supported database integer range return HTTP 422. Do not repeatedly retry those responses as transient server failures.

## Security Contract

- Connector tokens have only the `hai:read` scope.
- Tokens are owner-scoped, expiring, revocable, and stored as hashes.
- The feed excludes internal notes, credentials, platform secret references, and image binaries.
- Uploaded images remain behind the owner's normal bearer session and are not exposed to HAI.
- The connector cannot create, edit, publish, delete, or complete marketplace jobs.
- Marketplace publishing remains assisted/manual unless a separate official API integration is implemented and proven.

Example request, using a placeholder token:

```bash
curl -H "Authorization: Bearer hai_REPLACE_ME" "https://autoposter.example/api/hai/records?limit=100"
```

For local Windows use, the source URL is `http://127.0.0.1:8000` from that Windows host. Inside another machine or container, `127.0.0.1` refers to that machine/container, not the Autoposter host. A reviewed network route is required. Do not open the experimental ngrok path before addressing the [documented lifecycle risks](WINDOWS_STANDALONE.md#ngrok).

## End-to-End Acceptance Still Required

1. Record the actual HAI revision and agreed transport; obtain approval before changing its installation or registering a data source.
2. Configure and accept the manual file handoff, or implement secret-backed authenticated fetching for automatic synchronization. The download already supplies generic-item field mapping and valid provider/item-type values.
3. Handle every page, persist cursors only after durable processing, deduplicate replayed records, and bound payloads/retries. The inspected HAI parser limits content to 200,000 bytes and metadata to 16,000 bytes per item; its HTTP fetcher reads at most 5 MiB.
4. Define and implement deletion/retention behaviour. Omitting a listing from a snapshot does not demonstrate deletion of previously ingested HAI data.
5. Test a real listing create/update/delete cycle, more than one page, an empty page, a replay, expired/revoked tokens, and cross-owner isolation against the real consumer. Confirm item counts and retained content, not merely a successful request.
6. Record the ingestion evidence and operator acceptance without granting the read-only feed authority to publish or execute actions.

This repository does not silently modify a HAI installation. The app-side feed tests and portable-build metadata checks do not satisfy these consumer-side acceptance steps.

## Reproduce the Real Consumer Contract Check

Use a separate disposable HAI source checkout at commit `91c8620c557229f1da4ed15fcbb7088c6a6947a7`; do not insert test files into an installed HAI service. Create one synthetic Autoposter listing titled `HAI consumer chair`, download its HAI file, and ensure that account has no other listings. With Go installed, copy this repository's `scripts/hai_consumer_contract_test.go` into that checkout's `backend/internal/accountfeed/` directory. Then, from HAI's `backend` directory:

```powershell
$env:AUTOPOSTER_HAI_EXPORT_PATH = "C:\absolute\path\autoposter-hai-feed.json"
go test ./internal/accountfeed -run TestAutoposterExport -count=1 -v
```

The harness calls HAI's actual `ParseGenericFeed` and `Registry.Sync`, creates one operation in HAI's in-memory repository, and verifies a repeated read refreshes rather than duplicates it. It also characterizes the old `records` envelope being read as zero items. This proves parser/local-file ingestion compatibility at that source revision, not database-backed HAI persistence, target deployment, remote authentication, or deletion propagation. No Go runtime is needed by Autoposter itself.
