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

out = {}
for nome, url, cab in TESTES:
    out[nome] = pega(url, cab)
    print(nome, "->", json.dumps(out[nome], ensure_ascii=False)[:300], flush=True)
    time.sleep(1)
print("\nRESUMO")
for k, v in out.items():
    print(f"  {v.get('status')}\t{k}")
