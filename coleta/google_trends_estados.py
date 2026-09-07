# -*- coding: utf-8 -*-
"""Google Trends dentro de cada estado, para os nomes das 54 disputas estaduais.

Refaz os mesmos 133 lotes que o navegador do Mac montou em 2/9/2026 e que
dados/estados/_trends-estados.json guarda: por disputa (UF e cargo), o líder da última pesquisa é
a âncora e entra em todos os lotes daquela disputa, com até quatro outros nomes por lote, geo
BR-UF. O plano de lotes não é recalculado aqui; muda só quem faz a chamada e a janela, que vai
até ontem.

Sai o mesmo JSON, no mesmo formato ("ts;v,v,v|ts;v,v,v" por lote), e quem transforma em CSV
continua sendo dados/estados/_integrar_busca.py --so-trends, com a reescala pela âncora.

São 133 consultas: com a pausa padrão a coleta leva uns quinze minutos. Se um lote falhar, o
anterior é mantido e o JSON registra a falha em "erros"; se falhar mais que o limite, nada é
gravado, para a série não ficar meio nova e meio velha.

Uso:
  python3 coleta/google_trends_estados.py
  python3 coleta/google_trends_estados.py --lotes 5 --dry-run     # ensaio com poucos lotes
"""
import argparse, io, json, os, sys, time
from datetime import datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
from google_trends import Sessao, ErroTrends  # noqa: E402

DUMP = os.path.join("dados", "estados", "_trends-estados.json")
INICIO = "2026-01-01"
BR = timezone(timedelta(hours=-3))
FALHAS_TOLERADAS = 0.15   # acima disso a coleta inteira é descartada


def serie_bruta(ses, termos, geo, inicio, fim):
    """Chama o Trends e devolve a string "ts;v,v,v|ts;v,v,v" que o dump guarda."""
    import urllib.parse
    periodo = "%s %s" % (inicio, fim)
    req = {"comparisonItem": [{"keyword": t, "geo": geo, "time": periodo} for t in termos],
           "category": 0, "property": ""}
    url = ("https://trends.google.com/trends/api/explore?hl=pt-BR&tz=180&req="
           + urllib.parse.quote(json.dumps(req, ensure_ascii=False), safe=""))
    dados = ses.json(url, {"Referer": "https://trends.google.com/trends/explore"})
    widget = next((w for w in dados.get("widgets", []) if w.get("id") == "TIMESERIES"), None)
    if not widget:
        raise ErroTrends("sem widget TIMESERIES")
    url2 = ("https://trends.google.com/trends/api/widgetdata/multiline?hl=pt-BR&tz=180&req="
            + urllib.parse.quote(json.dumps(widget["request"], ensure_ascii=False), safe="")
            + "&token=" + urllib.parse.quote(widget["token"], safe=""))
    linha = ses.json(url2, {"Referer": "https://trends.google.com/trends/explore"})
    pontos = linha.get("default", {}).get("timelineData", [])
    if not pontos:
        raise ErroTrends("série vazia")
    partes = []
    for p in pontos:
        vals = p.get("value") or []
        if len(vals) < len(termos):
            vals = list(vals) + [0] * (len(termos) - len(vals))
        partes.append("%s;%s" % (p["time"], ",".join(str(int(v or 0)) for v in vals[:len(termos)])))
    return "|".join(partes)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Google Trends por estado, nos lotes já planejados")
    ap.add_argument("--raiz", default=RAIZ)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--desde", default=INICIO)
    ap.add_argument("--ate", default=None, help="padrão: ontem em Brasília")
    ap.add_argument("--pausa", type=float, default=6.0)
    ap.add_argument("--lotes", type=int, default=0, help="limita quantos lotes coletar (ensaio)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    caminho = a.dump or os.path.join(a.raiz, DUMP)
    with io.open(caminho, encoding="utf-8") as f:
        dump = json.load(f)
    plano = dump.get("lotes") or {}
    if not plano:
        print("dump sem lotes: %s" % caminho)
        return 1

    hoje = datetime.now(BR).date()
    fim = a.ate or (hoje - timedelta(days=1)).isoformat()
    chaves = sorted(plano)
    if a.lotes:
        chaves = chaves[:a.lotes]

    ses = Sessao(pausa=a.pausa)
    novos, erros = {}, []
    for i, chave in enumerate(chaves):
        lote = plano[chave]
        if i:
            time.sleep(a.pausa)
        try:
            csv_novo = serie_bruta(ses, lote["kws"], lote["geo"], a.desde, fim)
            novos[chave] = csv_novo
            print("%3d/%d %s (%s): %d pontos" % (i + 1, len(chaves), chave, lote["geo"],
                                                 csv_novo.count("|") + 1), flush=True)
        except Exception as e:
            erros.append("%s: %s" % (chave, e))
            print("%3d/%d %s: FALHOU (%s)" % (i + 1, len(chaves), chave, e), flush=True)

    # segunda passada nos que falharam: quase sempre é 429 de momento, e uma pausa maior resolve
    if erros and not a.dry_run:
        refazer = [e.split(":")[0] for e in erros]
        print("\nsegunda passada em %d lote(s) que falharam" % len(refazer), flush=True)
        erros = []
        for chave in refazer:
            lote = plano[chave]
            time.sleep(a.pausa * 3)
            try:
                novos[chave] = serie_bruta(ses, lote["kws"], lote["geo"], a.desde, fim)
                print("  %s: recuperado" % chave, flush=True)
            except Exception as e:
                erros.append("%s: %s" % (chave, e))
                print("  %s: FALHOU de novo (%s)" % (chave, e), flush=True)

    limite = max(1, int(len(chaves) * FALHAS_TOLERADAS))
    print("\n%d lote(s) coletados, %d falha(s); o limite é %d" % (len(novos), len(erros), limite))
    if len(erros) > limite:
        print("nada gravado: falhas demais, a série ficaria metade nova e metade velha")
        return 1
    if not novos:
        print("nada gravado: nenhum lote respondeu")
        return 1
    if a.dry_run:
        print("nada gravado (--dry-run)")
        return 0

    carimbo = datetime.now(BR).strftime("%-d/%-m/%Y, %-Hh%M de Brasília")
    for chave, csv_novo in novos.items():
        plano[chave]["csv"] = csv_novo
    dump["lotes"] = plano
    dump["coletado"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    dump["fonte"] = ("Google Trends, API interna do explore, geo por estado, %s a %s, diário "
                     "(coleta própria no GitHub Actions, %s)" % (a.desde, fim, carimbo))
    dump["erros"] = erros
    with io.open(caminho, "w", encoding="utf-8", newline="") as f:
        json.dump(dump, f, ensure_ascii=False)
    print("gravado %s (%d lotes atualizados de %d)" % (caminho, len(novos), len(plano)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
