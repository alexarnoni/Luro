"""Utilities for working with HTTP cookies."""
from __future__ import annotations

from fastapi import Response, HTTPException, status
from itsdangerous import URLSafeSerializer

from app.core.config import settings

SESSION_COOKIE_NAME = "user_session"
_serializer = URLSafeSerializer(settings.SECRET_KEY, salt="session-cookie")


def _make_session_value(email: str) -> str:
    """Create a signed session payload containing the user email."""
    return _serializer.dumps({"email": email})


def parse_session_cookie(raw_value: str | None) -> str:
    """Parse and validate the signed session cookie, returning the user email."""
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = _serializer.loads(raw_value)
        email = data.get("email")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from None
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return email


def set_session_cookie(response: Response, email: str) -> None:
    """Set the session cookie with secure defaults."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_make_session_value(email),
        httponly=True,
        samesite="lax",
        secure=settings.ENV.lower() == "production",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie using the same security options."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.ENV.lower() == "production",
    )
