"""Seed default categories for a user."""

import argparse
import asyncio
from pathlib import Path
import sys
from typing import List

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.domain.categories.models import Category  # noqa: E402
from app.domain.users.models import User  # noqa: F401,E402
from app.domain.transactions.models import Transaction  # noqa: F401,E402
from app.domain.rules.models import Rule  # noqa: F401,E402
from app.domain.accounts.models import Account  # noqa: F401,E402

DEFAULT_CATEGORIES: List[dict] = [
    {"name": "Salary", "type": "income", "color": "#4CAF50"},
    {"name": "Freelance", "type": "income", "color": "#8BC34A"},
    {"name": "Groceries", "type": "expense", "color": "#FF9800"},
    {"name": "Rent", "type": "expense", "color": "#F44336"},
    {"name": "Utilities", "type": "expense", "color": "#03A9F4"},
    {"name": "Entertainment", "type": "expense", "color": "#9C27B0"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed default categories for a user")
    parser.add_argument("--user-id", type=int, required=True, help="Target user id")
    return parser.parse_args()


async def seed_categories(user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Category.name).where(Category.user_id == user_id)
        )
        existing_names = {row[0] for row in existing.all()}

        for category in DEFAULT_CATEGORIES:
            if category["name"] in existing_names:
                continue
            session.add(Category(user_id=user_id, **category))

        await session.commit()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_categories(args.user_id))
