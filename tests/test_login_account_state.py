"""Request-level login/account races on isolated SQLite or migrated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import LoginThrottle, User, UserSession
from app.routes import auth
from app.security import hash_password, hash_password_pbkdf2
from tests.test_job_claim_safety import job_engine as _job_engine

job_engine = _job_engine
EMAIL = "account-state@example.com"
PASSWORD = "correct-password"


@pytest.fixture
def login_client(job_engine, monkeypatch):
    def isolated_session():
        with Session(job_engine, autoflush=False) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_session)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def seed_user(engine, *, active=True, legacy=False):
    stored_hash = hash_password_pbkdf2(PASSWORD) if legacy else hash_password(PASSWORD)
    with Session(engine) as db:
        user = User(email=EMAIL, name="Account state", password_hash=stored_hash, is_active=active)
        db.add(user)
        db.commit()
        return user.id, stored_hash


def attempt(client):
    return client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})


def assert_rejected_without_session(response, engine):
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"
    assert "token" not in response.json()
    with Session(engine) as db:
        assert db.query(UserSession).count() == 0
        assert db.query(LoginThrottle).one().attempts == 1


def test_disabled_account_cannot_obtain_a_session(login_client, job_engine):
    seed_user(job_engine, active=False)
    assert_rejected_without_session(attempt(login_client), job_engine)


@pytest.mark.parametrize("legacy", [False, True], ids=["argon2", "legacy-rehash"])
@pytest.mark.parametrize("change", ["disabled", "password", "email", "deleted"])
def test_account_change_during_password_verification_prevents_session(
    login_client, job_engine, monkeypatch, legacy, change,
):
    user_id, old_hash = seed_user(job_engine, legacy=legacy)
    changed_hash = hash_password("replacement-password")
    entered, release = Event(), Event()
    original_verify = auth.verify_password

    def paused_verify(password, stored_hash):
        assert stored_hash == old_hash
        entered.set()
        assert release.wait(10), "Controller did not release credential verification"
        return original_verify(password, stored_hash)

    monkeypatch.setattr(auth, "verify_password", paused_verify)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(attempt, login_client)
        try:
            assert entered.wait(10), "Login did not reach credential verification"
            with Session(job_engine) as other:
                if change == "deleted":
                    other.execute(delete(User).where(User.id == user_id))
                else:
                    values = {
                        "disabled": {"is_active": False},
                        "password": {"password_hash": changed_hash},
                        "email": {"email": "changed@example.com"},
                    }[change]
                    other.execute(update(User).where(User.id == user_id).values(**values))
                other.commit()
        finally:
            release.set()
        response = pending.result(timeout=10)
    assert_rejected_without_session(response, job_engine)
    with Session(job_engine) as db:
        user = db.get(User, user_id)
        if change == "deleted":
            assert user is None
        else:
            assert user.password_hash == (changed_hash if change == "password" else old_hash)


@pytest.mark.parametrize("legacy", [False, True], ids=["argon2", "legacy-rehash"])
def test_password_work_does_not_hold_a_database_connection(login_client, job_engine, monkeypatch, legacy):
    seed_user(job_engine, legacy=legacy)
    observed = []
    original_verify, original_hash = auth.verify_password, auth.hash_password

    def verify(*args):
        observed.append(("verify", job_engine.pool.checkedout()))
        return original_verify(*args)

    def rehash(*args):
        observed.append(("rehash", job_engine.pool.checkedout()))
        return original_hash(*args)

    monkeypatch.setattr(auth, "verify_password", verify)
    monkeypatch.setattr(auth, "hash_password", rehash)
    response = attempt(login_client)
    assert response.status_code == 200, response.text
    assert observed == ([("verify", 0), ("rehash", 0)] if legacy else [("verify", 0)])
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    assert login_client.get("/api/auth/me", headers=headers).status_code == 200


def test_password_change_during_legacy_rehash_is_not_overwritten(login_client, job_engine, monkeypatch):
    user_id, _old_hash = seed_user(job_engine, legacy=True)
    new_hash = hash_password("replacement-password")
    original_hash = auth.hash_password

    def concurrent_rehash(password):
        with Session(job_engine) as other:
            other.execute(update(User).where(User.id == user_id).values(password_hash=new_hash))
            other.commit()
        return original_hash(password)

    monkeypatch.setattr(auth, "hash_password", concurrent_rehash)
    assert_rejected_without_session(attempt(login_client), job_engine)
    with Session(job_engine) as db:
        assert db.get(User, user_id).password_hash == new_hash


def test_session_commit_failure_rolls_back_rehash_and_throttle_clear(login_client, job_engine, monkeypatch):
    user_id, old_hash = seed_user(job_engine, legacy=True)
    original_commit = Session.commit

    def fail_session_commit(db):
        if any(isinstance(item, UserSession) for item in db.new):
            raise OperationalError("COMMIT", {}, RuntimeError("synthetic-session-failure"))
        return original_commit(db)

    monkeypatch.setattr(Session, "commit", fail_session_commit)
    response = attempt(login_client)
    assert response.status_code == 500
    assert "synthetic-session-failure" not in response.text
    assert response.json()["error"]["retryable"] is True
    with Session(job_engine) as db:
        assert db.get(User, user_id).password_hash == old_hash
        assert db.query(UserSession).count() == 0
        assert db.query(LoginThrottle).one().attempts == 1


def test_unrelated_profile_change_does_not_reject_valid_credentials(login_client, job_engine, monkeypatch):
    user_id, _old_hash = seed_user(job_engine)
    original_verify = auth.verify_password

    def rename_during_verification(*args):
        with Session(job_engine) as other:
            other.execute(update(User).where(User.id == user_id).values(name="Updated profile"))
            other.commit()
        return original_verify(*args)

    monkeypatch.setattr(auth, "verify_password", rename_during_verification)
    response = attempt(login_client)
    assert response.status_code == 200
    assert response.json()["user"]["name"] == "Updated profile"
    with Session(job_engine) as db:
        assert db.query(UserSession).count() == 1
        assert db.query(LoginThrottle).count() == 0
