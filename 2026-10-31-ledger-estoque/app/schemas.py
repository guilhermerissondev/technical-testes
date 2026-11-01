"""Formatos de entrada e saída da API (Pydantic v2).

As validações de formato ficam aqui e rodam antes de qualquer acesso ao banco. Por exemplo,
quantidade zero ou negativa é recusada com 422 sem nem consumir a Idempotency-Key.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models import MovementType

Sku = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        examples=["CAF-500G"],
    ),
]


class RequestModel(BaseModel):
    # forbid: campo desconhecido é erro. Sem isso, dois corpos diferentes ({"x": 1} a mais)
    # gerariam o mesmo hash de idempotência e um deles seria ignorado em silêncio.
    model_config = ConfigDict(extra="forbid")


class ProductCreate(RequestModel):
    sku: Sku
    name: str = Field(min_length=1, max_length=200)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str
    created_at: datetime


class MovementCreate(RequestModel):
    sku: Sku
    type: MovementType
    # strict: recusa 1.5 e "5" em vez de converter. O teto evita estourar o BIGINT na soma.
    quantity: int = Field(gt=0, le=1_000_000_000, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class MovementOut(BaseModel):
    id: int
    sku: str
    type: MovementType
    quantity: int
    delta: int
    reason: str
    occurred_at: datetime


class MovementCreated(MovementOut):
    balance_after: int


class MovementPage(BaseModel):
    items: list[MovementOut]
    # Passe este valor em ?cursor= para buscar a próxima página. Nulo quando acabou.
    next_cursor: str | None


class BalanceOut(BaseModel):
    sku: str
    balance: int
    # Ecoa o as_of pedido; nulo significa saldo atual.
    as_of: datetime | None


class LowStockItem(BaseModel):
    sku: str
    name: str
    balance: int
    # Quanto falta para chegar ao limite (threshold - balance).
    shortage: int
    # 1 = mais crítico. Produtos com o mesmo saldo dividem a posição.
    criticality_rank: int


class LowStockReport(BaseModel):
    threshold: int
    items: list[LowStockItem]
