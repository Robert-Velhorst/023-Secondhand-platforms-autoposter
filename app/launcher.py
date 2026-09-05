"""Windows-friendly launcher for the API, worker, and local data directory."""

import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.processes import owned_process


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def default_data_dir() -> Path:
    configured = os.environ.get("AUTOPOSTER_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "SecondhandAutoposter"
    return Path.cwd() / "data"


def _persistent_secret(data_dir: Path) -> str:
    secret_path = data_dir / ".standalone-secret"
    if secret_path.exists():
        value = secret_path.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    value = secrets.token_urlsafe(48)
    secret_path.write_text(value, encoding="utf-8")
    try:
        secret_path.chmod(0o600)
    except OSError:
        pass
    return value


def configure_standalone_environment(port: int) -> Path:
    data_dir = default_data_dir()
    upload_dir = data_dir / "uploads"
    data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_origin = f"http://127.0.0.1:{port}"
    defaults = {
        "APP_ENV": "standalone",
        "SECRET_KEY": _persistent_secret(data_dir),
        "DATABASE_URL": f"sqlite:///{(data_dir / 'autoposter.db').as_posix()}",
        "UPLOAD_DIR": str(upload_dir),
        "TOKEN_SECRET_DIR": str(data_dir / "secrets"),
        "PUBLIC_BASE_URL": local_origin,
        "CORS_ORIGINS": local_origin,
        "AUTH_TRANSPORT": "bearer",
        "DEV_AUTO_LOGIN": "false",
        "AUTO_CREATE_TABLES": "false",
        "JOB_PROCESS_INLINE": "false",
        "LOG_FORMAT": "text",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    return data_dir


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    root = resource_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")


def _worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker-child"]
    return [sys.executable, "-m", "app.launcher", "--worker-child"]


def _open_when_ready(url: str) -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)


@contextmanager
def owned_listener(host: str, port: int) -> Iterator[socket.socket]:
    """Hold the loopback address continuously, including startup and cleanup."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Standalone listeners must use IPv4 loopback")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        yield listener


@contextmanager
def owned_data_directory(data_dir: Path) -> Iterator[None]:
    """Serialize cooperating launchers without a stale PID-file heuristic."""
    data_dir.mkdir(parents=True, exist_ok=True)
    # Keep this file: unlinking it could let two launchers lock different inodes.
    with (data_dir / ".launcher.lock").open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"\0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Standalone data directory is already in use or cannot be locked") from exc
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def serve(host: str, port: int, open_browser: bool) -> int:
    with owned_listener(host, port) as listener, owned_data_directory(default_data_dir()):
        port = listener.getsockname()[1]
        configure_standalone_environment(port)
        run_migrations()
        with owned_process(_worker_command()):
            if open_browser:
                threading.Thread(
                    target=_open_when_ready,
                    args=(f"http://127.0.0.1:{port}",),
                    daemon=True,
                ).start()
            import uvicorn

            from app.main import app

            server = uvicorn.Server(uvicorn.Config(
                app, host="127.0.0.1", port=port, proxy_headers=True,
                forwarded_allow_ips="127.0.0.1", access_log=False,
            ))
            # Uvicorn may close its socket; retain our own handle until child cleanup finishes.
            with listener.dup() as server_socket:
                server.run(sockets=[server_socket])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Secondhand Autoposter standalone launcher")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--worker-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.worker_child:
        configure_standalone_environment(args.port)
        from app.worker import run_forever

        run_forever()
        return 0
    return serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
