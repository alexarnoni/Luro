"""add source hash to transactions

Revision ID: 202502151200
Revises: 6b8107a43619
Create Date: 2025-02-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202502151200'
down_revision: Union[str, None] = '6b8107a43619'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('source_hash', sa.String(length=64), nullable=True))
    op.create_index('ix_transactions_source_hash', 'transactions', ['source_hash'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_transactions_source_hash', table_name='transactions')
    op.drop_column('transactions', 'source_hash')
