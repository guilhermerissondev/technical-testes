"""Movimentações de estoque: registro, saldo e histórico.

Concorrência: lock pessimista na linha do produto (SELECT ... FOR UPDATE). Toda movimentação
de um produto trava o produto, lê o saldo, valida e insere, e só então libera no commit.
Duas saídas simultâneas nunca leem o mesmo saldo, então o saldo não fica negativo.
O README explica por que essa opção foi preferida ao lock otimista.
"""

from datetime import datetime

from sqlalchemy import BigInteger, cast, func, insert, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InsufficientStock
from app.models import Movement, MovementType, Product
from app.pagination import decode_cursor, encode_cursor
from app.schemas import MovementCreate, MovementCreated, MovementOut, MovementPage
from app.services import idempotency
from app.services.idempotency import StoredResponse
from app.services.products import get_product


async def create_movement(
    session: AsyncSession, payload: MovementCreate, idempotency_key: str
) -> tuple[StoredResponse, bool]:
    """Registra a movimentação uma única vez por chave.

    Devolve a resposta (status e corpo) e se ela é a repetição de uma anterior.

    A ordem das travas é sempre chave de idempotência e depois produto. Como toda requisição
    segue a mesma ordem, duas transações nunca ficam esperando uma pela outra (deadlock).
    """
    request_hash = idempotency.fingerprint(payload)

    async with session.begin():
        if not await idempotency.claim(session, idempotency_key, request_hash):
            replay = await idempotency.previous_response(session, idempotency_key, request_hash)
            return replay, True

        # Produto inexistente levanta 404 aqui. A exceção desfaz a transação inteira, então a
        # chave não fica consumida: dá para cadastrar o produto e repetir a mesma requisição.
        product = await get_product(session, payload.sku, for_update=True)

        try:
            movement, balance_after = await _insert_movement(
                session, product, payload, idempotency_key
            )
            body = MovementCreated(
                **_to_schema(movement, product.sku).model_dump(), balance_after=balance_after
            )
            response = StoredResponse(201, body.model_dump(mode="json"))
        except InsufficientStock as error:
            # Saldo insuficiente é uma resposta definitiva para esta chave e também é
            # guardada: repetir a mesma requisição devolve o mesmo 422, mesmo que entre
            # uma coisa e outra tenha entrado estoque. Para tentar de novo, use outra chave.
            response = StoredResponse(422, {"detail": str(error)})

        await idempotency.save_response(session, idempotency_key, response)

    return response, False


async def _insert_movement(
    session: AsyncSession, product: Product, payload: MovementCreate, idempotency_key: str
) -> tuple[Movement, int]:
    """Calcula o efeito no saldo e insere. Precisa do produto já travado pelo chamador."""
    current_balance = await get_balance(session, product.id)
    delta = compute_delta(payload.type, payload.quantity, current_balance)

    movement = await session.scalar(
        insert(Movement)
        .values(
            product_id=product.id,
            idempotency_key=idempotency_key,
            type=payload.type,
            quantity=payload.quantity,
            delta=delta,
            reason=payload.reason,
            # clock_timestamp() é a hora real do INSERT. now() seria a hora em que a
            # transação começou, e uma transação que esperou o lock ficaria com horário
            # anterior ao da movimentação que ela esperou. Aí o saldo "as_of" de um instante
            # intermediário poderia sair negativo. Com o lock, os horários de um produto
            # ficam sempre em ordem.
            occurred_at=func.clock_timestamp(),
        )
        .returning(Movement)
    )
    return movement, current_balance + delta


def compute_delta(movement_type: MovementType, quantity: int, current_balance: int) -> int:
    """Efeito da movimentação no saldo. Levanta InsufficientStock se o saldo ficaria negativo."""
    match movement_type:
        case MovementType.IN:
            return quantity
        case MovementType.OUT:
            if quantity > current_balance:
                raise InsufficientStock(current_balance, quantity)
            return -quantity
        case MovementType.ADJUST:
            # Recontagem: o saldo passa a ser exatamente o valor contado.
            return quantity - current_balance


async def get_balance(session: AsyncSession, product_id: int, as_of: datetime | None = None) -> int:
    """Saldo = soma dos deltas. Com `as_of`, só das movimentações até aquele instante."""
    # SUM de BIGINT devolve NUMERIC no Postgres; o cast traz de volta para inteiro.
    query = select(cast(func.coalesce(func.sum(Movement.delta), 0), BigInteger)).where(
        Movement.product_id == product_id
    )
    if as_of is not None:
        # "<=": a movimentação registrada exatamente no instante as_of entra no saldo.
        query = query.where(Movement.occurred_at <= as_of)
    return await session.scalar(query)


async def list_movements(
    session: AsyncSession, product: Product, limit: int, cursor: str | None
) -> MovementPage:
    """Histórico do produto, do mais recente para o mais antigo, paginado por cursor."""
    query = (
        select(Movement)
        .where(Movement.product_id == product.id)
        .order_by(Movement.occurred_at.desc(), Movement.id.desc())
        # Uma linha a mais só para saber se existe próxima página.
        .limit(limit + 1)
    )
    if cursor is not None:
        # Comparação de tupla: tudo que vem estritamente depois da última linha vista.
        # O id desempata movimentações com o mesmo occurred_at.
        last_occurred_at, last_id = decode_cursor(cursor)
        query = query.where(
            tuple_(Movement.occurred_at, Movement.id) < tuple_(last_occurred_at, last_id)
        )

    rows = list(await session.scalars(query))
    has_more = len(rows) > limit
    page = rows[:limit]

    next_cursor = encode_cursor(page[-1].occurred_at, page[-1].id) if has_more else None
    return MovementPage(items=[_to_schema(m, product.sku) for m in page], next_cursor=next_cursor)


def _to_schema(movement: Movement, sku: str) -> MovementOut:
    return MovementOut(
        id=movement.id,
        sku=sku,
        type=movement.type,
        quantity=movement.quantity,
        delta=movement.delta,
        reason=movement.reason,
        occurred_at=movement.occurred_at,
    )
