"""add period to insights for monthly ai cache"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202503010900"
down_revision = "202502151200"
branch_labels = None
depends_on = None

UQ_NAME = "uq_insights_user_period_type"
TABLE = "insights"


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _has_unique_constraint(name: str, table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for cons in insp.get_unique_constraints(table):
        if cons.get("name") == name:
            return True
    return False


def upgrade() -> None:
    # 1) Adicionar coluna 'period' se ainda não existir
    if not _has_column(TABLE, "period"):
        op.add_column(TABLE, sa.Column("period", sa.String(), nullable=True))

    # (Opcional) Se quiser garantir não-nulo futuramente, antes precisa popular valores existentes.
    # Ex.: op.execute("UPDATE insights SET period = '1970-01' WHERE period IS NULL")

    # 2) Criar UNIQUE(user_id, period, insight_type) com batch (necessário no SQLite)
    if not _has_unique_constraint(UQ_NAME, TABLE):
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.create_unique_constraint(
                UQ_NAME, ["user_id", "period", "insight_type"]
            )


def downgrade() -> None:
    # Remover UNIQUE com batch
    if _has_unique_constraint(UQ_NAME, TABLE):
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_constraint(UQ_NAME, type_="unique")

    # Remover coluna se existir
    if _has_column(TABLE, "period"):
        op.drop_column(TABLE, "period")
