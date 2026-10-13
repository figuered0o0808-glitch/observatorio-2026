#!/usr/bin/env bash
# Ensaio da rodada automática, antes de mexer no gerador ou no template.
#
# Copia o repositório (com o que ainda não foi commitado) para uma pasta temporária, roda nela o
# coletor nacional com uma página da Wikipédia guardada em testes/fixtures, passa o guarda de dados
# e o ./testes/verificar.sh inteiro. É o que o atualizar.yml faz, sem rede: o ensaio pega antes do
# push o tipo de quebra de 13/10/2026, quando as primeiras rodadas só de 2º turno chegaram pela
# coleta e derrubaram a regressão, e nenhuma atualização foi publicada até a correção.
#
# Uso:
#   ./testes/ensaio_rodada.sh                         página de 13/10/2026
#   ./testes/ensaio_rodada.sh caminho/pagina.html.gz  outra página guardada (REVID=n para a revisão dela)
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAGINA="${1:-$RAIZ/testes/fixtures/wikipedia/nacional-2026-10-13.html.gz}"
PAGINA="$(cd "$(dirname "$PAGINA")" && pwd)/$(basename "$PAGINA")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$RAIZ" "$TMP/obs"
cd "$TMP/obs"

echo "== coletor nacional com $(basename "$PAGINA") =="
python3 coleta/wikipedia_pesquisas_nacional.py --raiz . --html "$PAGINA" --revid "${REVID:-1}"
echo
echo "== guarda de dados =="
python3 testes/guarda_dados.py
echo
./testes/verificar.sh
echo
echo "ensaio verde: a rodada automática com essa página publicaria."
