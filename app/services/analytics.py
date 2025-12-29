"""Shared analytics helpers for building monthly summaries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.models import Account
from app.domain.categories.models import Category
from app.domain.transactions.models import Transaction

DEFAULT_CATEGORY_COLOR = "#9ca3af"
MONTH_SERIES_SIZE = 6


@dataclass(slots=True)
class _MonthRange:
    month: str
    first_day: date
    first_day_dt: datetime
    next_month_dt: datetime


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _as_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _get_month_series(end_month: date) -> list[date]:
    cursor = date(end_month.year, end_month.month, 1)
    series: list[date] = []
    for _ in range(MONTH_SERIES_SIZE):
        series.append(cursor)
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
    series.reverse()
    return series


def _parse_month(month: str) -> _MonthRange:
    try:
        year_str, month_str = month.split("-", 1)
        year = int(year_str)
        month_number = int(month_str)
        first_day = _month_start(year, month_number)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise ValueError("month must be formatted as YYYY-MM") from exc

    next_month = _next_month(first_day)
    return _MonthRange(
        month=month,
        first_day=first_day,
        first_day_dt=_as_datetime(first_day),
        next_month_dt=_as_datetime(next_month),
    )


async def build_month_summary(
    user_id: int,
    month: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Return aggregated analytics for a user's financial activity in a month."""

    month_range = _parse_month(month)

    totals_stmt = (
        select(
            Transaction.transaction_type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == user_id)
        .where(Transaction.transaction_date >= month_range.first_day_dt)
        .where(Transaction.transaction_date < month_range.next_month_dt)
        .group_by(Transaction.transaction_type)
    )

    totals_result = await db.execute(totals_stmt)
    totals_map = {
        row.transaction_type: Decimal(row.total or 0) for row in totals_result
    }
    income_total = totals_map.get("income", Decimal("0"))
    expense_total = totals_map.get("expense", Decimal("0"))

    category_stmt = (
        select(
            Transaction.category_id,
            Transaction.category.label("fallback_category"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            Category.name,
            Category.color,
        )
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(Account.user_id == user_id)
        .where(Transaction.transaction_type == "expense")
        .where(Transaction.transaction_date >= month_range.first_day_dt)
        .where(Transaction.transaction_date < month_range.next_month_dt)
        .group_by(Transaction.category_id, Transaction.category, Category.name, Category.color)
    )

    category_rows = await db.execute(category_stmt)
    category_details = []
    for row in category_rows:
        total_value = Decimal(row.total or 0)
        if total_value <= 0:
            continue
        category_id = row.category_id
        name = row.name or row.fallback_category or ("Sem categoria" if category_id is None else "Categoria")
        if category_id is None and not row.fallback_category:
            name = "Sem categoria"
        color = row.color or DEFAULT_CATEGORY_COLOR
        category_details.append(
            {
                "category_id": category_id,
                "name": name,
                "total": total_value,
                "color": color,
            }
        )

    category_details.sort(key=lambda item: item["total"], reverse=True)
    total_expense_value = sum((item["total"] for item in category_details), Decimal("0"))

    by_category = []
    for item in category_details:
        percent = (item["total"] / total_expense_value * 100) if total_expense_value else Decimal("0")
        by_category.append(
            {
                "name": item["name"],
                "total": item["total"],
                "percent": float(percent),
            }
        )

    month_series = _get_month_series(month_range.first_day)
    series_start = _as_datetime(month_series[0])
    series_end = _as_datetime(_next_month(month_series[-1]))
    month_keys = [value.strftime("%Y-%m") for value in month_series]

    series_data = {
        key: {
            "month": key,
            "income": Decimal("0"),
            "expense": Decimal("0"),
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
        .where(Account.user_id == user_id)
        .where(Transaction.transaction_date >= series_start)
        .where(Transaction.transaction_date < series_end)
    )

    monthly_result = await db.execute(monthly_stmt)
    for row in monthly_result:
        key = row.transaction_date.strftime("%Y-%m")
        if key not in series_data:
            continue
        amount = Decimal(row.amount or 0)
        if row.transaction_type == "income":
            series_data[key]["income"] += amount
        elif row.transaction_type == "expense":
            series_data[key]["expense"] += amount

    cash_flow = []
    for value in month_series:
        key = value.strftime("%Y-%m")
        row = series_data[key]
        net_total = row["income"] - row["expense"]
        cash_flow.append(
            {
                "date": value.strftime("%Y-%m-01"),
                "net": net_total,
            }
        )

    selected_key = month_range.month
    selected_row = series_data.get(selected_key, {"income": Decimal("0"), "expense": Decimal("0")})
    selected_income = selected_row["income"]
    selected_expense = selected_row["expense"]

    selected_index = month_keys.index(selected_key) if selected_key in month_keys else len(month_keys) - 1
    previous_keys = month_keys[max(0, selected_index - 3) : selected_index]

    if previous_keys:
        previous_income_total = sum((series_data[key]["income"] for key in previous_keys), Decimal("0"))
        previous_expense_total = sum((series_data[key]["expense"] for key in previous_keys), Decimal("0"))
        previous_income_avg = previous_income_total / len(previous_keys)
        previous_expense_avg = previous_expense_total / len(previous_keys)
    else:
        previous_income_avg = Decimal("0")
        previous_expense_avg = Decimal("0")

    def _compute_delta(current: Decimal, baseline: Decimal) -> Decimal:
        if baseline == 0:
            return Decimal("0")
        return (current - baseline) / baseline * 100

    delta_vs_3m = {
        "income_pct": float(_compute_delta(selected_income, previous_income_avg)),
        "expense_pct": float(_compute_delta(selected_expense, previous_expense_avg)),
    }

    outliers: list[dict[str, Any]] = []
    if category_details:
        average_expense = total_expense_value / len(category_details) if category_details else Decimal("0")
        if average_expense > 0:
            for item in category_details:
                deviation = (item["total"] - average_expense) / average_expense * 100
                if deviation > 25:  # highlight categories significantly above average
                    outliers.append(
                        {
                            "category": item["name"],
                            "deviation_pct": float(deviation),
                        }
                    )
            outliers.sort(key=lambda value: value["deviation_pct"], reverse=True)

    return {
        "month": month_range.month,
        "totals": {
            "income": income_total,
            "expense": expense_total,
        },
        "by_category": by_category,
        "cash_flow": cash_flow,
        "delta_vs_3m": delta_vs_3m,
        "outliers": outliers,
        "_internal": {
            "category_details": category_details,
            "series_data": series_data,
            "month_series": [value.strftime("%Y-%m") for value in month_series],
            "month_start": month_range.first_day_dt,
            "month_end": month_range.next_month_dt,
        },
    }
