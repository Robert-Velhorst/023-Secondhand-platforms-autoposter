"""Run real pytest children to verify collection cannot select application data."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_pytest_preserves_configured_database_and_uses_unique_local_storage(tmp_path):
    database = tmp_path / "existing-application.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        db.execute("INSERT INTO users VALUES (999, 'preserve@example.com')")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    uploads = tmp_path / "existing-uploads"
    uploads.mkdir()
    marker = uploads / "keep.txt"
    marker.write_text("existing application content", encoding="utf-8")
    env = os.environ.copy()
    env.update({"DATABASE_URL": f"sqlite:///{database.as_posix()}", "UPLOAD_DIR": str(uploads),
                "TOKEN_SECRET_DIR": str(tmp_path / "existing-secrets"),
                "APP_ENV": "production", "STORAGE_BACKEND": "s3", "S3_BUCKET": "do-not-use",
                "DEV_AUTO_LOGIN": "true", "AUTO_CREATE_TABLES": "false", "JOB_PROCESS_INLINE": "false"})
    child_code = """
import json
import sys
import pytest
code = pytest.main(['-q', 'tests/test_worker_health.py'])
from app.config import get_settings
from app.database import engine
settings = get_settings()
print('TEST_PATHS=' + json.dumps({'database': engine.url.database,
    'configured_database': settings.database_url,
    'uploads': settings.upload_dir, 'secrets': settings.token_secret_dir,
    'storage': settings.storage_backend, 'environment': settings.app_env}))
sys.exit(code)
"""
    results = []
    for _ in range(2):
        result = subprocess.run([sys.executable, "-c", child_code],
                                cwd=Path(__file__).resolve().parents[1], env=env,
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before, "Pytest altered application data"
        paths = json.loads(next(line.removeprefix("TEST_PATHS=") for line in result.stdout.splitlines()
                               if line.startswith("TEST_PATHS=")))
        root = Path(paths["database"]).parent
        assert Path(paths["uploads"]).parent == root
        assert Path(paths["secrets"]).parent == root
        assert paths["configured_database"] == f"sqlite:///{Path(paths['database']).as_posix()}"
        assert paths["storage"] == "local"
        assert paths["environment"] == "test"
        assert marker.read_text(encoding="utf-8") == "existing application content"
        assert not root.exists(), "Successful runs should clean up their own disposable storage"
        results.append(root)
    assert results[0] != results[1], "Separate pytest processes must not share a database or upload directory"


def test_preloaded_database_stops_pytest_before_destructive_fixtures(tmp_path):
    database = tmp_path / "preloaded.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    child_code = (
        "import app.database; import pytest; "
        "raise SystemExit(pytest.main(['-q', 'tests/test_worker_health.py']))"
    )
    result = subprocess.run([sys.executable, "-c", child_code],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode != 0
    assert "database was imported before test isolation" in result.stdout + result.stderr
    assert not database.exists(), "No database connection or schema mutation should occur"
