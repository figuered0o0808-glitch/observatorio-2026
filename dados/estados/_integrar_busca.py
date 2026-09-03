# -*- coding: utf-8 -*-
"""Integra as coletas próprias de 2/9/2026 para os candidatos estaduais:
- _tse-detalhe-estados.json  (API candidatura/buscar do DivulgaCandContas: bens, instrução, ocupação, vice, composição, sites, foto)
- _trends-estados.json       (Google Trends, geo por estado, lotes de até 5 nomes ancorados pelo líder da última pesquisa)
- _wikipedia-estados.json    (busca do verbete + pageviews diários, Wikimedia REST)
- _instagram-estados.json    (leitura do perfil público informado ao TSE; opcional)
Saídas: candidatos-detalhe.csv, trends-estados.csv, wikipedia-estados.csv, instagram-estados.csv
Regras: só campos públicos de perfil (nada de CPF ou título de eleitor); célula vazia = indisponível.
"""
import csv, io, json, os, re, datetime as dt, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
def carregar(nome):
    p = os.path.join(AQUI, nome)
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else None
def gravar(nome, cab, linhas):
    with io.open(os.path.join(AQUI, nome), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cab); w.writerows(linhas)
    print(nome, len(linhas), "linhas")

cands = list(csv.DictReader(io.open(os.path.join(AQUI, "candidatos-estados.csv"), encoding="utf-8-sig")))
por_slug = {c["slug"]: c for c in cands}
por_nome = {}
for c in cands:
    por_nome[(c["uf"], c["nome_urna"])] = c["slug"]
HOJE = dt.date.today().isoformat()

# ---------- TSE detalhe
det = carregar("_tse-detalhe-estados.json")
handles = {}
if det:
    linhas = []
    for slug, d in det["candidatos"].items():
        sites = d.get("sites") or []
        redes = {"instagram": "", "facebook": "", "tiktok": "", "youtube": "", "x": "", "site": ""}
        for s in sites:
            u = s.strip()
            m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", u)
            if m and not redes["instagram"]: redes["instagram"] = m.group(1).strip(".").lower(); continue
            m = re.search(r"tiktok\.com/@?([A-Za-z0-9_.]+)", u)
            if m and not redes["tiktok"]: redes["tiktok"] = m.group(1).lower(); continue
            m = re.search(r"(?:facebook|fb)\.com/([^/?#]+)", u)
            if m and not redes["facebook"]:
                if not m.group(1).startswith("profile.php"): redes["facebook"] = m.group(1)
                continue
            m = re.search(r"youtube\.com/(?:@|c/|channel/|user/)?([^/?#]+)", u)
            if m and not redes["youtube"]: redes["youtube"] = m.group(1); continue
            m = re.search(r"(?:twitter|x)\.com/([A-Za-z0-9_]+)", u)
            if m and not redes["x"]: redes["x"] = m.group(1); continue
            if not redes["site"]: redes["site"] = u
        if redes["instagram"]: handles[slug] = redes["instagram"]
        vice = "; ".join(f'{v.get("nome") or ""} ({v.get("partido") or ""})'.strip() for v in (d.get("vices") or []) if v.get("nome"))
        linhas.append([d.get("uf"), slug, d.get("nomeUrna"), d.get("nomeCompleto"), d.get("numero"), d.get("partido"), d.get("cargo"), d.get("situacao"), d.get("totalizacao"),
                       d.get("coligacao") or "", "" if (d.get("composicao") or "").strip("* ") == "" else d.get("composicao"), vice, d.get("nascimento") or "", d.get("sexo") or "", d.get("instrucao") or "", d.get("ocupacao") or "",
                       (d.get("ufNasc") or ""), (d.get("munNasc") or ""), d.get("totalBens") if d.get("totalBens") is not None else "", len(d.get("bens") or []),
                       redes["instagram"], redes["tiktok"], redes["facebook"], redes["youtube"], redes["x"], redes["site"], d.get("foto") or "",
                       "; ".join(f'{e.get("ano")}: {e.get("cargo")} ({e.get("sit")})' for e in (d.get("anteriores") or []) if e.get("ano")), d.get("atualizado") or "",
                       "TSE DivulgaCandContas, API candidatura/buscar, " + det["coletado"][:10]])
    gravar("candidatos-detalhe.csv", ["uf", "slug", "nome_urna", "nome_completo", "numero", "partido", "cargo", "situacao_tse", "totalizacao", "coligacao", "composicao_coligacao", "vice",
                                      "data_nascimento", "sexo", "instrucao", "ocupacao", "uf_nascimento", "municipio_nascimento", "total_bens", "n_bens",
                                      "instagram", "tiktok", "facebook", "youtube", "x", "site", "foto_url", "eleicoes_anteriores", "atualizado_tse", "fonte"], linhas)
    # bens detalhados
    lb = []
    for slug, d in det["candidatos"].items():
        for b in d.get("bens") or []:
            if not b: continue
            lb.append([d.get("uf"), slug, b.get("tipo") or "", (b.get("d") or "")[:160], b.get("v"), "TSE DivulgaCandContas, " + det["coletado"][:10]])
    gravar("bens-estados.csv", ["uf", "slug", "tipo", "descricao", "valor", "fonte"], lb)
    print("handles de instagram:", len(handles), "| erros da coleta:", len(det.get("erros") or []))

# ---------- Trends
tr = carregar("_trends-estados.json")
if tr:
    linhas = []; notas = {}
    COMUNS = {"fabio", "renan", "marina", "andre", "daniel", "carol", "tiago", "gabriel", "helder", "marley", "capi", "salles", "arruda", "elisson", "reginaldo", "edvaldo", "nabor", "pimenta", "zucco", "veneziano", "gleisi", "fufuca", "chicao", "conti", "juliete", "garotinho", "waguinho", "allyson", "tarcisio", "clecio", "estevao", "sanderson", "rigotto", "lunelli", "randolfe", "petecao", "luizianne", "gaguim", "renatinha", "neidinha", "nicoletti", "helder", "jhc"}
    def norm(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    # agrupa lotes por disputa
    por_disp = {}
    for key, lote in tr["lotes"].items():
        disp, idx = key.split("#"); por_disp.setdefault(disp, []).append((int(idx), lote))
    for disp, lotes in por_disp.items():
        uf, cargo3 = disp.split("-"); cargo = "governador" if cargo3 == "gov" else "senador"
        lotes.sort(key=lambda x: x[0])
        series = {}   # termo -> {ts: v}
        anchor_sum0 = None; anchor = None
        for idx, lote in lotes:
            kws = lote["kws"]; pts = [p.split(";") for p in lote["csv"].split("|")]
            vals = {k: [] for k in kws}
            for ts, vs in pts:
                for k, v in zip(kws, vs.split(",")):
                    vals[k].append((int(ts), float(v)))
            a = kws[0]
            sa = sum(v for _, v in vals[a])
            if idx == 0:
                anchor = a; anchor_sum0 = sa; fator = 1.0; nota_l = ""
            else:
                fator = (anchor_sum0 / sa) if sa > 0 and anchor_sum0 else 1.0
                fator = max(0.1, min(10.0, fator))
                nota_l = "" if sa > 0 else "lote sem sinal da âncora; escala própria"
            for k in kws:
                if idx > 0 and k == anchor: continue
                slug = por_nome.get((uf, k))
                if not slug:
                    # tenta por nome normalizado
                    for (u2, n2), s2 in por_nome.items():
                        if u2 == uf and norm(n2) == norm(k): slug = s2; break
                nota = []
                t0 = norm(k).split()
                if len(t0) == 1 and t0[0] in COMUNS: nota.append("termo ambíguo (nome comum, capta homônimos)")
                if nota_l: nota.append(nota_l)
                if fator != 1.0: nota.append(f"lote {idx} reescalado por {fator:.2f} pela âncora {anchor}")
                for ts, v in vals[k]:
                    d = dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                    linhas.append([d, uf, cargo, slug or "", k, round(v * fator, 1), idx, lote["geo"], "; ".join(nota), "Google Trends, API interna do explore, coleta própria " + tr["coletado"][:10]])
                if slug and nota: notas[slug] = "; ".join(nota)
    gravar("trends-estados.csv", ["data", "uf", "cargo", "slug", "termo", "indice", "lote", "geo", "nota", "fonte"], linhas)

# ---------- Wikipédia
wk = carregar("_wikipedia-estados.json")
COMUNS_TOK = set("jose joao maria carlos antonio francisco paulo pedro luiz luis marcos marcelo andre roberto ricardo rafael daniel eduardo fernando fabio felipe gabriel rodrigo bruno lucas mateus jorge sergio oliveira silva santos souza sousa lima costa pereira rodrigues almeida nascimento ferreira araujo ribeiro carvalho gomes martins rocha barbosa alves moreira mendes freitas cardoso correia correa dias teixeira monteiro moura castro campos andrade nunes machado marques cunha melo ramos fernandes goncalves lopes vieira batista medeiros pinto cavalcante cavalcanti neves xavier azevedo rezende resende barros duarte leal miranda soares reis morais moraes borges pires guimaraes coelho farias filho neto junior dos das de da do e".split())
def _toks(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", n) if t]
def verbete_plausivel(c, title, snip=""):
    """o título precisa compartilhar ao menos um token distintivo (não comum) com o nome de urna ou completo"""
    if not c: return True
    if "desambigua" in unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower(): return False
    tt = set(_toks(re.sub(r"\(.*?\)", "", title)))
    tn = set(_toks(c["nome_urna"]) + _toks(c["nome_completo"]))
    dist = (tt & tn) - COMUNS_TOK
    if dist: return True
    # só tokens comuns em comum: aceita se todos os tokens do título estão no nome (urna ou completo)
    return bool(tt) and tt <= tn
if wk:
    linhas = []; la = []
    rejeitados = 0
    for slug, a in wk["artigos"].items():
        c = por_slug.get(slug)
        ok = bool(a.get("title")) and a.get("sc", 0) >= 6 and verbete_plausivel(c, a["title"], a.get("snip", ""))
        if a.get("title") and a.get("sc", 0) >= 6 and not ok: rejeitados += 1
        a["_ok"] = ok
        la.append([c["uf"] if c else "", slug, a.get("title") or "", a.get("sc", 0), (a.get("snip") or "")[:140], "aceito" if ok else ("rejeitado: título sem token distintivo do nome" if a.get("title") and a.get("sc", 0) >= 6 else "sem verbete localizado")])
    print("verbetes rejeitados pelo filtro de nome:", rejeitados)
    gravar("wikipedia-verbetes-estados.csv", ["uf", "slug", "verbete", "pontuacao", "trecho", "status"], la)
    for slug, s in wk["pageviews"].items():
        c = por_slug.get(slug); t = wk["artigos"][slug]["title"]
        if not wk["artigos"][slug].get("_ok"): continue
        for par in s.split(","):
            mmdd, v = par.split(":")
            linhas.append([f"2026-{mmdd[:2]}-{mmdd[2:]}", c["uf"] if c else "", slug, t, int(v), "Wikimedia REST API, pageviews per-article, all-access, agente user, coleta própria " + wk["coletado"][:10]])
    gravar("wikipedia-estados.csv", ["data", "uf", "slug", "verbete", "pageviews", "fonte"], linhas)

# ---------- Instagram
ig = carregar("_instagram-estados.json")
if ig:
    linhas = []
    for slug, r in ig["perfis"].items():
        c = por_slug.get(slug)
        n = r.get("n")
        da_meta = bool(r.get("aprox"))
        # a meta da página abrevia a partir de mil ("12,3K", "1M"): só esses são aproximados; abaixo disso a meta traz o número inteiro
        aprox = 1 if (da_meta and n is not None and n >= 1000 and n % 100 == 0) else 0
        if n is None: suf = " (perfil sem número legível)"
        elif aprox: suf = " (número arredondado da meta da página do perfil)"
        elif da_meta: suf = " (número inteiro da meta da página do perfil)"
        else: suf = " (contagem exata do endpoint de perfil)"
        fonte = "coleta própria, perfil público do Instagram via navegador, " + ig["coletado"][:10] + suf
        linhas.append([ig["coletado"][:10], c["uf"] if c else "", slug, r.get("h") or "", r.get("n") if r.get("n") is not None else "", aprox, r.get("nome") or "", r.get("st") or "", fonte])
    gravar("instagram-estados.csv", ["data", "uf", "slug", "handle", "seguidores", "aproximado", "nome_perfil", "status", "fonte"], linhas)
    n_ap = sum(1 for l in linhas if l[5] == 1)
    n_ok = sum(1 for l in linhas if l[4] != "" and l[5] == 0)
    print("instagram: perfis", len(ig["perfis"]), "| exatos", n_ok, "| aproximados", n_ap, "| sem número", len(ig["perfis"]) - n_ok - n_ap)
