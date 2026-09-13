"""Windows-friendly launcher for the API, worker, and local data directory."""

import argparse
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace

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


def _api_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--api-child"]
    return [sys.executable, "-m", "app.launcher", "--api-child"]


@contextmanager
def owned_api(listener: socket.socket, instance: str, bootstrap: Path) -> Iterator[subprocess.Popen]:
    """Keep all API threads inside an owned process before releasing data ownership."""
    command = [*_api_command(), "--instance-id", instance, "--api-bootstrap", str(bootstrap),
               "--port", str(listener.getsockname()[1])]
    options = {} if os.name == "nt" else {"pass_fds": (listener.fileno(),)}
    with owned_process(command, stdin=subprocess.PIPE, **options) as process:
        try:
            deadline = time.monotonic() + 180
            while True:
                if process.poll() is not None:
                    raise RuntimeError("The owned API stopped before socket handoff")
                try:
                    with bootstrap.open("rb") as record:
                        raw_pid = record.read(32)
                except FileNotFoundError:
                    raw_pid = b""
                if raw_pid:
                    if not raw_pid.isdigit() or len(raw_pid) > 20 or int(raw_pid) <= 0:
                        raise RuntimeError("The owned API reported an invalid socket handoff")
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("The owned API did not request its socket before timeout")
                time.sleep(0.02)
            # Windows launchers/bootloaders can have a different PID from the real
            # interpreter. The child reports its own PID in this unique run directory;
            # the socket payload goes only through that owned child's stdin pipe.
            payload = listener.share(int(raw_pid)).hex() if os.name == "nt" else str(listener.fileno())
            process.stdin.write(payload.encode("ascii") + b"\n")
            process.stdin.flush()
            process.stdin.close()
            yield process
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()


def serve_api_child(bootstrap: Path, instance: str) -> int:
    temporary = bootstrap.with_suffix(".tmp")
    temporary.write_text(str(os.getpid()), encoding="ascii")
    temporary.replace(bootstrap)
    raw = sys.stdin.buffer.readline(8193)
    if not raw.endswith(b"\n") or len(raw) > 8192:
        raise RuntimeError("Invalid API socket handoff")
    listener = (socket.fromshare(bytes.fromhex(raw.decode("ascii").strip())) if os.name == "nt"
                else socket.socket(fileno=int(raw)))
    try:
        with listener:
            _run_api(listener, instance)
    finally:
        # A server can return while non-daemon request threads are still alive.
        # Tell the supervisor to terminate the whole owned API, not just its server.
        try:
            bootstrap.with_suffix(".stopped").touch()
        except OSError:
            # Storage failure must not strand non-daemon request threads. Exit
            # this dedicated API interpreter; the supervisor owns tree cleanup.
            os._exit(1)
    return 0


def _run_api(listener: socket.socket, instance: str = "") -> None:
    import uvicorn

    from app.main import app
    from app.ngrok import InstanceHealth

    server = uvicorn.Server(uvicorn.Config(
        InstanceHealth(app, instance) if instance else app, host="127.0.0.1", port=listener.getsockname()[1],
        proxy_headers=True, forwarded_allow_ips="127.0.0.1", access_log=False,
    ))
    with listener.dup() as server_socket:
        server.run(sockets=[server_socket])


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


def serve(host: str, port: int, open_browser: bool, *, ngrok_path: str | None = None,
          ngrok_domain: str = "", verify_only: bool = False) -> int:
    with owned_listener(host, port) as listener, owned_data_directory(default_data_dir()):
        port = listener.getsockname()[1]
        with ExitStack() as lifecycle:
            tunnel = None
            if ngrok_path is not None:
                from app.ngrok import managed_tunnel, monitor_session, tunnel_environment

                tunnel = lifecycle.enter_context(managed_tunnel(
                    listener, default_data_dir(), command=[ngrok_path], domain=ngrok_domain,
                ))
                lifecycle.enter_context(tunnel_environment(tunnel.public_url))
            configure_standalone_environment(port)
            run_migrations()
            instance = secrets.token_hex(16) if tunnel else ""
            worker_command = _worker_command()
            if instance:
                worker_command += ["--worker-id", f"worker-{instance}"]
            worker = lifecycle.enter_context(owned_process(worker_command))
            if open_browser and tunnel is None:
                threading.Thread(
                    target=_open_when_ready,
                    args=(f"http://127.0.0.1:{port}",),
                    daemon=True,
                ).start()
            if tunnel:
                bootstrap = tunnel.log_dir / "api.pid"
                api = lifecycle.enter_context(owned_api(listener, instance, bootstrap))
                server = SimpleNamespace(should_exit=False)
                lifecycle.enter_context(monitor_session(
                    server, tunnel, worker, f"http://127.0.0.1:{port}", instance,
                    verify_only=verify_only, open_browser=open_browser,
                ))
                try:
                    while not server.should_exit:
                        if api.poll() is not None or bootstrap.with_suffix(".stopped").exists():
                            raise RuntimeError("The owned API stopped; stopping the worker and ngrok")
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    pass
            else:
                _run_api(listener)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Secondhand Autoposter standalone launcher")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--ngrok", action="store_true", help="Explicitly expose this instance through ngrok HTTPS")
    parser.add_argument("--ngrok-path", default="ngrok", help="Path to an installed ngrok executable")
    parser.add_argument("--ngrok-domain", default="", help="Reserved ngrok hostname or HTTPS origin")
    parser.add_argument("--verify-only", action="store_true", help="Verify ngrok API/worker readiness, then stop")
    parser.add_argument("--worker-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--api-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api-bootstrap", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--instance-id", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if (args.verify_only or args.ngrok_domain) and not args.ngrok:
        parser.error("--verify-only and --ngrok-domain require --ngrok")
    if args.worker_child and args.ngrok:
        parser.error("Worker child mode cannot start ngrok")
    if args.api_child:
        if (args.worker_child or args.ngrok or args.api_bootstrap is None
                or not re.fullmatch(r"[0-9a-f]{32}", args.instance_id)):
            parser.error("API child mode requires a socket bootstrap and generated instance identity")
        return serve_api_child(args.api_bootstrap, args.instance_id)
    if args.api_bootstrap is not None or args.instance_id:
        parser.error("API socket options require API child mode")
    if args.worker_id and (not args.worker_child or not re.fullmatch(r"worker-[0-9a-f]{32}", args.worker_id)):
        parser.error("--worker-id requires worker child mode and a generated worker identity")
    if args.worker_child:
        configure_standalone_environment(args.port)
        from app.worker import run_forever

        run_forever(worker_id=args.worker_id or None)
        return 0
    return serve(args.host, args.port, not args.no_browser,
                 ngrok_path=args.ngrok_path if args.ngrok else None,
                 ngrok_domain=args.ngrok_domain, verify_only=args.verify_only)


if __name__ == "__main__":
    raise SystemExit(main())
