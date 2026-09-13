from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest

from app import rate_limit


@pytest.fixture
def clock(monkeypatch):
    seconds = [100.0]

    class TestDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds[0])

    monkeypatch.setattr(rate_limit, "datetime", TestDateTime)
    monkeypatch.setattr(rate_limit, "monotonic", lambda: seconds[0], raising=False)
    monkeypatch.setattr(rate_limit, "api_buckets", {})
    monkeypatch.setattr(rate_limit, "_api_expirations", [])
    yield seconds


def test_expired_identities_are_reclaimed_when_a_different_client_arrives(clock):
    for index in range(100):
        assert rate_limit.check_api_rate_limit(f"expired-{index}", 2, 60) is None
    clock[0] += 61
    assert rate_limit.check_api_rate_limit("new-client", 2, 60) is None
    assert len(rate_limit.api_buckets) == 1


def test_identity_churn_has_a_hard_memory_bound_without_resetting_active_quotas(clock):
    for index in range(10_000):
        assert rate_limit.check_api_rate_limit(f"active-{index}", 1, 60) is None
    assert rate_limit.check_api_rate_limit("overflow", 1, 60) == 60
    assert len(rate_limit.api_buckets) == 10_000
    assert rate_limit.check_api_rate_limit("active-0", 1, 60) == 60
    clock[0] += 60
    assert rate_limit.check_api_rate_limit("overflow", 1, 60) is None
    assert len(rate_limit.api_buckets) == 1


def test_window_resets_at_exact_expiry(clock):
    assert rate_limit.check_api_rate_limit("boundary", 1, 60) is None
    clock[0] += 60
    assert rate_limit.check_api_rate_limit("boundary", 1, 60) is None


def test_repeated_requests_do_not_grow_the_expiry_index(clock):
    for _ in range(50_000):
        rate_limit.check_api_rate_limit("hot-client", 3, 60)
    assert len(rate_limit.api_buckets) == len(rate_limit._api_expirations) == 1
    assert next(iter(rate_limit.api_buckets.values())).requests == 3


def test_capacity_rejects_churn_but_preserves_existing_available_quota(clock, monkeypatch):
    monkeypatch.setattr(rate_limit, "MAX_API_BUCKETS", 2)
    assert rate_limit.check_api_rate_limit("first", 2, 60) is None
    assert rate_limit.check_api_rate_limit("second", 2, 60) is None
    for index in range(1000):
        assert rate_limit.check_api_rate_limit(f"overflow-{index}", 2, 60) == 60
    assert len(rate_limit.api_buckets) == len(rate_limit._api_expirations) == 2
    assert rate_limit.check_api_rate_limit("first", 2, 60) is None
    assert rate_limit.check_api_rate_limit("first", 2, 60) == 60


def test_expiry_index_handles_different_window_lengths(clock, monkeypatch):
    monkeypatch.setattr(rate_limit, "MAX_API_BUCKETS", 2)
    assert rate_limit.check_api_rate_limit("long", 1, 60) is None
    assert rate_limit.check_api_rate_limit("short", 1, 5) is None
    assert rate_limit.check_api_rate_limit("overflow", 1, 60) == 5
    clock[0] += 5
    assert rate_limit.check_api_rate_limit("overflow", 1, 60) is None
    assert rate_limit.check_api_rate_limit("long", 1, 60) == 55
    assert len(rate_limit.api_buckets) == len(rate_limit._api_expirations) == 2


def test_retry_after_rounds_up_and_rejections_do_not_extend_the_window(clock):
    assert rate_limit.check_api_rate_limit("retry", 1, 60) is None
    clock[0] += 0.25
    assert rate_limit.check_api_rate_limit("retry", 1, 60) == 60
    clock[0] += 59.25
    assert rate_limit.check_api_rate_limit("retry", 1, 60) == 1
    clock[0] += 0.5
    assert rate_limit.check_api_rate_limit("retry", 1, 60) is None


def test_wall_clock_changes_do_not_affect_api_windows(clock, monkeypatch):
    class UnusableWallClock:
        @staticmethod
        def now(tz):
            raise AssertionError("API windows must not depend on the wall clock")

    monkeypatch.setattr(rate_limit, "datetime", UnusableWallClock)
    assert rate_limit.check_api_rate_limit("monotonic", 1, 60) is None
    clock[0] += 30
    assert rate_limit.check_api_rate_limit("monotonic", 1, 60) == 30


def test_concurrent_admission_never_exceeds_the_limit(clock):
    start = Barrier(16)

    def requests(_):
        start.wait(timeout=10)
        return [rate_limit.check_api_rate_limit("shared", 37, 60) for _ in range(100)]

    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = [result for batch in pool.map(requests, range(16)) for result in batch]
    assert outcomes.count(None) == 37
    assert outcomes.count(60) == 1600 - 37
    assert next(iter(rate_limit.api_buckets.values())).requests == 37
    assert len(rate_limit._api_expirations) == 1


def test_capacity_returns_real_http_429_but_leaves_health_and_static_available(clock, monkeypatch):
    from tests.test_api import client

    monkeypatch.setattr(rate_limit, "MAX_API_BUCKETS", 2)
    for token in ("first", "second"):
        assert client.get("/api/platforms", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    response = client.get("/api/platforms", headers={"Authorization": "Bearer overflow"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.json()["error"]["retryable"] is True
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200
    clock[0] += 60
    assert client.get("/api/platforms", headers={"Authorization": "Bearer overflow"}).status_code == 200
