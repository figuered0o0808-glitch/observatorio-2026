# -*- coding: utf-8 -*-
"""Coleta as 27 páginas "Pesquisas eleitorais para a eleição estadual de 2026 em ..." da
Wikipédia em português (mais a distrital do DF) e grava dados/estados/_wiki-pesquisas-estados.json
no mesmo formato que o coletor de navegador produzia, para que dados/estados/_parse_wiki.py
continue lendo sem mudança.

Formato do dump: JSON de uma linha com as chaves coletado (carimbo em America/Sao_Paulo), fonte
('pt.wikipedia.org, action=parse'), paginas (título -> texto compacto) e revisoes (título ->
{pageid, revid}), esta última acrescentada por este script para saber, na coleta seguinte, se a
página mudou. O texto compacto de cada página reproduz o que o navegador fazia com o HTML de
action=parse&prop=text|revid:

  @@PAGE <título> revid=<N>            primeira linha
  ## a > b > c                          caminho dos títulos h2 a h5 até cada table.wikitable
  CAP <legenda>                         só quando a tabela tem <caption>, mesmo vazio
  cel | cel | cel                       uma linha por <tr>, células separadas por ' | ',
                                        colspan e rowspan expandidos repetindo o conteúdo,
                                        prefixo 'H:' em toda célula <th>

O texto de cada célula é o textContent do elemento (sem separador entre elementos inline, por
isso 'Arthur HenriquePL'), sem as referências <sup class="reference">, com toda sequência de
espaço em branco reduzida a um espaço e aparada nas pontas. Diferente do navegador, o conteúdo
de <style> e <script> é descartado, para o CSS de tooltips não vazar para dentro das células.
O teste testes/test_extrator_wikipedia.py confere o extrator contra o dump de 02/09/2026 a
partir do HTML real das mesmas revisões, em testes/fixtures/wikipedia/.

Modo online (padrão): lista as páginas por prefixsearch, consulta pageid e última revisão de
todas numa chamada só, reparseia apenas as páginas cuja revisão mudou desde o dump anterior e
reaproveita o texto das demais. A ordem das páginas no JSON é a do dump anterior; página nova
entra no fim. HTTP 200 com corpo de erro próprio da página (inexistente, título inválido) vira o
valor 'ERRO ...' para aquela página, como o roteiro de coleta prevê. Erro transitório da API
(maxlag esgotado, internal_api_error, readonly), HTTP 429, 500, 502, 503, 504 ou falha de rede
que persista depois das tentativas mantém o texto anterior da página quando existe, para um
atraso de replicação na Wikimedia não apagar uma UF do CSV.

O reaproveitamento só vale quando o dump anterior foi gravado por este script (tem a chave
revisoes) e o texto anterior não carrega o CSS vazado do navegador; o dump de 02/09/2026, feito
no navegador, é reparseado inteiro na primeira coleta, mesmo sem --tudo. Dump anterior ilegível
(JSON truncado, por exemplo) aborta com código 2 sem gravar nada; --anterior "" coleta sem ele.

Uso:
  python3 coleta/wikipedia_pesquisas_estados.py                     coleta online, grava em dados/estados/
  python3 coleta/wikipedia_pesquisas_estados.py --saida /tmp/x.json  grava em outro lugar
  python3 coleta/wikipedia_pesquisas_estados.py --tudo               reparseia todas, ignorando revid
  python3 coleta/wikipedia_pesquisas_estados.py --fixtures testes/fixtures/wikipedia --revisao dump
                                                                     modo offline, a partir do HTML gravado

Só biblioteca padrão (Python 3.9 ou mais novo).
"""
import argparse
import datetime as dt
import gzip
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA_PADRAO = os.path.join(RAIZ, "dados", "estados", "_wiki-pesquisas-estados.json")

API = "https://pt.wikipedia.org/w/api.php"
UA = "observatorio-2026/0.3 (coleta automática; contato: figuered0o0808@gmail.com)"
FONTE = "pt.wikipedia.org, action=parse"
PREFIXO = "Pesquisas eleitorais para a eleição estadual de 2026"
TITULO_DF = "Pesquisas eleitorais para a eleição distrital de 2026 no Distrito Federal"
TENTATIVAS = 5
HTTP_REPETE = (429, 500, 502, 503, 504)
CSS_VAZADO = ".mw-parser-output"  # marca do CSS que o navegador deixava dentro das células

ESTADOS = (
    "Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará", "Distrito Federal", "Espírito Santo", "Goiás",
    "Maranhão", "Mato Grosso do Sul", "Mato Grosso", "Minas Gerais", "Pará", "Paraíba", "Paraná", "Pernambuco",
    "Piauí", "Rio de Janeiro", "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia", "Roraima", "Santa Catarina",
    "São Paulo", "Sergipe", "Tocantins",
)


# ---------------------------------------------------------------------------------------------
# Extrator: HTML de action=parse -> texto compacto
# ---------------------------------------------------------------------------------------------

# elementos HTML sem conteúdo, que nunca abrem escopo
VAZIOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
# a classe \s do JavaScript, que o navegador usava para reduzir o espaço em branco: inclui o espaço
# duro (U+00A0), os espaços tipográficos Unicode, os separadores de linha e parágrafo e o BOM
JS_ESPACO = re.compile("[ \t\n\x0b\x0c\r\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+")


class No:
    """Nó de uma árvore mínima de HTML: tag, atributos, filhos (nós ou strings) e pai."""
    __slots__ = ("tag", "attrs", "filhos", "pai")

    def __init__(self, tag, attrs, pai):
        self.tag = tag
        self.attrs = attrs
        self.filhos = []
        self.pai = pai

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def texto(self, manter_style=False):
        """Equivalente ao textContent do navegador, sem as referências e, por padrão, sem style e script."""
        partes = []
        _coleta_texto(self, partes, manter_style)
        return "".join(partes)


def _coleta_texto(no, partes, manter_style):
    for f in no.filhos:
        if isinstance(f, str):
            partes.append(f)
            continue
        if f.tag == "sup" and "reference" in f.classes():
            continue
        if not manter_style and f.tag in ("style", "script"):
            continue
        _coleta_texto(f, partes, manter_style)


class Arvore(HTMLParser):
    """Monta a árvore a partir do HTML do MediaWiki, que vem bem formado (tags fechadas, br e img auto-fechados)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = No("#raiz", {}, None)
        self.atual = self.raiz

    def handle_starttag(self, tag, attrs):
        no = No(tag, dict(attrs), self.atual)
        self.atual.filhos.append(no)
        if tag not in VAZIOS:
            self.atual = no

    def handle_startendtag(self, tag, attrs):
        self.atual.filhos.append(No(tag, dict(attrs), self.atual))

    def handle_endtag(self, tag):
        if tag in VAZIOS:
            return
        no = self.atual
        while no is not None and no.tag != tag:
            no = no.pai
        if no is not None and no.pai is not None:
            self.atual = no.pai

    def handle_data(self, data):
        self.atual.filhos.append(data)


def normaliza(s):
    return JS_ESPACO.sub(" ", s).strip()


def _titulos_e_tabelas(no, saida):
    """Lista, em ordem de documento, os títulos h2 a h5 e as tabelas com a classe wikitable."""
    for f in no.filhos:
        if isinstance(f, str):
            continue
        if f.tag in ("h2", "h3", "h4", "h5"):
            saida.append(f)
        elif f.tag == "table" and "wikitable" in f.classes():
            saida.append(f)
        _titulos_e_tabelas(f, saida)


def _linhas_da_tabela(tab):
    """Os <tr> da tabela, diretos ou dentro de thead, tbody e tfoot, sem entrar em tabelas aninhadas."""
    linhas = []
    for f in tab.filhos:
        if isinstance(f, str):
            continue
        if f.tag == "tr":
            linhas.append(f)
        elif f.tag in ("thead", "tbody", "tfoot"):
            for g in f.filhos:
                if not isinstance(g, str) and g.tag == "tr":
                    linhas.append(g)
    return linhas


def _span(valor):
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return 1
    return n if n >= 1 else 1


def tabela_compacta(tab, manter_style=False):
    """Expande a tabela numa grade e devolve uma linha de texto por linha da grade.

    Cada célula ocupa rowspan x colspan posições com o mesmo texto. Um rowspan que ultrapassa o
    número real de <tr> cria linhas extras só com as células que transbordaram, como o navegador
    fazia; posição nunca preenchida vira célula vazia."""
    grade = []
    for r, tr in enumerate(_linhas_da_tabela(tab)):
        while len(grade) <= r:
            grade.append([])
        c = 0
        for cel in tr.filhos:
            if isinstance(cel, str) or cel.tag not in ("td", "th"):
                continue
            while c < len(grade[r]) and grade[r][c] is not None:
                c += 1
            rs = _span(cel.attrs.get("rowspan"))
            cs = _span(cel.attrs.get("colspan"))
            txt = normaliza(cel.texto(manter_style))
            if cel.tag == "th":
                txt = "H:" + txt
            for i in range(rs):
                while len(grade) <= r + i:
                    grade.append([])
                lin = grade[r + i]
                for j in range(cs):
                    while len(lin) <= c + j:
                        lin.append(None)
                    lin[c + j] = txt
            c += cs
    return [" | ".join("" if x is None else x for x in lin) for lin in grade]


def texto_compacto(html, titulo, revid, manter_style=False):
    """Converte o HTML de action=parse&prop=text de uma página no texto compacto descrito no cabeçalho.

    manter_style=True reproduz o navegador ao pé da letra (o CSS de <style> dentro das células fica
    no texto); é o modo que o teste usa para conferir byte a byte contra o dump de 02/09."""
    arv = Arvore()
    arv.feed(html)
    arv.close()
    itens = []
    _titulos_e_tabelas(arv.raiz, itens)
    saida = ["@@PAGE %s revid=%s" % (titulo, revid)]
    caminho = []  # pilha de (nível, texto) dos títulos abertos
    for el in itens:
        if el.tag != "table":
            nivel = int(el.tag[1])
            while caminho and caminho[-1][0] >= nivel:
                caminho.pop()
            caminho.append((nivel, normaliza(el.texto(manter_style))))
            continue
        saida.append("## " + " > ".join(t for _, t in caminho))
        for f in el.filhos:
            if not isinstance(f, str) and f.tag == "caption":
                saida.append("CAP " + normaliza(f.texto(manter_style)))
        saida.extend(tabela_compacta(el, manter_style))
    return "\n".join(saida)


# ---------------------------------------------------------------------------------------------
# Cliente da MediaWiki API
# ---------------------------------------------------------------------------------------------

class ErroApi(Exception):
    """Falha de transporte ou da própria API, distinta de erro próprio de uma página."""


class DumpInvalido(Exception):
    """O dump anterior existe mas não é JSON legível."""


def erro_transitorio(j):
    """Corpo HTTP 200 cujo erro é da infraestrutura da Wikimedia, não da página pedida."""
    erro = j.get("error") if isinstance(j, dict) else None
    if not erro:
        return None
    code = str(erro.get("code", ""))
    if code == "maxlag" or code == "readonly" or code.startswith("internal_api_error"):
        return code
    return None


def _retry_after(cabecalhos, padrao):
    v = cabecalhos.get("Retry-After") if cabecalhos is not None else None
    if v is None:
        return padrao
    try:
        return max(1, int(v.strip()))
    except ValueError:
        return padrao


class Api:
    """Uma requisição por vez, User-Agent identificado, maxlag=5, espera em 429, 503 e maxlag."""

    def __init__(self, base=API, timeout=90, log=print):
        self.base = base
        self.timeout = timeout
        self.log = log
        self.requisicoes = 0

    def get(self, params):
        params = dict(params, format="json", formatversion="2", maxlag="5")
        url = self.base + "?" + urllib.parse.urlencode(params)
        for tentativa in range(1, TENTATIVAS + 1):
            self.requisicoes += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as h:
                    corpo = h.read()
                    cabecalhos = h.headers
            except urllib.error.HTTPError as e:
                if e.code in HTTP_REPETE and tentativa < TENTATIVAS:
                    espera = _retry_after(e.headers, 5 * tentativa)
                    self.log("  HTTP %d, esperando %d s (tentativa %d)" % (e.code, espera, tentativa))
                    time.sleep(espera)
                    continue
                raise ErroApi("HTTP %d em %s" % (e.code, params.get("action")))
            except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
                if tentativa < TENTATIVAS:
                    espera = 5 * tentativa
                    self.log("  falha de rede (%s), esperando %d s (tentativa %d)" % (e, espera, tentativa))
                    time.sleep(espera)
                    continue
                raise ErroApi("falha de rede em %s: %s" % (params.get("action"), e))
            try:
                j = json.loads(corpo.decode("utf-8"))
            except ValueError:
                raise ErroApi("resposta não é JSON em %s" % params.get("action"))
            code = erro_transitorio(j)
            if code is None:
                return j
            if tentativa < TENTATIVAS:
                espera = _retry_after(cabecalhos, 5 * tentativa)
                self.log("  %s, esperando %d s (tentativa %d)" % (code, espera, tentativa))
                time.sleep(espera)
                continue
            # erro da infraestrutura que persistiu: é falha da coleta, nunca da página
            raise ErroApi("%s persistente em %s: %s" % (code, params.get("action"), j["error"].get("info", "")))
        raise ErroApi("esgotadas as tentativas em %s" % params.get("action"))


def uf_do_titulo(titulo):
    for nome in sorted(ESTADOS, key=len, reverse=True):
        if titulo.endswith(nome):
            return nome
    return None


def listar_titulos(api, log=print):
    """Títulos das páginas estaduais pelo prefixsearch, mais a do DF, que não casa com o prefixo."""
    j = api.get({"action": "query", "list": "prefixsearch", "pssearch": PREFIXO, "pslimit": "100"})
    if "error" in j:
        raise ErroApi("prefixsearch: %s" % j["error"].get("info"))
    titulos = []
    for r in j.get("query", {}).get("prefixsearch", []):
        t = r.get("title", "")
        if r.get("ns", 0) != 0:
            continue
        if "/" in t:
            log("  ignorada (subpágina, uf_do_titulo não a reconhece ainda): %s" % t)
            continue
        if uf_do_titulo(t) is None:
            log("  ignorada (título não termina com nome de estado): %s" % t)
            continue
        titulos.append(t)
    if TITULO_DF not in titulos:
        titulos.append(TITULO_DF)
    return titulos


def info_paginas(api, titulos):
    """pageid e última revisão de cada título, numa chamada só (até 50 títulos); resolve redirecionamentos.

    Devolve {título pedido: {"titulo": título real, "pageid": N, "revid": N}} ou {"titulo": ..., "faltando": True}."""
    saida = {}
    for i in range(0, len(titulos), 50):
        lote = titulos[i:i + 50]
        j = api.get({"action": "query", "prop": "info", "titles": "|".join(lote), "redirects": "1"})
        if "error" in j:
            raise ErroApi("prop=info: %s" % j["error"].get("info"))
        q = j.get("query", {})
        real = {}
        for n in q.get("normalized", []):
            real[n["from"]] = n["to"]
        for r in q.get("redirects", []):
            real[r["from"]] = r["to"]
        por_titulo = {p.get("title"): p for p in q.get("pages", [])}
        for t in lote:
            alvo = t
            visto = set()
            while alvo in real and alvo not in visto:
                visto.add(alvo)
                alvo = real[alvo]
            p = por_titulo.get(alvo)
            if p is None or p.get("missing") or p.get("invalid"):
                saida[t] = {"titulo": alvo, "faltando": True}
            else:
                saida[t] = {"titulo": alvo, "pageid": p.get("pageid"), "revid": p.get("lastrevid")}
    return saida


def parsear_pagina(api, titulo):
    """HTML e revid de uma página. Devolve (html, revid) ou (None, mensagem 'ERRO ...').

    Só erro próprio da página chega aqui como corpo 'error' (missingtitle, invalidtitle,
    permissiondenied); os transitórios já viraram ErroApi dentro de Api.get."""
    j = api.get({"action": "parse", "page": titulo, "prop": "text|revid"})
    if erro_transitorio(j):
        raise ErroApi("%s em parse de %s" % (erro_transitorio(j), titulo))
    if "error" in j:
        e = j["error"]
        return None, "ERRO %s: %s" % (e.get("code", "?"), e.get("info", ""))
    p = j.get("parse") or {}
    html = p.get("text")
    if isinstance(html, dict):  # formatversion=1, por precaução
        html = html.get("*")
    if not html or "revid" not in p:
        return None, "ERRO resposta sem text ou revid"
    return html, p["revid"]


# ---------------------------------------------------------------------------------------------
# Dump: leitura do anterior, montagem e gravação
# ---------------------------------------------------------------------------------------------

def agora_sao_paulo():
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Sao_Paulo")
    except Exception:  # sem base de fusos na máquina: Brasília é -03:00 fixo desde 2019
        tz = dt.timezone(dt.timedelta(hours=-3))
    return dt.datetime.now(tz).replace(microsecond=0)


def ler_dump(caminho):
    """Dump anterior, ou None quando o caminho é vazio ou não existe. JSON ilegível levanta DumpInvalido."""
    if not caminho or not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as f:
            j = json.load(f)
    except (ValueError, UnicodeDecodeError) as e:
        raise DumpInvalido("%s não é JSON legível (%s)" % (caminho, e))
    if not isinstance(j, dict) or not isinstance(j.get("paginas"), dict):
        raise DumpInvalido("%s não tem a chave paginas" % caminho)
    return j


def revid_do_texto(texto):
    if not isinstance(texto, str):
        return None
    m = re.match(r"@@PAGE .* revid=(\d+)\s*$", texto.split("\n", 1)[0])
    return int(m.group(1)) if m else None


def revisao_anterior(anterior, titulo):
    """(pageid, revid) que o dump anterior guarda para o título; revid vem da chave revisoes ou da 1ª linha."""
    if anterior is None:
        return None, None
    r = (anterior.get("revisoes") or {}).get(titulo) or {}
    texto = anterior["paginas"].get(titulo)
    revid = r.get("revid")
    if revid is None:
        revid = revid_do_texto(texto)
    return r.get("pageid"), revid


def ordenar_titulos(anterior, novos):
    """Ordem do dump anterior primeiro (é a ordem das linhas do CSV), títulos novos no fim."""
    ordem = list(anterior["paginas"].keys()) if anterior else []
    for t in novos:
        if t not in ordem:
            ordem.append(t)
    return ordem


def gravar_dump(caminho, paginas, revisoes, coletado):
    """Grava num arquivo temporário na mesma pasta e troca no fim, para uma interrupção não deixar o dump truncado."""
    obj = {"coletado": coletado, "fonte": FONTE, "paginas": paginas, "revisoes": revisoes}
    caminho = os.path.abspath(caminho)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    os.replace(tmp, caminho)


def coletar_online(anterior, tudo=False, pausa=0.5, log=print):
    api = Api(log=log)
    log("listando páginas por prefixsearch")
    listados = listar_titulos(api, log)
    titulos = ordenar_titulos(anterior, listados)
    log("%d títulos (%d listados agora, %d do dump anterior)" % (len(titulos), len(listados), len(anterior["paginas"]) if anterior else 0))
    info = info_paginas(api, titulos)

    paginas = {}
    revisoes = {}
    resumo = {"reaproveitada": 0, "reparseada": 0, "erro": 0, "mantida_por_falha": 0}
    vistos = set()  # pageids já gravados, para um título antigo e um novo da mesma página não duplicarem
    for t in titulos:
        i = info.get(t) or {"titulo": t, "faltando": True}
        chave = i["titulo"]  # título real (depois de redirecionamento), que vira a chave do dump
        _, revid_ant = revisao_anterior(anterior, t)
        texto_ant = anterior["paginas"].get(t) if anterior else None
        if i.get("faltando"):
            paginas[chave] = "ERRO página não encontrada na Wikipédia (%s)" % t
            revisoes[chave] = {"pageid": None, "revid": None}
            resumo["erro"] += 1
            log("  ERRO  %s: não encontrada" % t)
            continue
        if i["pageid"] in vistos:
            log("  ignorada, mesma página já gravada sob outro título: %s -> %s" % (t, chave))
            continue
        vistos.add(i["pageid"])
        if chave != t:
            log("  renomeada: %s -> %s" % (t, chave))
        # só reaproveita texto gravado por este script (chave revisoes) e sem o CSS que o navegador deixava
        reaproveita = (not tudo and anterior is not None and isinstance(anterior.get("revisoes"), dict)
                       and revid_ant == i["revid"] and isinstance(texto_ant, str)
                       and not texto_ant.startswith("ERRO") and CSS_VAZADO not in texto_ant)
        if reaproveita:
            paginas[chave] = texto_ant
            revisoes[chave] = {"pageid": i["pageid"], "revid": i["revid"]}
            resumo["reaproveitada"] += 1
            log("  igual %s revid %s" % (uf_do_titulo(chave), i["revid"]))
            continue
        transporte = False  # falha de rede, HTTP ou erro transitório da API, distinta de erro próprio da página
        try:
            html, revid = parsear_pagina(api, chave)
        except ErroApi as e:
            html, revid, transporte = None, "ERRO %s" % e, True
        if html is None:
            if transporte and isinstance(texto_ant, str) and not texto_ant.startswith("ERRO"):
                # a rede falhou depois das tentativas; o texto da revisão anterior continua verdadeiro
                paginas[chave] = texto_ant
                revisoes[chave] = {"pageid": i["pageid"], "revid": revid_ant}
                resumo["mantida_por_falha"] += 1
                log("  FALHA %s (%s); mantido o texto do revid %s" % (uf_do_titulo(chave), revid, revid_ant))
            else:
                paginas[chave] = revid
                revisoes[chave] = {"pageid": i["pageid"], "revid": None}
                resumo["erro"] += 1
                log("  ERRO  %s: %s" % (uf_do_titulo(chave), revid))
        else:
            paginas[chave] = texto_compacto(html, chave, revid)
            revisoes[chave] = {"pageid": i["pageid"], "revid": revid}
            resumo["reparseada"] += 1
            log("  nova  %s revid %s -> %s (%d linhas)" % (uf_do_titulo(chave), revid_ant, revid, paginas[chave].count("\n") + 1))
        if pausa > 0:
            time.sleep(pausa)
    resumo["requisicoes"] = api.requisicoes
    return paginas, revisoes, resumo


def coletar_fixtures(pasta, revisao, anterior, log=print):
    """Modo offline: lê o HTML gravado em testes/fixtures/wikipedia/ (índice em indice.json)."""
    with open(os.path.join(pasta, "indice.json"), encoding="utf-8") as f:
        indice = json.load(f)
    est = indice.get("estaduais", {})
    titulos = ordenar_titulos(anterior, list(est.keys()))
    paginas = {}
    revisoes = {}
    resumo = {"reparseada": 0, "erro": 0}
    for t in titulos:
        e = est.get(t)
        if e is None:
            paginas[t] = "ERRO sem fixture para a página"
            revisoes[t] = {"pageid": None, "revid": None}
            resumo["erro"] += 1
            log("  ERRO  %s: sem fixture" % t)
            continue
        arq = e["arquivo_dump"] if revisao == "dump" else e["arquivo_atual"]
        revid = e["revid_dump"] if revisao == "dump" else e["revid_atual"]
        with gzip.open(os.path.join(pasta, arq), "rt", encoding="utf-8") as f:
            html = f.read()
        paginas[t] = texto_compacto(html, t, revid)
        revisoes[t] = {"pageid": None, "revid": revid}
        resumo["reparseada"] += 1
        log("  %s revid %s (%d linhas)" % (uf_do_titulo(t), revid, paginas[t].count("\n") + 1))
    return paginas, revisoes, resumo


def main(argv=None):
    ap = argparse.ArgumentParser(description="Coleta as páginas estaduais de pesquisas da Wikipédia em texto compacto.")
    ap.add_argument("--saida", default=SAIDA_PADRAO, help="arquivo JSON a gravar (padrão: dados/estados/_wiki-pesquisas-estados.json)")
    ap.add_argument("--anterior", default=None, help="dump anterior a reaproveitar (padrão: o próprio --saida, ou o dump em dados/estados/); \"\" coleta sem ele")
    ap.add_argument("--tudo", action="store_true", help="reparseia todas as páginas, mesmo sem mudança de revisão")
    ap.add_argument("--pausa", type=float, default=0.5, help="segundos entre chamadas de parse (padrão 0,5)")
    ap.add_argument("--fixtures", default=None, help="pasta com o HTML gravado (modo offline)")
    ap.add_argument("--revisao", choices=("dump", "atual"), default="atual", help="no modo offline, qual revisão ler (padrão: atual)")
    a = ap.parse_args(argv)

    anterior_caminho = a.anterior
    if anterior_caminho is None:
        anterior_caminho = a.saida if os.path.exists(a.saida) else SAIDA_PADRAO
    try:
        anterior = ler_dump(anterior_caminho)
    except DumpInvalido as e:
        print("dump anterior ilegível, nada gravado:", e)
        print('restaure o arquivo (git checkout) ou passe --anterior "" para coletar sem ele')
        return 2
    print("dump anterior: %s (%d páginas)" % (anterior_caminho if anterior else "nenhum", len(anterior["paginas"]) if anterior else 0))

    try:
        if a.fixtures:
            print("modo offline: %s, revisão %s" % (a.fixtures, a.revisao))
            paginas, revisoes, resumo = coletar_fixtures(a.fixtures, a.revisao, anterior)
        else:
            paginas, revisoes, resumo = coletar_online(anterior, tudo=a.tudo, pausa=a.pausa)
    except ErroApi as e:
        print("coleta abortada, nada gravado:", e)
        return 2

    coletado = agora_sao_paulo().isoformat()
    gravar_dump(a.saida, paginas, revisoes, coletado)
    erros = sum(1 for v in paginas.values() if not isinstance(v, str) or v.startswith("ERRO"))
    print("resumo:", ", ".join("%s %s" % (k, v) for k, v in resumo.items()))
    print("gravado %s: %d páginas, %d com ERRO, coletado %s" % (a.saida, len(paginas), erros, coletado))
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
