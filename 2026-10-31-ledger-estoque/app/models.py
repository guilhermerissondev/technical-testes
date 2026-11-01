"""Modelos ORM (tabelas do banco).

Todo modelo herda de `app.db.Base`. O `migrations/env.py` importa este módulo para que o
Alembic enxergue as tabelas ao gerar migrações com `make revision`.
"""

from app.db import Base  # noqa: F401
