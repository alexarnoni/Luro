import logging

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from datetime import datetime

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core.database import get_db
from app.core.validation import parse_money
from app.core.session import get_current_user
from app.core import i18n
from app.domain.users.models import User
from app.domain.accounts.models import Account
from app.domain.transactions.models import Transaction
from app.domain.categories.models import Category
from app.domain.goals.models import Goal
from app.domain.accounts.models import Account

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)
templates.env.globals.setdefault("_", i18n.gettext_proxy)
templates.env.globals.setdefault("ASSETS_VERSION", settings.ASSETS_VERSION)
templates.env.globals.setdefault(
    "is_admin",
    lambda user: bool(user and getattr(user, "email", None) and user.email.lower() in settings.ADMIN_EMAILS),
)


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
    balance: str | float = Form(0.0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new account."""
    # parse and validate balance input
    try:
        if isinstance(balance, (int, float)):
            bal_val = float(balance)
        else:
            bal_val, _warnings = parse_money(balance)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid account balance")

    if bal_val < 0:
        raise HTTPException(status_code=400, detail="Initial balance cannot be negative")

    account = Account(
        user_id=user.id,
        name=name.strip(),
        account_type=account_type.strip(),
        balance=bal_val
    )
    db.add(account)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create account")
    
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
    amount: str | float = Form(...),
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

    # parse amount robustly
    try:
        if isinstance(amount, (int, float)):
            amt = float(amount)
        else:
            amt, _warnings = parse_money(amount)
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail=str(exc.detail))

    if amt == 0:
        raise HTTPException(status_code=400, detail="Amount must be non-zero")

    tx_type = transaction_type.strip().lower()
    if tx_type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="Invalid transaction type")

    # Create transaction and update balance atomically
    transaction = Transaction(
        account_id=account_id,
        amount=abs(amt),
        transaction_type=tx_type,
        category=category_name,
        category_id=category_pk,
        description=description,
        transaction_date=trans_date
    )
    db.add(transaction)

    # Update account balance with safety checks
    try:
        if tx_type == "income":
            account.balance = (account.balance or 0.0) + abs(amt)
        else:  # expense
            # simple overdraft prevention
            if account.balance is not None and account.balance < abs(amt):
                await db.rollback()
                raise HTTPException(status_code=400, detail="Insufficient funds in account")
            account.balance = (account.balance or 0.0) - abs(amt)
        db.add(account)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create transaction")

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
    # Get user's accounts so they can contribute to goals
    accounts_result = await db.execute(select(Account).where(Account.user_id == user.id))
    accounts = accounts_result.scalars().all()

    return templates.TemplateResponse(
        "goals/list.html",
        {"request": request, "user": user, "goals": goals, "accounts": accounts}
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


@router.post("/accounts/{account_id}/edit")
async def edit_account(
    request: Request,
    account_id: int,
    name: str = Form(...),
    balance: str | float = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Edit an existing account."""
    result = await db.execute(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # parse balance
    try:
        if isinstance(balance, (int, float)):
            bal_val = float(balance)
        else:
            bal_val, _warnings = parse_money(balance)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid account balance")

    if bal_val < 0:
        raise HTTPException(status_code=400, detail="Balance cannot be negative")

    account.name = name.strip()
    account.balance = bal_val
    db.add(account)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update account")

    accept = request.headers.get('accept', '')
    is_xhr = request.headers.get('x-requested-with', '') == 'XMLHttpRequest'
    if 'application/json' in accept or is_xhr:
        return JSONResponse({'id': account.id, 'name': account.name, 'balance': float(account.balance)})

    return RedirectResponse(url="/accounts", status_code=303)


@router.post("/accounts/{account_id}/delete")
async def delete_account(
    request: Request,
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an account and its transactions for the current user."""
    result = await db.execute(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        # delete transactions belonging to the account
        await db.execute(delete(Transaction).where(Transaction.account_id == account_id))
        # delete the account
        await db.execute(delete(Account).where(Account.id == account_id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to delete account")

    accept = request.headers.get('accept', '')
    is_xhr = request.headers.get('x-requested-with', '') == 'XMLHttpRequest'
    if 'application/json' in accept or is_xhr:
        return JSONResponse({'id': account_id})

    return RedirectResponse(url="/accounts", status_code=303)


@router.post("/transactions/{txn_id}/edit")
async def edit_transaction(
    request: Request,
    txn_id: int,
    description: str = Form(None),
    amount: str | float = Form(...),
    transaction_type: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Edit an existing transaction and adjust account balance appropriately."""
    # fetch transaction ensuring ownership via join
    tx_result = await db.execute(
        select(Transaction).join(Account).where(Transaction.id == txn_id, Account.user_id == user.id)
    )
    transaction = tx_result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # parse amount
    try:
        if isinstance(amount, (int, float)):
            new_amt = float(amount)
        else:
            new_amt, _warnings = parse_money(amount)
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail=str(exc.detail))

    if new_amt == 0:
        raise HTTPException(status_code=400, detail="Amount must be non-zero")

    new_type = transaction_type.strip().lower()
    if new_type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="Invalid transaction type")

    # get account
    acc_result = await db.execute(select(Account).where(Account.id == transaction.account_id))
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # revert old transaction effect
    try:
        if transaction.transaction_type == 'income':
            account.balance = (account.balance or 0.0) - float(transaction.amount)
        else:
            account.balance = (account.balance or 0.0) + float(transaction.amount)

        # apply new transaction effect
        if new_type == 'income':
            account.balance = (account.balance or 0.0) + abs(new_amt)
        else:
            # check overdraft
            if account.balance is not None and account.balance < abs(new_amt):
                await db.rollback()
                raise HTTPException(status_code=400, detail="Insufficient funds in account for this change")
            account.balance = (account.balance or 0.0) - abs(new_amt)

        # update transaction
        transaction.description = description
        transaction.amount = abs(new_amt)
        transaction.transaction_type = new_type

        db.add(account)
        db.add(transaction)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update transaction")

    accept = request.headers.get('accept', '')
    is_xhr = request.headers.get('x-requested-with', '') == 'XMLHttpRequest'
    if 'application/json' in accept or is_xhr:
        return JSONResponse({'id': transaction.id, 'amount': float(transaction.amount), 'description': transaction.description or '', 'transaction_type': transaction.transaction_type})

    return RedirectResponse(url="/transactions", status_code=303)


@router.post("/transactions/{txn_id}/delete")
async def delete_transaction(
    request: Request,
    txn_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a transaction and adjust the related account balance."""
    tx_result = await db.execute(
        select(Transaction).join(Account).where(Transaction.id == txn_id, Account.user_id == user.id)
    )
    transaction = tx_result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # get account
    acc_result = await db.execute(select(Account).where(Account.id == transaction.account_id))
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        # revert transaction effect on account balance
        if transaction.transaction_type == 'income':
            account.balance = (account.balance or 0.0) - float(transaction.amount)
        else:
            account.balance = (account.balance or 0.0) + float(transaction.amount)

        # delete the transaction
        await db.execute(delete(Transaction).where(Transaction.id == txn_id))
        db.add(account)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to delete transaction")

    accept = request.headers.get('accept', '')
    is_xhr = request.headers.get('x-requested-with', '') == 'XMLHttpRequest'
    if 'application/json' in accept or is_xhr:
        return JSONResponse({'id': txn_id, 'account_balance': float(account.balance), 'account_id': account.id})

    return RedirectResponse(url="/transactions", status_code=303)


@router.post("/goals/{goal_id}")
async def update_goal(
    request: Request,
    goal_id: int,
    name: str = Form(...),
    description: str = Form(None),
    target_amount: float = Form(...),
    target_date: str = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing goal."""
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        return RedirectResponse(url="/goals", status_code=303)

    target_dt = None
    if target_date:
        try:
            target_dt = datetime.fromisoformat(target_date)
        except ValueError:
            target_dt = None

    goal.name = name
    goal.description = description
    goal.target_amount = target_amount
    goal.target_date = target_dt

    db.add(goal)
    await db.commit()

    return RedirectResponse(url="/goals", status_code=303)


@router.post("/goals/{goal_id}/contribute")
async def contribute_to_goal(
    request: Request,
    goal_id: int,
    account_id: int = Form(...),
    amount: float = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Contribute funds from an account to a goal.

    This creates a transaction (expense) on the given account, deducts the
    account balance, increments the goal's current_amount and marks the goal
    as completed if the target is reached.
    """
    # Validate goal ownership
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Validate account ownership
    acc_result = await db.execute(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # simple validation
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # create transaction (expense) to represent the contribution
    contribution = Transaction(
        account_id=account.id,
        amount=amount,
        transaction_type='expense',
        category='goal_contribution',
        description=f'Contribution to goal {goal.name}',
        goal_id=goal.id,
    )
    db.add(contribution)

    # update account balance
    # prevent overdraft: simple check
    if account.balance is not None and account.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient funds in account")
    account.balance -= amount
    db.add(account)

    # update goal amount
    goal.current_amount = (goal.current_amount or 0.0) + amount
    if goal.target_amount and goal.current_amount >= goal.target_amount:
        goal.is_completed = True
    db.add(goal)

    await db.commit()

    # If this was an AJAX/fetch request, return JSON with updated goal info
    accept = request.headers.get('accept', '')
    is_xhr = request.headers.get('x-requested-with', '') == 'XMLHttpRequest'
    if 'application/json' in accept or is_xhr:
        payload = {
            'goal_id': goal.id,
            'current_amount': float(goal.current_amount or 0.0),
            'target_amount': float(goal.target_amount or 0.0),
            'is_completed': bool(goal.is_completed),
        }
        return JSONResponse(content=payload)

    return RedirectResponse(url="/goals", status_code=303)
