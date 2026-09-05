import os
import socket
import subprocess
import sys
import time

import pytest

from app import launcher


@pytest.mark.parametrize("entry", ["serve", "main"])
def test_occupied_port_fails_before_data_or_migration_changes(tmp_path, monkeypatch, entry):
    data = tmp_path / "must-not-be-created"
    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(data))
    migrated = []

    def migration():
        migrated.append(True)
        raise RuntimeError("Migration must not be reached")

    monkeypatch.setattr(launcher, "run_migrations", migration)
    with socket.socket() as other_service:
        other_service.bind(("127.0.0.1", 0))
        other_service.listen()
        port = other_service.getsockname()[1]
        with pytest.raises(OSError):
            if entry == "main":
                launcher.main(["--port", str(port), "--no-browser"])
            else:
                launcher.serve("127.0.0.1", port, False)
        assert not migrated
        assert not data.exists()
        assert other_service.fileno() >= 0


def test_second_launcher_cannot_touch_the_same_data_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(tmp_path))
    with launcher.owned_data_directory(tmp_path):
        with pytest.raises(RuntimeError, match="already in use"):
            launcher.serve("127.0.0.1", 0, False)
        assert not (tmp_path / ".standalone-secret").exists()
        assert not (tmp_path / "autoposter.db").exists()


def test_listener_stays_exclusive_until_its_owner_exits():
    with launcher.owned_listener("127.0.0.1", 0) as listener:
        address = listener.getsockname()
        assert address[0] == "127.0.0.1"
        with socket.socket() as competing:
            competing.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError):
                competing.bind(address)
        with listener.dup() as server_copy:
            assert server_copy.getsockname() == address
        with socket.socket() as competing:
            with pytest.raises(OSError):
                competing.bind(address)
    with socket.socket() as replacement:
        replacement.bind(address)


def test_data_directory_lock_releases_on_exception(tmp_path):
    with pytest.raises(ValueError, match="test failure"):
        with launcher.owned_data_directory(tmp_path):
            raise ValueError("test failure")
    with launcher.owned_data_directory(tmp_path):
        assert tmp_path.is_dir()


def test_port_released_when_migration_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(tmp_path))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    def migration():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(launcher, "run_migrations", migration)
    with pytest.raises(RuntimeError, match="migration failed"):
        launcher.serve("127.0.0.1", port, False)
    with socket.socket() as replacement:
        replacement.bind(("127.0.0.1", port))
    with launcher.owned_data_directory(tmp_path):
        assert os.path.isdir(tmp_path)


@pytest.mark.parametrize("crash", [False, True])
def test_data_lock_is_cross_process_and_released_after_exit(tmp_path, crash):
    ready = tmp_path / "ready"
    code = (
        "import sys; from pathlib import Path; from app.launcher import owned_data_directory\n"
        "with owned_data_directory(Path(sys.argv[1])):\n"
        " Path(sys.argv[2]).write_text('ready')\n"
        " sys.stdin.buffer.read(1)\n"
    )
    with launcher.owned_process(
        [sys.executable, "-c", code, str(tmp_path), str(ready)], stdin=subprocess.PIPE,
    ) as child:
        deadline = time.monotonic() + 15
        while not ready.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.02)
        assert ready.exists(), "Child did not acquire the real OS lock"
        with pytest.raises(RuntimeError, match="already in use"):
            with launcher.owned_data_directory(tmp_path):
                pytest.fail("Concurrent process acquired the same data directory")
        if crash:
            child.kill()
        else:
            child.stdin.write(b"q")
            child.stdin.flush()
        child.wait(timeout=10)
    child.stdin.close()
    # Windows may release a crashed process's file locks shortly after process exit.
    # Wait for the actual OS condition, not an assumed synchronous cleanup guarantee.
    deadline = time.monotonic() + 5
    while True:
        try:
            with launcher.owned_data_directory(tmp_path):
                assert (tmp_path / ".launcher.lock").exists()
            break
        except RuntimeError:
            if not crash or time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def test_worker_launch_failure_releases_port_and_data_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "run_migrations", lambda: None)
    monkeypatch.setattr(launcher, "_worker_command", lambda: [str(tmp_path / "missing-worker-executable")])
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(OSError):
        launcher.serve("127.0.0.1", port, False)
    with socket.socket() as replacement:
        replacement.bind(("127.0.0.1", port))
    with launcher.owned_data_directory(tmp_path):
        pass


def test_server_failure_stops_real_child_before_releasing_owned_resources(tmp_path, monkeypatch):
    import uvicorn

    monkeypatch.setenv("AUTOPOSTER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "run_migrations", lambda: None)
    monkeypatch.setattr(launcher, "_worker_command", lambda: [sys.executable, "-c", "import time; time.sleep(60)"])
    real_popen = subprocess.Popen
    children = []
    addresses = []

    def track_child(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def server_failure(_server, sockets):
        address = sockets[0].getsockname()
        addresses.append(address)
        sockets[0].close()
        with socket.socket() as competing:
            with pytest.raises(OSError):
                competing.bind(address)
        with pytest.raises(RuntimeError, match="already in use"):
            with launcher.owned_data_directory(tmp_path):
                pytest.fail("Data lock released while child is running")
        raise RuntimeError("simulated server failure")

    monkeypatch.setattr(subprocess, "Popen", track_child)
    monkeypatch.setattr(uvicorn.Server, "run", server_failure)
    try:
        with pytest.raises(RuntimeError, match="simulated server failure"):
            launcher.serve("127.0.0.1", 0, False)
        assert children and children[0].poll() is not None
        with socket.socket() as replacement:
            replacement.bind(addresses[0])
        with launcher.owned_data_directory(tmp_path):
            pass
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)


def _wait_for_file(path):
    deadline = time.monotonic() + 15
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert path.exists(), "Child did not reach the test handshake"
    return path.read_text()


def _assert_port_eventually_free(port):
    deadline = time.monotonic() + 5
    while True:
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


_PORT_CHILD = (
    "import socket,sys,time; from pathlib import Path\n"
    "with socket.socket() as listener:\n"
    " listener.bind(('127.0.0.1',0)); listener.listen()\n"
    " Path(sys.argv[1]).write_text(str(listener.getsockname()[1]))\n"
    " time.sleep(60)\n"
)


@pytest.mark.parametrize("crash", [False, True])
def test_owned_process_stops_descendants_but_preserves_unrelated_process(tmp_path, crash):
    # Root-only termination would leave the grandchild's real listener bound.
    unrelated_ready = tmp_path / "unrelated"
    owned_ready = tmp_path / "owned"
    tree_code = (
        "import subprocess,sys\n"
        "child=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdin=subprocess.PIPE)\n"
        "sys.stdin.buffer.read(1)\n"
    )
    with launcher.owned_process(
        [sys.executable, "-c", _PORT_CHILD, str(unrelated_ready)], stdin=subprocess.PIPE,
    ) as unrelated:
        unrelated_port = int(_wait_for_file(unrelated_ready))
        with launcher.owned_process(
            [sys.executable, "-c", tree_code, _PORT_CHILD, str(owned_ready)], stdin=subprocess.PIPE,
        ) as owned:
            owned_port = int(_wait_for_file(owned_ready))
            if crash:
                owned.kill()
                owned.wait(timeout=10)
        owned.stdin.close()
        _assert_port_eventually_free(owned_port)
        assert unrelated.poll() is None
        with socket.socket() as probe:
            with pytest.raises(OSError):
                probe.bind(("127.0.0.1", unrelated_port))
    unrelated.stdin.close()
    _assert_port_eventually_free(unrelated_port)


@pytest.mark.skipif(os.name != "nt", reason="Windows kill-on-job-close contract")
def test_owner_crash_closes_its_job_and_stops_child_tree(tmp_path):
    ready = tmp_path / "child"
    owner_code = (
        "import os,subprocess,sys; from app.processes import owned_process\n"
        "with owned_process([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdin=subprocess.PIPE):\n"
        " sys.stdin.buffer.read(1)\n"
        " os._exit(23)\n"
    )
    # The outer job is only failure cleanup. Check the inner job before closing it.
    with launcher.owned_process(
        [sys.executable, "-c", owner_code, _PORT_CHILD, str(ready)], stdin=subprocess.PIPE,
    ) as owner:
        port = int(_wait_for_file(ready))
        owner.stdin.write(b"q")
        owner.stdin.flush()
        assert owner.wait(timeout=10) == 23
        _assert_port_eventually_free(port)
    owner.stdin.close()
