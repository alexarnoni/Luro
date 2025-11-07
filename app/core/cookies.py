"""Utilities for working with HTTP cookies."""
from __future__ import annotations

from fastapi import Response

from app.core.config import settings

SESSION_COOKIE_NAME = "user_email"


def set_session_cookie(response: Response, value: str) -> None:
    """Set the session cookie with secure defaults."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=value,
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
