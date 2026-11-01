import pytest

from tests.helpers import create_product, post_movement

pytestmark = pytest.mark.anyio


async def stock(client, sku: str, balance: int) -> None:
    await create_product(client, sku=sku)
    if balance:
        await post_movement(client, sku, "IN", balance)


async def test_low_stock_lists_products_below_threshold_most_critical_first(client):
    await stock(client, "SEM-MOVIMENTO", 0)
    await stock(client, "TRES", 3)
    await stock(client, "NOVE", 9)
    await stock(client, "DEZ", 10)
    await stock(client, "QUINZE", 15)

    response = await client.get("/reports/low-stock", params={"threshold": 10})

    assert response.status_code == 200
    report = response.json()
    assert report["threshold"] == 10
    # "Abaixo do limite" é estritamente menor: o produto com saldo 10 fica de fora.
    assert [
        (i["sku"], i["balance"], i["shortage"], i["criticality_rank"]) for i in report["items"]
    ] == [
        ("SEM-MOVIMENTO", 0, 10, 1),
        ("TRES", 3, 7, 2),
        ("NOVE", 9, 1, 3),
    ]


async def test_low_stock_uses_the_balance_after_outs_and_adjusts(client):
    await stock(client, "A", 20)
    await post_movement(client, "A", "OUT", 15)
    await stock(client, "B", 20)
    await post_movement(client, "B", "ADJUST", 2)

    response = await client.get("/reports/low-stock", params={"threshold": 10})

    assert [(i["sku"], i["balance"]) for i in response.json()["items"]] == [("B", 2), ("A", 5)]


async def test_products_with_the_same_balance_share_the_rank(client):
    await stock(client, "B", 2)
    await stock(client, "A", 2)
    await stock(client, "C", 5)

    response = await client.get("/reports/low-stock", params={"threshold": 10})

    assert [(i["sku"], i["criticality_rank"]) for i in response.json()["items"]] == [
        ("A", 1),
        ("B", 1),
        ("C", 3),
    ]


@pytest.mark.parametrize("params", [{}, {"threshold": -1}, {"threshold": "dez"}])
async def test_invalid_threshold_returns_422(client, params):
    response = await client.get("/reports/low-stock", params=params)

    assert response.status_code == 422
