"""Relatório de produtos com estoque baixo, numa única query SQL."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import LowStockItem, LowStockReport

# SQL escrito à mão porque é o centro do requisito: CTE para o saldo e window function para
# a posição de criticidade, tudo resolvido no banco numa ida só.
LOW_STOCK_SQL = text(
    """
    WITH balances AS (
        -- Saldo atual de cada produto. O LEFT JOIN mantém produtos sem nenhuma
        -- movimentação, com saldo 0: são justamente os mais críticos.
        SELECT
            p.sku,
            p.name,
            COALESCE(SUM(m.delta), 0)::bigint AS balance
        FROM products AS p
        LEFT JOIN movements AS m ON m.product_id = p.id
        GROUP BY p.id
    )
    SELECT
        sku,
        name,
        balance,
        :threshold - balance AS shortage,
        -- RANK: produtos com o mesmo saldo ficam na mesma posição.
        RANK() OVER (ORDER BY balance) AS criticality_rank
    FROM balances
    WHERE balance < :threshold
    -- O SKU desempata para a ordem ser estável entre chamadas.
    ORDER BY balance, sku
    """
)


async def low_stock(session: AsyncSession, threshold: int) -> LowStockReport:
    result = await session.execute(LOW_STOCK_SQL, {"threshold": threshold})
    items = [LowStockItem.model_validate(row, from_attributes=True) for row in result]
    return LowStockReport(threshold=threshold, items=items)
