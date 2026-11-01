# Ledger de Estoque Idempotente

Enunciado completo em [`ENUNCIADO.md`](ENUNCIADO.md).

## Stack

FastAPI, Pydantic v2, SQLAlchemy 2 (async, driver `psycopg` 3), Alembic, PostgreSQL 17, pytest + httpx, uv, ruff.

## Estrutura

```
app/
  main.py        # app FastAPI e rotas
  config.py      # settings (DATABASE_URL)
  db.py          # Base declarativa, engine async, dependência get_session
  models.py      # modelos ORM (o Alembic lê daqui)
migrations/      # Alembic; revisões em migrations/versions/
tests/
  conftest.py    # recria o schema via Alembic, zera tabelas entre testes, fixture `client`
docker/          # entrypoint (roda as migrações) e script que cria o banco ledger_test
```

## Como rodar

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Docker.

```bash
make install   # dependências
make up        # API + Postgres em http://localhost:8000 (docs em /docs)
make down
```

Para rodar a API fora do Docker: `make migrate && uv run uvicorn app.main:app --reload`.

## Como testar

```bash
make test      # sobe o Postgres se precisar e roda o pytest contra o banco ledger_test
make lint
```

Os testes são assíncronos (`pytest.mark.anyio`) e usam a fixture `client` (`httpx.AsyncClient` sobre a app). Requisições concorrentes saem com `asyncio.gather` e vão ao Postgres real; o pool dos testes aceita até 60 conexões.

## Migrações

```bash
make revision m="cria products"   # gera a partir dos modelos em app/models.py
make migrate                       # aplica no banco local
```

## Decisões

<!-- lock otimista x pessimista, escopo da Idempotency-Key, saldo por soma x tabela materializada -->

## O que ficou de fora

## Tempo gasto
