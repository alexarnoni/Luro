import hashlib
import logging

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import resend

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME, clear_session_cookie, set_session_cookie
from app.core.database import get_db
from app.core.rate_limit import rate_limiter
from app.core.security import magic_link_manager
from app.domain.users.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)

logger = logging.getLogger(__name__)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
):
    """Send magic link to user's email."""
    client_host = request.client.host if request.client else "unknown"
    rate_key = f"{client_host}:{email.lower()}"
    allowed = await rate_limiter.is_allowed(
        rate_key,
        settings.RATE_LIMIT_MAX,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )

    if not allowed:
        anonymised_key = hashlib.sha256(rate_key.encode()).hexdigest()[:12]
        logger.warning("Login rate limit exceeded for identifier %s", anonymised_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    # Generate magic link token
    token = magic_link_manager.generate_token(email)

    # Create magic link URL
    magic_link = f"{request.url_for('verify_magic_link')}?token={token}"

    # Send email with magic link using Resend
    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY

            # Validate and normalize the `from` field expected by Resend.
            # Accepts either plain email (user@example.com) or a display name format
            # (Name <user@example.com>). If a plain email is provided, wrap it
            # with the application name for better deliverability/clarity.
            import re

            from_raw = (settings.RESEND_FROM_EMAIL or "").strip()
            EMAIL_RE = re.compile(r"^[^@<>\s]+@[^@<>\s]+\.[^@<>\s]+$")
            NAME_EMAIL_RE = re.compile(r"^.+ <[^@<>\s]+@[^@<>\s]+\.[^@<>\s]+>$")

            if EMAIL_RE.match(from_raw):
                from_field = f"{settings.APP_NAME} <{from_raw}>"
            elif NAME_EMAIL_RE.match(from_raw):
                from_field = from_raw
            else:
                logger.warning(
                    "RESEND_FROM_EMAIL value '%s' is invalid; falling back to noreply",
                    from_raw,
                )
                from_field = f"{settings.APP_NAME} <noreply@example.com>"

            resend.Emails.send({
                "from": from_field,
                "to": email,
                "subject": f"Login to {settings.APP_NAME}",
                "html": f"""
                <html>
                    <body>
                        <h1>Login to {settings.APP_NAME}</h1>
                        <p>Click the link below to login:</p>
                        <a href="{magic_link}">Login to {settings.APP_NAME}</a>
                        <p>This link will expire in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes.</p>
                    </body>
                </html>
                """
            })
        except Exception as exc:  # noqa: BLE001
            anonymised_key = hashlib.sha256(rate_key.encode()).hexdigest()[:12]
            logger.error(
                "Failed to send login email for identifier %s", anonymised_key, exc_info=exc
            )
            # In development, we can show the link instead of sending email
            if settings.DEBUG:
                return templates.TemplateResponse(
                    "auth/magic_link_sent.html",
                    {
                        "request": request,
                        "email": email,
                        "magic_link": magic_link,
                        "debug": True
                    }
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Login is temporarily unavailable. Please try again later.",
            )

    return templates.TemplateResponse(
        "auth/magic_link_sent.html",
        {"request": request, "email": email, "debug": settings.DEBUG}
    )


@router.get("/verify", name="verify_magic_link")
async def verify_magic_link(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify magic link and log user in."""
    # Verify the token
    email = magic_link_manager.verify_token(token)

    if not email:
        return templates.TemplateResponse(
            "auth/error.html",
            {"request": request, "error": "Invalid or expired magic link"}
        )

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Store user session (simplified - in production use proper session management)
    response = RedirectResponse(url="/dashboard", status_code=303)
    set_session_cookie(response, email)

    return response


@router.get("/logout")
async def logout():
    """Log user out."""
    response = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(response)
    return response
