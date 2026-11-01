import pytest

from tests.helpers import create_product, db_scalar, get_balance, post_movement

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "steps",
    [
        # (tipo, quantidade enviada, delta esperado, saldo esperado depois)
        [("IN", 10, 10, 10), ("OUT", 4, -4, 6)],
        # ADJUST é recontagem: quantity é o saldo contado e o delta é a diferença.
        [("IN", 10, 10, 10), ("ADJUST", 12, 2, 12)],
        [("IN", 10, 10, 10), ("ADJUST", 3, -7, 3)],
        [("IN", 10, 10, 10), ("ADJUST", 10, 0, 10)],
    ],
)
async def test_each_movement_type_changes_the_balance(client, steps):
    await create_product(client)

    for type_, quantity, expected_delta, expected_balance in steps:
        response = await post_movement(client, "SKU-1", type_, quantity)

        assert response.status_code == 201
        assert response.json()["delta"] == expected_delta
        assert response.json()["balance_after"] == expected_balance

    assert await get_balance(client, "SKU-1") == steps[-1][3]


async def test_out_greater_than_balance_returns_422(client, engine):
    await create_product(client)
    await post_movement(client, "SKU-1", "IN", 3)

    response = await post_movement(client, "SKU-1", "OUT", 5)

    assert response.status_code == 422
    assert "Saldo insuficiente" in response.json()["detail"]
    assert await db_scalar(engine, "SELECT count(*) FROM movements") == 1
    assert await get_balance(client, "SKU-1") == 3


@pytest.mark.parametrize("type_", ["IN", "OUT", "ADJUST"])
@pytest.mark.parametrize("quantity", [0, -1, -100])
async def test_zero_or_negative_quantity_returns_422(client, engine, type_, quantity):
    await create_product(client)

    response = await post_movement(client, "SKU-1", type_, quantity)

    assert response.status_code == 422
    assert await db_scalar(engine, "SELECT count(*) FROM movements") == 0


@pytest.mark.parametrize("quantity", [1.5, "5", None])
async def test_non_integer_quantity_returns_422(client, quantity):
    await create_product(client)

    response = await post_movement(client, "SKU-1", "IN", quantity)

    assert response.status_code == 422


async def test_invalid_type_returns_422(client):
    await create_product(client)

    response = await post_movement(client, "SKU-1", "TRANSFER", 1)

    assert response.status_code == 422


async def test_missing_idempotency_key_returns_422(client):
    await create_product(client)

    response = await client.post(
        "/movements", json={"sku": "SKU-1", "type": "IN", "quantity": 1, "reason": "x"}
    )

    assert response.status_code == 422


async def test_unknown_product_returns_404(client):
    response = await post_movement(client, "NAO-EXISTE", "IN", 1)

    assert response.status_code == 404


async def test_history_is_paginated_by_cursor_newest_first(client):
    await create_product(client)
    created_ids = []
    for quantity in range(1, 6):
        response = await post_movement(client, "SKU-1", "IN", quantity)
        created_ids.append(response.json()["id"])

    pages = []
    cursor = None
    while True:
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        response = await client.get("/products/SKU-1/movements", params=params)
        assert response.status_code == 200
        page = response.json()
        pages.append([item["id"] for item in page["items"]])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert [len(p) for p in pages] == [2, 2, 1]
    # Todas as movimentações aparecem uma vez só, da mais recente para a mais antiga.
    assert [movement_id for page in pages for movement_id in page] == created_ids[::-1]


async def test_history_only_shows_the_requested_product(client):
    await create_product(client, sku="A")
    await create_product(client, sku="B")
    await post_movement(client, "A", "IN", 1)
    await post_movement(client, "B", "IN", 1)

    response = await client.get("/products/A/movements")

    assert [item["sku"] for item in response.json()["items"]] == ["A"]


@pytest.mark.parametrize("cursor", ["lixo", "bnVsbA==", "WyIyMDI2LTEwLTMxVDAwOjAwOjAwIiwgMV0="])
async def test_invalid_cursor_returns_422(client, cursor):
    # Os dois últimos são base64 válido, mas com conteúdo inválido: "null" e uma data sem fuso.
    await create_product(client)

    response = await client.get("/products/SKU-1/movements", params={"cursor": cursor})

    assert response.status_code == 422
