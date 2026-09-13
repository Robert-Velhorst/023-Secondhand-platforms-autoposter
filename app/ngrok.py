"""Owned ngrok process lifecycle. Starting this module's tunnel is an explicit public action."""

import ipaddress
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
import uuid
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.processes import owned_process


def public_origin(value: str) -> str:
    """Accept an HTTPS DNS origin, never credentials, paths, or local/IP endpoints."""
    if (not isinstance(value, str) or not value
            or any(character.isspace() or ord(character) < 32 for character in value)):
        raise ValueError("ngrok endpoint must be an HTTPS origin")
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("ngrok endpoint must be an HTTPS origin without credentials or a path")
    if ("." not in host or host.endswith((".local", ".localhost", ".internal", ".localdomain"))
            or len(host) > 253 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                                     for part in host.split("."))):
        raise ValueError("ngrok endpoint must use a public DNS hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return f"https://{host}"
    raise ValueError("ngrok endpoint cannot be an IP address")


@contextmanager
def tunnel_environment(public_url: str) -> Iterator[None]:
    overrides = {
        "APP_ENV": "standalone", "PUBLIC_BASE_URL": public_origin(public_url),
        "CORS_ORIGINS": public_origin(public_url), "AUTH_TRANSPORT": "bearer",
        "DEV_AUTO_LOGIN": "false", "AUTO_CREATE_TABLES": "false", "JOB_PROCESS_INLINE": "false",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@dataclass
class Tunnel:
    process: subprocess.Popen
    public_url: str
    log_dir: Path
    collector: "_AgentLog | None" = None

    def check_alive(self):
        if self.process.poll() is not None:
            raise RuntimeError(f"ngrok stopped; inspect {self.log_dir}")
        if self.collector and self.collector.error:
            raise RuntimeError(f"{self.collector.error}; inspect {self.log_dir}")


class _FailClosedLogHandler(RotatingFileHandler):
    def handleError(self, record):
        # The stdlib default swallows I/O errors and may print the raw provider
        # record. Propagate only a fixed error to the owning lifecycle instead.
        raise OSError("ngrok log write failed")


class _AgentLog:
    def __init__(self, stream, path: Path, upstream: str, requested_origin: str):
        self.stream = stream
        self.upstream = upstream
        self.requested_origin = requested_origin
        self.public_url = ""
        self.error = ""
        self.ready = threading.Event()
        self.handler = _FailClosedLogHandler(path, maxBytes=65536, backupCount=3, encoding="utf-8")
        self.thread = threading.Thread(target=self.read, name="ngrok-log-reader", daemon=True)

    def read(self):
        discarding_line = False
        try:
            while chunk := self.stream.readline(65537):
                if discarding_line:
                    discarding_line = not chunk.endswith(b"\n")
                    continue
                oversized = len(chunk) > 65536
                line = ("[oversized ngrok log record omitted]" if oversized
                        else chunk.decode("utf-8", errors="replace").rstrip("\r\n"))
                self.handler.emit(logging.LogRecord("ngrok", logging.INFO, "", 0, line, (), None))
                if oversized:
                    discarding_line = not chunk.endswith(b"\n")
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, RecursionError):
                    continue
                if (not isinstance(event, dict) or event.get("msg") != "started tunnel"
                        or event.get("addr") != self.upstream):
                    continue
                try:
                    origin = public_origin(event.get("url", ""))
                except (ValueError, TypeError):
                    self.error = "ngrok reported an invalid HTTPS endpoint"
                    self.ready.set()
                    continue
                if self.requested_origin and origin != self.requested_origin:
                    self.error = "ngrok reported a different endpoint than requested"
                elif self.public_url and origin != self.public_url:
                    self.error = "ngrok changed its endpoint during this run"
                else:
                    self.public_url = origin
                self.ready.set()
        except Exception:
            self.error = "ngrok log stream failed"
        finally:
            # Once observation ends, a still-running agent is not a healthy tunnel.
            # Normal context cleanup also produces EOF, but does not recheck readiness.
            if not self.error:
                self.error = "ngrok log stream ended"
            self.ready.set()
            try:
                self.handler.close()
            except Exception:
                self.error = "ngrok log close failed"

    def finish(self, timeout: float = 5) -> None:
        if self.thread.ident is not None:
            self.thread.join(timeout=timeout)
        if self.thread.is_alive():
            # BufferedReader.close() can wait indefinitely for an active readline.
            # Report the failed teardown without acquiring that reader's I/O lock.
            raise RuntimeError("ngrok log reader did not stop")
        failed = self.error == "ngrok log close failed"
        for resource in (self.handler, self.stream):
            try:
                resource.close()
            except Exception:
                failed = True
        if failed:
            raise RuntimeError("ngrok log cleanup failed") from None


@contextmanager
def managed_tunnel(
    listener: socket.socket, data_dir: Path, *, command: list[str] | None = None,
    domain: str = "", timeout: float = 30,
) -> Iterator[Tunnel]:
    address, port = listener.getsockname()
    if address != "127.0.0.1" or not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN):
        raise ValueError("ngrok requires an already-owned IPv4 loopback listener")
    requested = public_origin(domain if "://" in domain else f"https://{domain}") if domain else ""
    upstream = f"http://127.0.0.1:{port}"
    arguments = [*(command or ["ngrok"]), "http", upstream, "--inspect=false", "--pooling-enabled=false",
                 "--log=stdout", "--log-format=json"]
    if requested:
        arguments.append(f"--url={requested}")
    log_dir = data_dir / "runtime" / f"ngrok-{uuid.uuid4().hex}"
    log_dir.mkdir(parents=True, exist_ok=False)
    collector = None
    process = None
    try:
        with owned_process(
            arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        ) as process:
            collector = _AgentLog(process.stdout, log_dir / "ngrok.log", upstream, requested)
            collector.thread.start()
            deadline = time.monotonic() + timeout
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"ngrok exited before readiness; inspect {log_dir}")
                if collector.error:
                    raise RuntimeError(f"{collector.error}; inspect {log_dir}")
                if collector.public_url:
                    yield Tunnel(process, collector.public_url, log_dir, collector)
                    return
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"ngrok did not report an HTTPS endpoint before timeout; inspect {log_dir}")
                collector.ready.wait(min(0.1, max(0, deadline - time.monotonic())))
    finally:
        # Terminate the owned tree before joining a reader waiting for its pipe's EOF.
        if collector:
            collector.finish()
        elif process and process.stdout:
            process.stdout.close()


class InstanceHealth:
    """Attach a per-launch marker only to readiness responses, never an auth credential."""

    def __init__(self, app, instance: str):
        self.app = app
        self.instance = instance.encode("ascii")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] not in {"/api/health", "/api/worker-status"}:
            await self.app(scope, receive, send)
            return

        async def identified_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", [])
                    if key.lower() not in {b"x-autoposter-instance", b"cache-control"}
                ] + [(b"x-autoposter-instance", self.instance), (b"cache-control", b"no-store")]
            await send(message)

        await self.app(scope, receive, identified_send)


def instance_ready(client: httpx.Client, origin: str, instance: str) -> bool:
    for path in ("/api/health", "/api/worker-status"):
        try:
            started = time.monotonic()
            params = {"worker_id": f"worker-{instance}"} if path == "/api/worker-status" else None
            with client.stream(
                "GET", origin + path, params=params, headers={"Accept-Encoding": "identity"}, timeout=2,
            ) as response:
                if response.status_code != 200 or response.headers.get("X-Autoposter-Instance") != instance:
                    return False
                body = bytearray()
                for chunk in response.iter_raw():
                    if len(body) + len(chunk) > 8192 or time.monotonic() - started > 2:
                        return False
                    body.extend(chunk)
                value = json.loads(body)
                if not isinstance(value, dict) or value.get("status") != "ok":
                    return False
                if path == "/api/worker-status" and (
                    type(value.get("active_workers")) is not int or value["active_workers"] != 1
                    or value.get("worker_id") != f"worker-{instance}"
                ):
                    return False
        except (httpx.HTTPError, ValueError, RecursionError):
            return False
    return True


@contextmanager
def monitor_session(server, tunnel: Tunnel, worker: subprocess.Popen, local_url: str, instance: str,
                    *, verify_only: bool, open_browser: bool, timeout: float = 180):
    stop = threading.Event()
    ready = threading.Event()
    errors = []

    def monitor():
        try:
            deadline = time.monotonic() + timeout
            # No environment proxies, redirects, or disabled TLS verification.
            with httpx.Client(trust_env=False, follow_redirects=False) as client:
                while not stop.wait(0.2):
                    tunnel.check_alive()
                    if worker.poll() is not None:
                        raise RuntimeError("The owned worker stopped; stopping the app and ngrok")
                    if ready.is_set():
                        continue
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "ngrok readiness timed out: API, worker, and public instance must all be healthy"
                        )
                    if not instance_ready(client, local_url, instance) or stop.is_set():
                        continue
                    if not instance_ready(client, tunnel.public_url, instance) or stop.is_set():
                        continue
                    tunnel.check_alive()
                    if worker.poll() is not None:
                        raise RuntimeError("The owned worker stopped during readiness checks")
                    ready.set()
                    print(f"Verified local/public API and worker for this instance: {tunnel.public_url}", flush=True)
                    print(f"ngrok logs: {tunnel.log_dir}", flush=True)
                    if verify_only:
                        server.should_exit = True
                        return
                    print("Press Ctrl+C to stop this app and its tunnel.", flush=True)
                    if open_browser:
                        webbrowser.open(tunnel.public_url)
        except Exception as exc:
            # Keep arbitrary provider/HTTP exception details out of console output.
            errors.append(str(exc) if isinstance(exc, RuntimeError) else "ngrok readiness monitor failed")
            server.should_exit = True

    thread = threading.Thread(target=monitor, name="ngrok-readiness-monitor", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=10)
    if thread.is_alive():
        raise RuntimeError("ngrok readiness monitor did not stop")
    if errors:
        raise RuntimeError(errors[0])
    if verify_only and not ready.is_set():
        raise RuntimeError("The server stopped before ngrok readiness was verified")
