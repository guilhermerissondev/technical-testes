"""Fixtures compartilhadas pelos testes.

Os testes rodam contra um Postgres de verdade (banco `ledger_test`), não contra SQLite nem mocks.
Locks, constraints e concorrência são justamente o que o desafio pede para provar, e só o
banco real se comporta como em produção.

Ciclo de vida:
- uma vez por execução: `migrate` recria o schema aplicando as migrações do Alembic;
- a cada teste: `engine` abre um pool novo, `client` faz requisições à app usando esse pool e
  `clean_db` esvazia as tabelas no final.
"""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ledger:ledger@localhost:5432/ledger_test",
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Testes marcados com `pytest.mark.anyio` rodam no asyncio (o mesmo loop do uvicorn)."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def migrate() -> None:
    """Recria o schema e aplica as migrações, então os testes validam também as migrações.

    Apagar o schema inteiro, em vez de fazer `alembic downgrade`, evita quebrar quando uma
    migração é apagada ou reescrita durante o desenvolvimento.
    """
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Engine assíncrono exclusivo do teste.

    É criado por teste porque conexões assíncronas ficam presas ao event loop em que nasceram,
    e cada teste roda no seu próprio loop. O pool comporta até 60 conexões (20 fixas e 40 extras),
    o bastante para os testes que disparam 50 requisições em paralelo.
    """
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=20, max_overflow=40)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db(engine: AsyncEngine) -> AsyncIterator[None]:
    """Depois de cada teste, esvazia todas as tabelas para que nenhum teste dependa de outro."""
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if tables:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP que chama a app direto em memória, sem subir servidor.

    A dependência `get_session` é trocada por uma que usa o banco de teste. Várias chamadas
    disparadas com `asyncio.gather` rodam de fato em paralelo, cada uma com sua conexão.
    """
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
