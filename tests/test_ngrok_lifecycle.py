import io
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app import launcher


@pytest.fixture
def fake_agent(tmp_path, monkeypatch):
    record = tmp_path / "agent-record.json"
    monkeypatch.setenv("NGROK_TEST_RECORD", str(record))
    return [sys.executable, str(Path("tests/fixtures/ngrok_child.py").resolve())], record


def test_ngrok_cli_rejects_occupied_port_before_tunnel_or_data(tmp_path, monkeypatch):
    data = tmp_path / "not-created"
    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(data))
    with launcher.owned_listener("127.0.0.1", 0) as listener:
        with pytest.raises(OSError):
            launcher.main(["--ngrok", "--ngrok-path", str(tmp_path / "must-not-run"),
                           "--port", str(listener.getsockname()[1]), "--no-browser"])
    assert not data.exists()


def test_tunnel_uses_held_port_private_logs_and_owned_cleanup(tmp_path, fake_agent):
    from app.ngrok import managed_tunnel

    command, record = fake_agent
    with launcher.owned_listener("127.0.0.1", 0) as listener:
        with managed_tunnel(listener, tmp_path, command=command, domain="owned.example") as tunnel:
            assert tunnel.public_url == "https://owned.example"
            captured = json.loads(record.read_text())
            assert captured["port_owned"] is True
            assert captured["args"] == [
                "http", f"http://127.0.0.1:{listener.getsockname()[1]}", "--inspect=false",
                "--pooling-enabled=false", "--log=stdout", "--log-format=json", "--url=https://owned.example",
            ]
            assert tunnel.process.poll() is None
            first_dir = tunnel.log_dir
        assert tunnel.process.poll() is not None
        with managed_tunnel(listener, tmp_path, command=command) as other:
            assert other.log_dir != first_dir
        with socket.socket() as competing:
            with pytest.raises(OSError):
                competing.bind(listener.getsockname())


@pytest.mark.parametrize("mode", ["exit", "silent"])
def test_failed_tunnel_start_stops_child_and_keeps_listener_owned(tmp_path, fake_agent, monkeypatch, mode):
    from app.ngrok import managed_tunnel

    command, _record = fake_agent
    monkeypatch.setenv("NGROK_TEST_MODE", mode)
    with launcher.owned_listener("127.0.0.1", 0) as listener:
        with pytest.raises(RuntimeError, match="ngrok"):
            with managed_tunnel(listener, tmp_path, command=command, timeout=2):
                pytest.fail("Unready ngrok fixture was accepted")
        with socket.socket() as competing:
            with pytest.raises(OSError):
                competing.bind(listener.getsockname())


@pytest.mark.parametrize("url", [
    "http://review.example", "https://user:password@review.example", "https://review.example/path",
    "https://review.example?token=private", "https://review.example#fragment", "https://127.0.0.1",
    "https://localhost", "https://review.example:8000", "https://review.example/\n",
])
def test_tunnel_rejects_non_origin_or_local_endpoint_values(url):
    from app.ngrok import public_origin

    with pytest.raises(ValueError):
        public_origin(url)


@pytest.mark.parametrize("url", [17, True, ["https://owned.example"], {"url": "https://owned.example"}])
def test_tunnel_rejects_malformed_log_url_types_without_reader_crash(url):
    from app.ngrok import public_origin

    with pytest.raises(ValueError):
        public_origin(url)


def test_tunnel_health_fails_when_log_pipe_ends_but_agent_is_alive(tmp_path):
    from app.ngrok import Tunnel, _AgentLog

    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, "rb") as stream, os.fdopen(write_fd, "wb") as writer:
        collector = _AgentLog(stream, tmp_path / "ngrok.log", "http://127.0.0.1:8000", "")
        collector.thread.start()
        try:
            writer.write(json.dumps({"msg": "started tunnel", "addr": "http://127.0.0.1:8000",
                                     "url": "https://owned.example"}).encode() + b"\n")
            writer.flush()
            assert collector.ready.wait(2)
            assert collector.public_url == "https://owned.example"
            writer.close()
            collector.thread.join(timeout=2)
            assert not collector.thread.is_alive()
            with launcher.owned_process([sys.executable, "-c", "import time; time.sleep(60)"]) as process:
                assert process.poll() is None
                with pytest.raises(RuntimeError, match="log stream"):
                    Tunnel(process, collector.public_url, tmp_path, collector).check_alive()
        finally:
            writer.close()
            collector.thread.join(timeout=2)


def test_closed_log_stream_reports_a_sanitized_lifecycle_error(tmp_path):
    from app.ngrok import _AgentLog

    stream = io.BytesIO()
    stream.close()
    collector = _AgentLog(stream, tmp_path / "ngrok.log", "http://127.0.0.1:8000", "")
    collector.thread.start()
    collector.thread.join(timeout=2)
    assert not collector.thread.is_alive()
    assert collector.error == "ngrok log stream failed"
    assert collector.ready.is_set()


def test_log_write_failure_stops_observation_without_printing_provider_record(tmp_path, capsys):
    from app.ngrok import _AgentLog

    record = b'{"msg":"sensitive-provider-detail"}\n'
    collector = _AgentLog(io.BytesIO(record), tmp_path / "ngrok.log", "http://127.0.0.1:8000", "")
    collector.handler.stream.close()
    collector.handler.stream = (tmp_path / "ngrok.log").open("r", encoding="utf-8")
    collector.read()
    assert collector.error == "ngrok log stream failed"
    assert "sensitive-provider-detail" not in capsys.readouterr().err


def test_oversized_log_line_cannot_smuggle_a_valid_endpoint_in_its_suffix(tmp_path):
    from app.ngrok import _AgentLog

    event = json.dumps({"msg": "started tunnel", "addr": "http://127.0.0.1:8000",
                        "url": "https://wrong.example"}).encode()
    stream = io.BytesIO(b"x" * 65537 + event + b"\n")
    collector = _AgentLog(stream, tmp_path / "ngrok.log", "http://127.0.0.1:8000", "")
    collector.read()
    assert collector.public_url == "", "A fragment of one invalid log line became a valid endpoint event"


def test_log_close_failures_are_sanitized_and_remaining_stream_is_closed(tmp_path, monkeypatch):
    from app.ngrok import _AgentLog

    stream = io.BytesIO()
    collector = _AgentLog(stream, tmp_path / "ngrok.log", "http://127.0.0.1:8000", "")
    original_close = collector.handler.close
    calls = 0

    def failed_close():
        nonlocal calls
        calls += 1
        original_close()
        if calls == 1:
            raise OSError("raw-private-flush-detail")

    monkeypatch.setattr(collector.handler, "close", failed_close)
    collector.read()
    assert collector.error == "ngrok log close failed"
    with pytest.raises(RuntimeError, match="^ngrok log cleanup failed$") as error:
        collector.finish()
    assert error.value.__suppress_context__
    assert stream.closed


def test_reader_teardown_does_not_close_a_pipe_while_its_reader_is_blocked(tmp_path):
    from app.ngrok import _AgentLog

    # A real pipe remains blocked until its writer closes. Closing its BufferedReader
    # from the owning thread would itself block on the active read lock.
    read_fd, write_fd = os.pipe()
    stream = os.fdopen(read_fd, "rb")
    writer = os.fdopen(write_fd, "wb")
    collector = _AgentLog(stream, tmp_path / "ngrok.log", "http://127.0.0.1:8000", "")
    collector.thread.start()
    try:
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="reader did not stop"):
            collector.finish(timeout=0.05)
        assert time.monotonic() - started < 2
        assert not stream.closed
    finally:
        writer.close()
        collector.thread.join(timeout=2)
        stream.close()


def test_tunnel_environment_changes_are_restored(tmp_path, monkeypatch):
    from app.ngrok import tunnel_environment

    monkeypatch.setenv("CORS_ORIGINS", "https://original.example")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    before = dict(os.environ)
    with pytest.raises(ValueError):
        with tunnel_environment("https://owned.example"):
            assert os.environ["PUBLIC_BASE_URL"] == "https://owned.example"
            assert os.environ["CORS_ORIGINS"] == "https://owned.example"
            assert os.environ["APP_ENV"] == "standalone"
            assert os.environ["AUTH_TRANSPORT"] == "bearer"
            assert os.environ["DEV_AUTO_LOGIN"] == os.environ["AUTO_CREATE_TABLES"] == "false"
            assert os.environ["JOB_PROCESS_INLINE"] == "false"
            raise ValueError("controlled startup failure")
    assert dict(os.environ) == before


@contextmanager
def health_server(worker_ok=True, identity="expected-instance", large=False, worker_identity=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            healthy = worker_ok or self.path == "/api/health"
            self.send_response(200 if healthy else 503)
            self.send_header("X-Autoposter-Instance", identity)
            self.end_headers()
            body = {"status": "ok" if healthy else "error", "active_workers": int(worker_ok)}
            if self.path.startswith("/api/worker-status"):
                body["worker_id"] = (worker_identity if worker_identity is not None
                                     else parse_qs(urlsplit(self.path).query).get("worker_id", [None])[0])
            self.wfile.write(b"x" * 9000 if large else json.dumps(body).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("worker_ok,identity,large,expected", [
    (True, "expected-instance", False, True), (False, "expected-instance", False, False),
    (True, "different-instance", False, False), (True, "expected-instance", True, False),
])
def test_readiness_requires_real_api_worker_instance_and_bounded_body(worker_ok, identity, large, expected):
    from app.ngrok import instance_ready

    with health_server(worker_ok, identity, large) as url, httpx.Client(trust_env=False) as client:
        assert instance_ready(client, url, "expected-instance") is expected


def test_readiness_rejects_a_response_for_a_different_worker_even_with_the_right_api_instance():
    from app.ngrok import instance_ready

    with health_server(worker_identity="worker-other") as url, httpx.Client(trust_env=False) as client:
        assert instance_ready(client, url, "expected-instance") is False


def test_ngrok_launch_requires_both_ownership_locks_before_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(tmp_path))
    with launcher.owned_data_directory(tmp_path):
        with pytest.raises(RuntimeError, match="already in use"):
            launcher.main(["--ngrok", "--ngrok-path", str(tmp_path / "must-not-run"), "--no-browser"])
    assert not (tmp_path / ".standalone-secret").exists()


def test_requested_domain_must_match_reported_endpoint(tmp_path, fake_agent):
    from app.ngrok import managed_tunnel

    command, _record = fake_agent
    with launcher.owned_listener("127.0.0.1", 0) as listener:
        with pytest.raises(RuntimeError, match="different endpoint"):
            with managed_tunnel(listener, tmp_path, command=command, domain="requested.example"):
                pytest.fail("Different endpoint accepted")


@pytest.mark.parametrize("worker_ok", [True, False])
def test_verify_only_stops_after_both_health_checks_or_fails(tmp_path, worker_ok, capsys):
    from app.ngrok import Tunnel, monitor_session

    server = SimpleNamespace(should_exit=False)
    with launcher.owned_process([sys.executable, "-c", "import time; time.sleep(60)"]) as process:
        with health_server(worker_ok=worker_ok) as url:
            tunnel = Tunnel(process, url, tmp_path)
            try:
                with monitor_session(server, tunnel, process, url, "expected-instance", verify_only=True,
                                     open_browser=False, timeout=1):
                    deadline = time.monotonic() + 5
                    while not server.should_exit and time.monotonic() < deadline:
                        time.sleep(0.02)
                    assert server.should_exit, "Readiness monitor did not stop the server"
            except RuntimeError:
                assert not worker_ok
            else:
                assert worker_ok
    assert ("Verified" in capsys.readouterr().out) is worker_ok


def test_ngrok_exit_requests_server_shutdown(tmp_path):
    from app.ngrok import Tunnel, monitor_session

    server = SimpleNamespace(should_exit=False)
    with launcher.owned_process([sys.executable, "-c", "import time; time.sleep(60)"]) as process:
        with health_server() as url:
            tunnel = Tunnel(process, url, tmp_path)
            with pytest.raises(RuntimeError, match="ngrok"):
                with monitor_session(server, tunnel, process, url, "expected-instance", verify_only=False,
                                     open_browser=False):
                    process.kill()
                    process.wait(timeout=5)
                    deadline = time.monotonic() + 5
                    while not server.should_exit and time.monotonic() < deadline:
                        time.sleep(0.02)
                    assert server.should_exit


def test_source_launcher_verifies_real_api_worker_cors_and_cleans_up(tmp_path):
    from app.config import Settings

    env = dict(os.environ)
    for name in Settings.model_fields:
        env.pop(name.upper(), None)
    data = tmp_path / "data"
    record = tmp_path / "agent.json"
    env.update({"AUTOPOSTER_DATA_DIR": str(data), "NGROK_TEST_RECORD": str(record), "PYTHONPATH": str(Path.cwd())})
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with launcher.owned_process(
        [sys.executable, "tests/fixtures/ngrok_launcher.py", "--ngrok", "--verify-only", "--no-browser",
         "--port", str(port)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ) as process:
        output, _ = process.communicate(timeout=60)
        assert process.returncode == 0, output.decode(errors="replace")
        assert b"Verified local/public API and worker for this instance" in output
        # Check before the outer safety job closes, so it cannot conceal a leaked resource.
        with launcher.owned_listener("127.0.0.1", port), launcher.owned_data_directory(data):
            pass
    assert json.loads(record.read_text())["port_owned"] is True
    with sqlite3.connect(data / "autoposter.db") as database:
        assert database.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260913_0016"
        assert database.execute("SELECT count(*) FROM worker_heartbeats").fetchone()[0] >= 1


@pytest.mark.parametrize("request_mode,failure", [
    ("incomplete-body", "worker"), ("blocking-sync", "worker"), ("blocking-sync", "api-server-return"),
    ("blocking-sync", "api-signal-failure"),
])
def test_owned_runtime_failure_stops_inflight_requests_before_releasing_resources(tmp_path, request_mode, failure):
    from app.config import Settings

    env = dict(os.environ)
    for name in Settings.model_fields:
        env.pop(name.upper(), None)
    data = tmp_path / "data"
    stop_worker = tmp_path / "stop-worker"
    request_received = tmp_path / "request-received"
    env.update({
        "AUTOPOSTER_DATA_DIR": str(data), "NGROK_TEST_RECORD": str(tmp_path / "agent.json"),
        "PYTHONPATH": str(Path.cwd()), "NGROK_TEST_STOP_WORKER": str(stop_worker),
        "NGROK_TEST_REQUEST_RECEIVED": str(request_received),
    })
    if failure in {"api-server-return", "api-signal-failure"}:
        env["NGROK_TEST_SERVER_RETURN"] = "true"
    if failure == "api-signal-failure":
        env["NGROK_TEST_SIGNAL_FAILURE"] = "true"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with launcher.owned_process(
        [sys.executable, "tests/fixtures/ngrok_launcher.py", "--ngrok", "--no-browser", "--port", str(port)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ) as process:
        with httpx.Client(trust_env=False, timeout=1) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    output, _ = process.communicate(timeout=5)
                    pytest.fail(f"Owned API/worker exited during startup:\n{output.decode(errors='replace')}")
                try:
                    if client.get(f"http://127.0.0.1:{port}/api/worker-status").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("Owned API/worker did not start")
        with socket.create_connection(("127.0.0.1", port), timeout=2) as incomplete:
            if request_mode == "blocking-sync":
                incomplete.sendall(b"GET /fixture-blocking-sync HTTP/1.1\r\nHost: localhost\r\n\r\n")
            else:
                incomplete.sendall(
                    b"POST /api/auth/register HTTP/1.1\r\nHost: localhost\r\n"
                    b"Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{"
                )
            deadline = time.monotonic() + 5
            while not request_received.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert request_received.exists(), "Request never reached the actual application body reader"
            if failure == "worker":
                stop_worker.touch()
            output, _ = process.communicate(timeout=15)
            assert process.returncode != 0
            expected = b"owned worker stopped" if failure == "worker" else b"owned API stopped"
            assert expected in output, output.decode(errors="replace")
            # Outer test containment must not conceal leaked app/tunnel resources.
            with launcher.owned_listener("127.0.0.1", port), launcher.owned_data_directory(data):
                pass


def test_api_bootstrap_exit_keeps_supervisor_resources_owned(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "_api_command", lambda: [sys.executable, "-c", "pass"])
    with launcher.owned_listener("127.0.0.1", 0) as listener, launcher.owned_data_directory(tmp_path):
        with pytest.raises(RuntimeError, match="before socket handoff"):
            with launcher.owned_api(listener, "a" * 32, tmp_path / "api.pid"):
                pytest.fail("API that exited before socket handoff was accepted")
        with socket.socket() as other:
            with pytest.raises(OSError):
                other.bind(listener.getsockname())
        with pytest.raises(RuntimeError, match="already in use"):
            with launcher.owned_data_directory(tmp_path):
                pytest.fail("API child cleanup released the supervisor data lock")


@pytest.mark.skipif(os.name != "nt", reason="PowerShell Windows wrapper")
def test_powershell_wrapper_preserves_caller_environment_and_location_on_failure(tmp_path):
    source_python = Path(".venv/Scripts/python.exe")
    if not source_python.exists():
        pytest.skip("Source-wrapper test requires the documented local .venv")
    script = Path("scripts/start-ngrok.ps1").resolve()
    env = dict(os.environ)
    env["AUTOPOSTER_DATA_DIR"] = str(tmp_path / "must-not-exist")
    with launcher.owned_listener("127.0.0.1", 0) as listener:
        command = (
            "$before = (Get-ChildItem Env: | Sort-Object Name | ConvertTo-Json -Compress); "
            "$location = (Get-Location).Path; "
            "try { & $env:TEST_NGROK_SCRIPT -FromSource -NoBrowser -VerifyOnly "
            f"-Port {listener.getsockname()[1]} -NgrokPath 'not-an-agent'; throw 'unexpected success' "
            "} catch { if ($_ -like '*unexpected success*') { throw } }; "
            "if ($before -ne (Get-ChildItem Env: | Sort-Object Name | ConvertTo-Json -Compress)) "
            "{ throw 'caller environment changed' }; "
            "if ($location -ne (Get-Location).Path) { throw 'caller location changed' }; 'wrapper-state-preserved'"
        )
        env["TEST_NGROK_SCRIPT"] = str(script)
        with launcher.owned_process(
            ["powershell.exe", "-NoProfile", "-Command", command], env=env, cwd=tmp_path,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        ) as process:
            output, _ = process.communicate(timeout=30)
            assert process.returncode == 0, output.decode(errors="replace")
            assert b"wrapper-state-preserved" in output
            assert b"10048" in output, "Wrapper did not reach the actual exclusive-bind rejection"
    assert not Path(env["AUTOPOSTER_DATA_DIR"]).exists()
