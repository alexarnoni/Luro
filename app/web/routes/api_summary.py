"""API routes for dashboard financial summaries."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.accounts.models import Account
from app.domain.insights.services import get_or_create_monthly_insight
from app.domain.transactions.models import Transaction
from app.domain.users.models import User
from app.services.analytics import build_month_summary

router = APIRouter()

OTHER_CATEGORY_COLOR = "#d1d5db"


@router.get("/resumo")
async def get_financial_summary(
    mes: int | None = Query(default=None, ge=1, le=12),
    ano: int | None = Query(default=None, ge=1900, le=2100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return a summary of financial data for the requested month."""

    today = date.today()
    target_year = ano or today.year
    target_month = mes or today.month
    month_key = f"{target_year:04d}-{target_month:02d}"

    analytics_summary = await build_month_summary(user.id, month_key, db)
    internal = analytics_summary.get("_internal", {})
    category_details: list[dict[str, Any]] = internal.get("category_details", [])
    month_series = internal.get("month_series", [])
    series_data = internal.get("series_data", {})

    totals = analytics_summary["totals"]
    receitas = totals.get("income", 0.0)
    despesas = totals.get("expense", 0.0)
    saldo = receitas - despesas

    top_categories = category_details[:5]
    if len(category_details) > 5:
        others_total = sum(item["total"] for item in category_details[5:])
        if others_total > 0:
            top_categories = top_categories + [
                {
                    "category_id": None,
                    "name": "Outras",
                    "total": others_total,
                    "color": OTHER_CATEGORY_COLOR,
                }
            ]

    por_categoria = [
        {
            "category_id": item["category_id"],
            "name": item["name"],
            "total": item["total"],
            "color": item["color"],
        }
        for item in top_categories
    ]

    por_mes = [
        {
            "mes": key,
            "receitas": series_data.get(key, {}).get("income", 0.0),
            "despesas": series_data.get(key, {}).get("expense", 0.0),
        }
        for key in month_series
    ]

    # Use current account balances for the "Saldos por conta" section instead of month-scoped sums
    accounts_stmt = (
        select(Account.id, Account.name, Account.balance.label("saldo"))
        .where(Account.user_id == user.id)
        .order_by(Account.name)
    )

    accounts_result = await db.execute(accounts_stmt)
    contas = [
        {
            "id": row.id,
            "name": row.name,
            "saldo": float(row.saldo or 0),
        }
        for row in accounts_result
    ]

    summary_response: dict[str, Any] = {
        "totais": {
            "receitas": receitas,
            "despesas": despesas,
            "saldo": saldo,
        },
        "porCategoria": por_categoria,
        "porMes": por_mes,
        "contas": contas,
    }

    insight = await get_or_create_monthly_insight(
        db,
        user_id=user.id,
        period=month_key,
        summary_payload={
            key: value
            for key, value in analytics_summary.items()
            if key != "_internal"
        },
    )

    if insight is not None:
        summary_response["insights"] = {
            "id": insight.id,
            "title": insight.title,
            "content": insight.content,
            "period": insight.period,
            "generatedAt": insight.created_at.isoformat() if insight.created_at else None,
        }
    else:
        summary_response["insights"] = None

    return summary_response
