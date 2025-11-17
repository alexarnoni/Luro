import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", summary="Health check")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Simple health check that also touches the database."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        db_status = "error"
        logger.exception("Database healthcheck failed", exc_info=exc)

    return {"status": "ok", "database": db_status}
