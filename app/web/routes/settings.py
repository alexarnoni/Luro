"""Routes for user settings, including session management."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import i18n
from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME, parse_session_cookie
from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.security.models import UserSession
from app.domain.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)
templates.env.globals.setdefault("_", i18n.gettext_proxy)
templates.env.globals.setdefault("ASSETS_VERSION", settings.ASSETS_VERSION)
templates.env.globals.setdefault(
    "is_admin",
    lambda user: bool(user and getattr(user, "email", None) and user.email.lower() in settings.admin_emails),
)


def _get_current_token(raw_session: Optional[str]) -> str | None:
    """Extract the session token from the cookie without raising."""
    if not raw_session:
        return None
    try:
        _, token = parse_session_cookie(raw_session)
        return token
    except HTTPException:
        return None


@router.get("/settings/sessions", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    raw_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> HTMLResponse:
    """Show all active sessions for the current user."""
    current_token = _get_current_token(raw_session)

    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active.is_(True))
        .order_by(UserSession.last_seen_at.desc())
    )
    sessions = result.scalars().all()

    return templates.TemplateResponse(
        "settings/sessions.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "current_token": current_token,
        },
    )


@router.post("/settings/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Revoke a specific session by ID."""
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session.is_active = False
    db.add(session)
    await db.commit()

    return JSONResponse({"revoked": session_id})


@router.post("/settings/sessions/revoke-all")
async def revoke_all_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    raw_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> JSONResponse:
    """Revoke all sessions except the current one."""
    current_token = _get_current_token(raw_session)

    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active.is_(True))
    )
    # Exclude current session from revocation if we have its token
    if current_token:
        stmt = stmt.where(UserSession.token != current_token)

    result = await db.execute(stmt.values(is_active=False))
    await db.commit()

    return JSONResponse({"revoked": result.rowcount})
