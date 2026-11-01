# Ledger de Estoque Idempotente

Enunciado completo em [`ENUNCIADO.md`](ENUNCIADO.md).

API de estoque em que o saldo nunca é gravado: ele é sempre a soma das movimentações. Cada movimentação é idempotente pelo cabeçalho `Idempotency-Key`, e o saldo nunca fica negativo, nem com requisições concorrentes.

## Stack

FastAPI, Pydantic v2, SQLAlchemy 2 (async, driver `psycopg` 3), Alembic, PostgreSQL 17, pytest + httpx, uv, ruff.

## Estrutura

```
app/
  main.py               # cria a app, registra as rotas e traduz erros de domínio para HTTP
  models.py             # tabelas: products, movements, idempotency_keys
  schemas.py            # entrada e saída da API (validação de formato)
  errors.py             # erros de domínio e o status HTTP de cada um
  pagination.py         # cursor da paginação keyset
  routers/              # rotas HTTP, finas: validam, chamam o service, respondem
  services/
    movements.py        # registro com lock, cálculo do saldo, histórico
    idempotency.py      # reserva da chave e resposta guardada
    products.py         # cadastro e busca (com ou sem lock)
    reports.py          # relatório de estoque baixo em SQL
migrations/versions/    # migração única que cria as tabelas e constraints
tests/                  # um arquivo por requisito, contra Postgres real
```

## Como rodar

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Docker.

```bash
make install   # dependências
make up        # API + Postgres em http://localhost:8000 (documentação em /docs)
make down
```

Exemplo:

```bash
curl -X POST localhost:8000/products -H 'Content-Type: application/json' \
  -d '{"sku": "CAF-500G", "name": "Café 500 g"}'

curl -X POST localhost:8000/movements -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: compra-0001' \
  -d '{"sku": "CAF-500G", "type": "IN", "quantity": 12, "reason": "compra"}'

curl 'localhost:8000/products/CAF-500G/balance?as_of=2026-10-01T00:00:00Z'
curl 'localhost:8000/products/CAF-500G/movements?limit=20'
curl 'localhost:8000/reports/low-stock?threshold=10'
```

## Endpoints

| Método | Rota | Respostas |
|---|---|---|
| `POST` | `/products` | 201; 409 SKU repetido; 422 corpo inválido |
| `GET` | `/products/{sku}` | 200; 404 |
| `POST` | `/movements` | 201; 404 produto; 409 chave reusada com outro corpo; 422 corpo inválido ou saldo insuficiente |
| `GET` | `/products/{sku}/balance?as_of=` | 200; 404; 422 data sem fuso horário |
| `GET` | `/products/{sku}/movements?limit=&cursor=` | 200 com `items` e `next_cursor`; 404; 422 cursor inválido |
| `GET` | `/reports/low-stock?threshold=` | 200 |

`POST /movements` devolve o cabeçalho `Idempotent-Replayed: true` quando a resposta é a repetição de uma anterior.

## Como testar

```bash
make test      # sobe o Postgres se precisar e roda o pytest no banco ledger_test
make lint
```

Cada critério de aceite tem um teste:

| Critério | Teste |
|---|---|
| Mesma chave 20 vezes em paralelo gera uma movimentação | `test_idempotency.py::test_same_key_20_times_in_parallel_records_a_single_movement` |
| 50 `OUT` concorrentes em saldo 10 nunca deixam negativo | `test_concurrency.py::test_50_concurrent_outs_never_make_the_balance_negative` |
| `as_of` antes da primeira movimentação devolve 0 | `test_balance.py::test_as_of_before_the_first_movement_returns_zero` |
| `as_of` no instante exato inclui a movimentação | `test_balance.py::test_as_of_at_the_exact_instant_includes_the_movement` |
| Quantidade zero ou negativa devolve 422 | `test_movements.py::test_zero_or_negative_quantity_returns_422` |
| Saldo da API bate com a soma no banco | `test_balance.py::test_api_balance_matches_the_sum_of_movements_in_the_database` |

Os testes de concorrência foram conferidos ao contrário: tirando o `FOR UPDATE`, o `ON CONFLICT` da idempotência ou trocando `clock_timestamp()` por `now()`, o teste correspondente falha. Ou seja, eles pegam o bug que dizem pegar.

## Decisões

### O saldo é a soma de `delta`

Cada movimentação guarda o que o cliente enviou (`type`, `quantity`) e o efeito no saldo (`delta`): `+quantity` no `IN`, `-quantity` no `OUT`. O saldo é `SUM(delta)`, e a tabela `movements` só recebe `INSERT`.

Guardar o `delta` deixa toda leitura (saldo atual, `as_of`, relatório) como uma soma simples, sem `CASE` por tipo. Uma constraint no banco confere que o `delta` é coerente com o tipo.

### `ADJUST` é recontagem de inventário

O enunciado não define `ADJUST`, e a regra "quantidade zero ou negativa devolve 422" vale para todos os tipos. Então `ADJUST` não pode ser uma correção com sinal. A leitura adotada foi a mais comum em estoque: `quantity` é o saldo contado no inventário, e o `delta` é a diferença para o saldo anterior (pode ser positivo, negativo ou zero). Uma recontagem que bate com o sistema também fica registrada, o que serve de trilha de auditoria.

Consequência: zerar o estoque é feito com `OUT`, não com `ADJUST`.

### Concorrência: lock pessimista no produto

Toda movimentação faz `SELECT ... FROM products WHERE sku = ? FOR UPDATE`, lê o saldo, valida e insere. Duas movimentações do mesmo produto ficam em fila; produtos diferentes não se bloqueiam.

Por que pessimista e não otimista:

- **Conflito é o caso normal aqui.** O lock otimista (coluna `version` e repetir quando muda) compensa quando conflitos são raros. Com 50 saídas simultâneas no mesmo produto, quase todas colidiriam e teriam que repetir várias vezes, com retry, backoff e um limite de tentativas a definir.
- **Resultado previsível.** Com fila, cada requisição vê o saldo exato deixado pela anterior: 10 saídas passam e 40 recebem 422, sempre.
- **Custo baixo.** O lock dura uma transação curta (uma soma por índice e um insert) e trava só a linha de um produto.

"Restrição no banco" sozinha não resolve, porque não dá para escrever `CHECK (SUM(delta) >= 0)`. Isso exigiria uma tabela de saldo materializada (veja a comparação abaixo).

### Horário da movimentação: `clock_timestamp()`

O `occurred_at` é definido pelo banco com `clock_timestamp()`, a hora real do `INSERT`, e não com `now()`, que é a hora em que a transação começou. Uma saída que esperou o lock começou antes da entrada que ela esperou. Com `now()`, ela ficaria registrada antes dessa entrada, e o saldo `as_of` daquele instante sairia negativo. Com o horário do insert e o lock, as movimentações de um produto ficam sempre em ordem cronológica. Existe um teste para esse caso.

O cliente não informa a data da movimentação. Isso mantém o `as_of` confiável: ninguém consegue inserir algo no passado e mudar um saldo histórico.

### `as_of`

- `occurred_at <= as_of`: a movimentação feita exatamente no instante pedido entra no saldo.
- A data precisa ter fuso horário (`Z`, `-03:00`...). Sem fuso ela seria ambígua, então volta 422 em vez de o servidor adivinhar.

### Idempotência

- **Escopo da chave:** global, única na API toda. O hash cobre o corpo inteiro, inclusive o SKU, então reusar a chave para outro produto devolve 409. Num sistema com autenticação, o escopo seria por cliente (`(client_id, key)`).
- **Comparação do corpo:** SHA-256 do corpo já validado, com as chaves ordenadas. A ordem dos campos no JSON não importa, e campos desconhecidos são recusados (422) para não serem ignorados em silêncio.
- **Concorrência:** a chave é a chave primária de `idempotency_keys`. A primeira requisição insere a chave e processa tudo na mesma transação. As outras, com `INSERT ... ON CONFLICT DO NOTHING`, ficam esperando o Postgres até a primeira terminar, e então leem a resposta guardada. Não existe estado "em processamento" visível nem polling. Além disso, `movements.idempotency_key` é `UNIQUE`: mesmo com um bug na aplicação, o banco não aceita duas movimentações com a mesma chave.
- **O que fica guardado:** o 201 e o 422 de saldo insuficiente. São respostas definitivas para aquela requisição: repetir a mesma chave devolve o mesmo 422, mesmo que tenha entrado estoque depois. Para tentar de novo, o cliente usa outra chave.
- **O que não fica guardado:** erros de validação (o corpo nem chega a ser processado) e produto inexistente (404). Nesse último caso a transação é desfeita e a chave fica livre: dá para cadastrar o produto e repetir a mesma requisição.

### Histórico com paginação keyset

O cursor é a posição da última linha vista, `(occurred_at, id)`, em base64. A próxima página é `WHERE (occurred_at, id) < (cursor) ORDER BY occurred_at DESC, id DESC`, usando o índice `(product_id, occurred_at, id)`. Diferente de `OFFSET`, o custo não cresce com o número da página, e movimentações novas não fazem itens pularem ou se repetirem.

### Relatório de estoque baixo

Uma query só, em [`app/services/reports.py`](app/services/reports.py): uma CTE calcula o saldo de cada produto (com `LEFT JOIN`, para incluir produtos sem movimentação, com saldo 0), e `RANK()` dá a posição de criticidade. "Abaixo do limite" é estritamente menor que `threshold`. A ordem é pelo menor saldo, com o SKU como desempate.

### Testes contra Postgres real

Locks, constraints e `ON CONFLICT` são justamente o que o desafio pede para provar, e não se comportam igual em SQLite ou em mocks. Os testes rodam no Postgres, com o schema criado pelas próprias migrações do Alembic, então as migrações também ficam testadas.

## Saldo por soma x tabela de saldo materializada

| | Soma das movimentações (adotado) | Tabela `balances` atualizada a cada movimentação |
|---|---|---|
| Fonte da verdade | Uma só: o ledger | Duas, que precisam concordar |
| Leitura do saldo atual | `SUM` sobre as movimentações do produto (índice) | Uma linha, O(1) |
| Saldo `as_of` | Mesma query, com filtro de data | Continua precisando da soma (a tabela só sabe o saldo atual) |
| Saldo nunca negativo | Lock e validação na aplicação | Dá para usar `CHECK (balance >= 0)` no banco |
| Concorrência | Lock na linha do produto | O `UPDATE` da linha de saldo já serializa |
| Risco | Leitura fica mais cara com históricos enormes | Divergência se alguma escrita esquecer de atualizar o saldo |
| Relatório de estoque baixo | `GROUP BY` sobre todas as movimentações | Varredura de uma tabela pequena |

Para este desafio a soma basta: o índice `(product_id, occurred_at, id)` deixa o cálculo rápido até muitos milhares de movimentações por produto, e não existe saldo que possa divergir. Se o volume crescesse, o caminho seria um meio-termo: manter a soma como fonte da verdade e adicionar um saldo materializado (ou snapshots periódicos, "saldo até o dia X") atualizado na mesma transação da movimentação, com um job que confere se os dois batem.

## O que ficou de fora

- Autenticação, e com ela o escopo da chave de idempotência por cliente.
- Expiração das chaves de idempotência. Em produção, as chaves teriam um prazo (ex.: 24 h) e um job removeria as antigas.
- Edição e remoção de produtos (não pedidas).
- Snapshots de saldo para históricos muito grandes (veja a comparação acima).

## Tempo gasto

<!-- ex.: 6 h -->
