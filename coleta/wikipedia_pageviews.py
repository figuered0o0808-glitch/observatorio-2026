# -*- coding: utf-8 -*-
"""Acréscimo diário das séries de acessos à Wikipédia, nacional e estadual.

Lê a lista congelada de verbetes (dados/candidatos.csv, coluna wikipedia_titulo, e
dados/estados/wikipedia-verbetes-estados.csv, status "aceito"), pede à API REST da
Wikimedia os acessos diários de cada verbete numa janela de dias fechados e acrescenta
aos dois CSVs só as chaves que ainda não existem. Nunca altera nem remove linha antiga,
nunca rebusca verbete e nunca chama a API de busca da Wikipédia: quem decide qual verbete
vale para cada candidatura é a conferência humana registrada nos dois arquivos de entrada.

Arquivos gravados (contrato exato dos arquivos já existentes):
  dados/wikipedia-pageviews.csv        data,candidato,artigo,pageviews,fonte,url_fonte,observacao
                                       chave (data, candidato); mantido ordenado por (data, candidato)
  dados/estados/wikipedia-estados.csv  data,uf,slug,verbete,pageviews,fonte
                                       chave (data, uf, slug); linhas antigas ficam na ordem em que
                                       estão e as novas entram no fim, ordenadas por (data, uf, slug)

Regras de dado: UTF-8 com BOM e CRLF; toda linha nova leva a fonte por extenso com a data da
coleta em Brasília; zero devolvido pela API é valor observado e é gravado como 0; dia que a API
omite não gera linha (é indisponível, nunca 0); 404 significa "sem dados no período" e não é erro.

Janela padrão: os últimos quatro dias fechados em Brasília (T-4 a T-1). A API fecha o dia anterior
por volta das 6h UTC, e pedir quatro dias absorve correções e uma execução perdida.

Uso:
  python3 coleta/wikipedia_pageviews.py                          janela padrão, os dois arquivos
  python3 coleta/wikipedia_pageviews.py --desde 2026-09-02        preenche de 2 de setembro até T-1
  python3 coleta/wikipedia_pageviews.py --desde 2026-09-02 --ate 2026-09-05
  python3 coleta/wikipedia_pageviews.py --so nacional             só dados/wikipedia-pageviews.csv
  python3 coleta/wikipedia_pageviews.py --raiz /outra/copia       lê e grava numa cópia do projeto
  python3 coleta/wikipedia_pageviews.py --offline pasta           lê respostas JSON de uma pasta
                                                                  (pageviews-<Título_com_sublinhado>.json;
                                                                  arquivo ausente vale por 404)

A variável de ambiente OBSERVATORIO_RAIZ equivale a --raiz. Só biblioteca padrão (Python 3.9+).
Código de saída 0 quando a coleta correu; 1 quando um arquivo de entrada falta ou está fora do
contrato, ou quando nenhum verbete respondeu (rede ou API fora do ar).
"""
import argparse
import csv
import datetime as dt
import email.utils
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "observatorio-2026/0.3 (coleta automática; contato: figuered0o0808@gmail.com)"
REST = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/pt.wikipedia/"
        "all-access/user/{artigo}/daily/{desde}/{ate}")
FONTE_BASE = "Wikimedia REST API, pageviews per-article, all-access, agente user, coleta própria "
URL_VERBETE = "https://pt.wikipedia.org/wiki/"
PAUSA = 0.3          # segundos entre chamadas
TENTATIVAS = 4       # tentativas por verbete em 429, 5xx ou falha de rede
ESPERA_PADRAO = 5    # segundos de espera quando a resposta não traz Retry-After
ESPERA_MAXIMA = 120  # teto para o Retry-After
TIMEOUT = 60
DIAS_JANELA = 4

COLUNAS_NACIONAL = ["data", "candidato", "artigo", "pageviews", "fonte", "url_fonte", "observacao"]
COLUNAS_ESTADUAL = ["data", "uf", "slug", "verbete", "pageviews", "fonte"]

# texto explicativo que polui o valor de wikipedia_titulo de um candidato em candidatos.csv
RE_URL_CANONICO = re.compile(r"\s*\(URL can[oô]nico[^)]*\)\s*", re.IGNORECASE)


class ErroEntrada(Exception):
    """Arquivo de entrada ausente ou fora do contrato."""


# ------------------------------------------------------------------ datas

def fuso_brasilia():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Sao_Paulo")
    except Exception:  # máquina sem base de fusos: Brasília é -03:00 fixo desde 2019
        return dt.timezone(dt.timedelta(hours=-3))


def hoje_brasilia(agora=None):
    """Data de hoje em Brasília. `agora` (datetime com fuso) serve aos testes."""
    if agora is None:
        agora = dt.datetime.now(dt.timezone.utc)
    return agora.astimezone(fuso_brasilia()).date()


def janela_padrao(hoje):
    """Os últimos quatro dias fechados: T-4 a T-1."""
    return hoje - dt.timedelta(days=DIAS_JANELA), hoje - dt.timedelta(days=1)


def data_iso(texto):
    try:
        return dt.date.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError("data inválida %r, use AAAA-MM-DD" % texto)


# ------------------------------------------------------------------ títulos

def titulo_limpo(valor):
    """Tira o texto "(URL canônico ...)" que polui um valor de candidatos.csv e espaços sobrando."""
    return RE_URL_CANONICO.sub(" ", valor or "").strip()


def artigo_para_api(titulo):
    """Título como a REST espera: espaços viram sublinhado e tudo é percent-encoded."""
    return urllib.parse.quote(titulo.replace(" ", "_"), safe="")


def url_verbete(titulo):
    """URL do verbete como já está gravada no CSV nacional: sublinhados, sem percent-encoding."""
    return URL_VERBETE + titulo.replace(" ", "_")


def nome_arquivo_offline(titulo):
    return "pageviews-" + titulo.replace(" ", "_").replace("/", "%2F") + ".json"


# ------------------------------------------------------------------ CSV

def ler_csv(caminho, colunas):
    """Lê um CSV do dataset (UTF-8 com BOM, CRLF) e confere o cabeçalho."""
    if not os.path.exists(caminho):
        raise ErroEntrada("arquivo não encontrado: %s" % caminho)
    with open(caminho, "r", newline="", encoding="utf-8-sig") as f:
        linhas = list(csv.reader(f))
    if not linhas or linhas[0] != colunas:
        raise ErroEntrada("cabeçalho fora do contrato em %s: esperado %s, veio %s"
                          % (caminho, colunas, linhas[0] if linhas else "arquivo vazio"))
    return linhas[1:]


def gravar_csv(caminho, colunas, linhas):
    """Grava UTF-8 com BOM e CRLF, num arquivo temporário trocado no fim (nunca deixa CSV pela metade)."""
    temp = caminho + ".parcial"
    with open(temp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(colunas)
        w.writerows(linhas)
    os.replace(temp, caminho)


def ler_dicts(caminho):
    if not os.path.exists(caminho):
        raise ErroEntrada("arquivo não encontrado: %s" % caminho)
    with open(caminho, "r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def verbetes_nacionais(raiz):
    """(candidato, título) de candidatos.csv; devolve também quem está sem verbete."""
    linhas = ler_dicts(os.path.join(raiz, "dados", "candidatos.csv"))
    if not linhas or "wikipedia_titulo" not in linhas[0] or "candidato" not in linhas[0]:
        raise ErroEntrada("candidatos.csv sem as colunas candidato e wikipedia_titulo")
    com, sem = [], []
    for r in linhas:
        titulo = titulo_limpo(r["wikipedia_titulo"])
        if titulo:
            com.append((r["candidato"], titulo))
        else:
            sem.append(r["candidato"])
    return com, sem


def verbetes_estaduais(raiz):
    """(uf, slug, verbete) das candidaturas com status aceito, na ordem do arquivo."""
    linhas = ler_dicts(os.path.join(raiz, "dados", "estados", "wikipedia-verbetes-estados.csv"))
    if not linhas or not {"uf", "slug", "verbete", "status"} <= set(linhas[0]):
        raise ErroEntrada("wikipedia-verbetes-estados.csv sem as colunas uf, slug, verbete e status")
    return [(r["uf"], r["slug"], r["verbete"]) for r in linhas
            if r["status"].strip() == "aceito" and r["verbete"].strip()]


# ------------------------------------------------------------------ REST

def _retry_after(cabecalhos):
    """Segundos a esperar segundo o Retry-After (inteiro ou data HTTP); padrão quando não há."""
    valor = cabecalhos.get("Retry-After") if cabecalhos is not None else None
    if not valor:
        return ESPERA_PADRAO
    valor = valor.strip()
    try:
        segundos = int(valor)
    except ValueError:
        try:
            quando = email.utils.parsedate_to_datetime(valor)
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=dt.timezone.utc)
            segundos = (quando - dt.datetime.now(dt.timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            return ESPERA_PADRAO
    return int(min(ESPERA_MAXIMA, max(1, segundos)))


class ClienteRest:
    """Uma requisição por vez, User-Agent identificado, espera em 429 e 5xx respeitando Retry-After."""

    def __init__(self, pausa=PAUSA, log=print, dormir=time.sleep, abrir=urllib.request.urlopen):
        self.pausa = pausa
        self.log = log
        self.dormir = dormir
        self.abrir = abrir
        self.chamadas = 0

    def pageviews(self, titulo, desde, ate):
        """Itens da REST para o verbete na janela. Devolve (itens, situacao).

        situacao: "ok" (lista de itens, pode ser vazia), "404" (sem dados no período) ou o texto
        do erro quando as tentativas se esgotaram.
        """
        url = REST.format(artigo=artigo_para_api(titulo), desde=desde.strftime("%Y%m%d"),
                          ate=ate.strftime("%Y%m%d"))
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        erro = "sem tentativa"
        for tentativa in range(1, TENTATIVAS + 1):
            if self.chamadas:
                self.dormir(self.pausa)
            self.chamadas += 1
            try:
                with self.abrir(req, timeout=TIMEOUT) as resp:
                    corpo = resp.read()
                dados = json.loads(corpo.decode("utf-8"))
                return dados.get("items", []), "ok"
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return [], "404"
                erro = "HTTP %d" % e.code
                if e.code == 429 or e.code >= 500:
                    espera = _retry_after(e.headers)
                    self.log("  %s em %s, esperando %d s (tentativa %d de %d)"
                             % (erro, titulo, espera, tentativa, TENTATIVAS))
                    self.dormir(espera)
                    continue
                return [], erro
            except (urllib.error.URLError, OSError, ValueError) as e:
                erro = "%s: %s" % (type(e).__name__, e)
                espera = ESPERA_PADRAO * tentativa
                self.log("  %s em %s, esperando %d s (tentativa %d de %d)"
                         % (erro, titulo, espera, tentativa, TENTATIVAS))
                self.dormir(espera)
        return [], erro


class ClienteOffline:
    """Lê pageviews-<Título>.json de uma pasta; arquivo ausente vale por 404."""

    def __init__(self, pasta):
        self.pasta = pasta
        self.chamadas = 0

    def pageviews(self, titulo, desde, ate):
        self.chamadas += 1
        caminho = os.path.join(self.pasta, nome_arquivo_offline(titulo))
        if not os.path.exists(caminho):
            return [], "404"
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados.get("items", []), "ok"


def serie_da_resposta(itens, desde, ate):
    """{data: views} dos itens dentro da janela; item malformado ou fora da janela é ignorado."""
    serie = {}
    for item in itens:
        ts = str(item.get("timestamp", ""))
        views = item.get("views")
        if len(ts) < 8 or not ts[:8].isdigit() or not isinstance(views, int):
            continue
        try:
            dia = dt.date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
        except ValueError:
            continue
        if desde <= dia <= ate:
            serie[dia.isoformat()] = views
    return serie


# ------------------------------------------------------------------ coleta

class Coleta:
    def __init__(self, cliente, desde, ate, log=print):
        self.cliente = cliente
        self.desde = desde
        self.ate = ate
        self.log = log
        self.cache = {}
        self.sem_dados = []   # (título, situação) com 404 ou lista vazia
        self.erros = []       # (título, erro)
        self.com_dados = 0    # verbetes que trouxeram pelo menos um dia da janela

    def serie(self, titulo):
        if titulo in self.cache:
            return self.cache[titulo]
        itens, situacao = self.cliente.pageviews(titulo, self.desde, self.ate)
        if situacao == "ok":
            serie = serie_da_resposta(itens, self.desde, self.ate)
            if serie:
                self.com_dados += 1
            else:
                self.sem_dados.append((titulo, "resposta sem dias na janela"))
        elif situacao == "404":
            serie = {}
            self.sem_dados.append((titulo, "404, sem dados no período"))
        else:
            serie = {}
            self.erros.append((titulo, situacao))
        self.cache[titulo] = serie
        return serie


def acrescentar_nacional(raiz, coleta, fonte, log=print):
    caminho = os.path.join(raiz, "dados", "wikipedia-pageviews.csv")
    antigas = ler_csv(caminho, COLUNAS_NACIONAL)
    chaves = {(l[0], l[1]) for l in antigas}
    lista, sem_titulo = verbetes_nacionais(raiz)
    novas = []
    for candidato, titulo in lista:
        for data, views in coleta.serie(titulo).items():
            if (data, candidato) in chaves:
                continue
            chaves.add((data, candidato))
            novas.append([data, candidato, titulo, str(views), fonte, url_verbete(titulo), ""])
    if novas:
        todas = antigas + novas
        todas.sort(key=lambda l: (l[0], l[1]))
        gravar_csv(caminho, COLUNAS_NACIONAL, todas)
    return len(novas), len(lista), sem_titulo


def acrescentar_estadual(raiz, coleta, fonte, log=print):
    caminho = os.path.join(raiz, "dados", "estados", "wikipedia-estados.csv")
    antigas = ler_csv(caminho, COLUNAS_ESTADUAL)
    chaves = {(l[0], l[1], l[2]) for l in antigas}
    lista = verbetes_estaduais(raiz)
    novas = []
    for uf, slug, verbete in lista:
        for data, views in coleta.serie(verbete).items():
            if (data, uf, slug) in chaves:
                continue
            chaves.add((data, uf, slug))
            novas.append([data, uf, slug, verbete, str(views), fonte])
    if novas:
        novas.sort(key=lambda l: (l[0], l[1], l[2]))
        gravar_csv(caminho, COLUNAS_ESTADUAL, antigas + novas)
    return len(novas), len(lista)


def raiz_padrao():
    return os.environ.get("OBSERVATORIO_RAIZ") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Acrescenta aos CSVs os acessos diários aos verbetes dos candidatos na Wikipédia.")
    ap.add_argument("--desde", type=data_iso, default=None, help="primeiro dia da janela (padrão: T-4 em Brasília)")
    ap.add_argument("--ate", type=data_iso, default=None, help="último dia da janela (padrão: T-1 em Brasília)")
    ap.add_argument("--so", choices=("nacional", "estadual"), default=None, help="coletar só um dos arquivos")
    ap.add_argument("--raiz", default=raiz_padrao(), help="pasta do projeto (padrão: a pasta acima de coleta/, ou OBSERVATORIO_RAIZ)")
    ap.add_argument("--offline", default=None, metavar="PASTA", help="ler respostas JSON gravadas nesta pasta em vez de chamar a API")
    ap.add_argument("--pausa", type=float, default=PAUSA, help="segundos entre chamadas à API (padrão 0,3)")
    args = ap.parse_args(argv)

    hoje = hoje_brasilia()
    desde, ate = janela_padrao(hoje)
    if args.ate is not None:
        ate = args.ate
        if ate >= hoje:
            print("aviso: a API só fecha o dia anterior; --ate %s recuado para %s" % (ate, hoje - dt.timedelta(days=1)))
            ate = hoje - dt.timedelta(days=1)
        # sem --desde, a janela continua com o mesmo comprimento, terminando no --ate pedido
        desde = ate - dt.timedelta(days=DIAS_JANELA - 1)
    if args.desde is not None:
        desde = args.desde
    if desde > ate:
        print("erro: --desde %s é posterior a --ate %s" % (desde, ate))
        return 1

    raiz = os.path.abspath(args.raiz)
    fonte = FONTE_BASE + hoje.isoformat()
    if args.offline:
        cliente = ClienteOffline(os.path.abspath(args.offline))
        modo = "offline (%s)" % cliente.pasta
    else:
        cliente = ClienteRest(pausa=args.pausa)
        modo = "Wikimedia REST"
    print("coleta de %s (Brasília), janela %s a %s, modo %s, raiz %s" % (hoje, desde, ate, modo, raiz))
    coleta = Coleta(cliente, desde, ate)

    codigo = 0
    try:
        if args.so != "estadual":
            n, total, sem_titulo = acrescentar_nacional(raiz, coleta, fonte)
            print("dados/wikipedia-pageviews.csv: %d linhas acrescentadas (%d verbetes pedidos)" % (n, total))
            if sem_titulo:
                print("  candidatos sem wikipedia_titulo em candidatos.csv, fora da coleta: %s" % "; ".join(sem_titulo))
        if args.so != "nacional":
            n, total = acrescentar_estadual(raiz, coleta, fonte)
            print("dados/estados/wikipedia-estados.csv: %d linhas acrescentadas (%d verbetes aceitos pedidos)" % (n, total))
    except ErroEntrada as e:
        print("erro: %s" % e)
        return 1

    print("chamadas à API: %d; verbetes com dados na janela: %d" % (cliente.chamadas, coleta.com_dados))
    print("verbetes sem resposta: %d (sem dados no período: %d; erro: %d)"
          % (len(coleta.sem_dados) + len(coleta.erros), len(coleta.sem_dados), len(coleta.erros)))
    for titulo, motivo in coleta.sem_dados:
        print("  sem dados: %s (%s)" % (titulo, motivo))
    for titulo, motivo in coleta.erros:
        print("  erro: %s (%s)" % (titulo, motivo))
    if coleta.erros and not coleta.com_dados and not coleta.sem_dados:
        print("erro: nenhum verbete respondeu; nada foi gravado")
        codigo = 1
    return codigo


if __name__ == "__main__":
    sys.exit(main())
