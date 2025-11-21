"""CSRF token utilities for JSON APIs."""
from __future__ import annotations

import secrets
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.session import get_session_identifier

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CsrfManager:
    """Generate and validate CSRF tokens bound to a session."""

    def __init__(self) -> None:
        self._serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="csrf-token")

    def generate(self, session_identifier: str) -> str:
        payload = {
            "session": session_identifier,
            "nonce": secrets.token_urlsafe(16),
        }
        return self._serializer.dumps(payload)

    def validate(self, token: str, session_identifier: str, max_age: int = 3600) -> bool:
        try:
            data = self._serializer.loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return False
        return data.get("session") == session_identifier


csrf_manager = CsrfManager()


async def enforce_csrf_protection(
    request: Request,
    session_identifier: str = Depends(get_session_identifier),
) -> None:
    """Dependency that ensures the request includes a valid CSRF token."""
    if not settings.ENABLE_CSRF_JSON:
        return

    if request.method.upper() in SAFE_METHODS:
        return

    header_token = request.headers.get("X-CSRF-Token")
    if not header_token or not csrf_manager.validate(header_token, session_identifier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token.",
        )


__all__ = [
    "SAFE_METHODS",
    "csrf_manager",
    "enforce_csrf_protection",
]
