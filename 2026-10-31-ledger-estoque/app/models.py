"""Modelos ORM (tabelas do banco).

Todo modelo herda de `app.db.Base`. O `migrations/env.py` importa este módulo para que o
Alembic enxergue as tabelas ao gerar migrações com `make revision`.

Não existe coluna de saldo em lugar nenhum: o saldo de um produto é sempre
`SUM(movements.delta)`. A tabela `movements` é só de inserção (um ledger).
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MovementType(enum.StrEnum):
    IN = "IN"
    """Entrada: soma `quantity` ao saldo."""

    OUT = "OUT"
    """Saída: subtrai `quantity` do saldo. Recusada se o saldo não comportar."""

    ADJUST = "ADJUST"
    """Recontagem de inventário: `quantity` é o saldo contado, e o delta é a diferença."""


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKey(Base):
    """Registro de cada `Idempotency-Key` já usada em `POST /movements`.

    A chave primária garante que só uma requisição "ganha" a chave. As demais esperam essa
    terminar e devolvem a resposta guardada aqui (ou 409, se o corpo for diferente).
    """

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    # SHA-256 do corpo da requisição, para detectar a mesma chave com corpo diferente.
    request_hash: Mapped[str] = mapped_column(String(64))
    # Ficam nulos só dentro da transação que está processando a requisição; quando ela
    # faz commit, a resposta já está gravada. Ninguém de fora vê o estado intermediário.
    response_status: Mapped[int | None]
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # O banco confere que o efeito no saldo é coerente com o tipo. ADJUST fica livre
        # porque o delta dele depende do saldo no momento da recontagem.
        CheckConstraint(
            "(type = 'IN' AND delta = quantity)"
            " OR (type = 'OUT' AND delta = -quantity)"
            " OR type = 'ADJUST'",
            name="delta_matches_type",
        ),
        # Atende às três leituras do ledger: saldo por produto até uma data (as_of),
        # histórico paginado por (occurred_at, id) e o relatório de estoque baixo.
        Index("ix_movements_product_id_occurred_at_id", "product_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    # UNIQUE: mesmo que a lógica de idempotência falhasse, o banco não aceitaria duas
    # movimentações com a mesma chave.
    idempotency_key: Mapped[str] = mapped_column(ForeignKey("idempotency_keys.key"), unique=True)
    type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, native_enum=False, length=10, create_constraint=True, name="type")
    )
    # O que o cliente enviou (sempre > 0).
    quantity: Mapped[int] = mapped_column(BigInteger)
    # O efeito no saldo: +quantity (IN), -quantity (OUT) ou contado - saldo anterior (ADJUST).
    delta: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500))
    # Preenchido pelo banco com clock_timestamp() no momento do INSERT (veja services/movements.py).
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
