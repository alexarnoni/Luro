import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

# 1) Carregar variáveis do .env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv é opcional; se não existir, seguimos com as envs do sistema
    pass

# 2) Alembic config (lê alembic.ini)
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3) Importar Base e modelos (ajuste os paths se necessário)
from app.core.database import Base
from app.domain.users.models import User  # noqa: F401
from app.domain.accounts.models import Account  # noqa: F401
from app.domain.transactions.models import Transaction  # noqa: F401
from app.domain.categories.models import Category  # noqa: F401
from app.domain.rules.models import Rule  # noqa: F401
from app.domain.goals.models import Goal  # noqa: F401
from app.domain.insights.models import Insight  # noqa: F401

target_metadata = Base.metadata

# ------------------------------------------
# Helpers
# ------------------------------------------

def _sync_url_from_env() -> str:
    """
    Converte a DATABASE_URL assíncrona para uma URL síncrona
    apenas para as migrações do Alembic.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL não está definido nas envs dentro do container.")
    url = make_url(db_url)

    # Trocar drivers async por sync equivalentes
    if url.drivername == "sqlite+aiosqlite":
        url = url.set(drivername="sqlite+pysqlite")
    elif url.drivername == "postgresql+asyncpg":
        url = url.set(drivername="postgresql+psycopg2")
    # acrescente outros mapeamentos se usar MySQL async, etc.

    return url.render_as_string(hide_password=False)


def _configure_sqlalchemy_url():
    """
    Injeta a URL convertida (síncrona) no config do Alembic.
    """
    config.set_main_option("sqlalchemy.url", _sync_url_from_env())


# ------------------------------------------
# Configuração Alembic (offline/online)
# ------------------------------------------

def run_migrations_offline() -> None:
    """Executa migrações no modo 'offline'."""
    _configure_sqlalchemy_url()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,   # detectar mudanças de tipo
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações no modo 'online'."""
    _configure_sqlalchemy_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
