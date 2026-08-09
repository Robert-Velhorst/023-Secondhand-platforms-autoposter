# HAI Connector

The app exposes an owner-scoped, read-only connector contract that HAI can consume without receiving the user's main login token.

## Connection Flow

1. Sign in to Secondhand Autoposter.
2. Open Settings and create a named HAI connector token with an expiry date.
3. Copy the `hai_...` token immediately; only its SHA-256 hash is stored and the plaintext is never shown again.
4. Configure the HAI HTTP source with the app base URL and `Authorization: Bearer hai_...`.
5. Read the discovery document at `/.well-known/hai-connector.json`, verify the connector with `GET /api/hai/status`, then consume `GET /api/hai/records`.

The feed is cursor-based. Persist `next_cursor` after each page and pass it as `cursor` on the next request. Upserts contain listing metadata and a source link; deletes are emitted as tombstones. Consumers should deduplicate by record `id` and apply events in cursor order.

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

For local Windows use, the source URL is `http://127.0.0.1:8000`. For an ngrok session, use the verified HTTPS URL printed by `scripts/start-ngrok.ps1`. HAI-side adapter registration is an external configuration step; this repository provides and tests the app-side protocol but does not silently modify another HAI installation.
