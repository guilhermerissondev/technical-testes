"""Erros de domínio e o status HTTP de cada um.

Os services levantam estes erros sem saber nada de HTTP. Um único handler em `app/main.py`
transforma qualquer `DomainError` em resposta `{"detail": "..."}` com o status da classe.
"""


class DomainError(Exception):
    status_code = 400


class ProductNotFound(DomainError):
    status_code = 404

    def __init__(self, sku: str) -> None:
        super().__init__(f"Produto '{sku}' não encontrado.")


class SkuAlreadyExists(DomainError):
    status_code = 409

    def __init__(self, sku: str) -> None:
        super().__init__(f"Já existe um produto com o SKU '{sku}'.")


class IdempotencyKeyReused(DomainError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("Esta Idempotency-Key já foi usada com um corpo diferente.")


class InsufficientStock(DomainError):
    status_code = 422

    def __init__(self, balance: int, requested: int) -> None:
        super().__init__(f"Saldo insuficiente: saldo atual {balance}, saída pedida {requested}.")


class InvalidCursor(DomainError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("Cursor de paginação inválido.")
