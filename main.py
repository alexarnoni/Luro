from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.middleware import CSRFMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.i18n import I18nMiddleware, gettext_proxy
from app.core import i18n
from app.core.cookies import SESSION_COOKIE_NAME
from app.web.routes import api, auth, dashboard, pages, admin
from app.web.routes import account, health

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize app on startup."""
    # Initialize database
    await init_db()
    yield


# Create FastAPI app
app = FastAPI(
    title="Luro",
    description="Personal Finance Manager",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
# Internationalization middleware - sets a per-request translator
app.add_middleware(I18nMiddleware)

# Shared templates instance for global handlers
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)
templates.env.globals.setdefault("_", i18n.gettext_proxy)
templates.env.globals.setdefault("ASSETS_VERSION", settings.ASSETS_VERSION)
templates.env.globals.setdefault(
    "is_admin",
    lambda user: bool(user and getattr(user, "email", None) and user.email.lower() in settings.admin_emails),
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# Include routers
app.include_router(pages.router, tags=["pages"])
app.include_router(auth.router, tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(admin.router, tags=["admin"])
app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(account.router, tags=["account"])
app.include_router(health.router, tags=["health"])


# Friendly handling for HTML 401/403 on web routes
@app.exception_handler(Exception)
async def http_error_handler(request: Request, exc: Exception):
    from fastapi import HTTPException  # local import to avoid circulars

    if not isinstance(exc, HTTPException):
        raise exc

    accepts_html = "text/html" in (request.headers.get("accept") or "")
    wants_web = accepts_html and not request.url.path.startswith("/api")

    if exc.status_code == status.HTTP_401_UNAUTHORIZED and wants_web:
        next_url = request.url.path
        return RedirectResponse(url=f"/login?next={next_url}", status_code=status.HTTP_302_FOUND)

    if exc.status_code == status.HTTP_403_FORBIDDEN and wants_web:
        return templates.TemplateResponse(
            "errors/403.html",
            {"request": request, "detail": exc.detail},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
