# -*- coding: utf-8 -*-
"""Rodadas de 2024 e 2025 que entraram em dados/pesquisas-registradas.csv datadas como 2026.

Até 27/9/2026 o coletor nacional lia o ano de cada tabela pelo título da seção, e o título
"2025" da página não era reconhecido: as tabelas de 2025 e 2024 herdavam "2026". Este script
refaz a leitura da página dos dois jeitos (o antigo e o corrigido), pega as rodadas cujo ano
muda e procura no CSV a rodada que entrou com a data errada. Só conta como a mesma rodada quando
o instituto e o fim de campo batem e os números do primeiro cenário também batem, candidato a
candidato; assim uma rodada genuína de 2026 do mesmo instituto no mesmo dia nunca é marcada.

Não altera nada: imprime as linhas no formato de dados/rodadas-excluidas.csv.

    python3 coleta/_rodadas_datadas_errado.py
"""
import csv, io, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wikipedia_pesquisas_nacional as w

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extrair_com(html, revid, antigo):
    if antigo:
        original = w.AnoPelaOrdem.ano
        w.AnoPelaOrdem.ano = lambda self, caminho, padrao: w.ano_do_caminho(caminho, padrao)
        try:
            return w.extrair(html, revid)
        finally:
            w.AnoPelaOrdem.ano = original
    return w.extrair(html, revid)


def main():
    linhas = w.ler_csv(os.path.join(RAIZ, "dados", "pesquisas-registradas.csv"))
    institutos = w.institutos_do_csv(linhas)
    html, revid, _ = w.baixar_pagina() if len(sys.argv) < 2 else (*w.carregar_html(sys.argv[1], "0"), None)
    velho = extrair_com(html, revid, True)
    novo = extrair_com(html, revid, False)
    hoje = w.hoje_brasilia()
    w.completar(velho, institutos, hoje)
    certo = {(rd["secao"], rd["instituto_pagina"], rd["campo_texto"]): rd["campo_fim"] for rd in novo["primeiro"]}
    # rodadas do CSV: (instituto, fim de campo) -> {divulgação: {candidato: percentual}} do 1º cenário
    csv_rod = defaultdict(lambda: defaultdict(dict))
    for l in linhas:
        if l["cenario"] == "1º turno" and l["percentual"]:
            csv_rod[(l["instituto"], l["data_campo_fim"])][l["data_divulgacao"]][l["candidato"]] = float(l["percentual"])
    achadas = []
    for rd in velho["primeiro"]:
        errado = rd["campo_fim"]
        bom = certo.get((rd["secao"], rd["instituto_pagina"], rd["campo_texto"]))
        if not bom or bom[:4] == errado[:4] or not errado.startswith("2026"):
            continue
        pagina = dict((n, float(v)) for n, v in (rd["cenarios"][0]["candidatos"] if rd["cenarios"] else []))
        for div, nums in csv_rod.get((rd["instituto"], errado), {}).items():
            comuns = [n for n in pagina if n in nums]
            if len(comuns) >= 2 and all(abs(pagina[n] - nums[n]) < 0.05 for n in comuns):
                achadas.append((rd["instituto"], errado, div, bom, rd["secao"]))
    print("instituto,data_campo_fim,data_divulgacao,motivo")
    for inst, errado, div, bom, secao in sorted(achadas, key=lambda x: (x[1], x[0])):
        motivo = ("rodada de %s (fim de campo %s) que entrou datada como %s: o coletor lia o ano pelo "
                  "título da seção e a tabela '%s' herdava 2026" % (bom[:4], bom, errado, secao.split(" > ")[-1]))
        w_ = csv.writer(sys.stdout, lineterminator="\n")
        w_.writerow([inst, errado, div, motivo])
    print("# %d rodadas do CSV datadas errado" % len(achadas), file=sys.stderr)


if __name__ == "__main__":
    main()
