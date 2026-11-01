"""Cadastro e consulta de produtos."""

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ProductNotFound, SkuAlreadyExists
from app.models import Product
from app.schemas import ProductCreate


async def create_product(session: AsyncSession, payload: ProductCreate) -> Product:
    # Não basta checar "já existe?" antes de inserir: duas requisições simultâneas passariam
    # pela checagem. Quem garante o SKU único é a constraint do banco; aqui só traduzimos
    # a violação para 409.
    try:
        async with session.begin():
            return await session.scalar(
                insert(Product).values(sku=payload.sku, name=payload.name).returning(Product)
            )
    except IntegrityError as error:
        raise SkuAlreadyExists(payload.sku) from error


async def get_product(session: AsyncSession, sku: str, *, for_update: bool = False) -> Product:
    """Busca o produto pelo SKU ou levanta 404.

    Com `for_update=True` a linha do produto fica travada até o fim da transação
    (SELECT ... FOR UPDATE). É o que serializa as movimentações de um mesmo produto.
    """
    query = select(Product).where(Product.sku == sku)
    if for_update:
        query = query.with_for_update()

    product = await session.scalar(query)
    if product is None:
        raise ProductNotFound(sku)
    return product
