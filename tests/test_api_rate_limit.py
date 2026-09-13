from app.rate_limit import _api_expirations, api_buckets, check_api_rate_limit


def setup_function():
    api_buckets.clear()
    _api_expirations.clear()


def test_api_rate_limit_tracks_hashed_identifier_windows():
    assert check_api_rate_limit("bearer-token", limit=2, window_seconds=60) is None
    assert check_api_rate_limit("bearer-token", limit=2, window_seconds=60) is None

    retry_after = check_api_rate_limit("bearer-token", limit=2, window_seconds=60)

    assert retry_after is not None
    assert retry_after > 0
    assert "bearer-token" not in api_buckets
    assert len(next(iter(api_buckets))) == 64
