# Auth Security Posture

The current deployment mode is bearer-token authentication only.

## Current Mode

- `AUTH_TRANSPORT=bearer` is the only supported value.
- Login and registration return a bearer token in the JSON response body.
- Authenticated requests must send `Authorization: Bearer <token>`.
- The application does not set session cookies.
- Logout revokes the server-side session record for the bearer token.
- Session expiry is controlled by `SESSION_EXPIRE_HOURS`.

Because browsers do not automatically attach bearer tokens from application state the way they attach cookies, API authentication is not currently exposed to normal cookie-based CSRF. The app still restricts CORS in production and sends security headers, but there is no CSRF token middleware because there are no authenticated cookie sessions to protect.

## Browser session recovery

The dashboard keeps its bearer token in browser `localStorage` and a runtime
copy. A temporary network/server failure during `GET /api/auth/me` no longer
deletes it: the protected shell stays hidden, a live status message explains
the failure, and **Retry session check** performs a fresh check. A `401` or
`403` clears the unusable browser credential. A response associated with an
older token cannot clear or replace newer session state.

Sign-in and registration share a single pending-action guard; credential
fields and auth buttons are disabled while authentication is pending. Both
actions use browser form validation. The password input is cleared after a
successful authentication response. The guard releases once the session is
verified, before dashboard reads finish, so slow data loading cannot prevent
sign-out. An older action cannot release a newer action's guard.

Auth and bootstrap requests have a 15-second timeout per request, with no
automatic replay. Aborting a browser request does not prove that the server
stopped processing it or rolled back a commit. Registration recovery below
still applies when a response is lost. Public bootstrap checks are sequential;
this is not a 15-second limit for the entire startup sequence.

Sign-out clears the browser token only after successful server revocation or
a `401` indicating the session is no longer valid. A network/server failure
shows an error and retains the credential so the user can retry; it must not
be described as a completed sign-out. These controls do not synchronize every
open tab or add cookie authentication. Browser storage remains exposed to
same-origin JavaScript, so CSP, XSS prevention, trusted-device use, and explicit
server-side revocation remain important.

## Registration transactions and recovery

Registration creates the account and its first bearer session in one database
transaction. A rejected insert or failed pre-commit session write leaves neither
behind. The response profile is captured before commit, avoiding a separate
post-commit account lookup.

A cheap existing-email check rejects known duplicates without hashing. That
read transaction ends before Argon2 hashing starts. The final insert uses the
unique email index to arbitrate races: concurrent sign-ups for the same
lowercased email produce one account/session and a `409` conflict for the loser,
without overwriting the winning account. Only an email conflict is handled as
that `409`; unrelated constraint or database failures remain sanitized errors.

**An error response is not proof that a commit failed.** A database can commit
successfully before its acknowledgement or the HTTP response is lost. In that
case, this app preserves the committed account and session rather than deleting
them as compensation. Retrying registration may return `409`; select **Sign in**
and use the credentials submitted during sign-up. The original bearer token is
not replayed. These controls do not add registration idempotency keys, email
verification, or password recovery; independent edge limits remain necessary.

## Account state at login

Login rejects disabled accounts with the same `401` message as incorrect
credentials and does not issue a session. After committing the throttle
reservation, it reads a scalar credential snapshot and releases the database
connection before password verification or a legacy-hash upgrade.

Before session creation, one conditional database update requires the same
user ID, email, password hash, and an active account. That update holds the
user row through the session transaction. If a disable, deletion, email change,
or password change means the current row no longer matches, authentication fails;
an older login cannot overwrite a replacement password with its legacy rehash.
Unrelated profile-name changes do not invalidate credentials.

The guarded update (including an unchanged hash), optional rehash, fenced
throttle clear, and session creation commit together. This adds a short write
to successful login, but no connection or row lock spans password hashing.
It is not a claim of increased target throughput or reduced hashing memory:
Argon2 settings and the request thread pool are unchanged.

This guard does not introduce an account-administration or password-reset UI.
It also does not retroactively cancel already-issued sessions when an operator
changes a password directly in the database. Existing session authentication
checks the account's current active flag; disabling an account is not permanent
session revocation if it is later re-enabled. Operators must revoke existing
sessions separately when that is required. Changes committed after login's
session transaction are outside its credential snapshot guarantee.

## Browser Security Headers

Every HTTP response includes:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy` restricted to same-origin scripts/styles/connects, no objects, same-origin forms, and no frame ancestors
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`

HTTPS requests also receive `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

## Production Controls

- Set `APP_ENV=production`.
- Keep `AUTH_TRANSPORT=bearer`.
- Restrict `CORS_ORIGINS` to trusted frontend origins.
- Serve the app only over HTTPS so bearer tokens are not sent over plaintext connections.
- Terminate TLS at the deployment edge and preserve HTTPS scheme forwarding so HSTS is emitted for browser traffic.
- The shipped dashboard persists its bearer token in `localStorage`; review that trusted-device/XSS tradeoff before deployment. Do not copy tokens into logs, URLs, analytics, screenshots, or exports. Clearing browser storage alone does not revoke a server-side session.
- Keep `API_RATE_LIMIT_REQUESTS` and `API_RATE_LIMIT_WINDOW_SECONDS` enabled for general API throttling in addition to login-specific throttling.
- Login throttling atomically reserves attempts before credential verification and stores a SHA-256 client/email identifier plus counters, timestamps, and an internal reservation fence. Only a still-latest successful attempt clears its window, in the same transaction as session creation. Expired records are reclaimed in bounded worker batches; lockout responses include `Retry-After`. See [atomic login admission](RATE_LIMITS.md#atomic-login-admission) for concurrency, interrupted-request, identity, and backlog limits.
- Use `POST /api/auth/logout` to revoke a session when the user signs out.

## If Cookie Auth Is Added Later

Cookie-based auth must not be enabled by configuration alone. It requires a code change and a new security review covering:

- `HttpOnly`, `Secure`, and `SameSite` cookie attributes
- CSRF token generation, storage, and validation for unsafe HTTP methods
- login/logout cookie rotation and clearing behavior
- CORS and credentialed request settings
- tests proving cross-site unsafe requests are rejected

Until that work exists, startup rejects unsupported `AUTH_TRANSPORT` values.
