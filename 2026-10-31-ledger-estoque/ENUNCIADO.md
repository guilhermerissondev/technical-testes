# Ledger de Estoque Idempotente

**Data:** sábado, 31/10/2026
**Origem:** desafio original, não pertence a nenhuma empresa.
**Estimativa:** 5 a 7 horas.

## Enunciado

Construa uma API de controle de estoque em que o saldo nunca é editado diretamente. Ele sempre vem da soma de movimentações registradas.

1. **Cadastro de produtos.** `POST /products` e `GET /products/{sku}`, com SKU único.
2. **Movimentações.** `POST /movements` aceita `IN`, `OUT` ou `ADJUST`, com quantidade, motivo e o cabeçalho `Idempotency-Key`.
   - Repetir a mesma chave com o mesmo corpo devolve a resposta original e não grava de novo.
   - Repetir a mesma chave com corpo diferente devolve `409`.
3. **Saldo nunca negativo.** Um `OUT` maior que o saldo devolve `422`. Duas requisições concorrentes não podem passar do saldo, então use transação com lock ou restrição no banco.
4. **Consulta.**
   - `GET /products/{sku}/balance?as_of=2026-10-01T00:00:00Z` devolve o saldo naquela data.
   - `GET /products/{sku}/movements` devolve o histórico com paginação por cursor.
5. **Relatório.** `GET /reports/low-stock?threshold=10` lista os produtos abaixo do limite, ordenados do mais crítico, com uma única query SQL (CTE ou window function).
6. **Entrega.**
   - Migrações com Alembic.
   - Dockerfile e `docker-compose` com PostgreSQL.
   - Workflow de GitHub Actions que roda os testes.

## Critérios de aceite (o que os testes devem provar)

- [ ] A mesma `Idempotency-Key` enviada 20 vezes em paralelo gera uma única movimentação.
- [ ] 50 `OUT` concorrentes em um saldo de 10 unidades nunca deixam o saldo negativo.
- [ ] `as_of` antes da primeira movimentação devolve 0, e `as_of` no instante exato de uma movimentação a inclui.
- [ ] Quantidade zero ou negativa devolve `422`.
- [ ] O saldo calculado pela API bate com a soma das movimentações no banco.

## Tecnologias sugeridas

FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, pytest (com `httpx` ou `anyio` para os testes de concorrência), Docker, GitHub Actions.

## Extra, se sobrar tempo

- README com as decisões: por que lock otimista ou pessimista, como foi definido o escopo da chave de idempotência.
- Comparação entre calcular o saldo por soma e manter uma tabela de saldo materializada.
