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
- Store bearer tokens only in the frontend runtime needed by the static dashboard; do not copy them into logs, URLs, analytics, screenshots, or exports.
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
