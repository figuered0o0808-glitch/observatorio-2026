# -*- coding: utf-8 -*-
"""Gera mural.html (Mural dos Candidatos) a partir dos CSVs em ../dados.
Rodar a cada snapshot. Edição 2: histórico completo de pesquisas, redes, partidos."""
import re, csv, io, json, os, re
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "..", "dados")
import os as _os
from datetime import datetime as _dt
from zoneinfo import ZoneInfo as _ZI
def _agora_brasilia():
    t = _dt.now(_ZI("America/Sao_Paulo"))
    meses = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
    return f"{t.day} de {meses[t.month-1]} de {t.year}, {t.hour}h{t.minute:02d} de Brasília"
ATUALIZADO = _os.environ.get("MURAL_ATUALIZADO") or _agora_brasilia()   # hora da geração; sobrescreva com MURAL_ATUALIZADO="1 de setembro de 2026, 20h20 de Brasília"

def ler(nome):
    with io.open(os.path.join(DADOS, nome), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

cands = ler("candidatos.csv")
serie = ler("serie-diaria.csv")
pesq = ler("pesquisas-registradas.csv")
ev = ler("eventos.csv")
part = ler("partidos.csv")
trends_rows = ler("trends-2026.csv")
wiki_rows = ler("wikipedia-pageviews.csv")

OITO = ["Lula", "Flávio Bolsonaro", "Augusto Cury", "Ronaldo Caiado", "Romeu Zema",
        "Renan Santos", "Pablo Marçal", "Samara Martins"]

def num(x):
    try: return float(x)
    except: return None

# ---------------------------------------------------------------- pesquisas
rodadas = {}
for r in pesq:
    if not r["instituto"].startswith("Agregador"):
        k = (r["instituto"], r["data_divulgacao"])
        rodadas.setdefault(k, r)
def modo_de(met):
    m = (met or "").lower()
    if "telefon" in m: return "telefônica"
    if "presencial" in m or "domicili" in m or "face" in m: return "presencial"
    if "digital" in m or "online" in m or "eletrôn" in m or "web" in m or "formulário" in m or "internet" in m: return "digital"
    return "não informada"
modo_rodada = {k: modo_de(v["metodologia"]) for k, v in rodadas.items()}
polls_main, polls_2t, rej = [], [], []
for r in pesq:
    inst, dt, cen, cand = r["instituto"], r["data_divulgacao"], r["cenario"], r["candidato"]
    if inst.startswith("Agregador"): continue
    p, j = num(r["percentual"]), num(r["rejeicao"])
    if cand in OITO:
        if cen == "1º turno" and p is not None:
            polls_main.append([inst, dt, cand, p, r["url"], modo_rodada.get((inst, dt), "não informada")])
        if cen == "2º turno Lula x Flávio Bolsonaro" and p is not None and cand in ("Lula", "Flávio Bolsonaro"):
            polls_2t.append([inst, dt, cand, p])
        if j is not None:
            rej.append([inst, dt, cand, j])
# dedupe rejeição (mesma rodada, candidato repetido em vários cenários)
seen = set(); rej = [x for x in rej if not (tuple(x[:3]) in seen or seen.add(tuple(x[:3])))]
institutos = sorted({x[0] for x in polls_main})
meta = {"rodadas": len(rodadas), "institutos": len({k[0] for k in rodadas}),
        "primeira": min(k[1] for k in rodadas), "ultima": max(k[1] for k in rodadas)}

# fichas técnicas por rodada (para tooltip e tabela de rodadas)
fichas = [{"inst": k[0], "dt": k[1], "campo": f'{v["data_campo_inicio"]} a {v["data_campo_fim"]}',
           "met": v["metodologia"], "reg": v["registro_tse"], "url": v["url"]}
          for k, v in sorted(rodadas.items(), key=lambda kv: kv[0][1])]

# ---------------------------------------------------------------- redes
ig_serie = defaultdict(list)
series_plat = defaultdict(lambda: defaultdict(list))   # plataforma -> candidato -> pontos
idx_serie = defaultdict(list)
ultimo = {}
for r in sorted(serie, key=lambda r: r["data"]):
    cand, plat = r["candidato"], r["plataforma"]
    if cand not in OITO: continue
    if plat == "instagram" and r["seguidores"]:
        v = int(float(r["seguidores"]))
        ig_serie[cand].append({"d": r["data"], "v": v, "f": r["fonte"], "u": r["url_fonte"]})
        ultimo[(cand, "instagram")] = {"valor": v, "data": r["data"], "fonte": r["fonte"], "url": r["url_fonte"]}
    if plat in ("tiktok", "youtube", "x", "kwai") and r["seguidores"]:
        v = int(float(r["seguidores"]))
        ultimo[(cand, plat)] = {"valor": v, "data": r["data"], "fonte": r["fonte"], "url": r["url_fonte"]}
        series_plat[plat][cand].append({"d": r["data"], "v": v, "f": r["fonte"], "u": r["url_fonte"]})
    if plat in ("datrix_idp", "quaest_ipd") and r["trends_indice"]:
        idx_serie[plat].append({"d": r["data"], "c": cand, "v": float(r["trends_indice"])})

# ---------------------------------------------------------------- partidos
def lead_num(x):
    m = re.match(r"^\s*\"?([\d][\d.,]*)", x or "")
    if not m: return None
    s = m.group(1)
    if "," in s: return float(s.replace(".", "").replace(",", "."))
    return int(s.replace(".", ""))
def lead_txt(x):
    if not x: return ""
    return re.split(r"\s*\((?:TSE|API|Senado|Poder360|Agência|fonte|consulta)", x)[0].strip().strip('"')
partidos = []
for p in part:
    partidos.append({
        "sigla": p["sigla"], "numero": p["numero"], "nome": lead_txt(p["nome"]),
        "presidente": (lambda x: (lambda m: m.group(1) if m and len(m.group(1)) <= 30 and not re.search(r"TSE|API|consulta|Wikip|exerc|secret|\d|;", m.group(1)) else re.split(r"\s*\(", x)[0])(re.search(r"\(([^)]+)\)\s*$", x)))(lead_txt(p["presidente_nacional"])),
        "camara": lead_num(p["bancada_camara_2026"]), "senado": lead_num(p["bancada_senado_2026"]),
        "gov": lead_num(p["governadores_2022"]), "gov_txt": lead_txt(p["governadores_2022"]),
        "federacao": re.split(r",\s*registrad", lead_txt(p["federacao"]))[0], "filiados": lead_num(p["filiados_total"]),
        "fefc": lead_num(p["fefc_2026_reais"]),
        "tv": (lambda x: ("" if "sem tempo" in x.lower() else (lambda m1, m2: (m1.group(1) if m1 else "") + (" · " + m2.group(1) + " ins." if m2 else ""))(re.search(r"(\d+:\d+)", x), re.search(r"(\d+)\s*inser", x))))(p["tempo_tv_presidencial_2026"] or ""),
        "clausula": lead_txt(p["clausula_desempenho_2022"]), "fundacao": lead_txt(p["fundacao_ano"]),
        "obs": "", "secundario": p["sigla"] in ("PSB", "AGIR"),
    })

# ---------------------------------------------------------------- eventos
ev_sorted = sorted(ev, key=lambda r: r["data"], reverse=True)
def eventos_de(nome, n=4):
    out = [e for e in ev_sorted if nome in e["candidato"] or e["candidato"] == "todos"]
    return [{"data": e["data"], "evento": e["evento"], "categoria": e["categoria"], "url": e["url"]} for e in out[:n]]
timeline = [{"data": e["data"], "candidato": e["candidato"], "evento": e["evento"],
             "categoria": e["categoria"], "descricao": e["descricao"], "url": e["url"]} for e in ev_sorted]

# ---------------------------------------------------------------- candidatos
SITUACAO = {
 "Lula": "Lidera o primeiro turno em todas as 83 rodadas do ano, entre 33 e 48 pontos conforme o instituto, mas o segundo turno com Flávio estreitou: de folga de 7 a 9 pontos em março para empate técnico nas rodadas de agosto. Faltou à Band; presença indefinida em 14/9.",
 "Flávio Bolsonaro": "Segundo em todas as rodadas do ano. Cresceu até abril, oscilou com o caso Master desde maio e caiu 4 pontos na Nexus da semana da onda Cury. Só vai a debate com Lula presente.",
 "Augusto Cury": "Testado desde abril entre 0,4 e 3%, saltou para 7,8 a 11% nas três pesquisas pós-debate. Menor rejeição do campo. A onda de seguidores parou no fim de semana da sabatina.",
 "Ronaldo Caiado": "Oscila entre 2 e 7% o ano inteiro, sem tendência. Registro deferido. Único além de Flávio a empatar com Lula num segundo turno (Nexus 45 x 44 e Real Time 45 x 43).",
 "Romeu Zema": "Começou o ano entre 3 e 5% e chega a setembro entre 1 e 2%. Desistiu da Band horas antes. Renunciou ao governo de MG em março para concorrer.",
 "Renan Santos": "Subiu de 1 a 2% no início do ano para 4 a 9% em julho, empatou com Cury na Atlas de agosto e caiu a 3% na Nexus. Desde 31/8 com propaganda digital, fundo e debates suspensos por Toffoli e contas fora do ar no Brasil.",
 "Pablo Marçal": "Entrou nas pesquisas em agosto, entre 1,9 e 3%. Inelegível até 2032 pelo TRE-SP, impedido pelo TSE de usar fundo, rádio, TV e debates desde 20/8; julgamento do registro até 14/9.",
 "Samara Martins": "Testada desde agosto, 0,9 a 1%. Única mulher na disputa com menção nominal, chapa toda feminina pela UP, aprovada pelo partido em 1/2 e confirmada na convenção de 27/7 na Zumbi dos Palmares. Excluída da Band e do consórcio de 14/9 por falta de bancada.",
 "Clariana Barão": "Advogada de Cuiabá, primeira candidatura do DC sem Eymael desde 1995. Sem menção nominal nas pesquisas; fez da exclusão das mulheres do debate sua bandeira.",
 "Edmilson Costa": "Economista, 76 anos. Sem menção nominal nas pesquisas e sem debates; crítico de Lula por não revogar as reformas.",
 "Hertz Dias": "Professor e rapper, segunda disputa presidencial. Fora das pesquisas nominais e dos debates; sabatina no SBT News em 29/8.",
 "Rui Costa Pimenta": "0,1% na Atlas. Registro deferido. Atingido por operação da PF de 11/8 sobre fundos partidários; lançou candidatura em Porto Alegre em 29/8.",
 "Wilson Grassi": "Veterinário, primeiro presidenciável do Democrata (ex-PMB), 0,1% na Atlas. Propõe tirar o voto de beneficiários do Bolsa Família.",
}
RESTRITO = {"Renan Santos": "Campanha restrita pelo TSE (31/8)", "Pablo Marçal": "Impedido pelo TSE (20/8)"}
def link(handle, plat):
    if not handle: return ""
    h = handle.split(" (")[0].lstrip("@")
    base = {"instagram": "https://www.instagram.com/", "tiktok": "https://www.tiktok.com/@",
            "youtube": "https://www.youtube.com/@", "x": "https://x.com/", "kwai": "https://www.kwai.com/@"}[plat]
    return base + h
SIGLA = lambda s: s.title().replace("Psd","PSD").replace("Pt","PT").replace("Pl","PL").replace("Pcb","PCB").replace("Pstu","PSTU").replace("Pco","PCO").replace("Prtb","PRTB").replace("Up","UP").replace("Dc","DC").replace("Psb","PSB")
out = []
for c in cands:
    nome = c["candidato"]
    redes = []
    for plat, rot in (("instagram","Instagram"),("tiktok","TikTok"),("youtube","YouTube"),("x","X"),("kwai","Kwai")):
        h = c[plat]
        if not h: continue
        redes.append({"plat": rot, "handle": h.split(" (")[0], "url": link(h, plat),
                      "seg": ultimo.get((nome, plat))})
    out.append({
        "nome": nome, "nome_urna": c["nome_urna"].title(), "numero": c["numero"],
        "partido": SIGLA(c["partido"]),
        "coligacao": c["coligacao"].title() if c["coligacao"] != c["partido"] else "",
        "composicao": c["composicao_coligacao"], "situacao": c["situacao_tse"],
        "restrito": RESTRITO.get(nome, ""), "vice": c["vice"], "vice_partido": SIGLA(c["vice_partido"]),
        "idade": c["idade"], "naturalidade": c["naturalidade"], "ocupacao": c["ocupacao"],
        "nome_completo": c["nome_completo"].title(), "data_nascimento": c["data_nascimento"],
        "escolaridade": c["escolaridade"], "confianca": c["confianca_handles"],
        "foto_url": c["foto_url_tse"], "atualizado_tse": c["ultima_atualizacao_tse"],
        "bens": num(c["bens_declarados_reais"]), "grupo": c["grupo"], "url_tse": c["url_tse"],
        "wikipedia": c["wikipedia_titulo"], "redes": redes, "eventos": eventos_de(nome),
        "situacao_texto": SITUACAO.get(nome, ""),
    })

# ---------------------------------------------------------------- efeito casa
from datetime import date as _date
def _dias(s): a=s.split("-"); return _date(int(a[0]),int(a[1]),int(a[2])).toordinal()
vies = []
for inst in institutos:
    linha = {"inst": inst, "modo": next((modo_rodada[k] for k in modo_rodada if k[0]==inst), "não informada"),
             "n": sum(1 for k in rodadas if k[0]==inst)}
    for cand, chave in (("Lula","dLula"),("Flávio Bolsonaro","dFlavio")):
        pts_all = [(_dias(p[1]), p[3], p[0]) for p in polls_main if p[2]==cand]
        meus = [p for p in pts_all if p[2]==inst]
        desv = []
        for d0, v, _ in meus:
            base = [v2 for d2, v2, i2 in pts_all if abs(d2-d0)<=14 and i2!=inst]
            if len(base) >= 2: desv.append(v - sum(base)/len(base))
        linha[chave] = round(sum(desv)/len(desv), 1) if desv else None
    vies.append(linha)
vies.sort(key=lambda x: -(x["n"]))

# ---------------------------------------------------------------- busca e descoberta
trends_c = defaultdict(list)   # candidato -> [[MMDD, v]]
trends_t = defaultdict(list)   # termo -> [[MMDD, v]]
for r in trends_rows:
    if r["data"] == "2026-08-16":  # dia zerado na resposta do Google
        continue
    mmdd = r["data"][5:7] + r["data"][8:10]
    v = int(r["indice"])
    if r["lote"] == "candidatos_a":
        trends_c[r["termo"]].append([mmdd, v])
    elif r["lote"] == "candidatos_b" and r["termo"] != "Lula":
        trends_c[r["termo"]].append([mmdd, v])
    elif r["lote"] == "termos":
        trends_t[r["termo"]].append([mmdd, v])
wiki = defaultdict(list)
for r in wiki_rows:
    wiki[r["candidato"]].append([r["data"][5:7] + r["data"][8:10], int(r["pageviews"])])

# ---------------------------------------------------------------- estados
EST_DIR = os.path.join(DADOS, "estados")
def ler_est(nome):
    caminho = os.path.join(EST_DIR, nome)
    if not os.path.exists(caminho): return []
    with io.open(caminho, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def _num(v):
    try: return float(str(v).replace(",", "."))
    except: return None

cand_uf = ler_est("candidatos-estados.csv")
pesq_uf = ler_est("pesquisas-estados.csv")
PAL = ["#D62828", "#1F5FBF", "#1baf7a", "#eda100", "#7B4BC9", "#0A9396", "#e87ba4", "#EB6834", "#5A6B7B", "#8B5E00",
       "#2E86AB", "#C05299", "#6A994E", "#BC6C25", "#3D5A80", "#9E2A2B", "#52796F", "#D4A373"]
ufs = {}
for c in cand_uf:
    u = ufs.setdefault(c["uf"], {"sigla": c["uf"], "nome": c["estado"], "regiao": c["regiao"],
                                 "gov": [], "sen": [], "polls": [], "rodadas": [], "colig": {}})
    ficha = {"nome": c["nome_urna"], "completo": c["nome_completo"], "num": c["numero"],
             "partido": c["partido"], "colig": c["coligacao"], "sit": c["situacao_tse"],
             "slug": c["slug"], "url": c["url_tse"], "cargo": c["cargo"]}
    u["gov" if c["cargo"] == "governador" else "sen"].append(ficha)
    if c["coligacao"]:
        u["colig"].setdefault(c["coligacao"], set()).add(c["partido"])

# ---- deputado estadual e federal: grupo curado, por enquanto só RJ e SP.
# Proporcional não tem pesquisa nominal registrada (é prática do mercado), então esses
# dois cargos entram só com a ficha do TSE: nenhuma rodada, nenhum ponto, nenhuma vaga
# cortada. E a lista é curada, não o registro inteiro, então esses nomes nunca entram
# nas contagens que dizem "todas as candidaturas registradas" (partidos, coligações,
# lede do estado): eles só aparecem onde o cargo escolhido é o deles.
DEP_DIR = os.path.join(DADOS, "rjsp")
DEP_COLS = ("uf", "cargo", "id_tse", "nome_urna", "nome_completo", "numero", "partido",
            "situacao_tse", "slug", "url_tse")

def cargo_dep(v):
    t = (v or "").strip().lower()
    if "federal" in t: return "depfed"
    if "estadual" in t or "distrital" in t: return "depest"
    return None

def ler_dep():
    caminho = os.path.join(DEP_DIR, "candidatos-deputados.csv")
    if not os.path.exists(caminho): return []
    with io.open(caminho, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    if not linhas: return []
    falta = [c for c in DEP_COLS if c not in linhas[0]]
    if falta:
        raise SystemExit("candidatos-deputados.csv sem as colunas: " + ", ".join(falta))
    return linhas

for c in ler_dep():
    u = ufs.get(c["uf"])
    if u is None:                      # estado sem ficha estadual: não se inventa um
        print("aviso: deputados de", c["uf"], "sem estado correspondente, linha ignorada")
        continue
    cargo = cargo_dep(c["cargo"])
    if cargo is None:
        raise SystemExit("cargo de deputado não reconhecido em candidatos-deputados.csv: " + repr(c["cargo"]))
    ficha = {"nome": c["nome_urna"], "completo": c["nome_completo"], "num": c["numero"],
             "partido": c["partido"], "colig": c.get("coligacao", ""), "sit": c["situacao_tse"],
             "slug": c["slug"], "url": c["url_tse"], "cargo": cargo, "id_tse": c["id_tse"]}
    cat = (c.get("categoria") or "").strip().upper()
    if cat: ficha["cat"] = cat
    u.setdefault(cargo, []).append(ficha)

# o detalhe de cada deputado curado vem do arquivo completo do TSE, casado por id_tse (nunca por
# nome: proporcional tem milhares de candidatos e homônimo é regra, não exceção)
def enriquecer_deputados():
    caminho = os.path.join(DEP_DIR, "candidatos-rjsp.csv")
    if not os.path.exists(caminho): return {}
    with io.open(caminho, encoding="utf-8-sig") as f:
        return {r["id_tse"]: r for r in csv.DictReader(f)}

det_dep = enriquecer_deputados()
for u in ufs.values():
    for k in ("depfed", "depest"):
        for c in u.get(k, []):
            d = det_dep.get(c.get("id_tse"))
            if not d: continue
            anos = [a for a in (d.get("anos_anteriores") or "").split() if a]
            c["ext"] = {"bens": _num(d["bens_total"]) if d["bens_total"] != "" else None,
                        "nbens": int(d["bens_qtd"] or 0), "instr": d["escolaridade"], "ocup": d["ocupacao"],
                        "nasc": d["nascimento"], "vice": "", "comp": d["composicao_coligacao"],
                        "nascUF": d["uf_nascimento"], "nascMun": d["municipio_nascimento"],
                        "ig": d["instagram"], "tt": d["tiktok"], "fb": d["facebook"], "yt": d["youtube"],
                        "x": d["x"], "site": d["site"],
                        "foto": "https://divulgacandcontas.tse.jus.br/divulga/rest/arquivo/img/20322002026/%s/%s" % (d["id_tse"], d["uf"]),
                        "ant": "; ".join(anos)}

for u in ufs.values():
    for k in ("gov", "sen", "depfed", "depest"):
        if k not in u: continue
        u[k].sort(key=lambda c: (len(c["num"]), c["num"]))
        for i, c in enumerate(u[k]):
            c["cor"] = PAL[i % len(PAL)]
    # a ordem dos botões do seletor de disputa sai daqui: só os cargos que o estado tem
    u["cargos"] = [k for k in ("governador", "senador", "depfed", "depest")
                   if u.get({"governador": "gov", "senador": "sen", "depfed": "depfed", "depest": "depest"}[k])]
    u["colig"] = {k: sorted(v) for k, v in sorted(u["colig"].items())}

# ---- pesquisas estaduais: consolidado (Wikipédia + Gazeta) quando existir; senão, só as rodadas da Gazeta
cons_uf = ler_est("pesquisas-estados-consolidado.csv")
MUTED = ["#8E9AAF", "#A98467", "#6C757D", "#B08968", "#7F8C8D", "#95A5A6", "#A0A0A0", "#8D99AE", "#9C6644", "#adb5bd"]
if cons_uf:
    rod_idx = {}
    for r in cons_uf:
        u = ufs.get(r["uf"])
        if not u: continue
        if not r["data_ref"].startswith("2026"): continue   # o mural acompanha a série de 2026
        pct = _num(r["percentual"])
        if pct is None: continue
        turno = int(r["turno"] or 1)
        rk = (r["uf"], r["cargo"], turno, r["instituto"], r["data_ref"], r["cenario"] if turno == 2 else "")
        if rk not in rod_idx:
            rod_idx[rk] = {"cargo": r["cargo"], "turno": turno, "inst": r["instituto"], "data": r["data_ref"], "div": r["data_divulgacao"],
                           "reg": r["registro_tse"], "amostra": r["amostra"], "margem": r["margem_erro"], "modo": r["metodologia"] or "não informada",
                           "contratante": r["contratante"], "campo": (r["campo_inicio"] + " a " + r["campo_fim"]) if r["campo_inicio"] and r["campo_inicio"] != r["campo_fim"] else r["campo_fim"],
                           "url": "" if "wikipedia.org" in r["url"] else r["url"],
                           "fonte": "WG" if "Gazeta" in r["fonte"] and "Wikip" in r["fonte"] else ("G" if "Gazeta" in r["fonte"] or "TSE" in r["fonte"] else "W"),
                           "par": r["cenario"] if turno == 2 else "", "cens": set(), "uf": r["uf"]}
            if "wikipedia.org" in r["url"]: u["wiki_url"] = r["url"]
            if turno == 1: u["rodadas"].append(rod_idx[rk])
        rod = rod_idx[rk]
        rod["cens"].add(str(r["cenario"]))
        if turno == 1 and r["principal"] == "1":
            u["polls"].append([r["cargo"], r["instituto"], r["data_ref"], r["candidato"], pct, r["slug"], "", r["partido"]])
        elif turno == 1:
            u.setdefault("cenarios", []).append([r["cargo"], r["instituto"], r["data_ref"], str(r["cenario"]), r["candidato"], pct, r["slug"], r["partido"]])
        else:
            u.setdefault("polls2", []).append([r["instituto"], r["data_ref"], r["cenario"], r["candidato"], pct, r["slug"], r["partido"]])
    for rod in rod_idx.values():
        rod["ncen"] = len(rod["cens"]); del rod["cens"]
else:
    for r in pesq_uf:
        u = ufs.get(r["uf"])
        if not u: continue
        try: pct = float(r["percentual"])
        except: continue
        u["polls"].append([r["cargo"], r["instituto"], r["data_divulgacao"], r["candidato"], pct, "", "", ""])
        ch = (r["cargo"], r["instituto"], r["data_divulgacao"])
        if not any((x["cargo"], x["inst"], x["data"]) == ch for x in u["rodadas"]):
            u["rodadas"].append({"cargo": r["cargo"], "turno": 1, "inst": r["instituto"], "data": r["data_divulgacao"], "div": r["data_divulgacao"],
                                 "reg": r["registro_tse"], "amostra": r["amostra"], "margem": r["margem_erro"],
                                 "modo": r["metodologia"], "contratante": r["contratante"],
                                 "campo": r["data_campo"], "url": r["url"], "fonte": "G", "par": "", "ncen": 1})
for u in ufs.values():
    u["rodadas"].sort(key=lambda x: (x["data"], x["inst"]), reverse=True)
    for rod in u["rodadas"]: rod.pop("uf", None)
    # casar nome da pesquisa com o candidato registrado (por nome de urna aproximado) quando o consolidado não trouxe slug
    def achar(cargo, nome):
        alvo = nome.lower()
        pool = u["gov"] if cargo == "governador" else u["sen"]
        for c in pool:
            if c["nome"].lower() == alvo: return c
        for c in pool:
            a, b = c["nome"].lower(), alvo
            if a.startswith(b) or b.startswith(a) or (len(b) > 4 and b in a) or (len(a) > 4 and a in b): return c
        prim = alvo.split()[0]
        for c in pool:
            if c["nome"].lower().split()[0] == prim and len(prim) > 3: return c
        return None
    por_slug = {c["slug"]: c for c in u["gov"] + u["sen"]}
    muted_idx = {}
    def cor_de(cargo, nome, slug):
        c = por_slug.get(slug) if slug else achar(cargo, nome)
        if c: return c["slug"], c["cor"]
        k = (cargo, nome)
        if k not in muted_idx: muted_idx[k] = MUTED[len(muted_idx) % len(MUTED)]
        return "", muted_idx[k]
    for p in u["polls"]:
        slug, cor = cor_de(p[0], p[3], p[5]); p[5] = slug; p[6] = cor
        if slug: p[7] = ""
    for p in u.get("cenarios", []):
        slug, cor = cor_de(p[0], p[4], p[6]); p[6] = slug; p.append(cor)
        if slug: p[7] = ""
    for p in u.get("polls2", []):
        slug, cor = cor_de("governador", p[3], p[5]); p[5] = slug; p.append(cor)
        if slug: p[6] = ""

def parse_composicao(txt):
    """'PSB / PDT / FEDERAÇÃO BRASIL DA ESPERANÇA - FE BRASIL(PT/PC do B/PV) / MDB' -> lista de partidos, federações expandidas"""
    out, buf, depth = [], "", 0
    for ch in txt:
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "/" and depth == 0:
            out.append(buf); buf = ""
        else:
            buf += ch
    out.append(buf)
    partidos = []
    for tok in out:
        tok = tok.strip()
        if not tok: continue
        m = re.search(r"\(([^)]*)\)", tok)
        if m and "FEDERA" in tok.upper():
            for p in m.group(1).split("/"):
                p = p.strip()
                if p and p not in partidos: partidos.append(p)
        else:
            tok = re.sub(r"\s*\(.*\)$", "", tok).strip()
            if tok and tok not in partidos: partidos.append(tok)
    return partidos

# ---- coleta própria de busca e redes + detalhe do TSE por candidato
det_uf = {r["slug"]: r for r in ler_est("candidatos-detalhe.csv")}
for u in ufs.values():
    for c in u["gov"] + u["sen"]:
        d = det_uf.get(c["slug"])
        if not d: continue
        c["ext"] = {"bens": _num(d["total_bens"]) if d["total_bens"] != "" else None, "nbens": int(d["n_bens"] or 0), "instr": d["instrucao"], "ocup": d["ocupacao"],
                    "nasc": d["data_nascimento"], "vice": d["vice"], "comp": d["composicao_coligacao"], "nascUF": d["uf_nascimento"], "nascMun": d["municipio_nascimento"],
                    "ig": d["instagram"], "tt": d["tiktok"], "fb": d["facebook"], "yt": d["youtube"], "x": d["x"], "site": d["site"], "foto": d["foto_url"], "ant": d["eleicoes_anteriores"]}
        if d["composicao_coligacao"] and c["colig"]:
            u["colig"][c["colig"]] = parse_composicao(d["composicao_coligacao"])
import datetime as _dt
DIA0 = _dt.date(2026, 1, 1)
def serie_str(pares):
    """série diária alinhada a DIA0: valores separados por vírgula, vazio = sem dado; zeros à direita cortados"""
    m = {}
    for d, v in pares:
        try: i = (_dt.date.fromisoformat(d) - DIA0).days
        except Exception: continue
        if i < 0: continue
        vv = str(v)
        if vv.endswith(".0"): vv = vv[:-2]
        m[i] = vv
    if not m: return ""
    n = max(m) + 1
    arr = [m.get(i, "") for i in range(n)]
    while arr and arr[-1] in ("", "0"): arr.pop()
    return ",".join(arr)
busca_uf = {}
def bkt(uf): return busca_uf.setdefault(uf, {"tr": {}, "trn": {}, "wk": {}, "ig": {}, "data": ""})
_tr = {}
for r in ler_est("trends-estados.csv"):
    if not r["slug"]: continue
    _tr.setdefault((r["uf"], r["slug"]), []).append((r["data"], r["indice"]))
    if r["nota"]: bkt(r["uf"])["trn"][r["slug"]] = r["nota"]
    bkt(r["uf"])["data"] = r["fonte"][-10:]
for (uf, slug), pares in _tr.items():
    vals = [(d, (str(int(float(v))) if float(v) == int(float(v)) else v)) for d, v in pares]
    if all(float(v) == 0 for _, v in vals): continue   # sem sinal: fica em branco, não zero
    bkt(uf)["tr"][slug] = serie_str(vals)
_wk = {}
for r in ler_est("wikipedia-estados.csv"):
    _wk.setdefault((r["uf"], r["slug"]), {"t": r["verbete"], "p": []})["p"].append((r["data"], r["pageviews"]))
for (uf, slug), w in _wk.items():
    bkt(uf)["wk"][slug] = {"t": w["t"], "pv": serie_str(w["p"])}
for r in ler_est("instagram-estados.csv"):
    if r["seguidores"] == "": continue
    e = {"h": r["handle"], "n": int(float(r["seguidores"])), "d": r["data"]}
    if r.get("aproximado") in ("1", "true", "True"): e["a"] = 1
    bkt(r["uf"])["ig"][r["slug"]] = e
for k, u in ufs.items():
    if k in busca_uf: u["busca"] = busca_uf[k]

# ---- compactação: nomes em tabela, pontos referenciando a rodada por índice (o template expande de volta)
def compactar(v):
    nomes = []; nidx = {}
    def n_id(nome, slug, partido, cor):
        k = (nome, slug)
        if k not in nidx:
            nidx[k] = len(nomes); nomes.append([nome, slug, partido if not slug else "", cor if not slug else ""])
        return nidx[k]
    ridx = {(r["cargo"], r["inst"], r["data"]): i for i, r in enumerate(v["rodadas"])}
    polls = []
    for p in v["polls"]:
        i = ridx.get((p[0], p[1], p[2]))
        if i is None: continue
        polls.append([i, n_id(p[3], p[5], p[7], p[6]), p[4]])
    cens = []
    for p in v.get("cenarios", []):
        i = ridx.get((p[0], p[1], p[2]))
        if i is None: continue
        cens.append([i, p[3], n_id(p[4], p[6], p[7], p[8]), p[5]])
    # segundo turno: rodadas próprias (par)
    r2 = []; r2idx = {}
    polls2 = []
    for p in v.get("polls2", []):
        k = (p[0], p[1], p[2])
        if k not in r2idx:
            r2idx[k] = len(r2); r2.append({"inst": p[0], "data": p[1], "par": p[2]})
        polls2.append([r2idx[k], n_id(p[3], p[5], p[6], p[7]), p[4]])
    return {"nomes": nomes, "polls": polls, "cenarios": cens, "rodadas2": r2, "polls2": polls2}

for u in ufs.values():
    for k in ("depfed", "depest"):
        for c in u.get(k, []): c.pop("id_tse", None)

estados = {}
for k, v in sorted(ufs.items()):
    c = compactar(v)
    estados[k] = {"sigla": v["sigla"], "nome": v["nome"], "regiao": v["regiao"], "gov": v["gov"], "sen": v["sen"],
                  "cargos": v["cargos"], "rodadas": v["rodadas"], "colig": v["colig"],
                  "wiki_url": v.get("wiki_url", ""), "busca": v.get("busca"), **c}
    for dep in ("depfed", "depest"):
        if v.get(dep): estados[k][dep] = v[dep]

GEO_PATH = os.path.join(DADOS, "geo", "br-uf-paths.json")
geo = json.load(io.open(GEO_PATH, encoding="utf-8")) if os.path.exists(GEO_PATH) else None

data = {"estados": estados, "geo": geo, "dia0": DIA0.isoformat(), "atualizado": ATUALIZADO, "candidatos": out, "polls": polls_main, "polls2t": polls_2t,
        "rej": rej, "institutos": institutos, "meta": meta, "fichas": fichas,
        "ig": ig_serie, "series": {k: dict(v) for k, v in series_plat.items()}, "idx": idx_serie, "partidos": partidos, "timeline": timeline,
        "trends": trends_c, "termos": trends_t, "wiki": wiki, "vies": vies}

# ---- o que a página pública carrega e o que fica atrás do cadastro
# A aba principal (Visão geral da Presidência) é aberta a todo mundo; o resto do mural pede
# conta. Isso só é de verdade se o dado não estiver na página: uma trava em JavaScript com os
# 2,2 MB dentro do HTML é cortina, não parede. Então o gerador escreve duas cargas.
#
# A divisão foi medida, não chutada: com estas chaves de fora, a aba principal renderiza
# idêntica à do mural inteiro (conferido linha a linha no texto da seção), e a página cai de
# 2,2 MB para cerca de 600 KB, o que também a deixa mais rápida para quem chega pelo link.
#
# Aviso que precisa ficar escrito: o repositório é público, e os CSVs e este gerador estão
# nele. Quem quiser refaz a carga protegida sozinho. A trava serve ao produto (cadastro,
# personalização, exportação), não à proteção do dado; para ser proteção, o repositório teria
# de ser privado.
PROTEGIDO = ("estados", "geo", "wiki", "termos", "ig", "idx", "series", "vies", "rej", "polls2t")
VAZIO = {"estados": {}, "geo": None, "wiki": {}, "termos": {}, "ig": {}, "idx": {},
         "series": {}, "vies": [], "rej": [], "polls2t": []}

tpl = io.open(os.path.join(AQUI, "_template.html"), encoding="utf-8").read()
# As chaves do Supabase entram por ambiente (o workflow passa dos segredos do repositório).
# São valores públicos por definição: a URL do projeto e a chave "anon", que só serve para
# falar com o Supabase respeitando as regras de acesso por linha. Nada de chave de serviço aqui.
SUPA_URL = _os.environ.get("MURAL_SUPABASE_URL", "")
SUPA_ANON = _os.environ.get("MURAL_SUPABASE_ANON", "")
CARGA_URL = _os.environ.get("MURAL_CARGA_URL", "mural-completo.json")

# A divisão só acontece quando existe cadastro para devolver o que foi tirado. Sem as chaves
# configuradas o template deixa TRAVA falsa, ninguém consegue entrar e ninguém hidrata a carga:
# dividir aí não tranca a página, apaga a página. Foi exatamente o que aconteceu quando esta
# condição não existia (bug do mural publicado sem estados nem deputados, 10/9/2026). Quem manda
# na divisão é a mesma coisa que manda na trava, para os dois nunca discordarem.
TRAVA = bool(SUPA_URL and SUPA_ANON)
publico = ({k: (VAZIO[k] if k in PROTEGIDO else v) for k, v in data.items()}
           if TRAVA else dict(data))
protegido = {k: data[k] for k in PROTEGIDO}

def montar(d):
    return (tpl.replace("/*__DATA__*/", "const DATA = " + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";")
               .replace("__SUPABASE_URL__", SUPA_URL).replace("__SUPABASE_ANON__", SUPA_ANON)
               .replace("__CARGA_URL__", CARGA_URL))

html = montar(publico)
io.open(os.path.join(AQUI, "mural.html"), "w", encoding="utf-8").write(html)
# a carga protegida, que a página busca depois do login
js_prot = json.dumps(protegido, ensure_ascii=False, separators=(",", ":"))
io.open(os.path.join(AQUI, "..", "mural-completo.json"), "w", encoding="utf-8").write(js_prot)
# o mural inteiro num arquivo só continua existindo para conferência e para os testes, que
# precisam ver todas as abas sem passar por login
io.open(os.path.join(AQUI, "mural-inteiro.html"), "w", encoding="utf-8").write(montar(data))
# O GitHub Pages serve a raiz do repositório, então a mesma página também é
# gravada em index.html lá em cima: assim o endereço publicado é a raiz do
# site, e não /mural/mural.html. Os dois arquivos são idênticos e ambos são
# gerados; mural.html continua sendo o canônico.
io.open(os.path.join(AQUI, "..", "index.html"), "w", encoding="utf-8").write(html)
# ---- politica de privacidade
# Gerada a partir do que o site faz de fato, com a identificacao de quem responde pelos dados
# vinda de notas/organizacao.json. Enquanto esses campos estiverem por preencher, a pagina sai
# com um aviso visivel e a regressao barra a publicacao com o cadastro ligado: cadastro no ar
# com politica incompleta e o tipo de coisa que nao pode passar por descuido.
ORG_PATH = os.path.join(AQUI, "..", "notas", "organizacao.json")
org = json.load(io.open(ORG_PATH, encoding="utf-8")) if os.path.exists(ORG_PATH) else {}
falta = [k for k in ("nome", "cnpj", "endereco", "email", "encarregado")
         if str(org.get(k, "")).startswith("PREENCHER") or not org.get(k)]
_meses_pv = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
_hoje_pv = _dt.datetime.now(_ZI("America/Sao_Paulo")) if hasattr(_dt, "datetime") else _dt.now(_ZI("America/Sao_Paulo"))
aviso = ("" if not falta else
         '<p class="falta"><b>Esta politica ainda esta incompleta.</b> Faltam preencher: '
         + ", ".join(falta) + '. Enquanto isso, o cadastro nao deve ser aberto ao publico.</p>')
pv = io.open(os.path.join(AQUI, "_privacidade.html"), encoding="utf-8").read()
_troca = [("__DATA_POLITICA__", "%d de %s de %d" % (_hoje_pv.day, _meses_pv[_hoje_pv.month - 1], _hoje_pv.year)),
          ("__AVISO_LACUNA__", aviso),
          ("__ORG_NOME__", org.get("nome", "")), ("__ORG_CNPJ__", org.get("cnpj", "")),
          ("__ORG_ENDERECO__", org.get("endereco", "")), ("__ORG_EMAIL__", org.get("email", "")),
          ("__ORG_ENCARREGADO__", org.get("encarregado", ""))]
for _k, _v in _troca:
    pv = pv.replace(_k, _v)
io.open(os.path.join(AQUI, "..", "privacidade.html"), "w", encoding="utf-8").write(pv)

ndep = sum(len(e.get("depfed", [])) + len(e.get("depest", [])) for e in estados.values())
print("mural.html", len(html), "bytes público +", len(js_prot), "bytes protegidos |", len(estados), "estados |", sum(len(e["gov"])+len(e["sen"]) for e in estados.values()), "candidatos estaduais |", ndep, "deputados curados |", len(out), "presidenciais |", len(polls_main), "pontos 1T |",
      len(rej), "pontos rejeição |", len(polls_2t), "pontos 2T |", sum(len(v) for v in ig_serie.values()), "pontos IG |",
      len(timeline), "eventos |", meta)
