import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import i18n
from app.core.admin import require_admin
from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core.database import get_db
from app.domain.security.models import LoginRequest
from app.domain.users.models import User
from app.services.llm_client import test_llm_connectivity

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


async def _build_admin_context(
    request: Request,
    user: User,
    db: AsyncSession,
    ai_test_result: dict | None = None,
):
    db_ok = await _database_health(db)
    db_size = _database_size_bytes()

    # Recent login/magic link requests
    login_rows = await db.execute(
        select(LoginRequest)
        .order_by(desc(LoginRequest.requested_at))
        .limit(20)
    )
    login_events = login_rows.scalars().all()

    # Login summaries (last 30 days)
    window_start = datetime.utcnow() - timedelta(days=30)
    email_summary_rows = await db.execute(
        select(
            LoginRequest.email.label("email"),
            func.count(LoginRequest.id).label("count"),
            func.max(LoginRequest.requested_at).label("last_seen"),
        )
        .where(LoginRequest.requested_at >= window_start)
        .group_by(LoginRequest.email)
        .order_by(desc(func.max(LoginRequest.requested_at)))
        .limit(10)
    )
    login_email_summary = [
        {
            "email": row.email,
            "count": row.count,
            "last_seen": row.last_seen,
        }
        for row in email_summary_rows.fetchall()
    ]

    ip_summary_rows = await db.execute(
        select(
            LoginRequest.ip.label("ip"),
            func.count(LoginRequest.id).label("count"),
            func.max(LoginRequest.requested_at).label("last_seen"),
        )
        .where(LoginRequest.requested_at >= window_start, LoginRequest.ip.is_not(None))
        .group_by(LoginRequest.ip)
        .order_by(desc(func.max(LoginRequest.requested_at)))
        .limit(10)
    )
    login_ip_summary = [
        {
            "ip": row.ip,
            "count": row.count,
            "last_seen": row.last_seen,
        }
        for row in ip_summary_rows.fetchall()
    ]

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
        "login_email_summary": login_email_summary,
        "login_ip_summary": login_ip_summary,
        "logs_tail": _tail_logs(),
        "app_env": settings.ENV,
        "app_name": settings.APP_NAME,
        "allowed_hosts": settings.ALLOWED_HOSTS,
        "server_time": datetime.utcnow(),
        "db_url": settings.DATABASE_URL,
        "ai_test_result": ai_test_result,
    }
    return context


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard with health, security, data, AI config, and logs."""
    context = await _build_admin_context(request, user, db)
    return templates.TemplateResponse("admin/index.html", context)


@router.post("/admin/ai-test", response_class=HTMLResponse)
async def admin_ai_test(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Run a lightweight connectivity test to the configured LLM provider."""
    result = await test_llm_connectivity()
    context = await _build_admin_context(request, user, db, ai_test_result=result)
    return templates.TemplateResponse("admin/index.html", context)
