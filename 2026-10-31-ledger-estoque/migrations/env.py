"""Ponto de entrada do Alembic: diz qual banco migrar e quais modelos comparar.

Este arquivo roda a cada comando `alembic ...` (upgrade, revision etc.).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importar os modelos registra as tabelas em Base.metadata. Sem isso, o
# `alembic revision --autogenerate` acharia que o banco deveria estar vazio.
from app import models  # noqa: F401
from app.config import settings
from app.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL pode vir de quem chamou o Alembic (os testes passam a do banco de teste).
# Caso contrário, usa a mesma DATABASE_URL da aplicação, então não há URL duplicada no alembic.ini.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem conectar ao banco (`alembic upgrade head --sql`)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Conecta ao banco e aplica as migrações dentro de uma transação."""
    # O Alembic é síncrono. O mesmo driver psycopg serve aos dois modos, então a URL é a mesma
    # da API. NullPool porque o comando abre uma conexão, migra e termina.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
