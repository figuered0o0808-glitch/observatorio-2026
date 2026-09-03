# -*- coding: utf-8 -*-
"""Converte o dump das páginas "Pesquisas eleitorais para a eleição estadual de 2026 ..." da Wikipédia
(extraído no navegador em texto compacto: cabeçalhos "## a > b > c", células "a | b | c", "H:" marca th)
em linhas normalizadas de pesquisa.

Saída: pesquisas-estados-wiki.csv com uma linha por (uf, cargo, turno, instituto, campo, cenário, candidato).
Regras: nada é inventado; o que a tabela não traz (modo de coleta, contratante, registro no TSE, data de
divulgação) fica em branco. A data de referência é o último dia de campo.
"""
import json, re, csv, sys, os, unicodedata

SRC = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/observatorio-2026/dados/estados/_wiki-pesquisas-estados.json"
OUT = "/home/claude/observatorio-2026/dados/estados/pesquisas-estados-wiki.csv"

UF_DE_TITULO = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
    "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA", "Mato Grosso do Sul": "MS", "Mato Grosso": "MT", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ",
    "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC",
    "São Paulo": "SP", "Sergipe": "SE", "Tocantins": "TO",
}
MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}

def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def uf_do_titulo(t):
    for nome in sorted(UF_DE_TITULO, key=len, reverse=True):
        if t.endswith(nome):
            return UF_DE_TITULO[nome]
    return None

def cargo_turno(path):
    p = norm(" > ".join(path))
    if "espont" in p or "rejei" in p or "avalia" in p or "aprova" in p:
        return None, None
    cargo = None
    if "senad" in p: cargo = "senador"
    elif "governador" in p or "governo" in p: cargo = "governador"
    elif "turno" in p: cargo = "governador"   # "Segundo Turno > A e B": só o governo tem segundo turno
    if cargo is None:
        return None, None
    turno = 2 if "segundo turno" in p or "2.o turno" in p or "2o turno" in p or "2º turno" in norm(p) else 1
    return cargo, turno

def ano_de(path):
    for seg in path:
        m = re.search(r"\b(20\d\d)\b", seg)
        if m: return int(m.group(1))
    return 2026

ABREV = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
def datas(txt, ano):
    """Aceita '15 e 19 de agosto', '24 a 28 de julho', '28 de maio a 1 de junho', '30 de março a 1º de abril', '12 de agosto',
    '29 – 31 Ago', '29 Ago – 2 Set', '13 a 19 março de 2026'. Devolve (início, fim) ISO; mês do início herda o do fim se omitido."""
    t = norm(txt.replace("º", "").replace("°", "").replace("ª", ""))
    t = re.sub(r"(\d)[oa]\b", r"\1", t)
    t = re.sub(r"[–—/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    m_ano = re.search(r"\b(20\d\d)\b", t)
    if m_ano: ano = int(m_ano.group(1)); t = t.replace(m_ano.group(1), " ")
    toks = re.findall(r"\b(\d{1,2})\b(?:\s+de)?\s*([a-z]{3,9})?", t)
    toks = [(int(d), ABREV.get(m[:3]) if m and m[:3] in ABREV else None) for d, m in toks if 1 <= int(d) <= 31]
    if not toks:
        return "", ""
    d_ini, m_ini = toks[0]; d_fim, m_fim = toks[-1]
    if m_fim is None:
        # mês pode vir depois do último dia sem número: '12 e 13 de agosto' já cobre; tenta o último mês citado no texto
        ms = [ABREV[w[:3]] for w in re.findall(r"[a-z]{3,9}", t) if w[:3] in ABREV]
        if not ms: return "", ""
        m_fim = ms[-1]
    if m_ini is None: m_ini = m_fim
    if m_ini == m_fim and d_ini > d_fim: d_ini, d_fim = d_fim, d_ini
    return f"{ano}-{m_ini:02d}-{d_ini:02d}", f"{ano}-{m_fim:02d}-{d_fim:02d}"

def num(v):
    v = v.strip()
    if v in ("", "—", "–", "-", "—%", "n/a", "N/A", "?"):
        return None
    v = re.sub(r"\[[^\]]*\]", "", v)
    v = v.replace("%", "").replace("±", "").replace(",", ".").strip()
    m = re.match(r"^-?\d+(\.\d+)?$", v)
    return float(v) if m else None

def amostra(v):
    v = re.sub(r"[^\d]", "", v)
    return int(v) if v else ""

PARTIDOS = ["REPUBLICANOS", "SOLIDARIEDADE", "CIDADANIA", "PSDB", "PSOL", "PODE", "REDE", "NOVO", "AVANTE", "AGIR", "PRTB", "PMB", "PCDOB", "PCdoB", "PSTU", "PSD", "PSB", "PDT", "MDB", "MISSÃO", "MISSAO", "UNIÃO", "UNIAO", "DEMOCRATA", "PATRIOTA", "PRD", "PCO", "PCB", "REP", "CID", "SD", "PL", "PT", "PP", "PV", "UP", "DC"]
def cand_header(h):
    """'Ciro Gomes(PSDB)' -> ('Ciro Gomes','PSDB'); 'TarcísioREP' -> ('Tarcísio','REP'); 'GeraldoRufinoPODE' -> ('Geraldo Rufino','PODE')"""
    h = h.replace("H:", "").strip()
    h = re.sub(r"^(Dr\.?ª|Dra\.?|Dr\.?|Prof\.?ª|Profª|Prof\.?|Pr\.|Pe\.)(?=[A-ZÀ-Ú])", r"\1 ", h)
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m2 = re.match(r"^(.*[a-zà-ú])(Solidariedade|Republicanos|Cidadania|Podemos|Avante|Democrata|Democratas|Novo|Rede|Missão|Missao|União|Uniao|Mobiliza|Agir|Patriota)$", h)
    if m2:
        nome = re.sub(r"(?<=[a-zà-ú])(?=[A-ZÀ-Ú])", " ", m2.group(1).strip(" -"))
        return nome, m2.group(2).upper()
    for p in sorted(PARTIDOS, key=len, reverse=True):
        if h.endswith(p) and len(h) > len(p) and not h[-len(p)-1].isupper():
            nome = h[:-len(p)].strip(" -")
            nome = re.sub(r"(?<=[a-zà-ú])(?=[A-ZÀ-Ú])", " ", nome)
            return nome, p
    return h, ""

FALHAS = []
NAO_CAND = ("outros", "brancos", "nulos", "indecis", "nao sabe", "não sabe", "vantagem", "absten", "nenhum", "ns/nr", "ns / nr", "cen.", "cenario")

def parse_page(titulo, texto):
    uf = uf_do_titulo(titulo)
    revid = ""
    m = re.search(r"revid=(\d+)", texto.split("\n", 1)[0])
    if m: revid = m.group(1)
    linhas = texto.split("\n")
    out = []
    path = []; header_rows = []; in_table = False
    cols = None; ntab = 0
    for ln in linhas[1:]:
        if ln.startswith("## "):
            path = [s.strip() for s in ln[3:].split(">")]
            header_rows = []; cols = None; in_table = True; ntab += 1
            continue
        if ln.startswith("CAP "):
            continue
        cells = [c.strip() for c in ln.split(" | ")]
        if all(c.startswith("H:") or c == "" for c in cells):
            header_rows.append(cells)
            continue
        # linha de dados: define colunas a partir dos cabeçalhos acumulados
        if cols is None:
            cols = definir_colunas(header_rows)
            if cols is None:
                continue
        cargo, turno = cargo_turno(path)
        if cargo is None:
            continue
        ano = ano_de(path)
        inst = cells[cols["inst"]] if cols["inst"] < len(cells) else ""
        if not inst or inst.startswith("H:"):
            continue
        dt = cells[cols["data"]] if cols["data"] is not None and cols["data"] < len(cells) else ""
        m_ano = re.search(r"\b(20\d\d)\b", dt)
        if m_ano: ano = int(m_ano.group(1))
        ini, fim = datas(dt, ano)
        if not fim:
            FALHAS.append((uf, dt)); continue
        am = amostra(cells[cols["amostra"]]) if cols["amostra"] is not None and cols["amostra"] < len(cells) else ""
        mg = num(cells[cols["margem"]]) if cols["margem"] is not None and cols["margem"] < len(cells) else None
        cen = cells[cols["cen"]] if cols["cen"] is not None and cols["cen"] < len(cells) else "1"
        cen = re.sub(r"[^\dA-Za-z]", "", cen) or "1"
        outros = num(cells[cols["outros"]]) if cols["outros"] is not None and cols["outros"] < len(cells) else None
        indec = num(cells[cols["indec"]]) if cols["indec"] is not None and cols["indec"] < len(cells) else None
        for ci, (nome, partido) in cols["cands"]:
            if ci >= len(cells):
                continue
            v = num(cells[ci])
            if v is None:
                continue
            out.append({
                "uf": uf, "cargo": cargo, "turno": turno, "instituto_bruto": inst, "campo_inicio": ini, "campo_fim": fim,
                "amostra": am, "margem_erro": "" if mg is None else mg, "cenario": cen, "candidato": nome, "partido": partido,
                "percentual": v, "outros": "" if outros is None else outros, "indecisos": "" if indec is None else indec,
                "secao": " > ".join(path), "tabela": ntab, "ordem_col": ci, "pagina": titulo, "revid": revid,
            })
    return out

def definir_colunas(header_rows):
    if not header_rows:
        return None
    # escolhe a linha de cabeçalho com nomes de candidatos: a que tem mais células não vazias entre as posições > 3
    best = max(header_rows, key=lambda r: sum(1 for c in r if c.strip() not in ("H:", "")))
    n = len(best)
    cols = {"inst": 0, "data": None, "amostra": None, "margem": None, "cen": None, "outros": None, "indec": None, "cands": []}
    for i, c in enumerate(best):
        c = re.sub(r"\.mw-parser-output[^{]*\{[^}]*\}", "", c)
        t = norm(c.replace("H:", "")).strip()
        if not t:
            continue
        if i == 0 or "contratante" in t or "pesquisa" == t or "instituto" in t:
            cols["inst"] = i; continue
        if "data" in t and cols["data"] is None:
            cols["data"] = i; continue
        if "amostra" in t and cols["amostra"] is None:
            cols["amostra"] = i; continue
        if "margem" in t and cols["margem"] is None:
            cols["margem"] = i; continue
        if t.startswith("cen") or "cenario" in t or t.endswith("cen.") or t == "cen":
            cols["cen"] = i; continue
        if t.startswith("outros"):
            cols["outros"] = i; continue
        if any(k in t for k in ("indecis", "nao sabe", "brancos", "nulos", "absten", "nenhum", "ns/nr")):
            if cols["indec"] is None: cols["indec"] = i
            continue
        if "vantagem" in t or "diferenca" in t or "lideranca" in t:
            continue
        # candidato
        if i > 1:
            cols["cands"].append((i, cand_header(c)))
    if not cols["cands"]:
        return None
    return cols

def main():
    j = json.load(open(SRC, encoding="utf-8"))
    rows = []
    for titulo, texto in j["paginas"].items():
        if not isinstance(texto, str) or texto.startswith("ERRO"):
            print("ERRO", titulo, str(texto)[:80]); continue
        r = parse_page(titulo, texto)
        rows.extend(r)
        print(f"{uf_do_titulo(titulo)}: {len(r)} pontos")
    cab = ["uf", "cargo", "turno", "instituto_bruto", "campo_inicio", "campo_fim", "amostra", "margem_erro", "cenario", "candidato", "partido", "percentual", "outros", "indecisos", "secao", "tabela", "ordem_col", "pagina", "revid"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cab); w.writeheader(); w.writerows(rows)
    print("total:", len(rows), "->", OUT)
    import collections
    print("datas não lidas:", len(FALHAS), collections.Counter(FALHAS).most_common(12))

if __name__ == "__main__":
    main()
