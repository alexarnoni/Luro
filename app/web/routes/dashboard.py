import logging
from datetime import datetime, date
from calendar import monthrange

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete, func

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
from app.domain.cards.models import CardCharge, CardStatement

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


def add_months(dt: datetime, months: int) -> datetime:
    """Return datetime advanced by N months (keeps day when possible)."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def compute_close_date(purchase_dt: datetime, statement_day: int) -> date:
    """Compute close date for a purchase; purchase on closing day goes to next cycle."""
    if statement_day is None:
        raise HTTPException(status_code=400, detail="Defina o dia de fechamento do cartão antes de lançar compras")
    # purchase exactly on closing day vai para próxima fatura
    if purchase_dt.day >= statement_day:
        target = add_months(purchase_dt.replace(day=statement_day), 1)
    else:
        target = purchase_dt.replace(day=statement_day)
    return target.date()


def compute_due_date(close_dt: date, due_day: int | None) -> date:
    """Compute due date ensuring it is after close date."""
    if due_day is None:
        raise HTTPException(status_code=400, detail="Defina o dia de vencimento do cartão antes de lançar compras")
    y, m = close_dt.year, close_dt.month
    last_day = monthrange(y, m)[1]
    day = min(due_day, last_day)
    candidate = date(y, m, day)
    if candidate <= close_dt:
        nxt = add_months(datetime.combine(close_dt, datetime.min.time()), 1)
        y2, m2 = nxt.year, nxt.month
        last2 = monthrange(y2, m2)[1]
        candidate = date(y2, m2, min(due_day, last2))
    return candidate


async def get_user_account(db: AsyncSession, user_id: int, account_id: int) -> Account:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


async def get_or_create_statement(
    db: AsyncSession, account: Account, close_dt: date
) -> CardStatement:
    """Get or create statement for the given close date."""
    result = await db.execute(
        select(CardStatement).where(
            CardStatement.account_id == account.id,
            CardStatement.close_date == close_dt,
        )
    )
    statement = result.scalar_one_or_none()
    if statement:
        return statement

    due_dt = compute_due_date(close_dt, account.due_day)
    stmt = CardStatement(
        account_id=account.id,
        year=close_dt.year,
        month=close_dt.month,
        close_date=close_dt,
        due_date=due_dt,
        status="open",
        amount_due=0.0,
        amount_paid=0.0,
    )
    db.add(stmt)
    await db.flush()
    return stmt


async def _sum_statement_charges(db: AsyncSession, statement_id: int) -> float:
    res = await db.execute(
        select(func.coalesce(func.sum(CardCharge.amount), 0)).where(
            CardCharge.statement_id == statement_id
        )
    )
    total = res.scalar()
    return float(total or 0.0)


async def close_card_statements(db: AsyncSession, account: Account, today: date) -> None:
    """Close any open statements whose close_date has passed and roll balance forward."""
    result = await db.execute(
        select(CardStatement)
        .where(CardStatement.account_id == account.id)
        .order_by(CardStatement.close_date)
    )
    statements = result.scalars().all()

    for stmt in statements:
        if stmt.status == "paid":
            continue
        if stmt.close_date > today:
            continue

        # recompute totals
        stmt.amount_due = await _sum_statement_charges(db, stmt.id)
        # status
        outstanding = stmt.amount_due - (stmt.amount_paid or 0.0)
        if outstanding <= 0:
            stmt.status = "paid"
        else:
            stmt.status = "overdue" if today > stmt.due_date else "closed"

        # roll forward if needed and not yet applied
        if outstanding > 0 and not stmt.carry_applied:
            next_close_dt = add_months(
                datetime.combine(stmt.close_date, datetime.min.time()), 1
            ).date()
            next_statement = await get_or_create_statement(db, account, next_close_dt)
            adj = CardCharge(
                account_id=account.id,
                statement_id=next_statement.id,
                purchase_date=datetime.combine(today, datetime.min.time()),
                amount=outstanding,
                description=f"Saldo anterior {stmt.close_date.strftime('%m/%Y')}",
                installment_number=1,
                installment_total=1,
                is_adjustment=True,
            )
            db.add(adj)
            stmt.carry_applied = True
            stmt.amount_paid = stmt.amount_due  # mark as settled via carry-over
            stmt.status = "paid"

        db.add(stmt)
    await db.flush()


async def apply_card_payment(
    db: AsyncSession, account: Account, amount: float, payment_date: datetime
) -> CardStatement | None:
    """Apply a payment to the oldest open statements; returns the latest touched statement."""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    await close_card_statements(db, account, payment_date.date())

    res = await db.execute(
        select(CardStatement)
        .where(CardStatement.account_id == account.id)
        .order_by(CardStatement.close_date)
    )
    statements = res.scalars().all()
    remaining = amount
    last_touched = None
    for stmt in statements:
        outstanding = stmt.amount_due - (stmt.amount_paid or 0.0)
        if outstanding <= 0:
            continue
        applied = min(remaining, outstanding)
        stmt.amount_paid = (stmt.amount_paid or 0.0) + applied
        remaining -= applied
        last_touched = stmt

        # recalc status
        outstanding_after = stmt.amount_due - stmt.amount_paid
        if outstanding_after <= 0:
            stmt.status = "paid"
        else:
            stmt.status = "overdue" if payment_date.date() > stmt.due_date else "closed"

        db.add(stmt)
        if remaining <= 0:
            break

    if remaining > 0 and statements:
        # nothing to pay, allow creating a negative adjustment in current cycle
        current_stmt = statements[-1]
        current_stmt.amount_paid = (current_stmt.amount_paid or 0.0) + remaining
        current_stmt.status = "paid" if current_stmt.amount_paid >= current_stmt.amount_due else current_stmt.status
        db.add(current_stmt)
        last_touched = current_stmt

    await db.flush()
    return last_touched


async def create_card_purchase(
    db: AsyncSession,
    account: Account,
    purchase_dt: datetime,
    total_amount: float,
    installments_total: int,
    description: str | None,
    category_id: int | None,
) -> None:
    if installments_total < 1:
        raise HTTPException(status_code=400, detail="Total de parcelas inválido")
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser positivo")
    per_installment = total_amount / installments_total

    for i in range(installments_total):
        parcel_dt = add_months(purchase_dt, i)
        close_dt = compute_close_date(parcel_dt, account.statement_day)
        statement = await get_or_create_statement(db, account, close_dt)
        charge = CardCharge(
            account_id=account.id,
            statement_id=statement.id,
            purchase_date=parcel_dt,
            amount=per_installment,
            description=description or "Compra cartão",
            category_id=category_id,
            installment_number=i + 1,
            installment_total=installments_total,
        )
        db.add(charge)
    await db.flush()


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
    credit_limit: str | float | None = Form(None),
    statement_day: str | None = Form(None),
    due_day: str | None = Form(None),
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

    credit_limit_val = None
    if credit_limit not in (None, ""):
        try:
            credit_limit_val, _ = parse_money(credit_limit)
        except HTTPException as exc:
            raise HTTPException(status_code=400, detail=str(exc.detail))

    def _parse_day(val):
        if val in (None, "", "null"):
            return None
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if s == "":
            return None
        if "-" in s:
            try:
                return datetime.fromisoformat(s).day
            except ValueError:
                pass
        try:
            return int(s)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid day value")

    statement_day_val = _parse_day(statement_day)
    due_day_val = _parse_day(due_day)

    account = Account(
        user_id=user.id,
        name=name.strip(),
        account_type=account_type.strip(),
        balance=bal_val,
        credit_limit=credit_limit_val if account_type.strip() == "credit" else None,
        statement_day=statement_day_val if account_type.strip() == "credit" else None,
        due_day=due_day_val if account_type.strip() == "credit" else None,
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
    accounts_result = await db.execute(select(Account).where(Account.user_id == user.id))
    accounts = accounts_result.scalars().all()
    bank_accounts = [acc for acc in accounts if acc.account_type != "credit"]
    card_accounts = [acc for acc in accounts if acc.account_type == "credit"]

    today = date.today()
    for card in card_accounts:
        if card.statement_day and card.due_day:
            await close_card_statements(db, card, today)

    transactions_result = await db.execute(
        select(Transaction)
        .join(Account)
        .where(Account.user_id == user.id, Account.account_type != "credit")
        .order_by(desc(Transaction.transaction_date))
    )
    transactions = transactions_result.scalars().all()

    charges_result = await db.execute(
        select(CardCharge)
        .join(Account)
        .where(Account.user_id == user.id, Account.account_type == "credit")
        .order_by(desc(CardCharge.purchase_date))
    )
    card_charges = charges_result.scalars().all()

    statements_result = await db.execute(
        select(CardStatement)
        .join(Account)
        .where(Account.user_id == user.id, Account.account_type == "credit")
        .order_by(desc(CardStatement.close_date))
    )
    card_statements = statements_result.scalars().all()

    return templates.TemplateResponse(
        "transactions/list.html",
        {
            "request": request,
            "user": user,
            "accounts": bank_accounts,
            "card_accounts": card_accounts,
            "transactions": transactions,
            "card_charges": card_charges,
            "card_statements": card_statements,
        },
    )


@router.post("/transactions")
async def create_transaction(
    request: Request,
    payment_method: str = Form("account"),
    account_id: int = Form(...),
    amount: str | float = Form(...),
    installments_total: int = Form(1),
    transaction_type: str = Form(...),
    category: str = Form(None),
    category_id: int | None = Form(None),
    description: str = Form(None),
    transaction_date: str = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new transaction."""
    payment_mode = (payment_method or "account").strip().lower()

    # Parse date
    trans_date = datetime.utcnow()
    if transaction_date:
        try:
            trans_date = datetime.fromisoformat(transaction_date)
        except ValueError:
            pass

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

    if payment_mode == "card":
        account = await get_user_account(db, user.id, account_id)
        if account.account_type != "credit":
            raise HTTPException(status_code=400, detail="Selecione um cartão de crédito válido")
        if account.statement_day is None or account.due_day is None:
            raise HTTPException(status_code=400, detail="Configure fechamento e vencimento do cartão antes de lançar compras")

        category_pk = None
        if category_id is not None:
            result = await db.execute(
                select(Category).where(Category.id == category_id, Category.user_id == user.id)
            )
            category_obj = result.scalar_one_or_none()
            if not category_obj:
                raise HTTPException(status_code=404, detail="Category not found")
            category_pk = category_obj.id

        await create_card_purchase(
            db=db,
            account=account,
            purchase_dt=trans_date,
            total_amount=abs(amt),
            installments_total=installments_total,
            description=description,
            category_id=category_pk,
        )
        await close_card_statements(db, account, date.today())
        await db.commit()
        return RedirectResponse(url="/transactions", status_code=303)

    # Debit/credit (conta) flow
    account = await get_user_account(db, user.id, account_id)
    if account.account_type == "credit":
        raise HTTPException(status_code=400, detail="Use o modo cartão para lançar compras de crédito")

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

    # Update account balance (allow negative balances for record-keeping)
    try:
        if tx_type == "income":
            account.balance = (account.balance or 0.0) + abs(amt)
        else:  # expense
            account.balance = (account.balance or 0.0) - abs(amt)
        db.add(account)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create transaction")

    return RedirectResponse(url="/transactions", status_code=303)


@router.post("/cards/{card_id}/statements/{statement_id}/pay")
async def pay_card_statement(
    request: Request,
    card_id: int,
    statement_id: int,
    amount: str | float = Form(...),
    payment_date: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a payment for a credit card statement (does not touch bank accounts)."""
    account = await get_user_account(db, user.id, card_id)
    if account.account_type != "credit":
        raise HTTPException(status_code=400, detail="Conta selecionada não é um cartão")

    stmt_res = await db.execute(
        select(CardStatement).where(
            CardStatement.id == statement_id, CardStatement.account_id == account.id
        )
    )
    statement = stmt_res.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")

    pay_dt = datetime.utcnow()
    if payment_date:
        try:
            pay_dt = datetime.fromisoformat(payment_date)
        except ValueError:
            pass

    try:
        pay_amount = float(amount) if isinstance(amount, (int, float)) else parse_money(amount)[0]
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail=str(exc.detail))

    touched = await apply_card_payment(db, account, pay_amount, pay_dt)
    await db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse(
            {
                "statement_id": statement.id,
                "amount_paid": float(touched.amount_paid if touched else 0.0),
            }
        )
    return RedirectResponse(url="/transactions", status_code=303)


@router.post("/cards/{card_id}/statements/{statement_id}/adjust")
async def adjust_card_statement(
    request: Request,
    card_id: int,
    statement_id: int,
    amount: str | float = Form(...),
    description: str | None = Form("Ajuste"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add an adjustment (e.g., estorno) to an open card statement."""
    account = await get_user_account(db, user.id, card_id)
    if account.account_type != "credit":
        raise HTTPException(status_code=400, detail="Conta selecionada não é um cartão")

    stmt_res = await db.execute(
        select(CardStatement).where(
            CardStatement.id == statement_id, CardStatement.account_id == account.id
        )
    )
    statement = stmt_res.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    if statement.status == "paid":
        raise HTTPException(status_code=400, detail="Fatura já está quitada")

    try:
        adj_amount = float(amount) if isinstance(amount, (int, float)) else parse_money(amount)[0]
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail=str(exc.detail))

    adj_charge = CardCharge(
        account_id=account.id,
        statement_id=statement.id,
        purchase_date=datetime.utcnow(),
        amount=adj_amount,
        description=description or "Ajuste",
        installment_number=1,
        installment_total=1,
        is_adjustment=True,
    )
    db.add(adj_charge)

    # refresh statement totals
    statement.amount_due = await _sum_statement_charges(db, statement.id)
    statement.status = "paid" if statement.amount_paid >= statement.amount_due else statement.status
    db.add(statement)
    await db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse(
            {
                "statement_id": statement.id,
                "amount_due": float(statement.amount_due),
                "amount_paid": float(statement.amount_paid),
            }
        )
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
    credit_limit: str | float | None = Form(None),
    statement_day: str | None = Form(None),
    due_day: str | None = Form(None),
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

    credit_limit_val = None
    if credit_limit not in (None, ""):
        try:
            credit_limit_val, _ = parse_money(credit_limit)
        except HTTPException as exc:
            raise HTTPException(status_code=400, detail=str(exc.detail))

    def _parse_day(val):
        if val in (None, "", "null"):
            return None
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if s == "":
            return None
        if "-" in s:
            try:
                return datetime.fromisoformat(s).day
            except ValueError:
                pass
        try:
            return int(s)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid day value")

    statement_day_val = _parse_day(statement_day)
    due_day_val = _parse_day(due_day)

    account.name = name.strip()
    account.balance = bal_val
    if account.account_type == "credit":
        account.credit_limit = credit_limit_val
        account.statement_day = statement_day_val
        account.due_day = due_day_val
    else:
        account.credit_limit = None
        account.statement_day = None
        account.due_day = None
    db.add(account)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update account")

    accept = request.headers.get('accept', '')
    is_xhr = request.headers.get('x-requested-with', '') == 'XMLHttpRequest'
    if 'application/json' in accept or is_xhr:
        return JSONResponse(
            {
                'id': account.id,
                'name': account.name,
                'balance': float(account.balance),
                'account_type': account.account_type,
                'credit_limit': float(account.credit_limit) if account.credit_limit is not None else None,
                'statement_day': account.statement_day,
                'due_day': account.due_day,
            }
        )

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
