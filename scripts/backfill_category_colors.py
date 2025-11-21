#!/usr/bin/env python3
"""
Backfill missing colors for categories using a deterministic palette based on name.

Run inside the project root:
    python3 scripts/backfill_category_colors.py

This script uses DATABASE_URL from config/env and will update categories with null/empty color.
"""
from __future__ import annotations

import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.domain.users.models import User  # noqa: F401
from app.domain.transactions.models import Transaction  # noqa: F401
from app.domain.rules.models import Rule  # noqa: F401
from app.domain.categories.models import Category

PALETTE = [
    "#60a5fa", "#f472b6", "#22c55e", "#f59e0b", "#a78bfa",
    "#38bdf8", "#fb7185", "#10b981", "#f97316", "#8b5cf6",
]


def pick_color(name: str | None) -> str:
    if not name:
        return PALETTE[0]
    return PALETTE[abs(hash(name)) % len(PALETTE)]


async def main() -> None:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///") or db_url.startswith("sqlite+aiosqlite:///") and db_url.endswith(".db"):
        # ensure aiosqlite for async sqlite
        if not db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url, future=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # find categories without color or empty
        stmt = select(Category).where((Category.color.is_(None)) | (Category.color == ""))
        result = await session.execute(stmt)
        cats = result.scalars().all()
        if not cats:
            print("No categories missing colors.")
            return
        for cat in cats:
            cat.color = pick_color(cat.name)
            session.add(cat)
        await session.commit()
        print(f"Updated {len(cats)} categories with colors.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
