import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import LoginThrottle, UserSession
from app.routes import auth
from app.worker import run_once
from tests.test_api import client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_concurrent_login_burst_cannot_start_more_password_checks_than_the_limit(monkeypatch):
    registered = client.post('/api/auth/register', json={
        'email': 'login-burst@example.com', 'password': 'correct-password', 'name': 'Login burst',
    })
    assert registered.status_code == 200
    monkeypatch.setenv('LOGIN_RATE_LIMIT_ATTEMPTS', '2')
    get_settings.cache_clear()
    entered = threading.Condition()
    release = threading.Event()
    checks = []

    def blocked_password_check(*args):
        with entered:
            checks.append(threading.get_ident())
            position = len(checks)
            entered.notify_all()
        if position <= 2:
            assert release.wait(10), 'Test controller did not release password checks'
        return False

    monkeypatch.setattr(auth, 'verify_password', blocked_password_check)

    def attempt():
        return client.post('/api/auth/login', json={
            'email': 'login-burst@example.com', 'password': 'wrong-password',
        })

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(attempt) for _ in range(2)]
            try:
                with entered:
                    assert entered.wait_for(lambda: len(checks) >= 2, timeout=10)
                excess = attempt()
                assert excess.status_code == 429, excess.text
                assert len(checks) == 2
            finally:
                release.set()
            assert [future.result(timeout=10).status_code for future in pending] == [401, 401]
    finally:
        get_settings.cache_clear()


def test_older_success_cannot_clear_a_newer_failed_login(monkeypatch):
    registered = client.post('/api/auth/register', json={
        'email': 'login-order@example.com', 'password': 'correct-password', 'name': 'Login order',
    })
    assert registered.status_code == 200
    entered = threading.Event()
    release = threading.Event()

    def verify(password, _hash):
        if password == 'correct-password':
            entered.set()
            assert release.wait(10)
            return True
        return False

    monkeypatch.setattr(auth, 'verify_password', verify)
    with ThreadPoolExecutor(max_workers=1) as pool:
        older = pool.submit(client.post, '/api/auth/login', json={
            'email': 'login-order@example.com', 'password': 'correct-password',
        })
        try:
            assert entered.wait(10)
            newer = client.post('/api/auth/login', json={
                'email': 'login-order@example.com', 'password': 'wrong-password',
            })
            assert newer.status_code == 401
        finally:
            release.set()
        assert older.result(timeout=10).status_code == 200
    with SessionLocal() as db:
        assert db.query(LoginThrottle).count() == 1, 'Older success erased a newer attempt'


def test_worker_reclaims_only_a_bounded_batch_of_expired_login_records():
    now = datetime.now(UTC)
    expired = now - timedelta(seconds=get_settings().login_rate_limit_window_seconds + 1)
    with SessionLocal() as db:
        db.add_all([
            LoginThrottle(identifier_hash=f'{index:064x}', attempts=5,
                          window_started_at=expired, last_failed_at=expired)
            for index in range(103)
        ])
        db.add(LoginThrottle(identifier_hash='f' * 64, attempts=5, window_started_at=now, last_failed_at=now))
        db.commit()
    assert run_once() == 0
    with SessionLocal() as db:
        assert db.query(LoginThrottle).count() == 4
        assert db.query(LoginThrottle).filter_by(identifier_hash='f' * 64).one().attempts == 5
    assert run_once() == 0
    with SessionLocal() as db:
        assert db.query(LoginThrottle).count() == 1


def test_admission_database_failure_does_not_start_password_verification(monkeypatch):
    registered = client.post('/api/auth/register', json={
        'email': 'unavailable@example.com', 'password': 'correct-password', 'name': 'Unavailable admission',
    })
    assert registered.status_code == 200
    password_checks = []

    def unavailable(*args):
        raise OperationalError('INSERT', {}, RuntimeError('sensitive-admission-details'))

    def forbidden(*args):
        password_checks.append(True)
        return False

    monkeypatch.setattr(auth, 'reserve_login_attempt', unavailable)
    monkeypatch.setattr(auth, 'verify_password', forbidden)
    response = TestClient(app, raise_server_exceptions=False).post('/api/auth/login', json={
        'email': 'unavailable@example.com', 'password': 'wrong-password',
    })
    assert response.status_code == 500
    assert 'sensitive-admission-details' not in response.text
    assert response.json()['error']['retryable'] is True
    assert password_checks == []


def test_failed_session_creation_rolls_back_successful_throttle_clear(monkeypatch):
    response = client.post('/api/auth/register', json={
        'email': 'session-failure@example.com', 'password': 'correct-password', 'name': 'Session failure',
    })
    assert response.status_code == 200

    original_commit = Session.commit

    def unavailable(db):
        if any(isinstance(item, UserSession) for item in db.new):
            raise OperationalError('INSERT', {}, RuntimeError('sensitive-session-details'))
        return original_commit(db)

    monkeypatch.setattr(Session, 'commit', unavailable)
    response = TestClient(app, raise_server_exceptions=False).post('/api/auth/login', json={
        'email': 'session-failure@example.com', 'password': 'correct-password',
    })
    assert response.status_code == 500
    assert 'sensitive-session-details' not in response.text
    with SessionLocal() as db:
        assert db.query(LoginThrottle).one().attempts == 1
        assert db.query(UserSession).count() == 1
