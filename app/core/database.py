from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# Create async engine
database_url = make_url(settings.DATABASE_URL)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

if database_url.get_backend_name() == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[arg-type]
        cursor = dbapi_connection.cursor()
        pragmas = (
            text("PRAGMA journal_mode=WAL"),
            text("PRAGMA synchronous=NORMAL"),
            text("PRAGMA foreign_keys=ON"),
            text("PRAGMA busy_timeout=5000"),
        )

        for pragma in pragmas:
            cursor.execute(pragma.text)
            if pragma.text.startswith("PRAGMA journal_mode"):
                cursor.fetchone()
        cursor.close()

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
