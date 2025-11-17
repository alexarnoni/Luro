"""Custom middleware components for the application."""
from __future__ import annotations

import logging
import secrets
import time
from typing import Callable, Awaitable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core.csrf import SAFE_METHODS, csrf_manager

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request context (id, timing) and log a compact access line."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._skip_prefixes = ("/static", "/health")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
        request.state.request_id = request_id
        path = request.url.path
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Unhandled error for %s %s [request_id=%s]",
                request.method,
                path,
                request_id,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers.setdefault("X-Request-ID", request_id)

        if not path.startswith(self._skip_prefixes):
            status = getattr(response, "status_code", "unknown")
            client = request.client.host if request.client else "unknown"
            logger.info(
                "Handled %s %s -> %s in %.1fms (client=%s) [request_id=%s]",
                request.method,
                path,
                status,
                duration_ms,
                client,
                request_id,
            )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply a standard set of security-focused HTTP response headers."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)

        # Build a CSP that is permissive for development (allows inline scripts
        # and connect to jsdelivr for source map lookups), but keeps stricter
        # defaults in production. The header value must be a single string.
        if settings.ENV.lower() == "development":
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self' https://cdn.jsdelivr.net;"
            )
        else:
            csp = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self';"
            )

        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )

        if settings.ENV.lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate CSRF tokens for JSON API requests that mutate state."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.scope.get("type") != "http":
            return await call_next(request)

        if not settings.ENABLE_CSRF_JSON:
            return await call_next(request)

        method = request.method.upper()
        if method in SAFE_METHODS:
            return await call_next(request)

        content_type = request.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return await call_next(request)

        session_identifier = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_identifier:
            return await call_next(request)

        header_token = request.headers.get("X-CSRF-Token")
        if not header_token or not csrf_manager.validate(header_token, session_identifier):
            logger.warning("Rejected JSON request with invalid CSRF token on %s", request.url.path)
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or missing CSRF token."},
            )

        return await call_next(request)


__all__ = ["CSRFMiddleware", "RequestContextMiddleware", "SecurityHeadersMiddleware"]
