"""Admin-only authorization helpers."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.session import get_current_user
from app.domain.users.models import User


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure the current user is in the configured admin allowlist."""
    email = (user.email or "").lower().strip()
    if email not in settings.ADMIN_EMAILS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user


__all__ = ["require_admin"]
