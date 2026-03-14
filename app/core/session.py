"""Session helpers and dependencies."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import SESSION_COOKIE_NAME, parse_session_cookie
from app.core.database import get_db
from app.domain.security.models import UserSession
from app.domain.users.models import User

security_logger = logging.getLogger("app.security")


async def get_session_identifier(
    raw_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Return the user email extracted from the signed session cookie."""
    try:
        email, _ = parse_session_cookie(raw_session)
        return email
    except HTTPException:
        security_logger.warning("Unauthorized access attempt with invalid/absent session")
        raise


async def get_current_user(
    raw_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Load the current user from the database, validating the session token when present."""
    try:
        email, session_token = parse_session_cookie(raw_session)
    except HTTPException:
        security_logger.warning("Unauthorized access attempt with invalid/absent session")
        raise

    # If the cookie includes a session token, verify it is still active in the DB
    if session_token:
        session_row = await db.execute(
            select(UserSession).where(
                UserSession.token == session_token,
                UserSession.is_active.is_(True),
            )
        )
        db_session = session_row.scalar_one_or_none()
        if not db_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked or expired")

        # Bump last_seen_at without loading the full object
        await db.execute(
            update(UserSession)
            .where(UserSession.token == session_token)
            .values(last_seen_at=datetime.utcnow())
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        hashed_email = hashlib.sha256(email.encode()).hexdigest()[:12]
        security_logger.warning("Unauthorized access attempt for email hash=%s", hashed_email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
