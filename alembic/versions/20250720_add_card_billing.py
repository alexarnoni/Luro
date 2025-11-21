"""Add credit card statements and charges tables"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250720_add_card_billing"
down_revision = "20250710_add_login_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("credit_limit", sa.Float(), nullable=True))
    op.add_column("accounts", sa.Column("statement_day", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("due_day", sa.Integer(), nullable=True))

    op.create_table(
        "card_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("close_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("amount_due", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carry_applied", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "year", "month", name="uq_card_statements_account_month")
    )
    op.create_index("ix_card_statements_account_close", "card_statements", ["account_id", "close_date"], unique=False)

    op.create_table(
        "card_charges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("purchase_date", sa.DateTime(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("installment_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("installment_total", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("merchant", sa.String(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("is_adjustment", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["statement_id"], ["card_statements.id"], ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_card_charges_account_date", "card_charges", ["account_id", "purchase_date"], unique=False)
    op.create_index("ix_card_charges_source_hash", "card_charges", ["source_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_card_charges_account_date", table_name="card_charges")
    op.drop_index("ix_card_charges_source_hash", table_name="card_charges")
    op.drop_table("card_charges")
    op.drop_index("ix_card_statements_account_close", table_name="card_statements")
    op.drop_table("card_statements")
    op.drop_column("accounts", "due_day")
    op.drop_column("accounts", "statement_day")
    op.drop_column("accounts", "credit_limit")
