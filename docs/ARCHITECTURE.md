# Architecture

The application is a FastAPI service with a static dashboard mounted from `public/`.

## Backend Shape

- `app/main.py` builds the application, applies middleware, validates startup settings, and includes route modules.
- `app/routes/system.py` owns health, diagnostics, metrics, localization, analytics, and account-readiness routes.
- `app/routes/auth.py` owns registration, login, logout, current-user lookup, and self-service account deletion.
- `app/routes/hai.py` owns the read-only HAI discovery, token, status, and incremental record-feed contract.
- `app/api.py` owns product routes for platforms, listings, images, publishing jobs, accounts, OAuth handoff, templates, category mappings, audit events, and data portability.
- `app/launcher.py` owns the Windows standalone bootstrap, persistent local settings, migrations, and API/worker lifecycle.
- `app/dependencies.py` owns shared request dependencies such as bearer-session lookup and current-user resolution.
- `app/services/` holds domain workflows that need to stay independent of route wiring, including jobs, audit events, OAuth state, localization, analytics, and quality checks.

## Data And Boundary Rules

Routes should stay thin: they validate HTTP input, enforce ownership through `get_current_user`, and delegate reusable behavior to service modules. Shared dependencies belong in `app/dependencies.py`, not inside a feature route module. New broad product areas should get a dedicated route module under `app/routes/` and be included from `app/main.py`.

The app uses SQLAlchemy models in `app/models.py` with Alembic migrations under `migrations/versions/`. Listing model events append owner-scoped HAI change rows in the same transaction. SQLite is the local/standalone default; production still requires target PostgreSQL migration evidence as tracked in the completion matrix.

## Verification

`tests/test_architecture.py` guards the current module boundaries so auth/system routes and shared session dependencies do not drift back into the product API module. The full local gate remains:

```bash
python scripts/verify.py
```
