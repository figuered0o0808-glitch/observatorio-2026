#!/usr/bin/env bash
# Regenera o mural a partir dos dados atuais e roda os dois testes.
# Uso:
#   ./testes/verificar.sh            regenera e verifica
#   ./testes/verificar.sh --pular-geracao   só verifica o mural.html que já existe
#
# Precisa de: playwright instalado (pip install -r requirements.txt) e, na
# primeira vez, do Chromium do Playwright (playwright install chromium).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ "${1:-}" != "--pular-geracao" ]]; then
  echo "== regenerando pesquisas-estados-consolidado.csv =="
  python3 dados/estados/_consolidar_pesquisas.py
  echo
  echo "== regenerando mural.html =="
  python3 mural/_gerar_mural.py
  echo
fi

echo "== regressão de bugs já corrigidos =="
python3 testes/regressao_bugs_conhecidos.py
echo
echo "== varredura geral (27 estados x 2 cargos, mobile, tema escuro) =="
python3 testes/varredura_geral.py
echo
echo "tudo verificado."
