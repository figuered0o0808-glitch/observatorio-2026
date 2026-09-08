#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pesquisas presidenciais compiladas pela Wikipédia -> dados/pesquisas-registradas.csv

Lê a página "Pesquisas de opinião para a eleição presidencial no Brasil em 2026" da
Wikipédia em português (HTML renderizado de action=parse&prop=text|revid) e acrescenta
ao CSV nacional as rodadas de 2026 que ainda não estão lá. Nunca altera linha existente:
só acrescenta no fim do arquivo, preservando BOM e CRLF.

O que entra: as tabelas mensais da seção "Primeiro turno" (o primeiro cenário de cada
rodada vira "1º turno", os demais "1º turno, cenário N") e, para essas mesmas rodadas,
a linha correspondente da tabela de 2º turno Lula x Flávio Bolsonaro, só para os dois
nomes. A tabela de agregadores (UOL, PollingData etc.) não entra. O que a página não
traz fica em branco (registro no TSE, rejeição, modo de coleta); "<1%", travessão e
"N/A" são ausência e não geram linha; "0%" é zero observado e fica como veio.

Uma rodada da página é considerada já presente no CSV quando existe ali rodada do mesmo
instituto (nomes normalizados, com sinônimos como Apex/Futura ~ Futura Inteligência,
Genial/Quaest ~ Quaest, PoderData/Aya ~ PoderData) com data de fim de campo a até um
dia de diferença ou com a mesma data de divulgação.

Uso:
    python3 coleta/wikipedia_pesquisas_nacional.py --dry-run
    python3 coleta/wikipedia_pesquisas_nacional.py --saida /caminho/fora/de/dados/pesquisas-registradas.csv
    python3 coleta/wikipedia_pesquisas_nacional.py --html testes/fixtures/wikipedia/nacional-atual.html.gz --revid 72935890 --dry-run

Só biblioteca padrão (Python 3.9 ou mais novo). Datas de "hoje" em America/Sao_Paulo.
"""
import argparse
import csv
import email.utils
import gzip
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

TITULO_PAGINA = "Pesquisas de opinião para a eleição presidencial no Brasil em 2026"
API = "https://pt.wikipedia.org/w/api.php"
USER_AGENT = "observatorio-2026/0.3 (coleta automática; contato: figuered0o0808@gmail.com)"
COLUNAS = ["instituto", "data_campo_inicio", "data_campo_fim", "data_divulgacao", "metodologia",
           "cenario", "candidato", "percentual", "rejeicao", "margem_erro", "registro_tse", "url",
           "observacao"]
CENARIO_2T = "2º turno Lula x Flávio Bolsonaro"

# Título do verbete (como aparece no atributo title do link do cabeçalho) -> nome usado no CSV.
CANDIDATOS = {
    "Luiz Inácio Lula da Silva": "Lula", "Lula": "Lula",
    "Flávio Bolsonaro": "Flávio Bolsonaro", "Augusto Cury": "Augusto Cury",
    "Renan Santos": "Renan Santos", "Ronaldo Caiado": "Ronaldo Caiado",
    "Pablo Marçal": "Pablo Marçal", "Romeu Zema": "Romeu Zema",
    "Samara Martins": "Samara Martins", "Wilson Grassi": "Wilson Grassi",
    "Clariana Barão": "Clariana Barão", "Hertz Dias": "Hertz Dias",
    "Edmilson Costa": "Edmilson Costa", "Rui Costa Pimenta": "Rui Costa Pimenta",
    "Jair Bolsonaro": "Jair Bolsonaro", "Michelle Bolsonaro": "Michelle Bolsonaro",
    "Tarcísio de Freitas": "Tarcísio de Freitas", "Ratinho Júnior": "Ratinho Junior",
    "Ratinho Junior": "Ratinho Junior", "Eduardo Leite": "Eduardo Leite",
    "Fernando Haddad": "Fernando Haddad", "Ciro Gomes": "Ciro Gomes",
    "Geraldo Alckmin": "Geraldo Alckmin", "Aldo Rebelo": "Aldo Rebelo",
    "Simone Tebet": "Simone Tebet", "Michel Temer": "Michel Temer",
    "Aécio Neves": "Aécio Neves", "Joaquim Barbosa": "Joaquim Barbosa",
    "Marcos Pontes": "Marcos Pontes", "Damares Alves": "Damares Alves",
    "Tereza Cristina": "Tereza Cristina", "Rogério Marinho": "Rogério Marinho",
    "Cabo Daciolo": "Cabo Daciolo", "Eduardo Bolsonaro": "Eduardo Bolsonaro",
    "Nikolas Ferreira": "Nikolas Ferreira",
}

# Nome do instituto como a página escreve (normalizado) -> nome que o CSV já usa.
SINONIMOS = {
    "verita": "Instituto Veritá", "institutoverita": "Instituto Veritá",
    "apexfutura": "Futura Inteligência (100% Cidades)", "futuraapex": "Futura Inteligência (100% Cidades)",
    "futura": "Futura Inteligência (100% Cidades)", "futurainteligencia": "Futura Inteligência (100% Cidades)",
    "genialquaest": "Quaest", "quaest": "Quaest", "quaestgenial": "Quaest",
    "poderdataaya": "PoderData", "poderdata": "PoderData", "ayapoderdata": "PoderData",
    "nexusbtgpactual": "BTG/Nexus", "nexusbtg": "BTG/Nexus", "btgnexus": "BTG/Nexus", "nexus": "BTG/Nexus",
    "atlasintel": "AtlasIntel/Bloomberg", "atlasintelbloomberg": "AtlasIntel/Bloomberg",
    "bloombergatlasintel": "AtlasIntel/Bloomberg", "atlasinstel": "AtlasIntel/Bloomberg",
    "meioideia": "Ideia (Meio/Ideia)", "ideiameio": "Ideia (Meio/Ideia)", "ideia": "Ideia (Meio/Ideia)",
    "ideiameioideia": "Ideia (Meio/Ideia)",
    "realtimebigdata": "Real Time Big Data", "rtbd": "Real Time Big Data",
    "datafolha": "Datafolha", "gerp": "Gerp", "cntmda": "CNT/MDA", "mdacnt": "CNT/MDA",
    "indexabroadcast": "Indexa/Broadcast", "paranapesquisas": "Paraná Pesquisas",
    "americananalytics": "American Analytics (Times Brasil)",
    "americananalyticstimesbrasil": "American Analytics (Times Brasil)",
}
# Palavras que não distinguem um instituto do outro ao comparar nomes por token.
TOKENS_COMUNS = {"instituto", "pesquisa", "pesquisas", "inteligencia", "cidades", "brasil", "grupo",
                 "de", "do", "da", "dos", "das", "e"}
ABREV = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8,
         "set": 9, "out": 10, "nov": 11, "dez": 12}
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def norm(s):
    """Minúsculas, sem acento, sem nada que não seja letra ou dígito."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def norm_texto(s):
    """Minúsculas e sem acento, preservando espaços e pontuação (para procurar palavras)."""
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def hoje_brasilia():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    except Exception:
        return datetime.now(timezone(timedelta(hours=-3))).date()


# ------------------------------------------------------------------ árvore HTML
VAZIOS = {"br", "img", "hr", "input", "link", "meta", "wbr", "col", "source", "area", "base",
          "param", "track"}


class Nodo:
    __slots__ = ("tag", "attrs", "filhos")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = {k: (v or "") for k, v in (attrs or {}).items()}
        self.filhos = []

    @property
    def classe(self):
        return self.attrs.get("class", "")

    def iterar(self):
        """Todos os nós descendentes (inclusive este), em ordem de documento."""
        pilha = [self]
        while pilha:
            n = pilha.pop()
            yield n
            pilha.extend(reversed([f for f in n.filhos if isinstance(f, Nodo)]))


class Arvore(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = Nodo("raiz")
        self.pilha = [self.raiz]

    def handle_starttag(self, tag, attrs):
        n = Nodo(tag, dict(attrs))
        self.pilha[-1].filhos.append(n)
        if tag not in VAZIOS:
            self.pilha.append(n)

    def handle_startendtag(self, tag, attrs):
        self.pilha[-1].filhos.append(Nodo(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.pilha) - 1, 0, -1):
            if self.pilha[i].tag == tag:
                del self.pilha[i:]
                return

    def handle_data(self, dados):
        if self.pilha[-1].tag in ("style", "script"):
            return
        self.pilha[-1].filhos.append(dados)


def arvore(html):
    p = Arvore()
    p.feed(html)
    p.close()
    return p.raiz


def texto(n, com_refs=False, ignorar=()):
    """Texto visível de um nó: sem <style>, sem as chamadas de referência [n] e sem o
    'editar' das seções; <br> e blocos viram espaço; espaços repetidos colapsam.
    `ignorar` recebe pares (tag, classe) de nós cujo conteúdo fica de fora."""
    partes = []

    def rec(x):
        if isinstance(x, str):
            partes.append(x)
            return
        if x.tag in ("style", "script"):
            return
        if not com_refs and x.tag == "sup" and "reference" in x.classe:
            return
        if x.tag == "span" and "mw-editsection" in x.classe:
            return
        if any(x.tag == t and c in x.classe for t, c in ignorar):
            return
        if x.tag in ("br", "p", "div", "li", "tr", "td", "th"):
            partes.append(" ")
        for f in x.filhos:
            rec(f)
        if x.tag in ("p", "div", "li", "td", "th"):
            partes.append(" ")

    rec(n)
    return re.sub(r"\s+", " ", "".join(partes)).strip()


# ------------------------------------------------------------------ datas e números
def datas(txt, ano):
    """'1 Set - 4 Set', '30 Ago - 2 Set', '27 Ago - 1 Set', '10 Set - 14 - Set', '15 e 19 de
    agosto', '28 de maio a 1 de junho', '13 a 19 março de 2026'. Devolve (início, fim) em
    AAAA-MM-DD ou ('', '') quando não há data legível. O mês do início herda o do fim se
    omitido; se o início cai num mês posterior ao do fim, é do ano anterior (virada de ano)."""
    t = norm_texto(txt.replace("º", "").replace("°", "").replace("ª", ""))
    t = re.sub(r"(\d)[oa]\b", r"\1", t)
    t = re.sub(r"[–—−/]", " ", t).replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip()
    m_ano = re.search(r"\b(20\d\d)\b", t)
    if m_ano:
        ano = int(m_ano.group(1))
        t = t.replace(m_ano.group(1), " ")
    toks = re.findall(r"\b(\d{1,2})\b(?:\s+de\b)?\s*([a-z]{3,9})?", t)
    toks = [(int(d), ABREV.get(m[:3]) if m and m[:3] in ABREV else None) for d, m in toks
            if 1 <= int(d) <= 31]
    if not toks:
        return "", ""
    d_ini, m_ini = toks[0]
    d_fim, m_fim = toks[-1]
    if m_fim is None:
        ms = [ABREV[w[:3]] for w in re.findall(r"[a-z]{3,9}", t) if w[:3] in ABREV]
        if not ms:
            return "", ""
        m_fim = ms[-1]
    if m_ini is None:
        m_ini = m_fim
    if m_ini == m_fim and d_ini > d_fim:
        d_ini, d_fim = d_fim, d_ini
    ano_ini = ano - 1 if m_ini > m_fim else ano
    try:
        ini = date(ano_ini, m_ini, d_ini)
        fim = date(ano, m_fim, d_fim)
    except ValueError:
        return "", ""
    return ini.isoformat(), fim.isoformat()


def data_extenso(txt):
    """Primeira data por extenso ('6 de setembro de 2026') no texto, em AAAA-MM-DD, ou ''."""
    t = norm_texto(txt)
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", t)
    if not m or m.group(2) not in MESES:
        return ""
    try:
        return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return ""


def valor(s):
    """'38,4%' -> '38.4'; '38%' -> '38'; '0%' -> '0'; '1%%' -> '1'; '2,0' -> '2.0'.
    Travessão, '-', 'N/A', vazio e '<1%' são ausência e devolvem None."""
    t = (s or "").replace("\xa0", " ")
    t = re.sub(r"\[[^\]]*\]", "", t).strip()
    if t in ("", "-", "—", "–", "−", "N/A", "n/a", "NA", "?", "—%", "–%"):
        return None
    if t.startswith("<") or t.startswith(">"):
        return None
    t = t.replace("%", "").replace("±", "").replace(" ", "").replace(",", ".").strip()
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    return t


def amostra(s):
    """'3 804' -> '3804'; '2.002' -> '2002'; sem número -> ''."""
    m = re.match(r"\s*(\d[\d\s.\xa0]*)", (s or ""))
    return re.sub(r"\D", "", m.group(1)) if m else ""


def dias_entre(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return None


def perto(a, b, dias=1):
    """As duas datas ISO existem e distam no máximo `dias`."""
    d = dias_entre(a, b)
    return d is not None and d <= dias


# ------------------------------------------------------------------ institutos
def tokens_instituto(nome):
    toks = set(re.findall(r"[a-z]+", norm_texto(nome)))
    return {t for t in toks if len(t) >= 3 and t not in TOKENS_COMUNS}


def nome_canonico(nome_pagina, institutos_csv):
    """Nome a gravar: o que o CSV já usa para o mesmo instituto (tabela SINONIMOS, depois
    igualdade normalizada), senão o nome como está na página. Nome parecido não basta:
    um instituto novo entra com o próprio nome e o aviso de parecidos() vai para o log,
    para o dono decidir se acrescenta um sinônimo."""
    nome_pagina = (nome_pagina or "").strip()
    n = norm(nome_pagina)
    if n in SINONIMOS:
        return SINONIMOS[n]
    for c in institutos_csv:
        if norm(c) == n:
            return c
    return nome_pagina


def casa_instituto(a, b):
    """Mesmo instituto? Igualdade normalizada ou mesmo nome canônico pela tabela SINONIMOS.
    Palavra em comum não casa (Instituto Real não é Real Time Big Data)."""
    na, nb = norm(a), norm(b)
    if na == nb:
        return True
    return norm(SINONIMOS.get(na, a)) == norm(SINONIMOS.get(nb, b))


def parecidos(nome, institutos_csv):
    """Institutos do CSV com alguma palavra distintiva em comum com `nome`, só para avisar."""
    tp = tokens_instituto(nome)
    return [c for c in institutos_csv
            if not c.startswith("Agregador") and tp & tokens_instituto(c)]


# ------------------------------------------------------------------ tabelas
class Celula:
    __slots__ = ("nodo", "linha", "coluna", "colspan", "rowspan")

    def __init__(self, nodo, linha, coluna, colspan, rowspan):
        self.nodo, self.linha, self.coluna, self.colspan, self.rowspan = nodo, linha, coluna, colspan, rowspan


def _inteiro(v, padrao):
    try:
        return max(int(re.sub(r"\D", "", v or "") or padrao), 1)
    except ValueError:
        return padrao


def linhas_da_tabela(tabela):
    trs = []

    def rec(n):
        for f in n.filhos:
            if not isinstance(f, Nodo):
                continue
            if f.tag == "tr":
                trs.append(f)
            elif f.tag in ("thead", "tbody", "tfoot"):
                rec(f)

    rec(tabela)
    return trs


def grade(tabela):
    """Matriz de células com colspan e rowspan expandidos: a mesma Celula aparece em todas
    as posições que ocupa. Posição sem célula fica None."""
    trs = linhas_da_tabela(tabela)
    pos, largura = {}, 0
    for r, tr in enumerate(trs):
        c = 0
        for cel in (f for f in tr.filhos if isinstance(f, Nodo) and f.tag in ("td", "th")):
            while (r, c) in pos:
                c += 1
            cs = min(_inteiro(cel.attrs.get("colspan"), 1), 100)
            rs = min(_inteiro(cel.attrs.get("rowspan"), 1), len(trs) - r)
            celula = Celula(cel, r, c, cs, rs)
            for dr in range(rs):
                for dc in range(cs):
                    pos[(r + dr, c + dc)] = celula
            c += cs
            largura = max(largura, c)
    return [[pos.get((r, c)) for c in range(largura)] for r in range(len(trs))]


def origens(linha):
    vistos, saida = set(), []
    for c in linha:
        if c is not None and id(c) not in vistos:
            vistos.add(id(c))
            saida.append(c)
    return saida


def eh_cabecalho(linha):
    cels = origens(linha)
    return bool(cels) and all(c.nodo.tag == "th" or texto(c.nodo) == "" for c in cels)


def eh_partido(title, href):
    t = norm_texto(title)
    return (t.startswith("partido ") or t.startswith("movimento ") or "partido_pol" in href.lower()
            or t in {"avante", "progressistas", "republicanos", "uniao brasil", "podemos (brasil)",
                     "solidariedade (partido politico)", "cidadania (partido politico)",
                     "rede sustentabilidade", "unidade popular (brasil)", "democrata (brasil)",
                     "democracia crista (brasil)", "novo", "agir (partido politico)", "psol"})


def nome_candidato(celulas):
    """Nome do candidato de uma coluna: o title do primeiro link de verbete (não de arquivo,
    não de partido) nas células de cabeçalho; sem link, o texto antes do primeiro <br>."""
    for cel in celulas:
        for a in cel.nodo.iterar():
            if a.tag != "a":
                continue
            href, title = a.attrs.get("href", ""), a.attrs.get("title", "")
            if not href.startswith("/wiki/") or not title or ":" in href[6:] or eh_partido(title, href):
                continue
            if title.startswith("Ficheiro") or title.startswith("Imagem"):
                continue
            base = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
            return CANDIDATOS.get(title, CANDIDATOS.get(base, base))
    for cel in celulas:
        if cel.nodo.tag != "th":
            continue
        partes = []
        for f in cel.nodo.filhos:
            if isinstance(f, Nodo) and f.tag == "br":
                break
            partes.append(f if isinstance(f, str) else texto(f))
        t = re.sub(r"\s+", " ", "".join(partes)).strip()
        if t:
            return t
    return ""


def classificar_colunas(g, n_cab):
    """Para cada coluna, (papel, nome). Papéis: instituto, campo, amostra, margem, cenario,
    registro, outros, indecisos, candidato, agregador, ignorar."""
    cols = []
    for c in range(len(g[0]) if g else 0):
        celulas, vistos = [], set()
        for r in range(n_cab):
            cel = g[r][c]
            if cel is not None and id(cel) not in vistos:
                vistos.add(id(cel))
                celulas.append(cel)
        txt = " ".join(texto(x.nodo) for x in celulas).strip()
        t = norm_texto(txt)
        papel, nome = "ignorar", txt
        if "agregador" in t:
            papel = "agregador"
        elif re.search(r"\bdatas?\b|\bperiodo\b", t):
            papel = "campo"
        elif re.search(r"\bcontratante\b|\binstituto\b|\bpesquisas?\b|\bempresa\b", t):
            papel = "instituto"
        elif "amostra" in t:
            papel = "amostra"
        elif "margem" in t:
            papel = "margem"
        elif t.startswith("outro"):
            papel = "outros"
        elif any(k in t for k in ("indecis", "absten", "absent", "branco", "nulo", "nao sabe", "nao respond")):
            papel = "indecisos"
        elif any(k in t for k in ("vantagem", "diferenca", "lideranca")):
            papel = "ignorar"
        elif re.match(r"cen(\.|ario)", t):
            papel = "cenario"
        elif "registro" in t or "identificacao" in t:
            papel = "registro"
        else:
            nome_c = nome_candidato(celulas)
            if nome_c:
                papel, nome = "candidato", nome_c
        cols.append((papel, nome))
    return cols


def refs_da_celula(cel):
    ids = []
    for a in cel.nodo.iterar():
        if a.tag == "a" and a.attrs.get("href", "").startswith("#cite_note-"):
            i = a.attrs["href"][1:]
            if i not in ids:
                ids.append(i)
    return ids


def extrair_tabela(tabela, ano):
    """Rodadas de uma table.wikitable: lista de dicionários com instituto_pagina, campo_inicio,
    campo_fim, amostra, margem, registro, refs e cenarios (lista de {candidatos, outros,
    indecisos, rotulo, rotulo_indecisos}). Devolve (rodadas, colunas, motivo_de_descarte)."""
    g = grade(tabela)
    if not g or not g[0]:
        return [], [], "tabela vazia"
    n_cab = 0
    while n_cab < len(g) and eh_cabecalho(g[n_cab]):
        n_cab += 1
    if n_cab == 0 or n_cab == len(g):
        return [], [], "sem cabeçalho ou sem dados"
    cols = classificar_colunas(g, n_cab)
    papeis = [p for p, _ in cols]
    if "agregador" in papeis:
        return [], cols, "agregadores"
    if "instituto" not in papeis or "campo" not in papeis:
        return [], cols, "sem colunas de instituto e data"
    idx = {p: papeis.index(p) for p in ("instituto", "campo", "amostra", "margem", "outros",
                                        "indecisos", "cenario", "registro") if p in papeis}
    cand_cols = [(i, nome) for i, (p, nome) in enumerate(cols) if p == "candidato"]
    if len(cand_cols) < 2:
        return [], cols, "menos de duas colunas de candidato"
    rotulo_indecisos = cols[idx["indecisos"]][1] if "indecisos" in idx else ""

    def celula_texto(linha, papel):
        cel = linha[idx[papel]] if papel in idx else None
        return texto(cel.nodo) if cel is not None else ""

    def ler_cenario(linha):
        cands = []
        for i, nome in cand_cols:
            cel = linha[i]
            v = valor(texto(cel.nodo)) if cel is not None else None
            if v is not None:
                cands.append((nome, v))
        return {"candidatos": cands,
                "outros": valor(celula_texto(linha, "outros")) if "outros" in idx else None,
                "indecisos": valor(celula_texto(linha, "indecisos")) if "indecisos" in idx else None,
                "rotulo": celula_texto(linha, "cenario"), "rotulo_indecisos": rotulo_indecisos}

    rodadas, atual, ultima_cel = [], None, None
    for r in range(n_cab, len(g)):
        linha = g[r]
        if any(c.colspan >= 3 and c.linha == r for c in origens(linha)):
            continue  # linha de evento ("1 Set | O candidato ...")
        cel_i = linha[idx["instituto"]]
        if cel_i is None:
            continue
        if atual is not None and cel_i is ultima_cel:
            atual["cenarios"].append(ler_cenario(linha))
            continue
        inst_txt = texto(cel_i.nodo)
        campo_txt = celula_texto(linha, "campo")
        if not inst_txt or not campo_txt:
            continue
        registro = ""
        m = re.search(r"\b[A-Z]{2}-\d{4,6}/\d{4}\b", inst_txt + " " + celula_texto(linha, "registro"))
        if m:
            registro = m.group(0)
            inst_txt = inst_txt.replace(m.group(0), "").strip(" -,;")
        ini, fim = datas(campo_txt, ano)
        atual = {"instituto_pagina": inst_txt, "campo_texto": campo_txt, "campo_inicio": ini,
                 "campo_fim": fim, "amostra": amostra(celula_texto(linha, "amostra")),
                 "margem": valor(celula_texto(linha, "margem")) or "", "registro": registro,
                 "refs": refs_da_celula(cel_i) + [x for x in refs_da_celula(linha[idx["campo"]])
                                                  if x not in refs_da_celula(cel_i)] if linha[idx["campo"]] else refs_da_celula(cel_i),
                 "cenarios": [ler_cenario(linha)], "linha_tabela": r}
        ultima_cel = cel_i
        rodadas.append(atual)
    return rodadas, cols, ""


# ------------------------------------------------------------------ página inteira
def referencias(raiz):
    """{id do cite_note -> {'url': URL do primeiro link externo (preferindo o que não é
    arquivo do Wayback), 'data': data de publicação em AAAA-MM-DD ou ''}}. A data vem do
    rft.date do COinS (o parâmetro |data= da citação); sem ele, da primeira data por extenso
    do texto da citação, descontadas a data de acesso e as datas dentro dos links (título e
    cópia arquivada); sem nenhuma, fica vazia e completar() usa o fim do campo."""
    saida = {}
    for li in raiz.iterar():
        if li.tag != "li" or not li.attrs.get("id", "").startswith("cite_note-"):
            continue
        corpo = li
        for s in li.iterar():
            if s.tag == "span" and "reference-text" in s.classe:
                corpo = s
                break
        url, primeira, data = "", "", ""
        # O span Z3988 (COinS) vem depois dos links no HTML da MediaWiki, por isso o laço
        # percorre a citação inteira em vez de parar no primeiro link.
        for a in corpo.iterar():
            if a.tag == "a" and "external" in a.classe and a.attrs.get("href", "").startswith("http"):
                h = a.attrs["href"]
                if not primeira:
                    primeira = h
                if not url and "web.archive.org" not in h and "archive.today" not in h:
                    url = h
            if a.tag == "span" and "Z3988" in a.classe and not data:
                q = urllib.parse.parse_qs(a.attrs.get("title", ""))
                for d in q.get("rft.date", []):
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                        data = d
        url = url or primeira
        if not data:
            # Sem |data= na citação, sobra a data por extenso do texto, tirando a data de
            # acesso ('Consultado em ...') e o texto dos links ('Cópia arquivada em ...'),
            # que não são data de publicação. Sem nada, fica vazio e completar() usa o
            # fim do campo.
            t = texto(corpo, ignorar=(("span", "reference-accessdate"), ("a", "external")))
            data = data_extenso(t)
        saida[li.attrs["id"]] = {"url": url, "data": data}
    return saida


def ano_do_caminho(caminho, padrao):
    for t in reversed(caminho):
        anos = re.findall(r"\b(20\d\d)\b", t)
        if anos:
            return int(anos[-1])
    return padrao


def tabelas_com_caminho(raiz):
    """(caminho de títulos h2..h5, nó da table.wikitable) em ordem de documento."""
    caminho = []
    for n in raiz.iterar():
        if n.tag in ("h2", "h3", "h4", "h5"):
            nivel = int(n.tag[1]) - 2
            del caminho[nivel:]
            while len(caminho) < nivel:
                caminho.append("")
            caminho.append(texto(n))
        elif n.tag == "table" and "wikitable" in n.classe:
            yield tuple(caminho), n


def extrair(html, revid=None, ano_padrao=2026):
    """Lê o HTML da página e devolve um dicionário com 'primeiro' (rodadas do 1º turno de
    2026, com secao), 'segundo' (rodadas da tabela Lula x Flávio Bolsonaro), 'refs',
    'descartes' (tabelas puladas e por quê) e 'avisos'."""
    raiz = arvore(html)
    refs = referencias(raiz)
    primeiro, segundo, descartes, avisos = [], [], [], []
    for caminho, tab in tabelas_com_caminho(raiz):
        secao = norm_texto(caminho[0]) if caminho else ""
        if any("agrega" in norm_texto(t) for t in caminho):
            descartes.append((caminho, "seção de agregadores"))
            continue
        ano = ano_do_caminho(caminho, ano_padrao)
        rodadas, cols, motivo = extrair_tabela(tab, ano)
        if motivo:
            descartes.append((caminho, motivo))
            continue
        for rd in rodadas:
            rd["secao"] = " > ".join(caminho)
            if not rd["campo_fim"]:
                avisos.append("data de campo ilegível em %s: %r (%s)" % (rd["secao"], rd["campo_texto"], rd["instituto_pagina"]))
        candidatos = {nome for p, nome in cols if p == "candidato"}
        if "primeiro turno" in secao or secao.startswith("1"):
            primeiro.extend(r for r in rodadas if r["campo_fim"])
        elif "segundo turno" in secao or secao.startswith("2"):
            if candidatos == {"Lula", "Flávio Bolsonaro"}:
                segundo.extend(r for r in rodadas if r["campo_fim"])
            else:
                descartes.append((caminho, "2º turno de outro par: " + ", ".join(sorted(candidatos))))
        else:
            descartes.append((caminho, "fora das seções de 1º e 2º turno"))
    return {"primeiro": primeiro, "segundo": segundo, "refs": refs, "descartes": descartes,
            "avisos": avisos, "revid": revid}


# ------------------------------------------------------------------ CSV
def ler_csv(caminho):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    return linhas


def rodadas_existentes(linhas):
    """Rodadas já no CSV: lista de (instituto, campo_fim, data_divulgacao), sem agregadores."""
    vistas, saida = set(), []
    for r in linhas:
        inst = (r.get("instituto") or "").strip()
        if not inst or inst.startswith("Agregador"):
            continue
        chave = (inst, r.get("data_campo_fim") or "", r.get("data_divulgacao") or "")
        if chave not in vistas:
            vistas.add(chave)
            saida.append(chave)
    return saida


def institutos_do_csv(linhas):
    """Nomes de instituto do CSV, do mais recente para o mais antigo (o último a aparecer
    no arquivo vence no desempate de nome_canonico)."""
    vistos = []
    for r in linhas:
        inst = (r.get("instituto") or "").strip()
        if inst and inst not in vistos:
            vistos.append(inst)
    return vistos


def rodada_presente(rodada, existentes):
    """A rodada da página já está no CSV? Mesmo instituto e fim de campo a até um dia, ou
    mesma data de divulgação. Devolve a chave que casou, ou None."""
    for inst, fim, div in existentes:
        if not casa_instituto(rodada["instituto_pagina"], inst) and not casa_instituto(rodada["instituto"], inst):
            continue
        if perto(rodada["campo_fim"], fim) or (div and div == rodada["data_divulgacao"]):
            return (inst, fim, div)
    return None


def completar(res, institutos_csv, hoje):
    """Preenche em cada rodada do 1º turno: instituto (nome canônico), data_divulgacao, url,
    nota (origem da data) e a rodada de 2º turno correspondente, se houver."""
    for rd in res["primeiro"] + res["segundo"]:
        rd["instituto"] = nome_canonico(rd["instituto_pagina"], institutos_csv)
        ref = next((res["refs"][i] for i in rd["refs"] if i in res["refs"]), None)
        rd["url"] = ref["url"] if ref and ref["url"] else ""
        data_ref = ref["data"] if ref else ""
        if data_ref and data_ref > hoje.isoformat():
            rd["data_divulgacao"] = rd["campo_fim"]
            rd["nota"] = "data de divulgação assumida como o fim do campo (citação datada de %s, no futuro)" % data_ref
        elif data_ref and data_ref >= rd["campo_fim"]:
            rd["data_divulgacao"], rd["nota"] = data_ref, ""
        elif data_ref:
            rd["data_divulgacao"] = rd["campo_fim"]
            rd["nota"] = "data de divulgação assumida como o fim do campo (citação datada de %s)" % data_ref
        else:
            rd["data_divulgacao"] = rd["campo_fim"]
            rd["nota"] = "data de divulgação assumida como o fim do campo (citação sem data)"
    for rd in res["primeiro"]:
        rd["segundo_turno"] = next(
            (s for s in res["segundo"]
             if casa_instituto(rd["instituto_pagina"], s["instituto_pagina"])
             and perto(rd["campo_fim"], s["campo_fim"])
             and (not rd["campo_inicio"] or not s["campo_inicio"]
                  or perto(rd["campo_inicio"], s["campo_inicio"]))), None)
        rd["futura"] = rd["campo_fim"] > hoje.isoformat()
    return res


def linhas_da_rodada(rd, revid):
    """Linhas de 13 colunas para uma rodada nova, na ordem (cenario, candidato)."""
    base = "compilação da Wikipédia, revisão %s" % revid
    metodologia = ("n=%s" % rd["amostra"]) if rd["amostra"] else ""
    url_pagina = "https://pt.wikipedia.org/w/index.php?title=%s&oldid=%s" % (
        urllib.parse.quote(TITULO_PAGINA.replace(" ", "_")), revid)
    url = rd["url"] or url_pagina
    comum = [rd["instituto"], rd["campo_inicio"], rd["campo_fim"], rd["data_divulgacao"], metodologia]
    cauda = ["", rd["margem"], rd["registro"], url]
    linhas = []
    cenarios = rd["cenarios"]
    uniao = []
    for cen in cenarios:
        for nome, _ in cen["candidatos"]:
            if nome not in uniao:
                uniao.append(nome)
    for i, cen in enumerate(cenarios, 1):
        rotulo = "1º turno" if i == 1 else "1º turno, cenário %d" % i
        obs = base
        if len(cenarios) > 1:
            obs += ", cenário %d" % i
            faltam = [n for n in uniao if n not in {c for c, _ in cen["candidatos"]}]
            if faltam:
                obs += " (sem %s)" % ", ".join(faltam)
        if rd.get("nota"):
            obs += "; " + rd["nota"]
        for nome, v in cen["candidatos"]:
            linhas.append(comum + [rotulo, nome, v] + cauda + [obs])
        if cen["outros"] is not None:
            linhas.append(comum + [rotulo, "outros", cen["outros"]] + cauda + [obs])
        if cen["indecisos"] is not None:
            obs_i = obs
            ri = norm_texto(cen.get("rotulo_indecisos", ""))
            if "absent" in ri or "absten" in ri or "branco" in ri or "nulo" in ri:
                obs_i += "; não sabe = %s somados pela fonte" % cen["rotulo_indecisos"].lower()
            linhas.append(comum + [rotulo, "não sabe", cen["indecisos"]] + cauda + [obs_i])
    s = rd.get("segundo_turno")
    if s and s["cenarios"]:
        cen = s["cenarios"][0]
        url2 = s.get("url") or url
        for nome, v in cen["candidatos"]:
            if nome in ("Lula", "Flávio Bolsonaro"):
                linhas.append(comum + [CENARIO_2T, nome, v] + ["", rd["margem"], rd["registro"], url2] +
                              [base + ("; " + rd["nota"] if rd.get("nota") else "")])
    linhas.sort(key=lambda l: (l[5], l[6]))
    return linhas


def acrescentar(caminho, linhas):
    """Acrescenta linhas no fim do CSV sem reescrever o que existe: BOM só quando o arquivo
    nasce aqui, CRLF sempre, UTF-8."""
    caminho = Path(caminho)
    existente = caminho.read_bytes() if caminho.exists() else b""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    if not existente:
        w.writerow(COLUNAS)
    w.writerows(linhas)
    with open(caminho, "ab") as f:
        if not existente:
            f.write(b"\xef\xbb\xbf")
        elif not existente.endswith(b"\n"):
            f.write(b"\r\n")
        f.write(buf.getvalue().encode("utf-8"))


# ------------------------------------------------------------------ rede e arquivos
def _dormir(retry_after, padrao):
    """Espera o que a API pedir, nunca menos que o próprio recuo. O Retry-After da Wikimedia vem
    fixo em 5 segundos mesmo quando a réplica está minutos atrasada; obedecer só a ele significa
    bater na porta a cada 5 segundos e desistir (foi o que derrubou a rodada de 8/9/2026, com a
    réplica 197 segundos atrás)."""
    segundos = padrao
    if retry_after:
        try:
            segundos = max(padrao, int(retry_after))
        except ValueError:
            try:
                alvo = email.utils.parsedate_to_datetime(retry_after)
                segundos = max(1, int((alvo - datetime.now(timezone.utc)).total_seconds()))
            except Exception:
                segundos = padrao
    time.sleep(min(max(segundos, 1), 120))


def baixar_pagina(titulo=TITULO_PAGINA, tentativas=7):
    """HTML renderizado e revid da página, pela MediaWiki API, uma requisição por vez, com
    maxlag=5 e espera em 429/503 e em erro maxlag respeitando Retry-After.
    Devolve (html, revid, corpo bruto da resposta)."""
    params = {"action": "parse", "page": titulo, "prop": "text|revid", "format": "json",
              "formatversion": "2", "maxlag": "5", "redirects": "1"}
    url = API + "?" + urllib.parse.urlencode(params)
    # começa em 15s e dobra até 240: sete tentativas cobrem uma réplica alguns minutos atrasada,
    # que é o caso comum de maxlag, sem martelar a API
    espera = 15
    for tentativa in range(tentativas):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                corpo = resp.read().decode("utf-8")
                retry_after = resp.headers.get("Retry-After")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and tentativa < tentativas - 1:
                print("HTTP %d; esperando para tentar de novo" % e.code, file=sys.stderr)
                _dormir(e.headers.get("Retry-After"), espera)
                espera = min(espera * 2, 240)
                continue
            raise
        try:
            dados = json.loads(corpo)
        except ValueError:
            # Costuma ser bloqueio transitório de proxy (HTML 'Access Denied'); vale repetir.
            if tentativa < tentativas - 1:
                print("a API não respondeu JSON; esperando para tentar de novo", file=sys.stderr)
                _dormir(retry_after, espera)
                espera = min(espera * 2, 240)
                continue
            raise RuntimeError("a API não respondeu JSON: %s" % corpo[:200].strip())
        if "error" in dados:
            if dados["error"].get("code") == "maxlag" and tentativa < tentativas - 1:
                print("API em maxlag; esperando para tentar de novo", file=sys.stderr)
                _dormir(retry_after, espera)
                espera = min(espera * 2, 240)
                continue
            raise RuntimeError("a API respondeu erro: %s" % dados["error"].get("info", dados["error"]))
        return dados["parse"]["text"], int(dados["parse"]["revid"]), corpo
    raise RuntimeError("a API não respondeu depois de %d tentativas" % tentativas)


def carregar_html(caminho, revid=None):
    """HTML de um arquivo local (gzip ou não; JSON da API ou HTML puro). Devolve (html, revid)."""
    caminho = str(caminho)
    abrir = gzip.open if caminho.endswith(".gz") else open
    with abrir(caminho, "rt", encoding="utf-8") as f:
        conteudo = f.read()
    if conteudo.lstrip().startswith("{"):
        dados = json.loads(conteudo)
        if "error" in dados:
            sys.exit("%s traz um erro da API: %s" % (caminho, dados["error"].get("info", dados["error"])))
        parse = dados.get("parse", dados)
        if "text" not in parse:
            sys.exit("%s não traz a resposta de action=parse (sem 'parse'/'text')" % caminho)
        texto_html = parse["text"]
        if isinstance(texto_html, dict):
            texto_html = texto_html.get("*", "")
        revid = revid or parse.get("revid")
        return texto_html, revid
    return conteudo, revid


# ------------------------------------------------------------------ programa
def processar(html, revid, linhas_csv, hoje=None, desde=""):
    """Núcleo sem efeitos colaterais: devolve (novas, presentes, res) onde novas e presentes
    são listas de rodadas do 1º turno já completadas."""
    hoje = hoje or hoje_brasilia()
    res = extrair(html, revid)
    completar(res, institutos_do_csv(linhas_csv), hoje)
    existentes = rodadas_existentes(linhas_csv)
    novas, presentes = [], []
    for rd in res["primeiro"]:
        if not rd["campo_fim"].startswith("2026"):
            res["avisos"].append("rodada fora de 2026 ignorada: %s %s" % (rd["instituto_pagina"], rd["campo_fim"]))
            continue
        if desde and rd["campo_fim"] < desde:
            continue
        if rd["futura"]:
            res["avisos"].append("data de campo no futuro, rodada ignorada: %s %s" % (rd["instituto_pagina"], rd["campo_fim"]))
            continue
        chave = rodada_presente(rd, existentes)
        if chave:
            rd["presente_como"] = chave
            presentes.append(rd)
        else:
            novas.append(rd)
    # dedup também entre rodadas da própria página (mesma rodada em duas tabelas)
    unicas, vistas = [], []
    for rd in novas:
        if any(casa_instituto(rd["instituto_pagina"], v["instituto_pagina"]) and
               perto(rd["campo_fim"], v["campo_fim"]) for v in vistas):
            res["avisos"].append("rodada repetida na página, mantida só a primeira: %s %s" % (rd["instituto_pagina"], rd["campo_fim"]))
            continue
        vistas.append(rd)
        unicas.append(rd)
    unicas.sort(key=lambda r: (r["data_divulgacao"], r["campo_fim"], r["instituto"]))
    institutos_csv = institutos_do_csv(linhas_csv)
    avisados = set()
    for rd in unicas:
        if rd["instituto"] in institutos_csv or rd["instituto"] in avisados:
            continue
        avisados.add(rd["instituto"])
        msg = "instituto novo para o CSV, gravado como está: '%s'" % rd["instituto"]
        semelhantes = parecidos(rd["instituto"], institutos_csv)
        if semelhantes:
            msg += "; parecido com %s (se for o mesmo, acrescente a SINONIMOS)" % ", ".join("'%s'" % c for c in semelhantes)
        res["avisos"].append(msg)
    return unicas, presentes, res


def descrever(rd):
    partes = ["%s (página: %s)" % (rd["instituto"], rd["instituto_pagina"]),
              "campo %s a %s" % (rd["campo_inicio"], rd["campo_fim"]),
              "divulgação %s" % rd["data_divulgacao"],
              "n=%s" % rd["amostra"] if rd["amostra"] else "amostra não informada",
              ("±" + rd["margem"]) if rd["margem"] else "margem não informada",
              "%d cenário(s)" % len(rd["cenarios"]),
              "2º turno Lula x Flávio: " + ("sim" if rd.get("segundo_turno") else "não"),
              rd["url"] or "sem URL de referência"]
    return " | ".join(partes)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Acrescenta a dados/pesquisas-registradas.csv as rodadas presidenciais de 2026 compiladas pela Wikipédia que ainda não estão lá.")
    ap.add_argument("--raiz", default=os.environ.get("OBSERVATORIO_RAIZ"), help="raiz do projeto (padrão: pasta acima deste script, ou OBSERVATORIO_RAIZ)")
    ap.add_argument("--csv", help="CSV de entrada (padrão: <raiz>/dados/pesquisas-registradas.csv)")
    ap.add_argument("--saida", help="CSV de destino fora de dados/; se não existir, nasce como cópia do CSV de entrada e recebe o acréscimo")
    ap.add_argument("--html", help="ler o HTML de um arquivo local (gzip ou não; JSON da API ou HTML puro) em vez de chamar a API")
    ap.add_argument("--revid", help="revisão da página quando o HTML local não a traz")
    ap.add_argument("--guardar-html", help="gravar a resposta bruta da API (gzip) neste caminho, para auditoria")
    ap.add_argument("--desde", default="", help="considerar só rodadas com fim de campo a partir desta data (AAAA-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="mostrar as rodadas novas sem gravar")
    args = ap.parse_args(argv)

    raiz = Path(args.raiz) if args.raiz else Path(__file__).resolve().parent.parent
    csv_in = Path(args.csv) if args.csv else raiz / "dados" / "pesquisas-registradas.csv"
    destino = Path(args.saida) if args.saida else csv_in
    if not csv_in.exists():
        sys.exit("CSV de entrada não encontrado: %s" % csv_in)
    if args.saida:
        pasta_dados = (raiz / "dados").resolve()
        if pasta_dados == destino.resolve() or pasta_dados in destino.resolve().parents:
            sys.exit("--saida não pode apontar para dentro de %s; omita --saida para gravar no CSV oficial" % pasta_dados)
    # Em --dry-run a cópia de saída não é criada: a simulação lê o CSV de entrada.
    if args.saida and not destino.exists() and not args.dry_run:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(csv_in.read_bytes())

    if args.html:
        html, revid = carregar_html(args.html, args.revid)
        if not revid:
            sys.exit("o HTML local não traz a revisão; informe --revid")
    else:
        html, revid, bruto = baixar_pagina()
        if args.guardar_html:
            Path(args.guardar_html).parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(args.guardar_html, "wt", encoding="utf-8") as f:
                f.write(bruto)
    revid = int(revid)

    origem = destino if destino.exists() else csv_in
    linhas_csv = ler_csv(origem)
    hoje = hoje_brasilia()
    novas, presentes, res = processar(html, revid, linhas_csv, hoje, args.desde)

    print("página: %s, revisão %s; hoje (Brasília) %s" % (TITULO_PAGINA, revid, hoje.isoformat()))
    print("CSV: %s (%d linhas, %d rodadas)" % (origem, len(linhas_csv), len(rodadas_existentes(linhas_csv))))
    print("1º turno na página: %d rodadas; 2º turno Lula x Flávio: %d rodadas; %d tabelas descartadas" % (
        len(res["primeiro"]), len(res["segundo"]), len(res["descartes"])))
    for a in res["avisos"]:
        print("AVISO   ", a)
    for rd in presentes:
        print("PRESENTE", descrever(rd), "| casa com", " ".join(x or "-" for x in rd["presente_como"]))
    total_linhas = 0
    for rd in novas:
        linhas = linhas_da_rodada(rd, revid)
        total_linhas += len(linhas)
        print("NOVA    ", descrever(rd))
        for l in linhas:
            print("          %s | %s | %s" % (l[5], l[6], l[7]))
    print("%d rodadas já presentes; %d novas (%d linhas)" % (len(presentes), len(novas), total_linhas))
    if args.dry_run:
        print("nada gravado (--dry-run)")
        return 0
    if not novas:
        print("nada a acrescentar em %s" % destino)
        return 0
    todas = []
    for rd in novas:
        todas.extend(linhas_da_rodada(rd, revid))
    acrescentar(destino, todas)
    print("%d rodadas (%d linhas) acrescentadas a %s" % (len(novas), len(todas), destino))
    return 0


if __name__ == "__main__":
    sys.exit(main())
