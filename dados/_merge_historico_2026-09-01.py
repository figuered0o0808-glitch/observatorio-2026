# -*- coding: utf-8 -*-
"""1/9/2026, terceira rodada: funde o histórico 2026 de pesquisas, seguidores e marcos."""
import csv, io, os, re, shutil, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
MURAL = "/home/claude/mural"

def ler(caminho):
    with io.open(caminho, encoding="utf-8-sig") as f:
        r = csv.reader(f); cab = next(r); return cab, [row for row in r]

def gravar(nome, cab, linhas):
    with open(os.path.join(BASE, nome), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cab); w.writerows(linhas)
    print(nome, len(linhas), "linhas")

# ------------------------------------------------------------- pesquisas
cabP, old = ler(os.path.join(BASE, "pesquisas-registradas.csv"))
_, A = ler(os.path.join(MURAL, "pesquisas-2026-A.csv"))
_, B = ler(os.path.join(MURAL, "pesquisas-2026-B.csv"))
# novos vêm com coluna extra observacao; o esquema antigo não tem. Adota o novo esquema (13 colunas).
CABP = ["instituto","data_campo_inicio","data_campo_fim","data_divulgacao","metodologia","cenario",
        "candidato","percentual","rejeicao","margem_erro","registro_tse","url","observacao"]
def norm_inst(x):
    return {"AtlasIntel":"AtlasIntel/Bloomberg"}.get(x, x)
novos = []
for r in A + B:
    r = list(r); r[0] = norm_inst(r[0]); novos.append(r)
rodadas_novas = {(r[0], r[3]) for r in novos}
chaves_novas = {(r[0], r[3], r[5], r[6]) for r in novos}
KEEP_RE = re.compile(r"anos|imagem|definitivo|mulheres")
mantidos = 0
saida = list(novos)
for r in old:
    r13 = r + [""] if len(r) == 12 else r
    inst, div, cen, cand = r13[0], r13[3], r13[5], r13[6]
    if (inst, div) in rodadas_novas:
        if (inst, div, cen, cand) in chaves_novas:
            continue  # versão nova substitui
        if not KEEP_RE.search(cen):
            continue  # cenário equivalente sob outro nome (ex.: com/sem Marçal)
    saida.append(r13); mantidos += 1
print("pesquisas: antigos mantidos", mantidos)
saida.sort(key=lambda r: (r[3], r[0], r[5], r[6]))
gravar("pesquisas-registradas.csv", CABP, saida)

# ------------------------------------------------------------- serie diaria
cabS, serie = ler(os.path.join(BASE, "serie-diaria.csv"))
_, hist = ler(os.path.join(MURAL, "seguidores-historico.csv"))
def parse_valor(v):
    v = v.strip()
    if not v: return None, False
    m = re.match(r"^([\d.,]+)\s*(milh(ão|ões)|mi)$", v)
    if m:
        return int(round(float(m.group(1).replace(".", "").replace(",", ".")) * 1e6)), True
    m = re.match(r"^([\d.,]+)\s*mil$", v)
    if m:
        return int(round(float(m.group(1).replace(".", "").replace(",", ".")) * 1e3)), True
    limpo = v.replace(".", "").replace(",", ".")
    try:
        f = float(limpo)
        if "," in v or v.replace(".", "").isdigit():
            return (f if f < 1000 else int(round(f))), False
    except: pass
    return None, False
PLAT = {"Instagram":"instagram","TikTok":"tiktok","X":"x","YouTube":"youtube"}
exist = {(r[0], r[1], r[2]) for r in serie}
add = 0
for d, cand, plat, val, fonte, url, obs in hist:
    plat_s = PLAT.get(plat, plat.lower())
    v, arred = parse_valor(val)
    if v is None: continue
    chave = (d, cand, plat_s)
    if chave in exist: continue
    exist.add(chave)
    o = (obs + "; " if obs else "") + ("valor arredondado pela fonte" if arred else "")
    if plat_s in ("datrix_idp", "quaest_ipd"):
        linha = [d, cand, plat_s, "", "", v, "", fonte, url, o.strip("; ")]
    else:
        linha = [d, cand, plat_s, int(v), "", "", "", fonte, url, o.strip("; ")]
    serie.append(linha); add += 1
print("serie: adicionadas", add)
serie.sort(key=lambda r: (r[0], r[2], r[1]))
gravar("serie-diaria.csv", cabS, serie)

# ------------------------------------------------------------- eventos + marcos
cabE, ev = ler(os.path.join(BASE, "eventos.csv"))
_, marcos = ler(os.path.join(MURAL, "marcos-2026.csv"))
def toks(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 3}
descartados = []
for d, cand, titulo, cat, desc, url in marcos:
    dup = False
    for e in ev:
        if e[0] == d and (cand in e[1] or e[1] in cand or e[1] == "todos" or cand == "todos"):
            t1, t2 = toks(titulo), toks(e[2])
            if t1 and t2 and len(t1 & t2) / min(len(t1), len(t2)) >= 0.5:
                dup = True; descartados.append((d, cand, titulo, "≈", e[2])); break
    if not dup:
        ev.append([d, cand, titulo, cat, desc, url])
print("marcos: incorporados", len(marcos) - len(descartados), "; duplicados descartados", len(descartados))
for x in descartados: print("  DUP:", x[0], x[1], "|", x[2][:60], x[3], x[4][:60])
ev.sort(key=lambda r: (r[0], r[1]))
gravar("eventos.csv", cabE, ev)

# ------------------------------------------------------------- partidos
shutil.copy(os.path.join(MURAL, "partidos.csv"), os.path.join(BASE, "partidos.csv"))
shutil.copy(os.path.join(MURAL, "seguidores-historico.csv"), os.path.join(BASE, "seguidores-historico-fontes.csv"))
print("partidos.csv e seguidores-historico-fontes.csv copiados")
