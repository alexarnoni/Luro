"""Session helpers and dependencies."""
from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import SESSION_COOKIE_NAME
from app.core.database import get_db
from app.domain.users.models import User


async def get_session_identifier(
    session_value: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Return the session identifier stored in the cookie."""
    if not session_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return session_value


async def get_current_user(
    session_value: str = Depends(get_session_identifier),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Load the current user from the database using the session value."""
    result = await db.execute(select(User).where(User.email == session_value))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
