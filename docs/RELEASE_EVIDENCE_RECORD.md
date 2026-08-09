# Release Evidence Record

Use this record for the final client-launch decision. Leave entries as `Not captured` until the evidence exists; do not replace missing evidence with assumptions.

## Local Hardening Evidence (Not Target-Launch Evidence)

| Gate | Evidence |
| --- | --- |
| Automated tests | 226 passed in one complete gate run on 2026-08-09 |
| Migration drill | Empty SQLite database upgraded to `20260809_0013`; target PostgreSQL evidence still requires deployment input |
| Windows standalone | Finalized EXE API and worker healthy; SHA-256 recorded in `docs/WINDOWS_STANDALONE.md` |
| HAI connector | Owner-scoped read-only token and incremental feed tests passed |
| Ngrok | Launcher fails closed and cleans up; live endpoint blocked by `ERR_NGROK_334` |
| Dependency audit | Installed environment: no known vulnerabilities; GitHub requirements-file check pending |

## Release Identity

| Field | Evidence |
| --- | --- |
| Release decision date | Not captured |
| Decision owner | Not captured |
| Commit SHA deployed | Not captured |
| Branch and remote | Not captured |
| Environment name | Not captured |
| Deployment URL | Not captured |

## Verification Evidence

| Gate | Evidence |
| --- | --- |
| Clean checkout verification command | Not captured |
| `python scripts/verify.py` output | Not captured |
| `python -m app.doctor --json` output | Not captured |
| Known warnings accepted for launch | Not captured |
| Final no-excuses search date and findings | Not captured |
| Final acceptance record | Not captured; use `docs/FINAL_ACCEPTANCE_RECORD.md` |

## Deployment Evidence

| Gate | Evidence |
| --- | --- |
| `APP_ENV=production` confirmed | Not captured |
| Default `SECRET_KEY` rejected | Not captured |
| Restrictive `CORS_ORIGINS` confirmed | Not captured |
| `AUTH_TRANSPORT=bearer` confirmed | Not captured |
| Alembic head on target database | Not captured |
| Worker process status | Not captured |
| Upload storage writable and backed up | Not captured |
| Backup restore test result | Not captured |
| Rollback procedure tested or accepted | Not captured |

## Security And Privacy Evidence

| Gate | Evidence |
| --- | --- |
| Edge/proxy rate-limit evidence | Not captured |
| Export/log secret scan result | Not captured |
| Production secret-manager or env handling | Not captured |
| OAuth/API credential proof with secrets redacted | Not captured |
| Legal/platform compliance acceptance | Not captured |

## Product Acceptance Evidence

| Gate | Evidence |
| --- | --- |
| Real non-technical user walkthrough | Not captured; use `docs/NON_TECHNICAL_USER_WALKTHROUGH_RECORD.md` |
| Keyboard navigation evidence | Not captured |
| Zoom evidence | Not captured |
| Screen-reader evidence | Not captured |
| Assisted-posting limitations accepted | Not captured |
| Platform limitations visible to client | Not captured |

## Launch Decision

| Field | Evidence |
| --- | --- |
| Decision | Not captured |
| Remaining accepted risks | Not captured |
| Blockers deferred with owner/date | Not captured |
| Final response readiness | Not captured; use `docs/FINAL_RESPONSE_REQUIREMENTS.md` |
