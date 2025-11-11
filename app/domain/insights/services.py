"""Services for generating and storing financial insights."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_client import generate_insight

from .models import Insight

logger = logging.getLogger(__name__)


INSIGHT_TYPE_MONTHLY = "monthly_summary"


async def get_or_create_monthly_insight(
    db: AsyncSession,
    *,
    user_id: int,
    period: str,
    summary_payload: dict[str, Any],
) -> Insight | None:
    """Return an insight for the given month, creating it if needed.

    The function is idempotent – if an insight already exists for the given
    ``user_id``/``period`` pair, the stored record is returned instead of
    requesting a new generation.
    """

    insight = await _get_existing_monthly_insight(db, user_id=user_id, period=period)
    if insight is not None:
        return insight

    content = await _generate_monthly_insight_text(summary_payload=summary_payload)
    if not content:
        return None

    title = _build_monthly_title(period)

    insight = Insight(
        user_id=user_id,
        title=title,
        content=content,
        insight_type=INSIGHT_TYPE_MONTHLY,
        period=period,
    )
    db.add(insight)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Another worker created the insight in the meantime; fetch it.
        return await _get_existing_monthly_insight(db, user_id=user_id, period=period)
    else:
        await db.refresh(insight)
        return insight


async def _get_existing_monthly_insight(
    db: AsyncSession, *, user_id: int, period: str
) -> Insight | None:
    result = await db.execute(
        select(Insight).where(
            Insight.user_id == user_id,
            Insight.period == period,
            Insight.insight_type == INSIGHT_TYPE_MONTHLY,
        )
    )
    return result.scalar_one_or_none()


def _build_monthly_title(period: str) -> str:
    try:
        dt = datetime.strptime(period, "%Y-%m")
        return f"Insights de {dt.strftime('%B/%Y').capitalize()}"
    except ValueError:
        return f"Insights de {period}"


async def _generate_monthly_insight_text(
    *, summary_payload: dict[str, Any]
) -> str | None:
    try:
        return await generate_insight(summary_payload)
    except ValueError as exc:
        logger.info("AI insight generation skipped: %s", exc)
        return None
    except Exception:  # pragma: no cover - defensive guard around HTTP client
        logger.exception("AI insight generation failed")
        return None
