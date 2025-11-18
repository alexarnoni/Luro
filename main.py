from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.middleware import CSRFMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.i18n import I18nMiddleware, gettext_proxy
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
