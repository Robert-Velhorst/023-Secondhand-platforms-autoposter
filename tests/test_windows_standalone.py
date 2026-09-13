import os
from pathlib import Path

from app.launcher import configure_standalone_environment, default_data_dir, resource_root


def test_standalone_environment_is_persistent_private_and_worker_backed(tmp_path, monkeypatch):
    isolated_env = {"AUTOPOSTER_DATA_DIR": str(tmp_path)}
    monkeypatch.setattr(os, "environ", isolated_env)

    data_dir = configure_standalone_environment(8123)
    first_secret = os.environ["SECRET_KEY"]

    assert data_dir == tmp_path
    assert default_data_dir() == tmp_path
    assert len(first_secret) >= 32
    assert (tmp_path / ".standalone-secret").read_text(encoding="utf-8") == first_secret
    assert os.environ["APP_ENV"] == "standalone"
    assert os.environ["DATABASE_URL"].startswith("sqlite:///")
    assert os.environ["PUBLIC_BASE_URL"] == "http://127.0.0.1:8123"
    assert os.environ["CORS_ORIGINS"] == "http://127.0.0.1:8123"
    assert os.environ["DEV_AUTO_LOGIN"] == "false"
    assert os.environ["AUTO_CREATE_TABLES"] == "false"
    assert os.environ["JOB_PROCESS_INLINE"] == "false"

    os.environ.pop("SECRET_KEY")
    configure_standalone_environment(8123)
    assert os.environ["SECRET_KEY"] == first_secret


def test_packaging_contains_launcher_and_migrations():
    root = resource_root()
    launcher = (root / "app" / "launcher.py").read_text(encoding="utf-8")
    spec = (root / "packaging" / "autoposter.spec").read_text(encoding="utf-8")
    build = (root / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")

    assert "run_migrations()" in launcher
    assert "--worker-child" in launcher
    assert 'forwarded_allow_ips="127.0.0.1"' in launcher
    assert "SecondhandAutoposter" in spec
    assert "console=True" in spec
    assert "Get-FileHash" in build


def test_sites_hosting_is_not_misrepresented_for_fastapi_runtime():
    assert not Path(".openai/hosting.json").exists()
