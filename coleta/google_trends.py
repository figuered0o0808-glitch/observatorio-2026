# -*- coding: utf-8 -*-
"""Série de busca no Google Trends para os nomes e termos nacionais.

Sondado em 7/9/2026: a API interna do Trends responde 200 a um runner do GitHub desde que a
sessão pegue antes os cookies da página (o 429 que a sonda de 6/9 registrou era chamada sem
cookie). É o mesmo caminho que o navegador do Mac usava, e por isso o arquivo continua com o
mesmo formato; muda só quem faz a chamada.

O índice do Trends é relativo: 100 é o pico da janela pedida, dentro do lote consultado. Como a
janela cresce um dia a cada coleta, o denominador muda e a série inteira é regravada a cada
execução, não acrescentada. É por isso que dados/trends-2026.csv sai da lista de intocáveis do
guarda e entra como arquivo regravado.

Lotes (os mesmos da coleta de navegador, para a série não trocar de escala):
  candidatos_a  Lula, Flávio Bolsonaro, Augusto Cury, Renan Santos, Ronaldo Caiado
  candidatos_b  Lula, Pablo Marçal, Romeu Zema, Samara Martins   (Lula é a âncora comum)
  termos        eleições 2026, como votar, propostas Augusto Cury,
                Augusto Cury é de esquerda ou direita
O gerador lê Lula do lote A e ignora o Lula do lote B, que serve só de âncora.

Uso:
  python3 coleta/google_trends.py                  # regrava dados/trends-2026.csv
  python3 coleta/google_trends.py --dry-run        # só mostra o que faria
  python3 coleta/google_trends.py --ate 2026-09-06 # fecha a janela numa data
"""
import argparse, csv, io, json, os, sys, time, urllib.parse, urllib.request, urllib.error
import http.cookiejar
from datetime import datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA = os.path.join("dados", "trends-2026.csv")
INICIO = "2026-01-01"
GEO = "BR"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
BR = timezone(timedelta(hours=-3))
COLUNAS = ["data", "lote", "termo", "indice", "geo", "janela", "fonte", "url_fonte", "observacao"]
OBS = ("índice relativo ao máximo da janela e ao lote da consulta; a série inteira é regravada "
       "a cada coleta porque a janela muda o denominador")

LOTES = [
    ("candidatos_a", ["Lula", "Flávio Bolsonaro", "Augusto Cury", "Renan Santos", "Ronaldo Caiado"]),
    ("candidatos_b", ["Lula", "Pablo Marçal", "Romeu Zema", "Samara Martins"]),
    ("termos", ["eleições 2026", "como votar", "propostas Augusto Cury",
                "Augusto Cury é de esquerda ou direita"]),
]


class ErroTrends(Exception):
    pass


class Sessao(object):
    """Sessão com cookie: sem os cookies da página inicial o Google devolve 429 na API."""

    def __init__(self, pausa=6.0, tentativas=4):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.pausa = pausa
        self.tentativas = tentativas
        self.aquecida = False

    def _abrir(self, url, cab=None, timeout=30):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9",
            "Accept": "application/json, text/plain, */*", **(cab or {})})
        return self.op.open(req, timeout=timeout)

    def aquecer(self):
        """Visita a página do Trends para receber os cookies da sessão."""
        with self._abrir("https://trends.google.com/trends/?geo=%s" % GEO,
                         {"Accept": "text/html,application/xhtml+xml"}) as r:
            r.read(2000)
        self.aquecida = True

    def json(self, url, cab=None):
        """GET que devolve JSON; o Trends prefixa a resposta com )]}' ou )]}',"""
        if not self.aquecida:
            self.aquecer()
        ultimo = None
        for tentativa in range(1, self.tentativas + 1):
            try:
                with self._abrir(url, cab) as r:
                    bruto = r.read().decode("utf-8", "replace")
                corte = bruto.find("{")
                if corte < 0:
                    raise ErroTrends("resposta sem JSON: %s" % bruto[:120])
                return json.loads(bruto[corte:])
            except urllib.error.HTTPError as e:
                ultimo = "HTTP %s" % e.code
                if e.code in (429, 500, 502, 503):
                    espera = self.pausa * tentativa * 2
                    print("  %s; esperando %.0fs e tentando de novo (%d de %d)"
                          % (ultimo, espera, tentativa, self.tentativas), flush=True)
                    time.sleep(espera)
                    self.aquecida = False
                    continue
                raise ErroTrends("%s em %s" % (ultimo, url[:90]))
            except Exception as e:
                ultimo = type(e).__name__ + ": " + str(e)[:120]
                time.sleep(self.pausa * tentativa)
        raise ErroTrends("desisti depois de %d tentativas (%s)" % (self.tentativas, ultimo))


def serie_do_lote(ses, termos, inicio, fim):
    """Devolve {termo: {data: indice}} para um lote, com uma consulta ao Trends."""
    periodo = "%s %s" % (inicio, fim)
    req = {"comparisonItem": [{"keyword": t, "geo": GEO, "time": periodo} for t in termos],
           "category": 0, "property": ""}
    url = ("https://trends.google.com/trends/api/explore?hl=pt-BR&tz=180&req="
           + urllib.parse.quote(json.dumps(req, ensure_ascii=False), safe=""))
    dados = ses.json(url, {"Referer": "https://trends.google.com/trends/explore"})
    widget = None
    for w in dados.get("widgets", []):
        if w.get("id") == "TIMESERIES":
            widget = w
            break
    if not widget:
        raise ErroTrends("o Trends não devolveu o widget TIMESERIES")
    url2 = ("https://trends.google.com/trends/api/widgetdata/multiline?hl=pt-BR&tz=180&req="
            + urllib.parse.quote(json.dumps(widget["request"], ensure_ascii=False), safe="")
            + "&token=" + urllib.parse.quote(widget["token"], safe=""))
    linha = ses.json(url2, {"Referer": "https://trends.google.com/trends/explore"})
    pontos = linha.get("default", {}).get("timelineData", [])
    if not pontos:
        raise ErroTrends("série vazia para %s" % ", ".join(termos))
    out = {t: {} for t in termos}
    for p in pontos:
        try:
            dia = datetime.fromtimestamp(int(p["time"]), timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            continue
        valores = p.get("value") or []
        for i, t in enumerate(termos):
            if i < len(valores) and valores[i] is not None:
                out[t][dia] = int(valores[i])
    return out


def montar_linhas(coletas, inicio, fim, carimbo):
    janela = "%s a %s, diário" % (inicio, fim)
    fonte = "Google Trends, coleta própria no GitHub Actions (%s)" % carimbo
    url = ("https://trends.google.com/trends/explore?date=%s%%20%s&geo=%s"
           % (inicio, fim, GEO))
    linhas = []
    for lote, termos in LOTES:
        serie = coletas[lote]
        for termo in termos:
            for dia in sorted(serie.get(termo, {})):
                linhas.append([dia, lote, termo, str(serie[termo][dia]), GEO, janela, fonte, url, OBS])
    return linhas


def gravar(caminho, linhas):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(COLUNAS)
    for l in linhas:
        w.writerow(l)
    with io.open(caminho, "wb") as f:
        f.write(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Série do Google Trends para os termos nacionais")
    ap.add_argument("--raiz", default=RAIZ)
    ap.add_argument("--saida", default=None)
    ap.add_argument("--desde", default=INICIO, help="primeiro dia da janela (padrão 2026-01-01)")
    ap.add_argument("--ate", default=None, help="último dia da janela (padrão: ontem em Brasília)")
    ap.add_argument("--pausa", type=float, default=6.0, help="segundos entre lotes")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    hoje = datetime.now(BR).date()
    fim = a.ate or (hoje - timedelta(days=1)).isoformat()
    saida = a.saida or os.path.join(a.raiz, SAIDA)
    carimbo = datetime.now(BR).strftime("%-d/%-m/%Y, %-Hh%M de Brasília")

    ses = Sessao(pausa=a.pausa)
    coletas, falhas = {}, []
    for i, (lote, termos) in enumerate(LOTES):
        if i:
            time.sleep(a.pausa)
        print("lote %s: %s" % (lote, ", ".join(termos)), flush=True)
        try:
            coletas[lote] = serie_do_lote(ses, termos, a.desde, fim)
            n = sum(len(v) for v in coletas[lote].values())
            print("  %d pontos, até %s" % (n, max(max(v) for v in coletas[lote].values() if v)), flush=True)
        except Exception as e:
            falhas.append("%s: %s" % (lote, e))
            print("  FALHOU: %s" % e, flush=True)

    if falhas:
        print("\nnada gravado: %d lote(s) falharam e a série só faz sentido inteira" % len(falhas))
        for f in falhas:
            print("  " + f)
        return 1

    linhas = montar_linhas(coletas, a.desde, fim, carimbo)
    dias = sorted({l[0] for l in linhas})
    print("\n%d linhas, %d termos, de %s a %s" % (len(linhas), len({l[2] for l in linhas}), dias[0], dias[-1]))
    if a.dry_run:
        print("nada gravado (--dry-run)")
        return 0
    gravar(saida, linhas)
    print("gravado %s" % saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
