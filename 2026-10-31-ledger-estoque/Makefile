.PHONY: install db up down logs test lint format migrate revision

install:  ## instala dependências (inclui dev)
	uv sync

db:  ## sobe só o Postgres (para rodar a API e os testes localmente)
	docker compose up -d --wait db

up:  ## sobe API + Postgres em http://localhost:8000
	docker compose up -d --build --wait

down:  ## derruba os containers (mantém o volume do banco)
	docker compose down

logs:
	docker compose logs -f api

test: db  ## roda os testes contra o banco ledger_test
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

migrate: db  ## aplica as migrações no banco local
	uv run alembic upgrade head

revision: db  ## gera migração a partir dos modelos: make revision m="cria products"
	uv run alembic revision --autogenerate -m "$(m)"
