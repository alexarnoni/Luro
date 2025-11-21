"""JSON API routes for security features."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.csrf import csrf_manager
from app.core.session import get_session_identifier
from app.web.routes import api_categories
from app.web.routes import api_import
from app.web.routes import api_insights
from app.web.routes import api_summary

router = APIRouter()

router.include_router(api_categories.router, prefix="/categories", tags=["categories"])
router.include_router(api_import.router, tags=["import"])
router.include_router(api_insights.router, prefix="/insights", tags=["insights"])
router.include_router(api_summary.router, tags=["summary"])


@router.get("/csrf-token")
async def get_csrf_token(session_identifier: str = Depends(get_session_identifier)):
    """Return a CSRF token tied to the current session and set a cookie for double-submit defense."""
    if not settings.ENABLE_CSRF_JSON:
        return {"csrfToken": None}

    token = csrf_manager.generate(session_identifier)
    response = JSONResponse({"csrfToken": token})
    # Double-submit: set non-HttpOnly cookie so form posts include it automatically
    response.set_cookie(
        "csrf_token",
        token,
        httponly=False,
        samesite="lax",
        secure=settings.ENV.lower() == "production",
    )
    return response
