import pytest

# Faz todos os testes async deste arquivo rodarem no event loop configurado em conftest.py.
pytestmark = pytest.mark.anyio


async def test_health(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
