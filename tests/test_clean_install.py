"""Exercise the documented source setup with a fresh, unedited environment copy."""

import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import httpx

from app.config import Settings
from app.processes import owned_process


def test_fresh_example_supports_migrations_api_worker_and_saved_listing(tmp_path):
    root = Path(__file__).resolve().parents[1]
    checkout = tmp_path / "fresh-checkout"
    checkout.mkdir()
    for directory in ("app", "migrations", "public"):
        shutil.copytree(root / directory, checkout / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(root / "alembic.ini", checkout / "alembic.ini")
    shutil.copyfile(root / ".env.example", checkout / ".env")
    env = dict(os.environ)
    for name in Settings.model_fields:
        env.pop(name.upper(), None)
    env["PYTHONPATH"] = str(checkout)

    with owned_process(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=checkout, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ) as migration:
        output, _ = migration.communicate(timeout=30)
        assert migration.returncode == 0, output.decode(errors="replace")

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with (tmp_path / "runtime.log").open("w", encoding="utf-8") as log:
        with owned_process(
            [sys.executable, "-m", "app.worker"], cwd=checkout, env=env,
            stdout=log, stderr=subprocess.STDOUT,
        ) as worker, owned_process(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=checkout, env=env, stdout=log, stderr=subprocess.STDOUT,
        ) as api, httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=2) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                assert api.poll() is None and worker.poll() is None, "Fresh source API or worker exited"
                try:
                    if client.get("/api/health").status_code == client.get("/api/worker-status").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                raise AssertionError("Fresh source API and worker did not become healthy")

            assert client.get("/").status_code == 200
            registration = client.post("/api/auth/register", json={
                "email": "fresh-install@example.com", "name": "Fresh install",
                "password": "fresh-install-only-password",
            })
            assert registration.status_code == 200
            headers = {"Authorization": "Bearer " + registration.json()["token"]}
            created = client.post("/api/listings", headers=headers, json={"title": "Fresh setup chair"})
            assert created.status_code == 200
            saved = client.get(f"/api/listings/{created.json()['id']}", headers=headers)
            assert saved.status_code == 200 and saved.json()["title"] == "Fresh setup chair"
            # Verify committed state through a separate connection before forced
            # test cleanup; immediate post-kill OS handle release is not setup.
            with closing(sqlite3.connect(checkout / "data" / "autoposter.db")) as database:
                assert database.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260913_0015"
                assert database.execute("SELECT title FROM listings").fetchall() == [("Fresh setup chair",)]
    assert api.poll() is not None and worker.poll() is not None
