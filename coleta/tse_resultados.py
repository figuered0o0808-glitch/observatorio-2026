# -*- coding: utf-8 -*-
"""Resultados oficiais da eleição de 2026 pela divulgação do TSE (resultados.tse.jus.br).

Roda no GitHub Actions (o ambiente de trabalho não alcança o TSE). Lê os arquivos de resultado
consolidado ("-u.json") de cada eleição e grava duas tabelas regravadas inteiras a cada coleta:

  dados/resultados/candidatos.csv  um candidato por linha: turno, cargo, abrangência (br, UF ou zz,
                                   o exterior), número, nome de urna, partido, votos, % dos válidos,
                                   situação ("Eleito", "2º turno", "Não eleito"...), e o slug/nome
                                   que o mural usa para o mesmo candidato
  dados/resultados/totais.csv      os totais de cada apuração: seções totalizadas, eleitorado,
                                   comparecimento, abstenção, válidos, brancos, nulos

Códigos das eleições de 2026 (configuração do TSE em comum/config/ele-c.json, conferida em 13/10/2026):
  6257 presidente, 1º turno     6258 presidente, 2º turno (25/10)
  6259 estaduais, 1º turno      6260 governador, 2º turno (25/10) em AC, AM, DF, ES e RN
Cargos: 1 presidente, 3 governador, 5 senador.

Identificação: o "sqcand" do TSE é o mesmo id_tse de dados/estados/candidatos-estados.csv; para a
Presidência o número de urna basta (dados/candidatos.csv). Candidato sem par fica com o nome do TSE.

Antes do dia da votação o arquivo do 2º turno existe com tudo zerado; ele é gravado igual, e o mural
só mostra apuração quando há seção totalizada.

    python3 coleta/tse_resultados.py            coleta e grava
    python3 coleta/tse_resultados.py --dry-run  coleta e só mostra o resumo
"""
import argparse, csv, io, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
BASE = "https://resultados.tse.jus.br/oficial/ele2026"
UA = {"User-Agent": "Mozilla/5.0 (observatorio-2026)", "Accept": "*/*"}
BR = timezone(timedelta(hours=-3))
UFS = ("ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to").split()
CARGO_NOME = {1: "presidente", 3: "governador", 5: "senador"}
# (eleição, turno, cargo, abrangências)
APURACOES = (
    [(6257, 1, 1, ["br"] + UFS + ["zz"])]
    + [(6258, 2, 1, ["br"] + UFS + ["zz"])]
    + [(6259, 1, 3, UFS), (6259, 1, 5, UFS)]
    + [(6260, 2, 3, ["ac", "am", "df", "es", "rn"])]
)
COL_CAND = ["turno", "cargo", "abrangencia", "numero", "sqcand", "nome_urna", "partido", "vice",
            "votos", "pct_validos", "situacao", "eleito", "mural", "data", "atualizado_tse", "fonte"]
COL_TOT = ["turno", "cargo", "abrangencia", "secoes", "secoes_totalizadas", "pct_totalizado", "eleitorado",
           "comparecimento", "abstencao", "votos_totais", "validos", "brancos", "nulos", "vagas", "data",
           "atualizado_tse", "fonte"]


def pedir(url, tentativas=5):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or i == tentativas - 1:
                raise
        except Exception:
            if i == tentativas - 1:
                raise
        time.sleep(4 * (i + 1))


def num(s):
    """'1.234' / '1234' -> 1234; vazio -> 0."""
    s = str(s or "").replace(".", "").strip()
    return int(s) if s.isdigit() else 0


def pct(s):
    """'47,03' -> '47.03'."""
    s = str(s or "").strip().replace(".", "").replace(",", ".")
    try:
        return "%.2f" % float(s)
    except ValueError:
        return ""


def ler_mapas(raiz):
    pres, est = {}, {}
    with io.open(os.path.join(raiz, "dados", "candidatos.csv"), encoding="utf-8-sig") as f:
        for c in csv.DictReader(f):
            # número de urna repetido (o PRTB trocou Marçal por Avalanche): fica quem não foi indeferido
            if not c["numero"]:
                continue
            fora = "indeferid" in c.get("situacao_tse", "").lower()
            if c["numero"] not in pres or (pres[c["numero"]][1] and not fora):
                pres[c["numero"]] = (c["candidato"], fora)
    with io.open(os.path.join(raiz, "dados", "estados", "candidatos-estados.csv"), encoding="utf-8-sig") as f:
        for c in csv.DictReader(f):
            if c.get("id_tse"):
                est[c["id_tse"]] = c["slug"]
    return {k: v[0] for k, v in pres.items()}, est


def data_iso(dg):
    """'13/10/2026' -> '2026-10-13'."""
    try:
        return datetime.strptime(dg, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def coletar(eleicao, turno, cargo, ab, pres, est):
    url = "%s/%d/dados/%s/%s-c%04d-e%06d-u.json" % (BASE, eleicao, ab, ab, cargo, eleicao)
    j = json.loads(pedir(url))
    atual = ("%s %s" % (j.get("dg", ""), j.get("hg", ""))).strip()
    data = data_iso(j.get("dg", ""))
    cand, vagas = [], ""
    for cg in j.get("carg", []):
        vagas = cg.get("nv", "")
        for ag in cg.get("agr", []):
            for par in ag.get("par", []):
                for c in par.get("cand", []):
                    vice = (c.get("vs") or [{}])[0]
                    if cargo == 1:
                        mural = pres.get(str(c.get("n", "")), "")
                    else:
                        mural = est.get(str(c.get("sqcand", "")), "")
                    cand.append({
                        "turno": turno, "cargo": CARGO_NOME[cargo], "abrangencia": ab, "numero": c.get("n", ""),
                        "sqcand": c.get("sqcand", ""), "nome_urna": (c.get("nmu") or c.get("nm") or "").strip(),
                        "partido": par.get("sg", ""), "vice": (vice.get("nmu") or "").strip(),
                        "votos": num(c.get("vap")), "pct_validos": pct(c.get("pvap")),
                        "situacao": c.get("st", ""), "eleito": c.get("e", ""), "mural": mural,
                        "data": data, "atualizado_tse": atual, "fonte": url})
    s, e, v = j.get("s", {}), j.get("e", {}), j.get("v", {})
    tot = {"turno": turno, "cargo": CARGO_NOME[cargo], "abrangencia": ab, "secoes": num(s.get("ts")),
           "secoes_totalizadas": num(s.get("st")), "pct_totalizado": pct(s.get("pst")),
           "eleitorado": num(e.get("te")), "comparecimento": num(e.get("c")), "abstencao": num(e.get("a")),
           "votos_totais": num(v.get("tv")), "validos": num(v.get("vv")), "brancos": num(v.get("vb")),
           "nulos": num(v.get("vn")), "vagas": vagas, "data": data, "atualizado_tse": atual, "fonte": url}
    cand.sort(key=lambda r: (-r["votos"], r["nome_urna"]))
    return cand, tot


def gravar(caminho, cols, linhas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\r\n")
    w.writeheader()
    w.writerows(linhas)
    with io.open(caminho, "wb") as f:
        f.write(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resultados oficiais de 2026 pelo TSE")
    ap.add_argument("--raiz", default=RAIZ)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    pres, est = ler_mapas(a.raiz)
    cands, tots, falhas = [], [], []
    for eleicao, turno, cargo, abrs in APURACOES:
        for ab in abrs:
            try:
                c, t = coletar(eleicao, turno, cargo, ab, pres, est)
            except Exception as ex:
                falhas.append("%d %s %s: %s" % (eleicao, CARGO_NOME[cargo], ab, repr(ex)[:120]))
                continue
            cands += c
            tots.append(t)
            time.sleep(0.3)
    print("%d linhas de candidato, %d apurações, %d falhas" % (len(cands), len(tots), len(falhas)))
    for f in falhas:
        print("  falhou: " + f)
    sem_par = sorted({(r["cargo"], r["abrangencia"], r["nome_urna"]) for r in cands if not r["mural"]})
    if sem_par:
        print("%d candidaturas sem par no mural (ficam com o nome do TSE), ex.: %s" % (len(sem_par), sem_par[:8]))
    for t in tots:
        if t["abrangencia"] == "br":
            print("  %s %sº turno: %s%% das seções, %d válidos" % (t["cargo"], t["turno"], t["pct_totalizado"], t["validos"]))
    # coleta incompleta não sobrescreve a anterior: é a mesma regra das outras coletas regravadas
    if falhas:
        print("nada gravado: houve falha em alguma apuração")
        return 1
    if a.dry_run:
        print("nada gravado (--dry-run)")
        return 0
    gravar(os.path.join(a.raiz, "dados", "resultados", "candidatos.csv"), COL_CAND, cands)
    gravar(os.path.join(a.raiz, "dados", "resultados", "totais.csv"), COL_TOT, tots)
    print("gravado dados/resultados/candidatos.csv e totais.csv, coletado %s" % datetime.now(BR).strftime("%Y-%m-%dT%H:%M:%S%z"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
