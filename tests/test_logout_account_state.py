"""Revocation must remain available without restoring disabled account access."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import User, UserSession
from app.security import hash_token
from tests.test_job_claim_safety import job_engine as _job_engine

job_engine = _job_engine


@pytest.fixture
def logout_client(job_engine, monkeypatch):
    def isolated_session():
        with Session(job_engine, autoflush=False) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_session)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def seed_session(engine, *, active=True, expired=False, revoked=False):
    token = uuid4().hex
    with Session(engine) as db:
        user = User(email=f"logout-{uuid4().hex}@example.com", password_hash="unused", is_active=active)
        db.add(user)
        db.flush()
        session = UserSession(
            user_id=user.id, token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=-1 if expired else 1),
            revoked_at=datetime.now(UTC) if revoked else None,
        )
        db.add(session)
        db.commit()
        return user.id, session.id, {"Authorization": f"Bearer {token}"}


def test_disabled_account_can_revoke_its_session_without_restoring_access(logout_client, job_engine):
    owner, session_id, headers = seed_session(job_engine, active=False)
    _, other_session, other_headers = seed_session(job_engine)
    for route in ("/api/auth/me", "/api/listings", "/api/dashboard"):
        assert logout_client.get(route, headers=headers).status_code == 403
    response = logout_client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    with Session(job_engine) as db:
        assert db.get(UserSession, session_id).revoked_at is not None
        assert db.get(UserSession, other_session).revoked_at is None
        assert db.get(User, owner).is_active is False
        db.execute(update(User).where(User.id == owner).values(is_active=True))
        db.commit()
    assert logout_client.get("/api/auth/me", headers=headers).status_code == 401
    assert logout_client.get("/api/auth/me", headers=other_headers).status_code == 200


@pytest.mark.parametrize("active", [False, True], ids=["disabled", "active"])
@pytest.mark.parametrize("invalid", ["expired", "revoked", "wrong-token"])
def test_logout_still_rejects_invalid_credentials(logout_client, job_engine, active, invalid):
    _, session_id, headers = seed_session(
        job_engine, active=active, expired=invalid == "expired", revoked=invalid == "revoked",
    )
    if invalid == "wrong-token":
        headers = {"Authorization": "Bearer not-a-real-session"}
    with Session(job_engine) as db:
        before = db.get(UserSession, session_id).revoked_at
    assert logout_client.post("/api/auth/logout", headers=headers).status_code == 401
    with Session(job_engine) as db:
        assert db.get(UserSession, session_id).revoked_at == before


@pytest.mark.parametrize("active", [False, True], ids=["disabled", "active"])
def test_failed_logout_is_not_acknowledged_and_can_retry(logout_client, job_engine, active):
    _, session_id, headers = seed_session(job_engine, active=active)

    def reject_update(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("update user_sessions"):
            raise OperationalError("synthetic session write failure", {}, Exception("private database detail"))

    event.listen(job_engine, "before_cursor_execute", reject_update)
    try:
        response = logout_client.post("/api/auth/logout", headers=headers)
    finally:
        event.remove(job_engine, "before_cursor_execute", reject_update)
    assert response.status_code == 500
    assert "private database detail" not in response.text
    with Session(job_engine) as db:
        assert db.get(UserSession, session_id).revoked_at is None
    assert logout_client.post("/api/auth/logout", headers=headers).status_code == 204
    assert logout_client.get("/api/auth/me", headers=headers).status_code == 401


def test_logout_requires_bearer_and_does_not_accept_session_cookie(logout_client, job_engine):
    _, session_id, headers = seed_session(job_engine, active=False)
    token = headers["Authorization"].removeprefix("Bearer ")
    for supplied in ({}, {"Cookie": f"session={token}"}):
        assert logout_client.post("/api/auth/logout", headers=supplied).status_code == 401
    with Session(job_engine) as db:
        assert db.get(UserSession, session_id).revoked_at is None
