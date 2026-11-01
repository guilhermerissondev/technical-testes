"""Cursor opaco da paginação keyset do histórico de movimentações.

Paginação por cursor (keyset) em vez de OFFSET: a próxima página começa logo depois da
última linha vista, usando o índice (product_id, occurred_at, id). Assim o custo não cresce
com o número da página, e movimentações novas não fazem itens pularem ou se repetirem
entre páginas.

O cursor é a posição da última linha, (occurred_at, id), em JSON e base64. É opaco para o
cliente: ele só devolve o valor recebido em `next_cursor`.
"""

import base64
import json
from datetime import datetime

from app.errors import InvalidCursor


def encode_cursor(occurred_at: datetime, movement_id: int) -> str:
    raw = json.dumps([occurred_at.isoformat(), movement_id])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        occurred_at_raw, movement_id = json.loads(base64.urlsafe_b64decode(cursor))
        occurred_at = datetime.fromisoformat(occurred_at_raw)
    except (ValueError, TypeError) as error:
        raise InvalidCursor() from error

    if occurred_at.tzinfo is None or not isinstance(movement_id, int):
        raise InvalidCursor()
    return occurred_at, movement_id
