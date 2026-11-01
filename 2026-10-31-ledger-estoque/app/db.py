"""Acesso ao banco: classe base dos modelos, engine e sessão por requisição."""

from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Sem uma convenção, o Postgres inventa nomes para constraints (ex.: "products_sku_key") e o
# Alembic não consegue referenciá-las de forma estável em migrações futuras. Com ela, toda
# constraint tem nome previsível, como "uq_products_sku" ou "ck_movements_quantity_positive".
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe mãe de todos os modelos ORM. O Alembic compara `Base.metadata` com o banco."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# O engine guarda o pool de conexões e é criado uma vez por processo.
engine = create_async_engine(settings.database_url)

# expire_on_commit=False: depois do commit os objetos continuam legíveis sem nova ida ao banco.
# Sem isso, ler um atributo para montar a resposta depois do commit dispararia uma query
# implícita, o que no modo assíncrono gera erro.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependência do FastAPI: abre uma sessão por requisição e a fecha no fim.

    A sessão não faz commit sozinha. Quem escreve no banco decide onde começa e termina a
    transação, o que importa para os locks e a idempotência deste desafio.
    """
    async with SessionLocal() as session:
        yield session
