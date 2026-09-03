# -*- coding: utf-8 -*-
"""Consolida as pesquisas estaduais em um único CSV, sem misturar fontes numa mesma linha:
- pesquisas-estados-wiki.csv: séries completas de 2026 compiladas na Wikipédia (governo e Senado, 1º e 2º turno, cenários);
- pesquisas-estados.csv: rodadas com ficha técnica registrada no TSE, via Gazeta do Povo (registro, modo, contratante).
Quando a mesma rodada aparece nas duas, os números vêm da compilação da Wikipédia (cenário completo) e a ficha
técnica (registro, modo de coleta, contratante, data de divulgação, URL) vem da Gazeta; a coluna `fonte` diz isso.
Cenário principal de cada rodada de 1º turno: o que mais coincide com as candidaturas registradas no TSE.
Saída: pesquisas-estados-consolidado.csv
"""
import csv, io, os, re, unicodedata, datetime as dt

AQUI = os.path.dirname(os.path.abspath(__file__))
WIKI = os.path.join(AQUI, "pesquisas-estados-wiki.csv")
GAZ = os.path.join(AQUI, "pesquisas-estados.csv")
CAND = os.path.join(AQUI, "candidatos-estados.csv")
OUT = os.path.join(AQUI, "pesquisas-estados-consolidado.csv")

def ler(p):
    if not os.path.exists(p): return []
    with io.open(p, encoding="utf-8-sig") as f: return list(csv.DictReader(f))

def norm(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()

INSTITUTOS = ["quaest", "ipec", "atlasintel", "datafolha", "real time big data", "parana pesquisas", "verita", "datatrends",
              "futura", "neokemp", "gerp", "vox populi", "meio", "ideia", "instituto opiniao", "consult", "perfil", "big data",
              "paraná pesquisas", "mda", "cnt", "ipespe", "poder data", "poderdata", "exame", "modalmais", "futura inteligencia",
              "brasmarket", "instituto veritá", "instituto futura", "amostragem", "methodus", "ranking", "phd", "ibrape", "opinião", "opiniao",
              "instituto paraná", "instituto verita", "voxx", "escutec", "dataway", "diagnóstico", "diagnostico", "iag", "ibope", "inteligência", "spin"]

def normaliza_instituto(bruto):
    """'Genial/Quaest' -> ('Quaest','Genial'); 'AtlasIntel/Focus' -> ('AtlasIntel','Focus'); 'Paraná Pesquisas' -> ('Paraná Pesquisas','')."""
    b = (bruto or "").strip()
    if "/" in b:
        esq, dir_ = [x.strip() for x in b.split("/", 1)]
        ne, nd = norm(esq), norm(dir_)
        if any(k in ne for k in ("atlasintel", "futura", "quaest", "datafolha", "real time", "parana", "verita", "ipec", "ipsos")) and not any(k in nd for k in ("quaest", "ipec", "ipsos", "atlas")):
            inst, contr = esq, dir_
        else:
            inst, contr = dir_, esq
    else:
        inst, contr = b, ""
    ni = norm(inst)
    if "ipec" in ni or "ipsos" in ni or "ipsus" in ni: inst = "Ipsos-Ipec"
    if norm(contr) in ("ipsus", "ipsos", "ipec", "genial") and inst in ("Ipsos-Ipec",): contr = ""
    elif "quaest" in ni: inst = "Quaest"
    elif "atlas" in ni: inst = "AtlasIntel"
    elif "real time" in ni or "realtime" in ni: inst = "Real Time Big Data"
    elif "parana" in ni: inst = "Paraná Pesquisas"
    elif "datafolha" in ni: inst = "Datafolha"
    elif "verita" in ni: inst = "Veritá"
    elif "futura" in ni: inst = "Futura"
    elif "datatrends" in ni: inst = "DataTrends"
    elif "neokemp" in ni: inst = "Neokemp"
    elif "meio" in ni and "ideia" in ni: inst = "Ideia"
    elif "poder" in ni and "data" in ni: inst = "PoderData"
    elif "gerp" in ni: inst = "Gerp"
    return inst, contr

def data_campo_gazeta(txt, data_div):
    """'23 a 26/08/2026' | '26/08/2026' | '23/08 a 26/08/2026' -> (ini, fim)"""
    t = (txt or "").strip()
    m = re.findall(r"(\d{1,2})(?:/(\d{1,2}))?(?:/(\d{4}))?", t)
    ano = data_div[:4] if data_div else "2026"
    if not m: return "", ""
    # último grupo é o fim
    d2, m2, y2 = m[-1]
    if not m2:
        return "", ""
    y2 = y2 or ano
    fim = f"{y2}-{int(m2):02d}-{int(d2):02d}"
    d1, m1, y1 = m[0]
    m1 = m1 or m2; y1 = y1 or y2
    ini = f"{y1}-{int(m1):02d}-{int(d1):02d}"
    return ini, fim

def dias(a, b):
    try:
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)
    except Exception:
        return 999

def main():
    cands = ler(CAND)
    pool = {}
    for c in cands:
        pool.setdefault((c["uf"], c["cargo"]), []).append(c)

    TITULOS = {"dr", "dra", "prof", "professor", "professora", "delegado", "delegada", "capitao", "capitã", "capita", "general", "coronel", "major", "sargento",
               "pastor", "pastora", "bispo", "padre", "doutor", "doutora", "deputado", "deputada", "senador", "senadora", "prefeito", "prefeita", "vereador", "vereadora",
               "governador", "governadora", "de", "da", "do", "das", "dos", "e", "o", "a", "junior", "jr", "filho", "neto", "sobrinho", "irmao", "tenente", "cabo", "soldado", "policial", "cb", "sd", "sgt"}
    def toks(n):
        return [t for t in re.split(r"[^a-z0-9]+", norm(n)) if t and t not in TITULOS and len(t) >= 2]
    # siglas que são, elas próprias, partidos distintos e usados de forma independente no registro
    # (não só fragmento de abreviação de outro) -- evita que "PSD" case com "PSDB" só por ser prefixo
    # textual (auditoria de 2/9/2026: era a causa de pelo menos 1 atribuição errada confirmada;
    # abreviações legítimas como "CID"->"CIDADANIA" continuam funcionando, porque só um lado ali é
    # uma sigla usada sozinha no registro)
    partidos_registro = {norm(c["partido"]) for c in cands if c["partido"]}
    def casar(uf, cargo, nome, partido=""):
        ps = pool.get((uf, cargo), [])
        if not ps: return None
        alvo = norm(nome); np_ = norm(partido)
        def pmatch(c):
            if not np_: return False
            pc = norm(c["partido"])
            if pc == np_: return True
            if np_ in pc or pc in np_:
                if np_ in partidos_registro and pc in partidos_registro and np_ != pc: return False
                return True
            return False
        for c in ps:
            if norm(c["nome_urna"]) == alvo: return c
        tn = toks(nome)
        if not tn: return None
        melhores = []
        for c in ps:
            tc = toks(c["nome_urna"]) + toks(c["nome_completo"])
            comuns = [t for t in tn if t in tc]
            prefixo = any(len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)) for a in tn for b in toks(c["nome_urna"]))
            pm = pmatch(c)
            # piso: precisa de alguma evidência léxica (token em comum ou prefixo) antes de qualquer
            # coisa -- sem isso, um partido batendo sozinho (zero tokens em comum) já bastaria para
            # "ganhar" um pool só por ser o único candidato daquele partido ali, o que é errado
            if not (comuns or prefixo): continue
            # barra mínima para aceitar um candidato por match difuso: precisa de nome E sobrenome
            # batendo (>=2 tokens em comum) OU confirmação de partido. Um token genérico isolado
            # (um nome ou sobrenome comum, tipo "Carlos" ou "Silva") sem partido é exatamente o
            # padrão por trás de toda atribuição errada confirmada na auditoria de 2/9/2026 (ver
            # notas/estados-metodo-2026-09-02.md) -- fraco demais sozinho
            if len(comuns) < 2 and not pm: continue
            sc = len(comuns) * 2 + (1 if prefixo else 0) + (2 if pm else 0)
            melhores.append((sc, c, pm))
        if not melhores: return None
        melhores.sort(key=lambda x: -x[0])
        top_score = melhores[0][0]
        empatados = [m for m in melhores if m[0] == top_score]
        if len(empatados) > 1:
            # ambíguo: aceita só se exatamente um dos empatados no topo tem partido batendo
            # (checa o partido de cada empatado, não só do primeiro da lista, como antes)
            com_partido = [m for m in empatados if m[2]]
            if len(com_partido) == 1: return com_partido[0][1]
            return None
        return melhores[0][1]

    wiki = ler(WIKI)
    gaz = ler(GAZ)
    saida = []

    # ---- rodadas da Wikipédia
    rod_w = {}
    for r in wiki:
        inst, contr = normaliza_instituto(r["instituto_bruto"])
        turno = int(r["turno"] or 1)
        key = (r["uf"], r["cargo"], turno, inst, r["campo_fim"], r.get("tabela", "") if turno == 2 else "")
        rod = rod_w.setdefault(key, {"uf": r["uf"], "cargo": r["cargo"], "turno": turno, "instituto": inst, "contratante": contr,
                                     "campo_inicio": r["campo_inicio"], "campo_fim": r["campo_fim"], "amostra": r["amostra"],
                                     "margem_erro": r["margem_erro"], "pagina": r["pagina"], "revid": r["revid"], "secao": r["secao"],
                                     "cenarios": {}, "registro_tse": "", "metodologia": "", "data_divulgacao": "", "url": "", "fonte": "Wikipédia (compilação das divulgações), " + r["pagina"]})
        rod["cenarios"].setdefault(r["cenario"], []).append(r)

    # ---- rodadas da Gazeta (ficha técnica)
    rod_g = {}
    for r in gaz:
        inst, contr = normaliza_instituto(r["instituto"])
        ini, fim = data_campo_gazeta(r["data_campo"], r["data_divulgacao"])
        key = (r["uf"], r["cargo"], inst, r["data_divulgacao"])
        rod = rod_g.setdefault(key, {"uf": r["uf"], "cargo": r["cargo"], "instituto": inst, "contratante": r["contratante"] or contr,
                                     "data_divulgacao": r["data_divulgacao"], "campo_inicio": ini, "campo_fim": fim, "amostra": r["amostra"],
                                     "margem_erro": r["margem_erro"], "metodologia": r["metodologia"], "registro_tse": r["registro_tse"],
                                     "url": r["url"], "fonte": r["fonte"], "pontos": [], "casada": False})
        rod["pontos"].append(r)

    # casamento Gazeta -> Wikipédia (1º turno)
    for gk, g in rod_g.items():
        cand_keys = [k for k, w in rod_w.items() if w["uf"] == g["uf"] and w["cargo"] == g["cargo"] and w["turno"] == 1 and w["instituto"] == g["instituto"]
                     and (dias(w["campo_fim"], g["campo_fim"]) <= 3 if g["campo_fim"] else dias(w["campo_fim"], g["data_divulgacao"]) <= 6)]
        if cand_keys:
            w = rod_w[min(cand_keys, key=lambda k: dias(rod_w[k]["campo_fim"], g["campo_fim"] or g["data_divulgacao"]))]
            w["registro_tse"] = g["registro_tse"]; w["metodologia"] = g["metodologia"]; w["contratante"] = g["contratante"] or w["contratante"]
            w["data_divulgacao"] = g["data_divulgacao"]; w["url"] = g["url"]
            w["fonte"] = "números pela compilação da Wikipédia; ficha técnica (registro, modo, contratante) pela Gazeta do Povo"
            if not w["amostra"]: w["amostra"] = g["amostra"]
            if not w["margem_erro"]: w["margem_erro"] = g["margem_erro"]
            g["casada"] = True

    def par_de(w):
        """rótulo do confronto: os nomes das colunas da tabela, na ordem em que aparecem"""
        nomes = []
        for rows in w["cenarios"].values():
            for r in sorted(rows, key=lambda x: int(x.get("ordem_col") or 0)):
                if r["candidato"] not in nomes: nomes.append(r["candidato"])
        return " × ".join(nomes)
    # ---- emite rodadas da Wikipédia
    for key, w in rod_w.items():
        uf, cargo, turno = w["uf"], w["cargo"], w["turno"]
        # cenário principal (1º turno): maior coincidência com o TSE
        if turno == 1:
            score = {}
            for cen, rows in w["cenarios"].items():
                n = sum(1 for r in rows if casar(uf, cargo, r["candidato"], r["partido"]))
                score[cen] = (n, -len(rows) * 0, cen)
            principal = max(w["cenarios"], key=lambda c: (score[c][0], -int(re.sub(r"\D", "", c) or 99)))
        else:
            principal = None
        for cen, rows in w["cenarios"].items():
            for r in rows:
                c = casar(uf, cargo, r["candidato"], r["partido"])
                saida.append({
                    "uf": uf, "cargo": cargo, "turno": turno, "instituto": w["instituto"], "contratante": w["contratante"],
                    "data_ref": w["data_divulgacao"] or w["campo_fim"], "data_divulgacao": w["data_divulgacao"],
                    "campo_inicio": w["campo_inicio"], "campo_fim": w["campo_fim"], "amostra": w["amostra"], "margem_erro": w["margem_erro"],
                    "metodologia": w["metodologia"], "registro_tse": w["registro_tse"],
                    "cenario": (par_de(w) if turno == 2 else cen),
                    "principal": 1 if (turno == 2 or cen == principal) else 0,
                    "candidato": r["candidato"], "partido": r["partido"], "slug": c["slug"] if c else "", "percentual": r["percentual"],
                    "fonte": w["fonte"], "url": w["url"] or ("https://pt.wikipedia.org/wiki/" + w["pagina"].replace(" ", "_")), "revid": w["revid"],
                })
    # ---- rodadas da Gazeta sem par na Wikipédia
    for gk, g in rod_g.items():
        if g["casada"]: continue
        for r in g["pontos"]:
            c = casar(g["uf"], g["cargo"], r["candidato"])
            saida.append({
                "uf": g["uf"], "cargo": g["cargo"], "turno": 1, "instituto": g["instituto"], "contratante": g["contratante"],
                "data_ref": g["data_divulgacao"], "data_divulgacao": g["data_divulgacao"], "campo_inicio": g["campo_inicio"], "campo_fim": g["campo_fim"],
                "amostra": g["amostra"], "margem_erro": g["margem_erro"], "metodologia": g["metodologia"], "registro_tse": g["registro_tse"],
                "cenario": "1", "principal": 1, "candidato": r["candidato"], "partido": c["partido"] if c else "", "slug": c["slug"] if c else "",
                "percentual": r["percentual"], "fonte": g["fonte"], "url": g["url"], "revid": "",
            })
    cab = ["uf", "cargo", "turno", "instituto", "contratante", "data_ref", "data_divulgacao", "campo_inicio", "campo_fim", "amostra", "margem_erro",
           "metodologia", "registro_tse", "cenario", "principal", "candidato", "partido", "slug", "percentual", "fonte", "url", "revid"]
    saida.sort(key=lambda r: (r["uf"], r["cargo"], r["turno"], r["data_ref"], r["instituto"], str(r["cenario"]), -float(r["percentual"] or 0)))
    with io.open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=cab); wr.writeheader(); wr.writerows(saida)
    rod = {(r["uf"], r["cargo"], r["turno"], r["instituto"], r["data_ref"], r["cenario"] if r["turno"] == 2 else "") for r in saida}
    casadas = sum(1 for g in rod_g.values() if g["casada"])
    sem_slug = sum(1 for r in saida if r["turno"] == 1 and r["principal"] == 1 and not r["slug"])
    print(f"{len(saida)} linhas | {len(rod)} rodadas | Gazeta casadas com Wikipédia: {casadas}/{len(rod_g)} | pontos principais sem candidatura registrada: {sem_slug} -> {OUT}")

if __name__ == "__main__":
    main()
