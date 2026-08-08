# Red Team Review

Date: 2026-07-09

This review looks for ways a user, operator, or attacker could misuse the current application. It focuses on the implemented FastAPI dashboard, not the quarantined legacy Selenium scripts.

## Scope

- Authentication, sessions, and login throttling.
- User ownership boundaries for listings, jobs, accounts, templates, mappings, exports, imports, and deletion.
- Assisted-posting honesty and platform compliance.
- Upload, export, log, and diagnostics data exposure.
- Job queue idempotency, retries, cooldowns, and stale-running recovery.

## Findings

| Risk | Current control | Remaining action |
| --- | --- | --- |
| Credential stuffing or password guessing | Argon2 hashes, bearer sessions, revocation, and database-backed hashed failed-login throttling with expiry, success clearing, and `Retry-After` responses. | Add deployment-edge rate-limit evidence for the chosen host/proxy. |
| Cross-user data access | Owner filters and direct owner-isolation tests cover core resources. | Keep owner-isolation tests mandatory when adding new owned tables or endpoints. |
| Fake automation claims | Registered production adapters are assisted and tests block fake published success. | Re-review UI copy before client launch and after any official API integration. |
| Platform anti-abuse bypass | Assisted package flow leaves login, CAPTCHA, payment, and final confirmation to the account owner. | Keep legacy browser automation out of production deployment and docs. |
| Upload path traversal or unsafe files | Filenames, MIME/signature checks, size limits, checksums, duplicate detection, and isolated local storage exist. | Add object-storage adapter review before enabling remote storage. |
| Exporting secrets | Data export sanitizes account metadata and excludes password/session/platform secrets. | Re-run export privacy checks whenever account connection data changes. |
| Job replay or duplicate posting | Idempotency keys include user, listing, revision, platform, account, action, and operation mode. | Add explicit user-controlled regenerate/repost UX before advanced repost workflows. |
| Worker race or stuck job | Atomic due-job claims and stale-running recovery are tested under SQLite. | Verify PostgreSQL behavior under concurrent workers before multi-instance production. |
| Sensitive logs | Request/job/audit logs avoid raw secrets in current flows. | Review logs during browser QA and first production dry run. |
| CSRF | Auth is bearer-only and not cookie-backed. | Revisit if cookie sessions are ever introduced. |

## Abuse Cases Reviewed

1. A user guesses another user's listing ID and calls detail, update, publish, export, or delete endpoints.
   Current expectation: denied by owner-scoped queries or 404.

2. A user repeatedly submits bad passwords.
   Current expectation: throttled after configured failed attempts using persistent database state.

3. A user uploads a file with an image extension but invalid image bytes.
   Current expectation: rejected by MIME/signature validation.

4. A user creates a listing and attempts to claim the app automatically published it.
   Current expectation: assisted adapters return `needs_user_action`, mapped fields, warnings, and posting URLs.

5. A worker crashes while a job is running.
   Current expectation: stale-running recovery returns old jobs to the queue after the configured timeout.

6. A user exports their account data.
   Current expectation: export includes portable listing/configuration data, not password hashes, sessions, tokens, raw secrets, or image binaries.

## Release Gate

Before client launch, this review should be refreshed after:

- any new authentication transport,
- any new platform account secret model,
- any official API provider,
- any remote storage backend,
- any new admin/operator UI,
- any new endpoint that reads or mutates owned data.

## Loop Two: Operator And Recovery Controls (2026-08-08)

The second loop challenged failure containment. A worker could previously be stopped only by
stopping its process, which was slow and easy to mishandle during a duplicate-risk incident.
The persistent operator-control singleton and `python -m app.operator_control pause --reason ...`
now stop new job claims across worker restarts. The status is exposed in diagnostics and worker
health without exposing user data. Remaining production proof: exercise pause and resume with the
target PostgreSQL database and process manager.

The same loop challenged support collection and data repair. The support-bundle command now emits
only aggregate counts, safe configuration, doctor results, and secret-presence booleans. The
reconciliation command is check-only by default and its repair mode is intentionally limited to
deterministic image-position gaps. Orphan deletion and publication inference remain manual.

## Loop Three: Product Claims And External Trust (2026-08-08)

The third loop treated every external boundary as hostile or unavailable. Listing guidance now
identifies its provider as `deterministic_local`, reports that no external data was sent, and cannot
be configured to an unimplemented provider. All marketplace adapters continue to return assisted
packages and `needs_user_action`; no UI or API path converts preparation into a false published
claim. A manual completion needs an owner-supplied marketplace URL.

The action center is owner-scoped and derived from existing records; it does not invent reminders
or transmit analytics. Remaining external gates are intentionally not papered over: deployment,
target PostgreSQL, backup/restore, edge rate limiting, real-user accessibility, official provider
credentials, and final acceptance still require evidence from the client environment.
