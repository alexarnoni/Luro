"""API routes for managing categories."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.accounts.models import Account
from app.domain.categories.models import Category
from app.domain.categories.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryReassignRequest,
    CategoryUpdate,
)
from app.domain.transactions.models import Transaction
from app.domain.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_category_for_user(
    category_id: int,
    user: User,
    db: AsyncSession,
) -> Category:
    """Return the category for the given user or raise 404."""
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.get("/", response_model=list[CategoryOut])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Category]:
    """Return all categories for the current user."""
    result = await db.execute(
        select(Category)
        .where(Category.user_id == user.id)
        .order_by(Category.type, Category.name)
    )
    categories = result.scalars().all()
    return categories


@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Category:
    """Create a new category for the current user."""
    existing = await db.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.name == payload.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists",
        )

    category = Category(
        user_id=user.id,
        name=payload.name,
        type=payload.type,
        color=payload.color,
    )
    db.add(category)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "IntegrityError while creating category for user %s", user.id, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists",
        ) from None

    await db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Category:
    """Update a category for the current user."""
    category = await _get_category_for_user(category_id, user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return category

    if "name" in update_data:
        existing = await db.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == update_data["name"],
                Category.id != category_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this name already exists",
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "IntegrityError while updating category %s for user %s", category_id, user.id, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists",
        ) from None

    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a category if there are no linked transactions."""
    category = await _get_category_for_user(category_id, user, db)

    transaction_count = await db.execute(
        select(func.count(Transaction.id))
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Transaction.category_id == category_id,
            Account.user_id == user.id,
        )
    )
    if transaction_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category has linked transactions. Reassign them before deleting.",
        )

    await db.delete(category)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{category_id}/reassign")
async def reassign_category_transactions(
    category_id: int,
    payload: CategoryReassignRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Reassign all transactions from one category to another."""
    source_category = await _get_category_for_user(category_id, user, db)
    target_category = await _get_category_for_user(payload.new_category_id, user, db)

    if source_category.id == target_category.id:
        return {"moved": 0}

    update_stmt = (
        update(Transaction)
        .where(Transaction.category_id == source_category.id)
        .where(
            Transaction.account_id.in_(
                select(Account.id).where(Account.user_id == user.id)
            )
        )
        .values(category_id=target_category.id, category=target_category.name)
    )

    result = await db.execute(update_stmt)
    moved = result.rowcount or 0

    await db.commit()

    return {"moved": moved}
