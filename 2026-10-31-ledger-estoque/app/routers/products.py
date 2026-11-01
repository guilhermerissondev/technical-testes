"""Rotas de produto: cadastro, consulta, saldo e histórico de movimentações."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.dependencies import Session
from app.schemas import BalanceOut, MovementPage, ProductCreate, ProductOut
from app.services import movements, products

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", status_code=201, responses={409: {"description": "SKU já cadastrado"}})
async def create_product(payload: ProductCreate, session: Session) -> ProductOut:
    return await products.create_product(session, payload)


@router.get("/{sku}", responses={404: {"description": "Produto não encontrado"}})
async def get_product(sku: str, session: Session) -> ProductOut:
    return await products.get_product(session, sku)


@router.get("/{sku}/balance", responses={404: {"description": "Produto não encontrado"}})
async def get_balance(
    sku: str,
    session: Session,
    # AwareDatetime exige fuso horário (ex.: ...Z ou ...-03:00). Uma data sem fuso seria
    # ambígua, então é recusada com 422 em vez de adivinhar.
    as_of: Annotated[AwareDatetime | None, Query(description="Saldo neste instante")] = None,
) -> BalanceOut:
    product = await products.get_product(session, sku)
    balance = await movements.get_balance(session, product.id, as_of)
    return BalanceOut(sku=product.sku, balance=balance, as_of=as_of)


@router.get("/{sku}/movements", responses={404: {"description": "Produto não encontrado"}})
async def list_movements(
    sku: str,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[
        str | None, Query(description="Valor de next_cursor da página anterior")
    ] = None,
) -> MovementPage:
    product = await products.get_product(session, sku)
    return await movements.list_movements(session, product, limit, cursor)
