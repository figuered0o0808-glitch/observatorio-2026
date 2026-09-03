"""Coleta pageviews diarios (Wikimedia REST) e edicoes recentes (MediaWiki API)
dos verbetes dos presidenciaveis 2026 na Wikipedia em portugues.

Uso: python3 wikipedia_pageviews.py [AAAAMMDD_inicio] [AAAAMMDD_fim]
Padrao: 20260815 ate ontem. Gera:
  wikipedia-pageviews.csv       (data, candidato, artigo, pageviews, fonte, url_fonte)
  wikipedia-edicoes-cury.csv    (data, edicoes, usuarios, resumo_comentarios)
  wikipedia-edicoes-cury-raw.csv (uma linha por revisao)

Requisitos: requests. Respeita a politica da Wikimedia com User-Agent identificado.
Limite documentado da API de pageviews: 100 req/s por cliente; aqui usamos 1 req por candidato.
"""
import csv, sys, time, datetime as dt, urllib.parse, collections
import requests

UA = "observatorio-2026/0.1 (contato: figuered0o0808@gmail.com)"
H = {"User-Agent": UA, "Accept": "application/json"}
OUT = "/home/claude/api-tests/"

# nome exibido -> termo de busca. O titulo exato e resolvido pela API de busca
# e, se a busca falhar, pelo fallback fixo.
CANDIDATOS = {
    "Lula":             ("Luiz Inácio Lula da Silva", "Luiz Inácio Lula da Silva"),
    "Flávio Bolsonaro": ("Flávio Bolsonaro",          "Flávio Bolsonaro"),
    "Augusto Cury":     ("Augusto Cury",              "Augusto Cury"),
    "Ronaldo Caiado":   ("Ronaldo Caiado",            "Ronaldo Caiado"),
    "Romeu Zema":       ("Romeu Zema",                "Romeu Zema"),
    "Renan Santos":     ("Renan Santos Missão",       "Renan Santos"),
    "Pablo Marçal":     ("Pablo Marçal",              "Pablo Marçal"),
    "Samara Martins":   ("Samara Martins Unidade Popular", "Samara Martins"),
}

def resolver_titulo(termo, fallback):
    """Busca o verbete; prefere resultado cujo titulo contenha o sobrenome."""
    try:
        r = requests.get("https://pt.wikipedia.org/w/api.php", headers=H, timeout=30,
                         params={"action": "query", "list": "search", "srsearch": termo,
                                 "format": "json", "srlimit": 5})
        r.raise_for_status()
        res = r.json()["query"]["search"]
        if not res:
            return fallback, "busca sem resultado; usando fallback"
        # confirma que o primeiro resultado existe e nao e redirect quebrado
        titulo = res[0]["title"]
        r2 = requests.get("https://pt.wikipedia.org/w/api.php", headers=H, timeout=30,
                          params={"action": "query", "titles": titulo, "redirects": 1, "format": "json"})
        pages = r2.json()["query"]["pages"]
        for p in pages.values():
            if "missing" not in p:
                return p["title"], "ok"
        return fallback, "titulo ausente; usando fallback"
    except Exception as e:
        return fallback, f"erro busca: {e}"

def pageviews(artigo, ini, fim):
    art = urllib.parse.quote(artigo.replace(" ", "_"), safe="")
    url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/pt.wikipedia/"
           f"all-access/user/{art}/daily/{ini}/{fim}")
    r = requests.get(url, headers=H, timeout=30)
    if r.status_code == 404:
        return [], url, "404 (sem dados para o periodo ou titulo)"
    r.raise_for_status()
    items = r.json().get("items", [])
    return [(i["timestamp"][:4] + "-" + i["timestamp"][4:6] + "-" + i["timestamp"][6:8], i["views"])
            for i in items], url, "ok"

def revisoes(artigo, desde_iso):
    """Revisoes de 'desde_iso' ate agora (rvdir=newer), paginando."""
    out, cont = [], {}
    while True:
        params = {"action": "query", "prop": "revisions", "titles": artigo, "rvlimit": 50,
                  "rvprop": "timestamp|user|comment|size|ids", "rvstart": desde_iso,
                  "rvdir": "newer", "format": "json", "redirects": 1}
        params.update(cont)
        r = requests.get("https://pt.wikipedia.org/w/api.php", headers=H, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        for p in j["query"]["pages"].values():
            out.extend(p.get("revisions", []))
        if "continue" in j:
            cont = j["continue"]; time.sleep(0.5)
        else:
            break
    return out

def main():
    ini = sys.argv[1] if len(sys.argv) > 1 else "20260815"
    fim = sys.argv[2] if len(sys.argv) > 2 else (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
    linhas, log = [], []
    for nome, (termo, fb) in CANDIDATOS.items():
        titulo, st = resolver_titulo(termo, fb)
        try:
            pv, url, st2 = pageviews(titulo, ini, fim)
        except Exception as e:
            pv, url, st2 = [], "", f"erro: {e}"
        log.append((nome, titulo, st, st2, len(pv)))
        for d, v in pv:
            linhas.append([d, nome, titulo, v, "Wikimedia Pageviews API (all-access, user)", url])
        time.sleep(0.3)
    with open(OUT + "wikipedia-pageviews.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["data", "candidato", "artigo", "pageviews", "fonte", "url_fonte"]); w.writerows(linhas)
    for l in log: print("pageviews:", l)

    # edicoes do verbete de Augusto Cury desde 20/8
    titulo_cury = next(l[1] for l in log if l[0] == "Augusto Cury")
    revs = revisoes(titulo_cury, "2026-08-20T00:00:00Z")
    por_dia = collections.defaultdict(list)
    for rv in revs:
        por_dia[rv["timestamp"][:10]].append(rv)
    with open(OUT + "wikipedia-edicoes-cury-raw.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["timestamp", "revid", "usuario", "tamanho_bytes", "comentario", "artigo"])
        for rv in revs:
            w.writerow([rv["timestamp"], rv.get("revid"), rv.get("user"), rv.get("size"), rv.get("comment", ""), titulo_cury])
    with open(OUT + "wikipedia-edicoes-cury.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["data", "artigo", "edicoes", "usuarios_distintos", "fonte"])
        for d in sorted(por_dia):
            w.writerow([d, titulo_cury, len(por_dia[d]), len({r.get("user") for r in por_dia[d]}),
                        "MediaWiki API prop=revisions"])
    print("edicoes Cury desde 20/8:", len(revs), "em", len(por_dia), "dias")

if __name__ == "__main__":
    main()
