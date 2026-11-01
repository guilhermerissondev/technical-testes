import asyncio

import pytest

from tests.helpers import create_product, db_scalar, get_balance, movement_body, post_movement

pytestmark = pytest.mark.anyio


async def test_same_key_and_body_returns_original_response_without_recording_again(client, engine):
    await create_product(client)

    first = await post_movement(client, "SKU-1", "IN", 5, key="chave-1")
    second = await post_movement(client, "SKU-1", "IN", 5, key="chave-1")

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert first.headers["Idempotent-Replayed"] == "false"
    assert second.headers["Idempotent-Replayed"] == "true"
    assert await db_scalar(engine, "SELECT count(*) FROM movements") == 1
    assert await get_balance(client, "SKU-1") == 5


@pytest.mark.parametrize(
    "changed",
    [{"quantity": 6}, {"type": "OUT"}, {"reason": "outro motivo"}, {"sku": "SKU-2"}],
)
async def test_same_key_with_different_body_returns_409(client, engine, changed):
    await create_product(client, sku="SKU-1")
    await create_product(client, sku="SKU-2")
    body = movement_body("SKU-1", "IN", 5)
    await client.post("/movements", json=body, headers={"Idempotency-Key": "chave-1"})

    response = await client.post(
        "/movements", json=body | changed, headers={"Idempotency-Key": "chave-1"}
    )

    assert response.status_code == 409
    assert await db_scalar(engine, "SELECT count(*) FROM movements") == 1


async def test_same_key_20_times_in_parallel_records_a_single_movement(client, engine):
    await create_product(client)

    responses = await asyncio.gather(
        *(post_movement(client, "SKU-1", "IN", 7, key="chave-paralela") for _ in range(20))
    )

    assert {r.status_code for r in responses} == {201}
    # Todas devolvem a mesma movimentação; só uma delas é a execução original.
    assert len({r.json()["id"] for r in responses}) == 1
    assert [r.headers["Idempotent-Replayed"] for r in responses].count("false") == 1
    assert await db_scalar(engine, "SELECT count(*) FROM movements") == 1
    assert await get_balance(client, "SKU-1") == 7


async def test_insufficient_stock_response_is_replayed(client):
    await create_product(client)
    first = await post_movement(client, "SKU-1", "OUT", 5, key="chave-1")
    await post_movement(client, "SKU-1", "IN", 10)

    # Mesmo com saldo suficiente agora, a mesma chave devolve a resposta original.
    second = await post_movement(client, "SKU-1", "OUT", 5, key="chave-1")

    assert first.status_code == second.status_code == 422
    assert first.json() == second.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert await get_balance(client, "SKU-1") == 10


async def test_key_is_not_consumed_when_product_does_not_exist(client):
    not_found = await post_movement(client, "SKU-1", "IN", 5, key="chave-1")
    await create_product(client)

    retry = await post_movement(client, "SKU-1", "IN", 5, key="chave-1")

    assert not_found.status_code == 404
    assert retry.status_code == 201
    assert retry.headers["Idempotent-Replayed"] == "false"
