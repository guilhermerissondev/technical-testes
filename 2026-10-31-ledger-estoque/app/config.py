"""Configuração da aplicação, lida de variáveis de ambiente.

O pydantic-settings procura cada campo como variável de ambiente (sem diferenciar maiúsculas)
e, se não achar, no arquivo `.env`. Assim o mesmo código roda no Docker, na máquina local e na CI
mudando só o ambiente.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": o .env também tem variáveis que não são da app (ex.: TEST_DATABASE_URL).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # O prefixo "postgresql+psycopg" diz ao SQLAlchemy para usar o driver psycopg 3,
    # que funciona tanto no modo síncrono (Alembic) quanto no assíncrono (API).
    database_url: str = "postgresql+psycopg://ledger:ledger@localhost:5432/ledger"


settings = Settings()
