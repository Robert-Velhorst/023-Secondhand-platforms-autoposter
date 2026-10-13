from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

RATE_LIMIT_HEADER_KEYS = ("rate_limit_headers", "quota_headers", "response_headers", "headers")
RETRY_AFTER_HEADERS = ("retry-after",)
RESET_DELTA_HEADERS = ("ratelimit-reset", "rate-limit-reset")
RESET_EPOCH_HEADERS = ("x-ratelimit-reset", "x-rate-limit-reset")
REMAINING_HEADERS = ("ratelimit-remaining", "x-ratelimit-remaining", "x-rate-limit-remaining")


def quota_retry_at_from_outcome(data: Mapping[str, Any] | None, now: datetime | None = None) -> datetime | None:
    if not isinstance(data, Mapping):
        return None
    headers = quota_headers_from_outcome(data)
    if not headers:
        return None
    return quota_retry_at_from_headers(headers, http_status=_http_status(data), now=now)


def quota_retry_at_from_headers(
    headers: Mapping[str, Any],
    *,
    http_status: int | None = None,
    now: datetime | None = None,
) -> datetime | None:
    now = _aware(now or datetime.now(UTC))
    normalized = {str(key).lower(): str(value).strip() for key, value in headers.items() if value is not None}

    retry_after = _first_header(normalized, RETRY_AFTER_HEADERS)
    if retry_after:
        parsed_retry_after = _parse_retry_after(retry_after, now)
        if parsed_retry_after:
            return parsed_retry_after

    remaining = _parse_int(_first_header(normalized, REMAINING_HEADERS))
    reset_at = _reset_at(normalized, now)
    if reset_at and (remaining == 0 or http_status == 429):
        return reset_at
    return None


def quota_backoff_payload(retry_at: datetime, headers: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": "official_api_headers",
        "next_retry_at": retry_at.isoformat(),
        "headers": {str(key): str(value) for key, value in headers.items()},
    }


def quota_headers_from_outcome(data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in RATE_LIMIT_HEADER_KEYS:
        value = data.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _first_header(headers: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = headers.get(name)
        if value:
            return value
    return None


def _http_status(data: Mapping[str, Any]) -> int | None:
    for key in ("http_status", "status_code"):
        status = _parse_int(data.get(key))
        if status is not None:
            return status
    return None


def _reset_at(headers: Mapping[str, str], now: datetime) -> datetime | None:
    delta_reset = _parse_int(_first_header(headers, RESET_DELTA_HEADERS))
    if delta_reset is not None:
        return now + timedelta(seconds=max(delta_reset, 0))

    epoch_reset = _parse_int(_first_header(headers, RESET_EPOCH_HEADERS))
    if epoch_reset is None:
        return None
    if epoch_reset > 10_000_000:
        return datetime.fromtimestamp(epoch_reset, tz=UTC)
    return now + timedelta(seconds=max(epoch_reset, 0))


def _parse_retry_after(value: str, now: datetime) -> datetime | None:
    seconds = _parse_int(value)
    if seconds is not None:
        return now + timedelta(seconds=max(seconds, 0))
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return _aware(parsed)


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
