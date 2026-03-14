"""Utilities for working with HTTP cookies."""
from __future__ import annotations

from fastapi import Response, HTTPException, status
from itsdangerous import URLSafeSerializer

from app.core.config import settings

SESSION_COOKIE_NAME = "user_session"
_serializer = URLSafeSerializer(settings.SECRET_KEY, salt="session-cookie")


def _make_session_value(email: str, session_token: str | None = None) -> str:
    """Create a signed session payload containing the user email and optional session token."""
    payload: dict = {"email": email}
    if session_token:
        payload["sid"] = session_token
    return _serializer.dumps(payload)


def parse_session_cookie(raw_value: str | None) -> tuple[str, str | None]:
    """Parse and validate the signed session cookie.

    Returns:
        A tuple of (email, session_token). ``session_token`` may be ``None``
        for legacy cookies that pre-date revocable sessions.
    """
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = _serializer.loads(raw_value)
        email = data.get("email")
        session_token: str | None = data.get("sid")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from None
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return email, session_token


def set_session_cookie(response: Response, email: str, session_token: str | None = None) -> None:
    """Set the session cookie with secure defaults."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_make_session_value(email, session_token),
        httponly=True,
        samesite="lax",
        secure=settings.ENV.lower() == "production",
        max_age=settings.SESSION_COOKIE_MAX_AGE_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie using the same security options."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.ENV.lower() == "production",
    )
