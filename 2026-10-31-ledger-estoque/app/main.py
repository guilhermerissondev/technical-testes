"""Aplicação FastAPI: criação da app, rotas e tradução de erros de domínio para HTTP."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.dependencies import Session
from app.errors import DomainError
from app.routers import movements, products, reports

app = FastAPI(
    title="Ledger de Estoque",
    description="Saldo de estoque derivado de movimentações idempotentes.",
)

app.include_router(products.router)
app.include_router(movements.router)
app.include_router(reports.router)


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
    """Mesmo formato dos erros do FastAPI ({"detail": ...}), com o status da classe do erro."""
    return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


@app.get("/health")
async def health(session: Session) -> dict[str, str]:
    """Responde ok só se o banco também responder. Usado pelo healthcheck do docker-compose."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
