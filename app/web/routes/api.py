"""JSON API routes for security features."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.csrf import csrf_manager
from app.core.session import get_session_identifier

router = APIRouter()


@router.get("/csrf-token")
async def get_csrf_token(session_identifier: str = Depends(get_session_identifier)) -> dict[str, str | None]:
    """Return a CSRF token tied to the current session."""
    if not settings.ENABLE_CSRF_JSON:
        return {"csrfToken": None}

    token = csrf_manager.generate(session_identifier)
    return {"csrfToken": token}
