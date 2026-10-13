"""Small helpers for stable worker-container identity."""

import hashlib
import socket


def worker_id_for_host(hostname: str | None = None) -> str:
    """Return a stable, bounded identity for one container hostname."""
    host = hostname or socket.gethostname()
    digest = hashlib.sha256(host.encode("utf-8")).hexdigest()[:32]
    return f"worker-{digest}"
