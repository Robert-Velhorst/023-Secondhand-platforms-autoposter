"""Verify SQLite before frozen application imports or data access."""

from app.sqlite_runtime import require_stable_sqlite

require_stable_sqlite()
