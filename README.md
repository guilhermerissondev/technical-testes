# Technical testes

Repositório para resolver testes técnicos de backend. Cada teste fica em uma pasta própria e independente, com enunciado, código, testes e notas de decisão.

O histórico de todos os testes recebidos, com status, está em [`testes_enviados.md`](testes_enviados.md).

## Estrutura

```
.
├── README.md                  # este arquivo
├── testes_enviados.md         # índice de testes: data, origem, estimativa, status
├── _template/                 # arquivos copiados para cada teste novo
├── scripts/
│   └── novo-teste.sh          # cria a pasta de um teste a partir do template
├── .github/workflows/         # um workflow por teste (veja "CI" abaixo)
└── AAAA-MM-DD-nome-do-teste/  # um teste
    ├── ENUNCIADO.md           # enunciado original, sem alterações de escopo
    ├── README.md              # como rodar, decisões, o que ficou de fora
    └── ...                    # código da solução (pyproject, src/, tests/, docker-compose...)
```

## Convenções

- **Nome da pasta:** `AAAA-MM-DD-nome-do-teste`, com a data em que o teste foi recebido e o nome em kebab-case. A ordem alfabética fica igual à ordem cronológica.
- **Cada teste é autocontido.** Dependências, `Dockerfile`, `docker-compose.yml` e configuração de testes ficam dentro da pasta do teste. Nada é compartilhado entre testes, então dá para apagar ou mover uma pasta sem quebrar as outras.
- **`ENUNCIADO.md` não muda depois de registrado.** Dúvidas e interpretações do enunciado vão no `README.md` do teste, na seção de decisões.
- **`README.md` do teste** segue o modelo em `_template/README.md`: como rodar, como testar, decisões técnicas e o que faltou.
- **Status em `testes_enviados.md`:** `Não iniciado`, `Em andamento`, `Concluído` ou `Abandonado`. Atualize a linha ao começar e ao terminar.
- **Commits** com o nome da pasta como escopo, por exemplo `ledger-estoque: adiciona endpoint de movimentações`.

## Novo teste

```bash
./scripts/novo-teste.sh 2026-11-07 nome-do-teste "Título do Teste"
```

O script cria a pasta a partir do `_template/` e adiciona uma linha em `testes_enviados.md`. Depois é só colar o enunciado em `ENUNCIADO.md`.

## CI

O GitHub Actions só lê workflows em `.github/workflows/` na raiz do repositório. Por isso cada teste que pede CI ganha um arquivo `.github/workflows/<pasta-do-teste>.yml` com:

- `paths: ['<pasta-do-teste>/**', '.github/workflows/<pasta-do-teste>.yml']`, para rodar só quando aquele teste muda;
- `defaults.run.working-directory: <pasta-do-teste>`, para executar os comandos dentro da pasta.

O modelo está em [`_template/workflow.yml`](_template/workflow.yml).
