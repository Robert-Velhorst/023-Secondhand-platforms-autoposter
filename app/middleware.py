import logging
import time
import uuid
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.rate_limit import check_api_rate_limit

request_logger = logging.getLogger("autoposter.requests")
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data: blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)
IMPORT_BODY_LIMIT_BYTES = 10 * 1024 * 1024


class _ImportBodyTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413, detail="JSON import exceeds the 10 MiB request limit.")


class ImportBodyLimitMiddleware:
    """Enforce the JSON import byte cap even when the request is streamed."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != "/api/import":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"content-length"),
            None,
        )
        try:
            too_large = content_length is not None and int(content_length) > IMPORT_BODY_LIMIT_BYTES
        except ValueError:
            too_large = True
        if too_large:
            await self.app(scope, self._rejecting_receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > IMPORT_BODY_LIMIT_BYTES:
                    raise _ImportBodyTooLarge
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _rejecting_receive() -> Message:
        raise _ImportBodyTooLarge


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
    field_errors: dict | None = None,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "field_errors": field_errors or {},
                "retryable": retryable,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        headers=headers,
    )


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(ImportBodyLimitMiddleware)
    @app.middleware("http")
    async def request_id_and_security_headers(
        request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()
        status_code = 500
        try:
            rate_limited = api_retry_after(request)
            if rate_limited is not None:
                status_code = 429
                response = error_response(
                    request,
                    status_code=429,
                    code="RATE_LIMITED",
                    message="Too many requests. Please slow down and try again shortly.",
                    retryable=True,
                )
                response.headers["Retry-After"] = str(rate_limited)
            else:
                response = await call_next(request)
                status_code = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            request_logger.info(
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        details = exc.detail if isinstance(exc.detail, dict) else {}
        return error_response(
            request,
            status_code=exc.status_code,
            code=http_error_code(exc.status_code),
            message=message,
            details=details,
            retryable=http_error_retryable(exc.status_code),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: dict[str, list[str]] = {}
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            field_errors.setdefault(location or "request", []).append(error.get("msg", "Invalid value"))
        return error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="The request contains invalid fields.",
            field_errors=field_errors,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return error_response(
            request,
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="Unexpected server error.",
            retryable=True,
        )


def http_error_code(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }
    return mapping.get(status_code, "HTTP_ERROR")


def http_error_retryable(status_code: int) -> bool:
    return status_code in {408, 429, 500, 502, 503, 504}


def api_retry_after(request: Request) -> int | None:
    if not request.url.path.startswith("/api/"):
        return None
    if request.url.path == "/api/health":
        return None
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    return check_api_rate_limit(
        f"ip:{client_host}",
        settings.api_rate_limit_requests,
        settings.api_rate_limit_window_seconds,
    )
