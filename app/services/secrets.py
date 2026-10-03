import json
import os
import secrets
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from app.config import Settings

_TOKEN_SECRET_WRITE_LOCK = Lock()


class TokenSecretStore(Protocol):
    def read_json(self, secret_ref: str) -> dict[str, Any]:
        raise NotImplementedError

    def write_json(self, secret_ref: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete_json(self, secret_ref: str) -> None:
        raise NotImplementedError


class FileTokenSecretStore:
    def __init__(self, root: Path):
        self.root = root

    def read_json(self, secret_ref: str) -> dict[str, Any]:
        target = self._target(secret_ref)
        return json.loads(target.read_text(encoding="utf-8"))

    def write_json(self, secret_ref: str, payload: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            try:
                os.chmod(self.root, 0o700)
            except OSError:
                pass
        target = self._target(secret_ref)
        temporary = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
        with _TOKEN_SECRET_WRITE_LOCK:
            try:
                with temporary.open("x", encoding="utf-8") as secret_file:
                    if os.name != "nt":
                        os.chmod(temporary, 0o600)
                    secret_file.write(json.dumps(payload, sort_keys=True))
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)

    def delete_json(self, secret_ref: str) -> None:
        self._target(secret_ref).unlink(missing_ok=True)

    def _target(self, secret_ref: str) -> Path:
        return self.root / f"{sha256(secret_ref.encode()).hexdigest()}.json"


def get_token_secret_store(settings: Settings) -> TokenSecretStore:
    return FileTokenSecretStore(settings.token_secret_path)
