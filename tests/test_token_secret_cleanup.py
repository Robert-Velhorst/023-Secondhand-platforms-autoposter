import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import PlatformAccount, PlatformOAuthState, TokenSecretDeletion, User, now_utc
from app.reconcile import reconcile_database
from app.services.secrets import FileTokenSecretStore
from app.services.token_secret_cleanup import process_due_token_secret_deletions
from tests.test_api import client
from tests.test_data_portability import auth_headers


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_file_token_secret_store_concurrent_writes_are_atomic_and_leave_no_temp_files(tmp_path):
    secret_ref = "secret://ebay/shared-reference"

    def write(version: int) -> None:
        FileTokenSecretStore(tmp_path).write_json(
            secret_ref, {"access_token": f"access-{version}", "version": version}
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(write, range(48)))

    stored = FileTokenSecretStore(tmp_path).read_json(secret_ref)
    assert stored["version"] in range(48)
    assert stored["access_token"] == f"access-{stored['version']}"
    assert not [path for path in tmp_path.iterdir() if path.suffix == ".tmp"]


def test_file_token_secret_store_removes_temporary_file_when_atomic_replace_fails(tmp_path, monkeypatch):
    store = FileTokenSecretStore(tmp_path)
    original_replace = Path.replace

    def fail_replace(path: Path, target: Path):
        if path.suffix == ".tmp":
            raise OSError("simulated replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        store.write_json("secret://ebay/replace-failure", {"access_token": "do-not-leak"})

    assert not list(tmp_path.iterdir())


def create_oauth_account(prefix: str, *, secret_ref: str | None = None):
    headers = auth_headers(prefix)
    response = client.post(
        "/api/accounts",
        headers=headers,
        json={"platform": "ebay", "display_name": f"OAuth {prefix}", "mode": "official_api", "status": "connected"},
    )
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        account = db.get(PlatformAccount, response.json()["id"])
        owner_id = account.owner_id
        reference = secret_ref or f"secret://ebay/user-{owner_id}/consent-{uuid.uuid4().hex}"
        account.secret_ref = reference
        state = PlatformOAuthState(
            user_id=owner_id,
            platform="ebay",
            state_hash=uuid.uuid4().hex * 2,
            redirect_uri="https://example.invalid/callback",
            scopes=["sell.inventory"],
            expires_at=now_utc() + timedelta(minutes=5),
        )
        db.add(state)
        db.commit()
        state_id = state.id
    store = FileTokenSecretStore(get_settings().token_secret_path)
    store.write_json(reference, {"access_token": "access-secret", "refresh_token": "refresh-secret"})
    return headers, response.json()["id"], owner_id, state_id, reference, store._target(reference)


def test_marketplace_account_delete_queues_and_retries_token_erasure(monkeypatch, caplog):
    headers, account_id, owner_id, state_id, secret_ref, path = create_oauth_account("secret-delete")

    def fail_delete(self, ref):
        assert ref == secret_ref
        raise PermissionError("refresh-secret and private-path-must-not-be-logged")

    with monkeypatch.context() as patch:
        patch.setattr(FileTokenSecretStore, "delete_json", fail_delete)
        response = client.delete(f"/api/accounts/{account_id}", headers=headers)

    assert response.status_code == 204, response.text
    assert path.is_file()
    with SessionLocal() as db:
        assert db.get(PlatformAccount, account_id) is None
        assert db.get(User, owner_id) is not None
        assert db.get(PlatformOAuthState, state_id) is None
        queued = db.query(TokenSecretDeletion).one()
        assert queued.secret_ref == secret_ref
        assert queued.last_error_type == "PermissionError"
        assert queued.attempts == 1
        assert reconcile_database(db)["issues"] == [{
            "code": "pending_token_secret_cleanup",
            "count": 1,
            "failed_attempts_pending": 1,
            "safe_to_auto_repair": False,
        }]
        queued.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    assert "refresh-secret" not in caplog.text
    assert secret_ref not in caplog.text
    with SessionLocal() as db:
        assert process_due_token_secret_deletions(db) == 1
        assert db.query(TokenSecretDeletion).count() == 0
    assert not path.exists()


def test_token_secret_cleanup_preserves_a_secret_still_referenced_by_another_account():
    first_headers, first_id, _, _, secret_ref, path = create_oauth_account("secret-shared-first")
    second_headers, second_id, _, _, _, _ = create_oauth_account("secret-shared-second", secret_ref=secret_ref)

    response = client.delete(f"/api/accounts/{first_id}", headers=first_headers)
    assert response.status_code == 204, response.text
    assert path.is_file()
    with SessionLocal() as db:
        assert db.query(TokenSecretDeletion).count() == 0
        assert db.get(PlatformAccount, second_id) is not None

    response = client.delete(f"/api/accounts/{second_id}", headers=second_headers)
    assert response.status_code == 204, response.text
    assert not path.exists()
def test_user_deletion_queues_secret_erasure_and_invalidates_oauth_state():
    headers, account_id, owner_id, state_id, secret_ref, path = create_oauth_account("secret-user-delete")

    response = client.delete("/api/auth/me", headers=headers)

    assert response.status_code == 204, response.text
    assert not path.exists()
    with SessionLocal() as db:
        assert db.get(User, owner_id) is None
        assert db.get(PlatformAccount, account_id) is None
        assert db.get(PlatformOAuthState, state_id) is None
        assert db.query(TokenSecretDeletion).count() == 0
    assert secret_ref
