import logging

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.users.models import User
from app.domain.accounts.models import Account
from app.domain.transactions.models import Transaction
from app.domain.categories.models import Category
from app.domain.goals.models import Goal

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Display user dashboard."""
    # Get user's accounts
    accounts_result = await db.execute(
        select(Account).where(Account.user_id == user.id)
    )
    accounts = accounts_result.scalars().all()
    
    # Get recent transactions
    transactions_result = await db.execute(
        select(Transaction)
        .join(Account)
        .where(Account.user_id == user.id)
        .order_by(desc(Transaction.transaction_date))
        .limit(10)
    )
    transactions = transactions_result.scalars().all()
    
    # Get user's goals
    goals_result = await db.execute(
        select(Goal).where(Goal.user_id == user.id)
    )
    goals = goals_result.scalars().all()
    
    # Calculate total balance
    total_balance = sum(account.balance for account in accounts)
    
    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "accounts": accounts,
            "transactions": transactions,
            "goals": goals,
            "total_balance": total_balance
        }
    )


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Display accounts page."""
    accounts_result = await db.execute(
        select(Account).where(Account.user_id == user.id)
    )
    accounts = accounts_result.scalars().all()
    
    return templates.TemplateResponse(
        "accounts/list.html",
        {"request": request, "user": user, "accounts": accounts}
    )


@router.post("/accounts")
async def create_account(
    request: Request,
    name: str = Form(...),
    account_type: str = Form(...),
    balance: float = Form(0.0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new account."""
    account = Account(
        user_id=user.id,
        name=name,
        account_type=account_type,
        balance=balance
    )
    db.add(account)
    await db.commit()
    
    return RedirectResponse(url="/accounts", status_code=303)


@router.get("/transactions", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Display transactions page."""
    # Get user's accounts
    accounts_result = await db.execute(
        select(Account).where(Account.user_id == user.id)
    )
    accounts = accounts_result.scalars().all()
    
    # Get transactions
    transactions_result = await db.execute(
        select(Transaction)
        .join(Account)
        .where(Account.user_id == user.id)
        .order_by(desc(Transaction.transaction_date))
    )
    transactions = transactions_result.scalars().all()
    
    return templates.TemplateResponse(
        "transactions/list.html",
        {
            "request": request,
            "user": user,
            "accounts": accounts,
            "transactions": transactions
        }
    )


@router.post("/transactions")
async def create_transaction(
    request: Request,
    account_id: int = Form(...),
    amount: float = Form(...),
    transaction_type: str = Form(...),
    category: str = Form(None),
    category_id: int | None = Form(None),
    description: str = Form(None),
    transaction_date: str = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new transaction."""
    # Verify account belongs to user
    account_result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == user.id
        )
    )
    account = account_result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Parse date
    trans_date = datetime.utcnow()
    if transaction_date:
        try:
            trans_date = datetime.fromisoformat(transaction_date)
        except ValueError:
            pass
    
    category_name = category.strip() if category else None
    category_pk = None

    if category_id is not None:
        category_result = await db.execute(
            select(Category).where(
                Category.id == category_id,
                Category.user_id == user.id,
            )
        )
        category_obj = category_result.scalar_one_or_none()
        if not category_obj:
            raise HTTPException(status_code=404, detail="Category not found")
        category_pk = category_obj.id
        if not category_name:
            category_name = category_obj.name
    elif category_name:
        logger.warning(
            "Transaction created with legacy category string for user %s", user.id
        )

    # Create transaction
    transaction = Transaction(
        account_id=account_id,
        amount=amount,
        transaction_type=transaction_type,
        category=category_name,
        category_id=category_pk,
        description=description,
        transaction_date=trans_date
    )
    db.add(transaction)
    
    # Update account balance
    if transaction_type == "income":
        account.balance += amount
    else:  # expense
        account.balance -= amount
    
    await db.commit()
    
    return RedirectResponse(url="/transactions", status_code=303)


@router.get("/goals", response_class=HTMLResponse)
async def goals_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Display goals page."""
    goals_result = await db.execute(
        select(Goal).where(Goal.user_id == user.id)
    )
    goals = goals_result.scalars().all()
    
    return templates.TemplateResponse(
        "goals/list.html",
        {"request": request, "user": user, "goals": goals}
    )


@router.post("/goals")
async def create_goal(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    target_amount: float = Form(...),
    target_date: str = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new goal."""
    target_dt = None
    if target_date:
        try:
            target_dt = datetime.fromisoformat(target_date)
        except ValueError:
            pass
    
    goal = Goal(
        user_id=user.id,
        name=name,
        description=description,
        target_amount=target_amount,
        target_date=target_dt
    )
    db.add(goal)
    await db.commit()
    
    return RedirectResponse(url="/goals", status_code=303)
