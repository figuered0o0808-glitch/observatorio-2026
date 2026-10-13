# -*- coding: utf-8 -*-
"""Monta as fixtures de resultado do TSE usadas pelos testes (lidas via MURAL_RESULTADOS).

  zerado/   cópia de dados/resultados de 13/10/2026: 1º turno apurado, 2º turno publicado zerado
  parcial/  o mesmo 1º turno e o 2º turno com 37,5% das seções totalizadas
  final/    o mesmo 1º turno e o 2º turno com 100% das seções e situação "Eleito"

Os números do 2º turno em parcial/ e final/ são sintéticos: cada nome recebe a parte que teve na
soma dos dois no 1º turno da mesma abrangência, e comparecimento, brancos e nulos saem de taxas
fixas. Não são resultado nem projeção, e a coluna fonte de cada linha diz isso. Rodar de novo só se
o formato de dados/resultados mudar:

    python3 testes/fixtures/resultados/_montar.py
"""
import csv
import io
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
ORIGEM = os.path.join(AQUI, "..", "..", "..", "dados", "resultados")
FONTE = "fixture de teste com números sintéticos (testes/fixtures/resultados/_montar.py); não é resultado do TSE"
ESTADOS = {
    "parcial": {"frac": 0.375, "data": "2026-10-25", "at": "25/10/2026 19:12:40"},
    "final": {"frac": 1.0, "data": "2026-10-26", "at": "26/10/2026 00:41:07"},
}


def ler(nome):
    with io.open(os.path.join(ORIGEM, nome), encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def gravar(pasta, nome, cab, linhas):
    os.makedirs(pasta, exist_ok=True)
    with io.open(os.path.join(pasta, nome), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cab, lineterminator="\r\n")
        w.writeheader()
        w.writerows(linhas)


def main():
    cab_c, cand = ler("candidatos.csv")
    cab_t, tot = ler("totais.csv")
    gravar(os.path.join(AQUI, "zerado"), "candidatos.csv", cab_c, cand)
    gravar(os.path.join(AQUI, "zerado"), "totais.csv", cab_t, tot)
    # votos do 1º turno de cada nome por (cargo, abrangência), pelo sqcand, para a divisão sintética
    v1 = {(r["cargo"], r["abrangencia"], r["sqcand"]): int(r["votos"]) for r in cand if r["turno"] == "1"}
    for nome, e in ESTADOS.items():
        novos_t, novos_c = [], []
        por_ab = {}
        for t in tot:
            if t["turno"] != "2":
                novos_t.append(t)
                continue
            sec = int(t["secoes"])
            st = sec if e["frac"] >= 1 else round(sec * e["frac"])
            pst = 100.0 * st / sec if sec else 0.0
            el = int(t["eleitorado"])
            alcancado = round(el * st / sec) if sec else 0
            comp = round(alcancado * 0.79)
            vb, vn = round(comp * 0.015), round(comp * 0.03)
            t = dict(t, secoes_totalizadas=str(st), pct_totalizado="%.2f" % pst, comparecimento=str(comp),
                     abstencao=str(alcancado - comp), votos_totais=str(comp), validos=str(comp - vb - vn),
                     brancos=str(vb), nulos=str(vn), data=e["data"], atualizado_tse=e["at"], fonte=FONTE)
            novos_t.append(t)
            por_ab[(t["cargo"], t["abrangencia"])] = t
        for c in cand:
            if c["turno"] != "2":
                novos_c.append(c)
                continue
            novos_c.append(dict(c))
        # divide os válidos de cada apuração entre os dois nomes, na proporção do 1º turno
        grupos = {}
        for c in novos_c:
            if c["turno"] == "2":
                grupos.setdefault((c["cargo"], c["abrangencia"]), []).append(c)
        for k, cs in grupos.items():
            t = por_ab[k]
            vv = int(t["validos"])
            base = [v1.get((k[0], k[1], c["sqcand"]), 1) for c in cs]
            soma = sum(base) or 1
            votos = [round(vv * b / soma) for b in base]
            votos[-1] = vv - sum(votos[:-1])
            for c, v in zip(cs, votos):
                c.update(votos=str(v), pct_validos="%.2f" % (100.0 * v / vv if vv else 0), situacao="", eleito="n",
                         data=e["data"], atualizado_tse=e["at"], fonte=FONTE)
        if e["frac"] >= 1:
            # na apuração final o TSE marca o vencedor; no presidente, o do Brasil em todas as abrangências
            venc_br = max(grupos[("presidente", "br")], key=lambda c: int(c["votos"]))["sqcand"]
            for (cargo, ab), cs in grupos.items():
                venc = venc_br if cargo == "presidente" else max(cs, key=lambda c: int(c["votos"]))["sqcand"]
                for c in cs:
                    c.update(situacao="Eleito" if c["sqcand"] == venc else "Não eleito", eleito="s" if c["sqcand"] == venc else "n")
        gravar(os.path.join(AQUI, nome), "candidatos.csv", cab_c, novos_c)
        gravar(os.path.join(AQUI, nome), "totais.csv", cab_t, novos_t)
        print(nome, len(novos_c), "candidatos,", len(novos_t), "totais")


if __name__ == "__main__":
    main()
