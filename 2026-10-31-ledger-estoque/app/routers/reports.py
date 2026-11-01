"""Rotas de relatório."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies import Session
from app.schemas import LowStockReport
from app.services import reports

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/low-stock")
async def low_stock(
    session: Session,
    threshold: Annotated[
        int, Query(ge=0, description="Lista produtos com saldo abaixo deste valor")
    ],
) -> LowStockReport:
    return await reports.low_stock(session, threshold)
