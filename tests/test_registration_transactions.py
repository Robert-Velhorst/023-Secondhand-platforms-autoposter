"""Real registration requests on isolated SQLite or migrated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import security
from app.database import get_db
from app.main import app
from app.models import User, UserSession
from app.routes import auth
from tests.test_job_claim_safety import job_engine as _job_engine

job_engine = _job_engine
EMAIL = "registration-transaction@example.com"
PASSWORD = "registration-test-password"


@pytest.fixture
def registration_client(job_engine, monkeypatch):
    def isolated_session():
        with Session(job_engine, autoflush=False) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_session)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def register(client, **changes):
    return client.post("/api/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "name": "Registration test", **changes,
    })


def test_concurrent_registration_returns_one_success_and_one_conflict(registration_client, job_engine, monkeypatch):
    hashing = Barrier(2)
    original_hash = auth.hash_password

    def simultaneous_hash(password):
        hashing.wait(timeout=10)
        return original_hash(password)

    monkeypatch.setattr(auth, "hash_password", simultaneous_hash)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(register, registration_client, name="First claimant")
        second = pool.submit(register, registration_client, email=EMAIL.upper(), name="Second claimant")
        responses = [first.result(timeout=15), second.result(timeout=15)]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["error"]["message"] == "Email is already registered"
    assert "token" not in loser.json()
    with Session(job_engine) as db:
        user = db.query(User).filter_by(email=EMAIL).one()
        assert user.name == winner.json()["user"]["name"]
        assert db.query(UserSession).filter_by(user_id=user.id).count() == 1
    headers = {"Authorization": f"Bearer {winner.json()['token']}"}
    assert registration_client.get("/api/auth/me", headers=headers).status_code == 200


def test_failed_session_commit_does_not_leave_a_registered_account(registration_client, job_engine, monkeypatch):
    original_commit = Session.commit

    def fail_session(db):
        if any(isinstance(item, UserSession) for item in db.new):
            raise OperationalError("COMMIT", {}, RuntimeError("synthetic-registration-session-failure"))
        return original_commit(db)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_session)
        failed = register(registration_client)
    assert failed.status_code == 500
    assert "synthetic-registration-session-failure" not in failed.text
    assert failed.json()["error"]["retryable"] is True
    with Session(job_engine) as db:
        assert db.query(User).filter_by(email=EMAIL).count() == 0
        assert db.query(UserSession).count() == 0
    retried = register(registration_client)
    assert retried.status_code == 200


def test_registration_hashing_does_not_hold_a_database_connection(registration_client, job_engine, monkeypatch):
    observed = []
    original_hash = auth.hash_password

    def measured_hash(password):
        observed.append(job_engine.pool.checkedout())
        return original_hash(password)

    monkeypatch.setattr(auth, "hash_password", measured_hash)
    response = register(registration_client)
    assert response.status_code == 200
    assert observed == [0]


@pytest.mark.parametrize("active", [True, False], ids=["active", "disabled"])
def test_existing_email_fast_path_does_not_hash_or_change_the_account(
    registration_client, job_engine, monkeypatch, active,
):
    with Session(job_engine) as db:
        db.add(User(email=EMAIL, name="Original account", password_hash="preserve-hash", is_active=active))
        db.commit()
    hashing_calls = []

    def forbidden_hash(password):
        hashing_calls.append(True)
        raise AssertionError("Existing-email fast path must not hash passwords")

    monkeypatch.setattr(auth, "hash_password", forbidden_hash)
    response = register(registration_client, email=EMAIL.upper())
    assert response.status_code == 409
    assert hashing_calls == []
    with Session(job_engine) as db:
        stored = db.query(User).filter_by(email=EMAIL).one()
        assert (stored.name, stored.password_hash, stored.is_active) == ("Original account", "preserve-hash", active)
        assert db.query(UserSession).count() == 0


def test_unrelated_user_constraint_failure_is_not_reported_as_duplicate_email(
    registration_client, job_engine, monkeypatch,
):
    monkeypatch.setattr(auth, "hash_password", lambda password: None)
    response = register(registration_client)
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Unexpected server error."
    assert "password_hash" not in response.text
    with Session(job_engine) as db:
        assert db.query(User).filter_by(email=EMAIL).count() == 0
        assert db.query(UserSession).count() == 0


def test_session_token_conflict_rolls_back_only_the_new_registration(registration_client, job_engine, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(security.secrets, "token_urlsafe", lambda size: "synthetic-colliding-session-token")
        first = register(registration_client, email="original-registration@example.com")
        assert first.status_code == 200
        failed = register(registration_client)
    assert failed.status_code == 500
    assert "synthetic-colliding-session-token" not in failed.text
    with Session(job_engine) as db:
        assert db.query(User).filter_by(email=EMAIL).count() == 0
        assert db.query(User).filter_by(email="original-registration@example.com").count() == 1
        assert db.query(UserSession).count() == 1
    headers = {"Authorization": f"Bearer {first.json()['token']}"}
    assert registration_client.get("/api/auth/me", headers=headers).status_code == 200


def test_account_is_not_visible_before_initial_session_commit(registration_client, job_engine, monkeypatch):
    original_create = auth.create_session
    observed = []

    def check_uncommitted(db, user):
        with Session(job_engine) as observer:
            observed.append(observer.query(User).filter_by(email=EMAIL).count())
            assert observer.query(UserSession).count() == 0
        return original_create(db, user)

    monkeypatch.setattr(auth, "create_session", check_uncommitted)
    response = register(registration_client)
    assert response.status_code == 200
    assert observed == [0]


def test_uncertain_commit_keeps_committed_account_and_allows_login(registration_client, job_engine, monkeypatch):
    original_commit = Session.commit

    def lose_acknowledgement(db):
        is_registration_commit = any(isinstance(item, UserSession) for item in db.new)
        original_commit(db)
        if is_registration_commit:
            raise OperationalError("COMMIT", {}, RuntimeError("synthetic-lost-commit-acknowledgement"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", lose_acknowledgement)
        response = register(registration_client)
    assert response.status_code == 500
    assert "synthetic-lost-commit-acknowledgement" not in response.text
    with Session(job_engine) as db:
        assert db.query(User).filter_by(email=EMAIL).count() == 1
        assert db.query(UserSession).count() == 1
    assert register(registration_client).status_code == 409
    login = registration_client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
