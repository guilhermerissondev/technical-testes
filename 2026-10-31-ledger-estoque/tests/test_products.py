import pytest

from tests.helpers import create_product

pytestmark = pytest.mark.anyio


async def test_create_and_get_product(client):
    created = await create_product(client, sku="CAF-500G", name="Café 500 g")

    response = await client.get("/products/CAF-500G")

    assert response.status_code == 200
    assert response.json() == created
    assert created["sku"] == "CAF-500G"
    assert created["name"] == "Café 500 g"


async def test_duplicate_sku_returns_409(client):
    await create_product(client, sku="CAF-500G")

    response = await client.post("/products", json={"sku": "CAF-500G", "name": "Outro"})

    assert response.status_code == 409


async def test_unknown_product_returns_404(client):
    response = await client.get("/products/NAO-EXISTE")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"sku": "com espaço", "name": "x"},
        {"sku": "", "name": "x"},
        {"sku": "OK", "name": ""},
        {"sku": "OK", "name": "x", "campo_extra": 1},
    ],
)
async def test_invalid_product_returns_422(client, body):
    response = await client.post("/products", json=body)

    assert response.status_code == 422
