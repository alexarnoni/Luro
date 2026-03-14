"""Add audit_logs and user_sessions tables"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260314_add_audit_logs_and_user_sessions"
down_revision = "20250710_add_login_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"])

    # --- user_sessions ---
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_user_sessions_id"), "user_sessions", ["id"])
    op.create_index(op.f("ix_user_sessions_token"), "user_sessions", ["token"])
    op.create_index("ix_user_sessions_user_active", "user_sessions", ["user_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_token"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_id"), table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_table("audit_logs")
