"""Rota de registro de movimentações, idempotente pelo cabeçalho Idempotency-Key."""

from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from app.dependencies import Session
from app.schemas import MovementCreate, MovementCreated
from app.services import movements

router = APIRouter(tags=["movements"])


@router.post(
    "/movements",
    status_code=201,
    response_model=MovementCreated,
    responses={
        404: {"description": "Produto não encontrado"},
        409: {"description": "Idempotency-Key já usada com outro corpo"},
        422: {"description": "Corpo inválido ou saldo insuficiente"},
    },
)
async def create_movement(
    payload: MovementCreate,
    session: Session,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
) -> JSONResponse:
    response, replayed = await movements.create_movement(session, payload, idempotency_key)
    # A resposta é montada a partir do que ficou guardado, então a primeira chamada e as
    # repetições devolvem exatamente o mesmo status e corpo. O cabeçalho só informa ao
    # cliente se aquela resposta é uma repetição.
    return JSONResponse(
        status_code=response.status_code,
        content=response.body,
        headers={"Idempotent-Replayed": str(replayed).lower()},
    )
