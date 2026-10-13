import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import LoginThrottle, User
from app.rate_limit import _identifier_hash, reserve_login_attempt
from app.security import hash_password_pbkdf2, verify_password
from tests.test_api import client


def unique_email() -> str:
    return f"auth-{uuid.uuid4().hex}@example.com"


def clear_login_throttles() -> None:
    db: Session = SessionLocal()
    try:
        db.query(LoginThrottle).delete()
        db.commit()
    finally:
        db.close()


def test_new_passwords_are_argon2_hashes():
    email = unique_email()
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-password", "name": "Auth User"},
    )
    assert response.status_code == 200, response.text

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        assert user.password_hash.startswith("$argon2")
        assert verify_password("correct-password", user.password_hash)
    finally:
        db.close()


def test_logout_revokes_session_token():
    email = unique_email()
    register_response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-password", "name": "Logout User"},
    )
    token = register_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/api/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 401


def test_auth_tokens_are_not_set_as_cookies():
    response = client.post(
        "/api/auth/register",
        json={"email": unique_email(), "password": "correct-password", "name": "Cookie Free User"},
    )

    assert response.status_code == 200, response.text
    assert "token" in response.json()
    assert "set-cookie" not in response.headers


def test_session_cookie_alone_does_not_authenticate():
    response = client.get("/api/auth/me", headers={"Cookie": "session=not-a-supported-auth-mode"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Missing bearer token"


def test_legacy_pbkdf2_hash_upgrades_on_successful_login():
    email = unique_email()
    db: Session = SessionLocal()
    try:
        user = User(
            email=email,
            name="Legacy User",
            password_hash=hash_password_pbkdf2("correct-password"),
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        assert user.password_hash.startswith("$argon2")
    finally:
        db.close()


def test_failed_login_attempts_are_rate_limited():
    clear_login_throttles()
    email = unique_email()
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-password", "name": "Rate User"},
    )

    for _ in range(5):
        response = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        assert response.status_code == 401

    response = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.json()["error"]["retryable"] is True

    db = SessionLocal()
    try:
        throttle = db.query(LoginThrottle).one()
        assert throttle.attempts == 5
        assert len(throttle.identifier_hash) == 64
        assert email not in throttle.identifier_hash
    finally:
        db.close()


def test_successful_login_clears_failed_login_throttle():
    clear_login_throttles()
    email = unique_email()
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-password", "name": "Clear Throttle User"},
    )

    response = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401

    response = client.post("/api/auth/login", json={"email": email, "password": "correct-password"})
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        assert db.query(LoginThrottle).count() == 0
    finally:
        db.close()


def test_expired_login_throttle_starts_a_fresh_admission_window():
    clear_login_throttles()
    settings = get_settings()
    identifier = "test-client:expired@example.com"
    old_window = datetime.now(UTC) - timedelta(seconds=settings.login_rate_limit_window_seconds + 1)
    db: Session = SessionLocal()
    try:
        db.add(
            LoginThrottle(
                identifier_hash=_identifier_hash(identifier),
                attempts=settings.login_rate_limit_attempts,
                window_started_at=old_window,
                last_failed_at=old_window,
            )
        )
        db.commit()

        reserve_login_attempt(db, identifier)

        assert db.query(LoginThrottle).one().attempts == 1
    finally:
        db.close()
