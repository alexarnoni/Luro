from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import resend

from app.core.database import get_db
from app.core.config import settings
from app.core.security import magic_link_manager
from app.domain.users.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Send magic link to user's email."""
    # Generate magic link token
    token = magic_link_manager.generate_token(email)
    
    # Create magic link URL
    magic_link = f"{request.url_for('verify_magic_link')}?token={token}"
    
    # Send email with magic link using Resend
    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
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
        except Exception as e:
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
            raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    
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
    response.set_cookie(key="user_email", value=email, httponly=True)
    
    return response


@router.get("/logout")
async def logout():
    """Log user out."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="user_email")
    return response
