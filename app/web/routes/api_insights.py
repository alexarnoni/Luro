"""Routes for AI-generated financial insights."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.insights.models import Insight
from app.domain.users.models import User
from app.services.analytics import build_month_summary
from app.services.llm_client import generate_insight

NO_DATA_MESSAGE = (
    "Poucos dados para gerar um insight. Registre suas movimentações e comece pela reserva de emergência."
)

router = APIRouter()


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
    if float(totals.get("income", 0) or 0) == 0 and float(
        totals.get("expense", 0) or 0
    ) == 0:
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

    sanitized_summary = {k: v for k, v in summary.items() if k != "_internal"}

    try:
        content = await generate_insight(sanitized_summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
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

    # TODO: aplicar rate limit mensal usando INSIGHTS_MAX_PER_MONTH

    return {"month": month, "insight": content}
