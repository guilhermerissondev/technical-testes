"""Atalhos usados pelos testes para montar cenários sem repetir chamadas HTTP."""

import asyncio
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def create_product(client: httpx.AsyncClient, sku: str = "SKU-1", name: str = "Produto"):
    response = await client.post("/products", json={"sku": sku, "name": name})
    assert response.status_code == 201, response.text
    return response.json()


def movement_body(sku: str, type_: str, quantity: int, reason: str = "teste") -> dict:
    return {"sku": sku, "type": type_, "quantity": quantity, "reason": reason}


async def post_movement(
    client: httpx.AsyncClient,
    sku: str,
    type_: str,
    quantity: int,
    *,
    key: str | None = None,
    reason: str = "teste",
) -> httpx.Response:
    """Envia POST /movements. Sem `key`, gera uma chave nova (requisição independente)."""
    return await client.post(
        "/movements",
        json=movement_body(sku, type_, quantity, reason),
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


async def get_balance(client: httpx.AsyncClient, sku: str, as_of: str | None = None) -> int:
    params = {"as_of": as_of} if as_of is not None else {}
    response = await client.get(f"/products/{sku}/balance", params=params)
    assert response.status_code == 200, response.text
    return response.json()["balance"]


async def db_scalar(engine: AsyncEngine, sql: str, **params):
    """Consulta direta no banco, por fora da API, para conferir o que foi gravado de fato."""
    async with engine.connect() as conn:
        return await conn.scalar(text(sql), params)


async def wait_until_a_query_is_blocked_on_a_lock(engine: AsyncEngine, timeout: float = 5) -> None:
    """Espera até alguma conexão do banco ficar parada esperando um lock.

    Usado para ter certeza, sem depender de sleep fixo, de que uma requisição já chegou ao
    SELECT ... FOR UPDATE e está esperando.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        waiting = await db_scalar(
            engine,
            "SELECT count(*) FROM pg_stat_activity"
            " WHERE datname = current_database() AND wait_event_type = 'Lock'",
        )
        if waiting:
            return
        await asyncio.sleep(0.01)
    raise TimeoutError("Nenhuma query ficou esperando lock.")
