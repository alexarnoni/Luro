import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import i18n
from app.core.admin import require_admin
from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core.database import get_db
from app.domain.security.models import LoginRequest
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


async def _database_health(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Database health check failed")
        return False


def _database_size_bytes() -> int | None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        return None
    # sqlite+aiosqlite:///path/to/db
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    if not os.path.exists(db_path):
        return None
    try:
        return os.path.getsize(db_path)
    except OSError:
        return None


def _tail_logs(max_lines: int = 20) -> list[str]:
    log_path = os.path.join("logs", "app.log")
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
            return [line.rstrip() for line in lines[-max_lines:]]
    except OSError:
        return []


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard with health, security, data, AI config, and logs."""
    db_ok = await _database_health(db)
    db_size = _database_size_bytes()

    # Recent login/magic link requests
    login_rows = await db.execute(
        select(LoginRequest)
        .order_by(desc(LoginRequest.requested_at))
        .limit(20)
    )
    login_events = login_rows.scalars().all()

    env_status = {
        "SECRET_KEY": bool(settings.SECRET_KEY and settings.SECRET_KEY != "change-this-secret-key-in-production"),
        "RESEND_API_KEY": bool(settings.RESEND_API_KEY),
        "TURNSTILE_SITE_KEY": bool(settings.TURNSTILE_SITE_KEY),
        "TURNSTILE_SECRET_KEY": bool(settings.TURNSTILE_SECRET_KEY),
    }

    ai_config = {
        "provider": settings.LLM_PROVIDER,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "insights_limit": settings.INSIGHTS_MAX_PER_MONTH,
    }

    context = {
        "request": request,
        "user": user,
        "db_ok": db_ok,
        "db_size": db_size,
        "env_status": env_status,
        "ai_config": ai_config,
        "login_events": login_events,
        "logs_tail": _tail_logs(),
        "app_env": settings.ENV,
        "app_name": settings.APP_NAME,
        "allowed_hosts": settings.ALLOWED_HOSTS,
        "server_time": datetime.utcnow(),
        "db_url": settings.DATABASE_URL,
    }

    return templates.TemplateResponse("admin/index.html", context)
