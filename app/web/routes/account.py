import hashlib
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_session_cookie
from app.core.database import get_db
from app.core.session import get_current_user
from app.domain.accounts.models import Account
from app.domain.cards.models import CardCharge, CardStatement
from app.domain.categories.models import Category
from app.domain.goals.models import Goal
from app.domain.insights.models import Insight
from app.domain.rules.models import Rule
from app.domain.transactions.models import Transaction
from app.domain.users.models import User

router = APIRouter()
security_logger = logging.getLogger("app.security")


@router.post("/account/delete")
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete the authenticated user's data and account."""
    account_ids = (
        await db.scalars(select(Account.id).where(Account.user_id == user.id))
    ).all()

    if account_ids:
        await db.execute(delete(CardCharge).where(CardCharge.account_id.in_(account_ids)))
        await db.execute(delete(CardStatement).where(CardStatement.account_id.in_(account_ids)))
        await db.execute(delete(Transaction).where(Transaction.account_id.in_(account_ids)))

    await db.execute(delete(Goal).where(Goal.user_id == user.id))
    await db.execute(delete(Rule).where(Rule.user_id == user.id))
    await db.execute(delete(Category).where(Category.user_id == user.id))
    await db.execute(delete(Insight).where(Insight.user_id == user.id))
    await db.execute(delete(Account).where(Account.user_id == user.id))
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()

    response = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(response)

    hashed_email = hashlib.sha256(user.email.encode()).hexdigest()[:12]
    security_logger.info("Account deleted [user_id=%s, email_hash=%s]", user.id, hashed_email)

    return response
