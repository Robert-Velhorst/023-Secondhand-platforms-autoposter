# Rate Limits And Cooldowns

The app includes a conservative per-platform cooldown for publishing jobs. This is designed to prevent rapid repeat attempts and to avoid implying that the app can evade marketplace restrictions.

## General API request limit

`API_RATE_LIMIT_REQUESTS` defaults to 300 and `API_RATE_LIMIT_WINDOW_SECONDS`
to 60. This is a fixed-window, in-memory limit **per API process**, separate
from database-backed failed-login throttling and publishing cooldowns.

- The key is a SHA-256 hash of the supplied Authorization header, or the client
  host observed by the app if that header is absent. This runs before route
  authentication: a supplied header is **not proof of a valid token or user**.
  Identity/header rotation can evade a per-identity quota. Proxy client-address
  handling and independent edge abuse controls must be reviewed for deployment.
- The limiter counts admitted API requests, including requests later rejected
  by authentication or validation. `/api/health` and non-API routes, including
  static assets, are excluded; this is not protection for every HTTP route.
- API windows use monotonic time, expire at the exact boundary, and are not
  extended by rejected requests. HTTP 429 includes a whole-second, rounded-up
  `Retry-After` and the usual retryable error envelope.
- State is capped at **10,000 identities per process**, with one expiry-index
  entry per identity, not per request. Expired entries are reclaimed on the next
  limited API request; an idle process may retain bounded expired state until
  then. Only hashes and counters/timestamps are stored, not raw header values.
- When full, the limiter rejects new identities until the earliest entry
  expires. Existing identities retain their remaining quota; active quotas are
  never evicted to make room. High identity churn can therefore temporarily
  deny new legitimate clients. The cap protects process memory, not fairness
  or availability under a distributed attack.
- One short lock protects expiry, admission, and counters across threads in
  the process. There is no database/network call or await inside it. Expiry
  cleanup is bounded by the 10,000-entry cap, but can add work to the first
  request after a large group of windows expires.

Restarting a process resets its API limiter. Multiple API processes do not
share these counters. Independently verified proxy/CDN/WAF limits, request-body
limits, and target load tests remain production requirements; this change is
not evidence that those controls exist. The database-backed login throttle is
unchanged by this API-memory hardening.

## Current Configuration

- Environment variables: `PLATFORM_RATE_LIMIT_SECONDS`, `PLATFORM_RATE_LIMIT_OVERRIDES`
- Default: `60`
- Scope: shared per platform across jobs
- Override format: comma-separated `platform=seconds`, for example `marktplaats=120,ebay=300`
- Behavior: if another job for the same platform started within the cooldown window, the next job remains queued and receives `next_retry_at`.

## Official API Quota Headers

Future official API adapters can return response metadata in `PublishOutcome.data` under one of these keys:

- `rate_limit_headers`
- `quota_headers`
- `response_headers`
- `headers`

The worker understands `Retry-After`, `RateLimit-Reset`, `X-RateLimit-Reset`, `RateLimit-Remaining`, and common dashed variants. If an adapter reports a `429` status or zero remaining quota with a reset time, the job is returned to `queued`, `next_retry_at` is persisted, and a warning log records the quota source. This keeps official API quota handling centralized instead of burying it inside each future adapter.

## Current Limitations

- Delayed jobs are persisted and picked up when due by a running, unpaused worker. Local tests verify this behavior, not the presence or health of a production worker.
- The frontend can show queued job state and logs, but does not yet show a dedicated countdown.
- Official API integrations are not implemented yet, so quota-header behavior is currently covered by adapter-level tests and worker simulation rather than live marketplace calls.

## Compliance Rule

Rate limiting must never be treated as something to bypass. If an official API later exposes quota headers or documented marketplace limits, the platform adapter must obey them and log delayed retries.

## Regression Tests

- A second job for the same platform is delayed.
- The job log includes the cooldown reason.
- `next_retry_at` is set.
- Permanent validation failures do not retry rapidly.
- Per-platform configured limits override the default.
- Official API `Retry-After` and reset headers requeue a job instead of retrying immediately.
