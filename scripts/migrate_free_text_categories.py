#!/usr/bin/env python3
"""
Migrate free-text transaction categories to real Category records and clear legacy text.

O que faz:
- Para cada usuário, pega categorias em texto livre (transactions.category quando category_id é NULL).
- Reaproveita Category existente (case-insensitive) ou cria uma nova com cor.
- Atualiza as transações para preencher category_id e limpa o campo legacy (category = NULL).

Como rodar no container de produção:
    docker compose -f docker-compose.prod.yml exec -T web env PYTHONPATH=/app python3 scripts/migrate_free_text_categories.py
"""
from __future__ import annotations

import asyncio
from typing import Dict

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.domain.accounts.models import Account  # noqa: F401
from app.domain.categories.models import Category
from app.domain.transactions.models import Transaction
from app.domain.users.models import User  # noqa: F401
from app.domain.rules.models import Rule  # noqa: F401
from app.domain.goals.models import Goal  # noqa: F401

PALETTE = [
    "#60a5fa", "#f472b6", "#22c55e", "#f59e0b", "#a78bfa",
    "#38bdf8", "#fb7185", "#10b981", "#f97316", "#8b5cf6",
]


def pick_color(name: str | None) -> str:
    if not name:
        return PALETTE[0]
    return PALETTE[abs(hash(name)) % len(PALETTE)]


async def migrate_user(session, user_id: int) -> tuple[int, int]:
    # Coletar categorias em texto livre nas transações do usuário
    distinct_stmt = (
        select(func.distinct(Transaction.category))
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == user_id)
        .where(Transaction.category_id.is_(None))
        .where(Transaction.category.is_not(None))
        .where(Transaction.category != "")
    )
    result = await session.execute(distinct_stmt)
    names = [row[0] for row in result if row[0]]
    if not names:
        return 0, 0

    # Cache de categorias existentes (case-insensitive)
    existing: Dict[str, Category] = {}
    existing_stmt = select(Category).where(Category.user_id == user_id)
    res_existing = await session.execute(existing_stmt)
    for cat in res_existing.scalars():
        existing[cat.name.lower()] = cat

    created_or_reused: Dict[str, int] = {}
    for name in names:
        key = name.lower()
        cat = existing.get(key)
        if not cat:
            cat = Category(
                user_id=user_id,
                name=name.strip(),
                type="expense",
                color=pick_color(name),
            )
            session.add(cat)
            await session.flush()
            existing[key] = cat
        created_or_reused[name] = cat.id

    updated = 0
    for name, cat_id in created_or_reused.items():
        upd = (
            update(Transaction)
            .values(category_id=cat_id, category=None)
            .where(Transaction.category_id.is_(None))
            .where(Transaction.category == name)
            .where(
                Transaction.account_id.in_(
                    select(Account.id).where(Account.user_id == user_id)
                )
            )
        )
        res = await session.execute(upd)
        updated += res.rowcount or 0

    return len(created_or_reused), updated


async def main() -> None:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///") or (db_url.startswith("sqlite+aiosqlite:///") and db_url.endswith(".db")):
        if not db_url.startswith("sqlite+aiosqlite://"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    engine = create_async_engine(db_url, future=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # user_ids distintos
        res_users = await session.execute(select(func.distinct(Account.user_id)))
        user_ids = [row[0] for row in res_users if row[0] is not None]
        if not user_ids:
            print("Nenhum usuário encontrado.")
            await engine.dispose()
            return

        total_cats = 0
        total_tx = 0
        for uid in user_ids:
            created_count, updated_count = await migrate_user(session, uid)
            total_cats += created_count
            total_tx += updated_count
        await session.commit()

    await engine.dispose()
    print(f"Categorização concluída: {total_cats} categorias criadas/reaproveitadas, {total_tx} transações atualizadas.")


if __name__ == "__main__":
    asyncio.run(main())
