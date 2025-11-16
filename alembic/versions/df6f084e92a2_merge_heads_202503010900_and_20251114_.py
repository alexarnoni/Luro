"""Merge heads 202503010900 and 20251114_add_goal_id_to_transactions

Revision ID: df6f084e92a2
Revises: 202503010900, 20251114_add_goal_id_to_transactions
Create Date: 2025-11-16 16:44:12.575837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df6f084e92a2'
down_revision: Union[str, None] = ('202503010900', '20251114_add_goal_id_to_transactions')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
