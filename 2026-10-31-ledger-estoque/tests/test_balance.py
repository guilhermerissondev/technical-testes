import random
from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers import create_product, db_scalar, get_balance, post_movement

pytestmark = pytest.mark.anyio

ONE_MICROSECOND = timedelta(microseconds=1)


def parse(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


async def test_product_without_movements_has_zero_balance(client):
    await create_product(client)

    assert await get_balance(client, "SKU-1") == 0


async def test_as_of_before_the_first_movement_returns_zero(client):
    await create_product(client)
    first = await post_movement(client, "SKU-1", "IN", 5)
    first_instant = parse(first.json()["occurred_at"])

    balance = await get_balance(
        client, "SKU-1", as_of=(first_instant - ONE_MICROSECOND).isoformat()
    )

    assert balance == 0


async def test_as_of_at_the_exact_instant_includes_the_movement(client):
    await create_product(client)
    first = await post_movement(client, "SKU-1", "IN", 5)
    second = await post_movement(client, "SKU-1", "IN", 3)

    at_first = await get_balance(client, "SKU-1", as_of=first.json()["occurred_at"])
    at_second = await get_balance(client, "SKU-1", as_of=second.json()["occurred_at"])
    between = await get_balance(
        client, "SKU-1", as_of=(parse(second.json()["occurred_at"]) - ONE_MICROSECOND).isoformat()
    )

    assert (at_first, between, at_second) == (5, 5, 8)


async def test_as_of_accepts_other_time_zones(client):
    await create_product(client)
    movement = await post_movement(client, "SKU-1", "IN", 5)
    instant = parse(movement.json()["occurred_at"])

    # O mesmo instante escrito em horário de Brasília (UTC-3).
    in_brasilia = instant.astimezone(timezone(timedelta(hours=-3))).isoformat()
    assert in_brasilia.endswith("-03:00")

    assert await get_balance(client, "SKU-1", as_of=in_brasilia) == 5


async def test_as_of_without_time_zone_returns_422(client):
    await create_product(client)

    response = await client.get("/products/SKU-1/balance", params={"as_of": "2026-10-01T00:00:00"})

    assert response.status_code == 422


async def test_api_balance_matches_the_sum_of_movements_in_the_database(client, engine):
    await create_product(client)
    rng = random.Random(42)
    expected = 0

    for _ in range(60):
        type_ = rng.choice(["IN", "OUT", "ADJUST"])
        quantity = rng.randint(1, 20)
        response = await post_movement(client, "SKU-1", type_, quantity)

        # Modelo de referência em Python, independente da implementação.
        if type_ == "IN":
            expected += quantity
        elif type_ == "ADJUST":
            expected = quantity
        elif quantity <= expected:
            expected -= quantity
        else:
            assert response.status_code == 422
            continue
        assert response.status_code == 201

    sum_in_database = await db_scalar(
        engine,
        "SELECT sum(delta) FROM movements"
        " WHERE product_id = (SELECT id FROM products WHERE sku = :sku)",
        sku="SKU-1",
    )
    assert await get_balance(client, "SKU-1") == sum_in_database == expected
