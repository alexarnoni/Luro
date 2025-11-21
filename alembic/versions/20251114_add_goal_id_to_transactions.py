"""add goal_id to transactions

Revision ID: 20251114_add_goal_id_to_transactions
Revises: 6b8107a43619
Create Date: 2025-11-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251114_add_goal_id_to_transactions'
down_revision = '6b8107a43619'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't support adding FK constraints via ALTER; add column only.
    op.add_column('transactions', sa.Column('goal_id', sa.Integer(), nullable=True))


def downgrade():
    # Only drop the column. FK constraint was not created for SQLite migrations.
    op.drop_column('transactions', 'goal_id')
