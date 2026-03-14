"""Routes for managing auto-categorization rules."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import i18n
from app.core.audit import log_action
from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.categories.models import Category
from app.domain.rules.models import Rule
from app.domain.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)
templates.env.globals.setdefault("_", i18n.gettext_proxy)
templates.env.globals.setdefault("ASSETS_VERSION", settings.ASSETS_VERSION)
templates.env.globals.setdefault(
    "is_admin",
    lambda user: bool(user and getattr(user, "email", None) and user.email.lower() in settings.admin_emails),
)


async def _get_rule_for_user(rule_id: int, user: User, db: AsyncSession) -> Rule:
    result = await db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return rule


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """List all auto-categorization rules for the current user."""
    rules_result = await db.execute(
        select(Rule)
        .where(Rule.user_id == user.id)
        .order_by(Rule.priority.desc(), Rule.created_at.desc())
    )
    rules = rules_result.scalars().all()

    categories_result = await db.execute(
        select(Category).where(Category.user_id == user.id).order_by(Category.name)
    )
    categories = categories_result.scalars().all()

    return templates.TemplateResponse(
        "rules/list.html",
        {
            "request": request,
            "user": user,
            "rules": rules,
            "categories": categories,
        },
    )


@router.post("/rules")
async def create_rule(
    request: Request,
    match_text: str = Form(...),
    category_id: int = Form(...),
    priority: int = Form(0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Create a new auto-categorization rule."""
    # Validate category belongs to user
    cat_result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    if not cat_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")

    rule = Rule(
        user_id=user.id,
        match_text=match_text.strip(),
        category_id=category_id,
        priority=priority,
        is_active=True,
    )
    db.add(rule)
    await log_action(db, user_id=user.id, action="create", entity_type="rule", detail={"match_text": match_text.strip(), "category_id": category_id})
    await db.commit()

    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}/edit")
async def edit_rule(
    rule_id: int,
    match_text: str = Form(...),
    category_id: int = Form(...),
    priority: int = Form(0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Edit an existing rule."""
    rule = await _get_rule_for_user(rule_id, user, db)

    # Validate category belongs to user
    cat_result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    if not cat_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")

    rule.match_text = match_text.strip()
    rule.category_id = category_id
    rule.priority = priority
    db.add(rule)
    await log_action(db, user_id=user.id, action="update", entity_type="rule", entity_id=rule_id, detail={"match_text": match_text.strip(), "category_id": category_id, "priority": priority})
    await db.commit()

    return JSONResponse({"id": rule.id, "match_text": rule.match_text, "category_id": rule.category_id, "priority": rule.priority, "is_active": rule.is_active})


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Toggle a rule active/inactive."""
    rule = await _get_rule_for_user(rule_id, user, db)
    rule.is_active = not rule.is_active
    db.add(rule)
    await log_action(db, user_id=user.id, action="update", entity_type="rule", entity_id=rule_id, detail={"is_active": rule.is_active})
    await db.commit()

    return JSONResponse({"id": rule.id, "is_active": rule.is_active})


@router.post("/rules/{rule_id}/delete")
async def delete_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Delete a rule."""
    rule = await _get_rule_for_user(rule_id, user, db)
    await log_action(db, user_id=user.id, action="delete", entity_type="rule", entity_id=rule_id, detail={"match_text": rule.match_text})
    await db.execute(delete(Rule).where(Rule.id == rule_id))
    await db.commit()

    return JSONResponse({"deleted": rule_id})
