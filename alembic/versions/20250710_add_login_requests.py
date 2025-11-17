"""Add login_requests table for magic link rate limiting"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250710_add_login_requests"
down_revision = "df6f084e92a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_login_requests_email_recent",
        "login_requests",
        ["email", "requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_login_requests_ip_recent",
        "login_requests",
        ["ip", "requested_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_login_requests_ip_recent", table_name="login_requests")
    op.drop_index("ix_login_requests_email_recent", table_name="login_requests")
    op.drop_table("login_requests")
