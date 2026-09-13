"""Select isolated test resources before pytest imports application modules."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from app.config import Settings, get_settings

if "app.database" in sys.modules:
    raise pytest.UsageError("Application database was imported before test isolation; disable application preloading.")

_test_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-runs"
_test_root.mkdir(parents=True, exist_ok=True)
_run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=_test_root))

# Ignore both inherited deployment values and .env overrides. Individual tests
# can still explicitly override Settings or use monkeypatch for the case under test.
for _name, _field in Settings.model_fields.items():
    os.environ[_name.upper()] = str(_field.default)
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{(_run_dir / 'test.db').as_posix()}",
    "UPLOAD_DIR": str(_run_dir / "uploads"),
    "TOKEN_SECRET_DIR": str(_run_dir / "secrets"),
    "PLATFORM_RATE_LIMIT_SECONDS": "0",
})
get_settings.cache_clear()


def pytest_addoption(parser):
    parser.addoption(
        "--job-postgres-url",
        help="Optional disposable PostgreSQL URL for job concurrency tests (database: autoposter_job_test_*).",
    )


def pytest_sessionfinish(session, exitstatus):
    if exitstatus != 0:
        return  # Retain failed-run fixtures for diagnosis.
    database = sys.modules.get("app.database")
    if database is not None:
        database.engine.dispose()
    resolved_run = _run_dir.resolve()
    if resolved_run.parent != _test_root.resolve():
        raise pytest.UsageError("Test resource path escaped its dedicated test-runs directory.")
    shutil.rmtree(resolved_run)
