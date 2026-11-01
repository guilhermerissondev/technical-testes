#!/bin/sh
# Roda as migrações antes de iniciar a API, então o container nunca sobe com o schema
# desatualizado. "exec" troca o shell pelo uvicorn, que passa a receber os sinais de
# parada do Docker (SIGTERM) diretamente.
set -e
alembic upgrade head
exec "$@"
