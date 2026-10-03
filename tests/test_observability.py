import json
import logging

from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app
from app.observability import JsonLogFormatter
from tests.test_api import client


def test_json_log_formatter_includes_operational_fields():
    record = logging.LogRecord(
        name="autoposter.requests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.method = "GET"
    record.path = "/api/health"
    record.status_code = 200
    record.duration_ms = 12.34

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "autoposter.requests"
    assert payload["message"] == "HTTP request completed"
    assert payload["request_id"] == "request-123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.34
    assert payload["timestamp"]


def test_request_logging_records_request_metadata(monkeypatch):
    captured: dict = {}

    def capture_log(message, *, extra):
        captured["message"] = message
        captured["extra"] = extra

    monkeypatch.setattr("app.middleware.request_logger.info", capture_log)

    response = client.get("/api/health", headers={"X-Request-ID": "observability-test"})

    assert response.status_code == 200
    assert captured["message"] == "HTTP request completed"
    assert captured["extra"]["request_id"] == "observability-test"
    assert captured["extra"]["method"] == "GET"
    assert captured["extra"]["path"] == "/api/health"
    assert captured["extra"]["status_code"] == 200
    assert captured["extra"]["duration_ms"] >= 0


def test_health_returns_sanitized_unavailable_when_database_probe_fails():
    class UnavailableDatabase:
        def execute(self, _statement):
            raise OperationalError("SELECT 1", {}, RuntimeError("private database endpoint"))

    def unavailable_database():
        yield UnavailableDatabase()

    app.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "private database endpoint" not in response.text
