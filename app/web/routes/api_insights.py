"""Routes for AI-generated financial insights."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.insights.models import Insight
from app.domain.users.models import User
from app.services.analytics import build_month_summary
from app.services.llm_client import generate_insight

logger = logging.getLogger(__name__)

NO_DATA_MESSAGE = (
    "Poucos dados para gerar um insight. Registre suas movimentações e comece pela reserva de emergência."
)

router = APIRouter()


def _current_month_range() -> tuple[datetime, datetime]:
    """Return UTC-aware current month boundaries for rate limit checks."""
    now = datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@router.post("/generate")
async def generate_monthly_insight(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Generate and persist an AI insight for the requested month."""

    try:
        summary = await build_month_summary(user.id, month, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    totals = summary.get("totals", {})
    if (totals.get("income", 0) or 0) == 0 and (totals.get("expense", 0) or 0) == 0:
        return {"month": month, "insight": NO_DATA_MESSAGE}

    existing_result = await db.execute(
        select(Insight).where(
            Insight.user_id == user.id,
            Insight.period == month,
            Insight.insight_type == "monthly",
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return {"month": month, "insight": existing.content}

    limit = settings.INSIGHTS_MAX_PER_MONTH
    if limit > 0:
        month_start, next_month_start = _current_month_range()
        count_stmt = (
            select(func.count())
            .select_from(Insight)
            .where(
                Insight.user_id == user.id,
                Insight.created_at >= month_start,
                Insight.created_at < next_month_start,
            )
        )
        current_count = await db.scalar(count_stmt) or 0
        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Limite mensal de insights alcançado. Tente novamente no próximo mês.",
            )

    sanitized_summary = {k: v for k, v in summary.items() if k != "_internal"}

    try:
        content = await generate_insight(sanitized_summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error(f"Falha na IA: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível gerar um insight no momento.",
        ) from exc

    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível gerar um insight no momento.",
        )

    insight = Insight(
        user_id=user.id,
        title=f"Insight de {month}",
        content=content,
        insight_type="monthly",
        period=month,
    )
    db.add(insight)
    await db.commit()
    await db.refresh(insight)

    return {"month": month, "insight": content}
