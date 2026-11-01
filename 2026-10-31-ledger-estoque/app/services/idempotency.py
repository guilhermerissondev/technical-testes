"""Idempotência de `POST /movements` pelo cabeçalho `Idempotency-Key`.

Como funciona, dentro da mesma transação que grava a movimentação:

1. `claim` tenta inserir a chave. Se ninguém a usou, a inserção funciona e esta requisição
   é a dona da chave: ela processa e grava a resposta com `save_response`.
2. Se outra transação já inseriu a mesma chave e ainda não terminou, o Postgres faz este
   INSERT esperar por ela (a chave primária está "reservada"). Quando a outra faz commit,
   o `ON CONFLICT DO NOTHING` não insere nada, e a requisição devolve a resposta guardada
   com `previous_response`. Se a outra fizer rollback, a chave fica livre e esta assume.

Assim, 20 requisições paralelas com a mesma chave viram uma única execução, sem polling
e sem estado "em processamento" visível.

O escopo da chave é global (ela é única em toda a API), e o corpo inteiro, inclusive o SKU,
entra no hash. Reusar a chave para outro produto é tratado como corpo diferente: 409.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import IdempotencyKeyReused
from app.models import IdempotencyKey


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


def fingerprint(payload: BaseModel) -> str:
    """Hash do corpo já validado, com chaves ordenadas.

    Usar o modelo validado, e não os bytes crus, faz `{"a":1,"b":2}` e `{"b":2, "a":1}`
    contarem como o mesmo corpo.
    """
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def claim(session: AsyncSession, key: str, request_hash: str) -> bool:
    """Tenta reservar a chave. True se esta requisição é a primeira a usá-la."""
    inserted_key = await session.scalar(
        insert(IdempotencyKey)
        .values(key=key, request_hash=request_hash)
        .on_conflict_do_nothing(index_elements=[IdempotencyKey.key])
        .returning(IdempotencyKey.key)
    )
    return inserted_key is not None


async def previous_response(session: AsyncSession, key: str, request_hash: str) -> StoredResponse:
    """Resposta guardada da primeira requisição com esta chave, ou 409 se o corpo mudou."""
    record = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    if record.request_hash != request_hash:
        raise IdempotencyKeyReused()
    return StoredResponse(record.response_status, record.response_body)


async def save_response(session: AsyncSession, key: str, response: StoredResponse) -> None:
    await session.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.key == key)
        .values(response_status=response.status_code, response_body=response.body)
    )
