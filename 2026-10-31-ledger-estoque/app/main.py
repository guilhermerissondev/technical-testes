"""Aplicação FastAPI: criação da app e rotas."""

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

app = FastAPI(title="Ledger de Estoque")

# Atalho de tipo: um parâmetro `session: Session` numa rota recebe uma sessão nova do banco.
Session = Annotated[AsyncSession, Depends(get_session)]


@app.get("/health")
async def health(session: Session) -> dict[str, str]:
    """Responde ok só se o banco também responder. Usado pelo healthcheck do docker-compose."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
