# Security and Privacy Design Review

## Trust boundaries

- Browser to API: bearer tokens only; production CORS must use explicit origins and HTTPS.
- API to database: all user-owned queries are scoped by authenticated owner ID.
- API/worker to marketplaces: no production adapter performs an unproved external publish.
- Uploads: file bytes cross an untrusted boundary and are checked by size, declared type, detected signature, safe filename, checksum, and storage backend.
- OAuth/secrets: APIs expose secret references and boolean configuration state, never token or client-secret values.

## Primary threats and controls

| Threat | Control | Residual risk |
| --- | --- | --- |
| Cross-user data access | Owner filters and isolation tests | New owner-owned routes require matching tests. |
| Session theft | Hashed opaque tokens, expiry, revocation, HTTPS requirement | Browser local storage remains exposed to same-origin script compromise. |
| Credential disclosure | Redaction, secret references, ignored runtime files, sanitized support bundles | Target secret-manager and rotation proof remain external. |
| Upload abuse/path traversal | Signature and size checks, safe generated paths, private S3 guidance | Malware scanning/image transformation is deployment-dependent. |
| Duplicate/false external action | Idempotency, bounded retries, assisted completion confirmation | Future official APIs need ambiguous-outcome reconciliation before enabling publish. |
| Worker runaway | Provider cooldowns, attempt limits, stale recovery, persistent operator pause | Operators must monitor paused state and resume intentionally. |
| Browser attacks | CSP, framing denial, MIME/referrer/permissions policies, HSTS in HTTPS | CSP must be re-reviewed if third-party assets are introduced. |

## Privacy impact assessment

The application stores account identity, listing content, images, marketplace metadata, job history, and sanitized audit events. Local analytics are derived in the same database and send no tracking data externally. Users can export JSON/CSV/images, review privacy activity, and delete their account and owned records. Audit events retain an email hash after user deletion for operational accountability and are purged according to `AUDIT_RETENTION_DAYS`; this residual retention must be reflected in the production privacy notice.

Production acceptance requires a named controller/processor, retention confirmation, target storage region, backup retention, access-control evidence, and incident contact.
