"""Dependências do FastAPI compartilhadas pelas rotas."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

# Atalho de tipo: um parâmetro `session: Session` numa rota recebe uma sessão nova do banco.
Session = Annotated[AsyncSession, Depends(get_session)]
