import asyncio

import pytest
from sqlalchemy import text

from tests.helpers import (
    create_product,
    db_scalar,
    get_balance,
    post_movement,
    wait_until_a_query_is_blocked_on_a_lock,
)

pytestmark = pytest.mark.anyio


async def test_50_concurrent_outs_never_make_the_balance_negative(client, engine):
    await create_product(client)
    await post_movement(client, "SKU-1", "IN", 10)

    responses = await asyncio.gather(*(post_movement(client, "SKU-1", "OUT", 1) for _ in range(50)))

    statuses = [r.status_code for r in responses]
    assert statuses.count(201) == 10
    assert statuses.count(422) == 40
    assert await get_balance(client, "SKU-1") == 0
    # Não basta o saldo final ser 0: o saldo acumulado, movimentação a movimentação na ordem
    # do ledger, nunca pode ter ficado abaixo de zero.
    lowest_running_balance = await db_scalar(
        engine,
        """
        SELECT min(running_balance) FROM (
            SELECT sum(delta) OVER (ORDER BY occurred_at, id) AS running_balance
            FROM movements
        ) AS ledger
        """,
    )
    assert lowest_running_balance == 0


async def test_concurrent_outs_with_mixed_quantities_respect_the_balance(client):
    await create_product(client)
    await post_movement(client, "SKU-1", "IN", 10)

    responses = await asyncio.gather(*(post_movement(client, "SKU-1", "OUT", 3) for _ in range(10)))

    # Três saídas de 3 cabem em 10; a quarta deixaria o saldo em -2.
    assert [r.status_code for r in responses].count(201) == 3
    assert await get_balance(client, "SKU-1") == 1


async def test_movement_that_waited_for_the_lock_is_recorded_after_the_one_it_waited_for(
    client, engine
):
    """Uma saída que esperou o lock fica registrada depois da entrada que liberou o saldo.

    Se o horário fosse o do início da transação (now()), a saída ficaria registrada antes da
    entrada da qual dependia, e o saldo "as_of" naquele instante sairia -5.
    """
    await create_product(client)

    async with engine.connect() as conn, conn.begin():
        # O teste segura o lock do produto, como faria outra movimentação em andamento.
        product_id = await conn.scalar(
            text("SELECT id FROM products WHERE sku = 'SKU-1' FOR UPDATE")
        )
        out_request = asyncio.create_task(post_movement(client, "SKU-1", "OUT", 5))
        await wait_until_a_query_is_blocked_on_a_lock(engine)

        # Enquanto a saída espera, entra estoque (gravado direto, na transação que tem o lock).
        await conn.execute(
            text("INSERT INTO idempotency_keys (key, request_hash) VALUES ('entrada', '-')")
        )
        await conn.execute(
            text(
                "INSERT INTO movements"
                " (product_id, idempotency_key, type, quantity, delta, reason, occurred_at)"
                " VALUES (:product_id, 'entrada', 'IN', 5, 5, 'entrada', clock_timestamp())"
            ),
            {"product_id": product_id},
        )
    # Saiu do bloco: commit, o lock é liberado e a saída continua com saldo 5.

    out = await out_request
    assert out.status_code == 201
    assert await get_balance(client, "SKU-1", as_of=out.json()["occurred_at"]) == 0
