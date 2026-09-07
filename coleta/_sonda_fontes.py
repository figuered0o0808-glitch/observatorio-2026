# -*- coding: utf-8 -*-
"""Sonda temporária: mede, de dentro do runner do GitHub, o que cada fonte responde.
Não grava nada em dados/. Roda só pelo workflow sonda-fontes.yml, que sai depois do diagnóstico.
"""
import json, sys, time, urllib.request, urllib.error, http.cookiejar

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
CJ = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CJ))

def pega(url, cab=None, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9",
                                               "Accept": "*/*", **(cab or {})})
    t0 = time.time()
    try:
        with OP.open(req, timeout=timeout) as r:
            corpo = r.read(4000)
            return {"status": r.status, "ms": int((time.time()-t0)*1000), "bytes": len(corpo),
                    "amostra": corpo[:200].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "ms": int((time.time()-t0)*1000), "erro": e.reason,
                "amostra": (e.read(200) or b"").decode("utf-8", "replace")}
    except Exception as e:
        return {"status": None, "ms": int((time.time()-t0)*1000), "erro": type(e).__name__+": "+str(e)[:160]}

TESTES = [
    ("wikimedia pageviews (controle)", "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/pt.wikipedia/all-access/user/Lula/daily/20260901/20260905", None),
    ("tse divulgacand, listagem", "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/buscar/2026/BR/20322002026/candidatos", None),
    ("tse divulgacand, com referer", "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/buscar/2026/BR/20322002026/candidatos", {"Referer": "https://divulgacandcontas.tse.jus.br/divulga/", "Origin": "https://divulgacandcontas.tse.jus.br"}),
    ("tse dados abertos", "https://dadosabertos.tse.jus.br/api/3/action/package_list", None),
    ("tse portal (html)", "https://www.tse.jus.br/", None),
    ("google trends home (pega cookie)", "https://trends.google.com/trends/?geo=BR", {"Accept": "text/html,application/xhtml+xml"}),
    ("google trends explore api", "https://trends.google.com/trends/api/explore?hl=pt-BR&tz=180&req=%7B%22comparisonItem%22%3A%5B%7B%22keyword%22%3A%22Augusto%20Cury%22%2C%22geo%22%3A%22BR%22%2C%22time%22%3A%22today%201-m%22%7D%5D%2C%22category%22%3A0%2C%22property%22%3A%22%22%7D", {"Referer": "https://trends.google.com/trends/explore"}),
    ("instagram web_profile_info", "https://www.instagram.com/api/v1/users/web_profile_info/?username=augustocury", {"x-ig-app-id": "936619743392459"}),
    ("instagram página pública", "https://www.instagram.com/augustocury/", {"Accept": "text/html"}),
    ("youtube data api (sem chave)", "https://www.googleapis.com/youtube/v3/channels?part=statistics&forHandle=%40AugustoCury", None),
    ("gazeta do povo agregador", "https://especiais.gazetadopovo.com.br/eleicoes/2026/pesquisas-eleitorais/", None),
    ("poder360 pesquisas", "https://www.poder360.com.br/pesquisas-de-opiniao/", None),
]

def instagram_publico(handle):
    """Tenta ler os seguidores da página pública, sem login: o número aparece na meta description
    ("338 mil seguidores...") e, às vezes, no JSON embutido."""
    import re
    r = pega("https://www.instagram.com/%s/" % handle, {"Accept": "text/html"})
    if r.get("status") != 200:
        return {"status": r.get("status"), "erro": r.get("erro")}
    req = urllib.request.Request("https://www.instagram.com/%s/" % handle,
                                 headers={"User-Agent": UA, "Accept": "text/html",
                                          "Accept-Language": "pt-BR,pt;q=0.9"})
    with OP.open(req, timeout=25) as resp:
        html = resp.read(400000).decode("utf-8", "replace")
    saida = {"status": 200, "bytes": len(html)}
    m = re.search(r'<meta property="og:description" content="([^"]{0,300})"', html)
    if m:
        saida["og"] = m.group(1)[:160]
    m2 = re.search(r'"edge_followed_by":\s*\{"count":\s*(\d+)\}', html)
    if m2:
        saida["edge_followed_by"] = int(m2.group(1))
    m3 = re.search(r'(\d[\d.,]*\s*(?:mil|mi|M|K)?)\s+seguidores', html)
    if m3:
        saida["texto_seguidores"] = m3.group(1)
    saida["tem_login_wall"] = "loginForm" in html or "accounts/login" in html
    return saida


out = {}
for nome, url, cab in TESTES:
    out[nome] = pega(url, cab)
    print(nome, "->", json.dumps(out[nome], ensure_ascii=False)[:300], flush=True)
    time.sleep(1)
print("\nINSTAGRAM PÁGINA PÚBLICA")
for h in ("augustocury", "lulaoficial", "flaviobolsonaro"):
    try:
        print(" ", h, "->", json.dumps(instagram_publico(h), ensure_ascii=False)[:400], flush=True)
    except Exception as e:
        print(" ", h, "-> erro", type(e).__name__, str(e)[:120], flush=True)
    time.sleep(3)

print("\nRESUMO")
for k, v in out.items():
    print(f"  {v.get('status')}\t{k}")
