"""API routes for dashboard financial summaries."""
from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.accounts.models import Account
from app.domain.categories.models import Category
from app.domain.transactions.models import Transaction
from app.domain.users.models import User

router = APIRouter()

DEFAULT_CATEGORY_COLOR = "#9ca3af"
OTHER_CATEGORY_COLOR = "#d1d5db"
MONTH_SERIES_SIZE = 6


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _as_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _get_month_series() -> list[date]:
    today = date.today()
    cursor = date(today.year, today.month, 1)
    series: list[date] = []
    for _ in range(MONTH_SERIES_SIZE):
        series.append(cursor)
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
    series.reverse()
    return series


@router.get("/resumo")
async def get_financial_summary(
    mes: int | None = Query(default=None, ge=1, le=12),
    ano: int | None = Query(default=None, ge=1900, le=2100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return a summary of financial data for the requested month."""

    today = date.today()
    target_year = ano or today.year
    target_month = mes or today.month

    first_day = _month_start(target_year, target_month)
    last_day_exclusive = _next_month(first_day)

    month_start_dt = _as_datetime(first_day)
    month_end_dt = _as_datetime(last_day_exclusive)

    # Totals (income vs expenses)
    totals_stmt = (
        select(
            Transaction.transaction_type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == user.id)
        .where(Transaction.transaction_date >= month_start_dt)
        .where(Transaction.transaction_date < month_end_dt)
        .group_by(Transaction.transaction_type)
    )

    totals_result = await db.execute(totals_stmt)
    totals_map = {row.transaction_type: float(row.total or 0) for row in totals_result}
    receitas = totals_map.get("income", 0.0)
    despesas = totals_map.get("expense", 0.0)
    saldo = receitas - despesas

    # Expenses grouped by category
    category_stmt = (
        select(
            Transaction.category_id,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            Category.name,
            Category.color,
        )
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(Account.user_id == user.id)
        .where(Transaction.transaction_type == "expense")
        .where(Transaction.transaction_date >= month_start_dt)
        .where(Transaction.transaction_date < month_end_dt)
        .group_by(Transaction.category_id, Category.name, Category.color)
    )

    category_result = await db.execute(category_stmt)
    categories = []
    for row in category_result:
        total_value = float(row.total or 0)
        if total_value <= 0:
            continue
        category_id = row.category_id
        name = row.name or ("Sem categoria" if category_id is None else "Categoria")
        if category_id is None:
            name = "Sem categoria"
        color = row.color or DEFAULT_CATEGORY_COLOR
        categories.append(
            {
                "category_id": category_id,
                "name": name,
                "total": total_value,
                "color": color,
            }
        )

    categories.sort(key=lambda item: item["total"], reverse=True)
    top_categories = categories[:5]
    if len(categories) > 5:
        others_total = sum(item["total"] for item in categories[5:])
        if others_total > 0:
            top_categories.append(
                {
                    "category_id": None,
                    "name": "Outras",
                    "total": others_total,
                    "color": OTHER_CATEGORY_COLOR,
                }
            )

    # Monthly evolution (last N months, independent from selected month)
    month_series = _get_month_series()
    series_start = _as_datetime(month_series[0])
    series_end = _as_datetime(_next_month(month_series[-1]))
    month_keys = [month.strftime("%Y-%m") for month in month_series]

    series_data = {
        key: {
            "mes": key,
            "despesas": 0.0,
            "receitas": 0.0,
        }
        for key in month_keys
    }

    monthly_stmt = (
        select(
            Transaction.transaction_date,
            Transaction.transaction_type,
            Transaction.amount,
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == user.id)
        .where(Transaction.transaction_date >= series_start)
        .where(Transaction.transaction_date < series_end)
    )

    monthly_result = await db.execute(monthly_stmt)
    for row in monthly_result:
        key = row.transaction_date.strftime("%Y-%m")
        if key not in series_data:
            continue
        amount = float(row.amount or 0)
        if row.transaction_type == "income":
            series_data[key]["receitas"] += amount
        elif row.transaction_type == "expense":
            series_data[key]["despesas"] += amount

    por_mes = [series_data[key] for key in month_keys]

    # Account balances within the selected month
    balance_case = case(
        (Transaction.transaction_type == "income", Transaction.amount),
        (Transaction.transaction_type == "expense", -Transaction.amount),
        else_=0,
    )

    accounts_stmt = (
        select(
            Account.id,
            Account.name,
            func.coalesce(func.sum(balance_case), 0).label("saldo"),
        )
        .outerjoin(
            Transaction,
            and_(
                Transaction.account_id == Account.id,
                Transaction.transaction_date >= month_start_dt,
                Transaction.transaction_date < month_end_dt,
            ),
        )
        .where(Account.user_id == user.id)
        .group_by(Account.id, Account.name)
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

    return {
        "totais": {
            "receitas": receitas,
            "despesas": despesas,
            "saldo": saldo,
        },
        "porCategoria": top_categories,
        "porMes": por_mes,
        "contas": contas,
    }
