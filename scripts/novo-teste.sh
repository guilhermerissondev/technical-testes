#!/usr/bin/env bash
# Cria a pasta de um teste novo a partir de _template/ e registra em testes_enviados.md.
# Uso: ./scripts/novo-teste.sh AAAA-MM-DD nome-do-teste "Título do Teste"
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Uso: $0 AAAA-MM-DD nome-do-teste \"Título do Teste\"" >&2
  exit 1
fi

data="$1"
nome="$2"
titulo="$3"

if ! [[ "$data" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Data inválida: $data (use AAAA-MM-DD)" >&2
  exit 1
fi
if ! [[ "$nome" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "Nome inválido: $nome (use kebab-case, ex.: ledger-estoque)" >&2
  exit 1
fi

raiz="$(cd "$(dirname "$0")/.." && pwd)"
pasta="$data-$nome"
destino="$raiz/$pasta"

if [[ -e "$destino" ]]; then
  echo "A pasta $pasta já existe." >&2
  exit 1
fi

mkdir "$destino"
for arquivo in ENUNCIADO.md README.md; do
  sed -e "s|{{TITULO}}|$titulo|g" -e "s|{{DATA}}|$data|g" -e "s|{{PASTA}}|$pasta|g" \
    "$raiz/_template/$arquivo" > "$destino/$arquivo"
done

echo "| $data | $titulo | [\`$pasta\`]($pasta/ENUNCIADO.md) | | | Não iniciado |" >> "$raiz/testes_enviados.md"

echo "Criado $pasta/. Cole o enunciado em $pasta/ENUNCIADO.md e preencha origem e estimativa em testes_enviados.md."
echo "Se o teste pedir CI: sed 's|{{PASTA}}|$pasta|g' _template/workflow.yml > .github/workflows/$pasta.yml"
