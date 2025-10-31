from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.database import init_db
from app.web.routes import auth, dashboard, pages


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

# Mount static files
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# Include routers
app.include_router(pages.router, tags=["pages"])
app.include_router(auth.router, tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
