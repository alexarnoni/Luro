"""add period to insights for monthly ai cache"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202503010900"
down_revision: Union[str, None] = "202502151200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("insights", sa.Column("period", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_insights_user_period_type",
        "insights",
        ["user_id", "period", "insight_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_insights_user_period_type", "insights", type_="unique")
    op.drop_column("insights", "period")
