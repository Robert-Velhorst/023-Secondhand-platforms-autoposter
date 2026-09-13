"""Source launcher integration with a local child fixture, never a public tunnel."""

import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from fastapi.routing import APIRoute

from app import launcher, ngrok

real_tunnel = ngrok.managed_tunnel
real_ready = ngrok.instance_ready
real_owned_process = launcher.owned_process
local_origin = ""
real_server_run = uvicorn.Server.run
real_touch = Path.touch


def controlled_touch(path, *args, **kwargs):
    if os.environ.get("NGROK_TEST_SIGNAL_FAILURE") and path.name == "api.stopped":
        raise OSError("Injected status-file storage failure")
    return real_touch(path, *args, **kwargs)


def controlled_server_return(server, **kwargs):
    if not os.environ.get("NGROK_TEST_SERVER_RETURN"):
        return real_server_run(server, **kwargs)
    stopped = threading.Event()

    def stop_after_request_enters():
        while not stopped.wait(0.02):
            if Path(os.environ["NGROK_TEST_REQUEST_RECEIVED"]).exists():
                server.should_exit = True
                return

    thread = threading.Thread(target=stop_after_request_enters, daemon=True)
    thread.start()
    # Inject the real Uvicorn cancellation/return behavior without changing the
    # production drain policy. The synchronous request deliberately stays alive.
    server.config.timeout_graceful_shutdown = 0.1
    try:
        return real_server_run(server, **kwargs)
    finally:
        stopped.set()
        thread.join(timeout=2)


@contextmanager
def controlled_worker(command, **options):
    with real_owned_process(command, **options) as worker:
        stop = threading.Event()

        def requested_worker_failure():
            path = os.environ.get("NGROK_TEST_STOP_WORKER")
            if path and "--worker-child" in command:
                while not stop.wait(0.02):
                    if Path(path).exists():
                        worker.kill()
                        return

        thread = threading.Thread(target=requested_worker_failure, daemon=True)
        thread.start()
        try:
            yield worker
        finally:
            stop.set()
            thread.join(timeout=2)


class ObservedInstanceHealth(ngrok.InstanceHealth):
    def __init__(self, app, instance):
        super().__init__(app, instance)

        def blocking_sync():
            Path(os.environ["NGROK_TEST_REQUEST_RECEIVED"]).touch()
            time.sleep(60)
            return {"unexpected": "request continued after shutdown"}

        app.router.routes.insert(0, APIRoute("/fixture-blocking-sync", blocking_sync, methods=["GET"]))

    async def __call__(self, scope, receive, send):
        async def observed_receive():
            message = await receive()
            path = os.environ.get("NGROK_TEST_REQUEST_RECEIVED")
            if path and scope.get("path") == "/api/auth/register" and message.get("body"):
                Path(path).touch()
            return message

        await super().__call__(scope, observed_receive, send)


@contextmanager
def controlled_tunnel(listener, data_dir, **_options):
    global local_origin
    local_origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    command = [sys.executable, str(Path(__file__).with_name("ngrok_child.py"))]
    with real_tunnel(listener, data_dir, command=command, timeout=5) as tunnel:
        yield tunnel


def controlled_public_transport(client, origin, instance):
    if origin == "https://owned.example":
        # Replace only the external HTTP transport boundary; use the real app,
        # per-instance response header, CORS middleware, and worker heartbeat.
        response = client.get(local_origin + "/api/health", headers={"Origin": origin})
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["x-autoposter-instance"] == instance
        assert response.headers["cache-control"] == "no-store"
        assert os.environ["PUBLIC_BASE_URL"] == origin
        assert os.environ["CORS_ORIGINS"] == origin
        origin = local_origin
    return real_ready(client, origin, instance)


ngrok.managed_tunnel = controlled_tunnel
ngrok.instance_ready = controlled_public_transport
ngrok.InstanceHealth = ObservedInstanceHealth
launcher.owned_process = controlled_worker
launcher._api_command = lambda: [sys.executable, str(Path(__file__).resolve()), "--api-child"]
uvicorn.Server.run = controlled_server_return
Path.touch = controlled_touch
raise SystemExit(launcher.main(sys.argv[1:]))
