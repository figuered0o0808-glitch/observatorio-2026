# -*- coding: utf-8 -*-
"""Fotos dos presidenciáveis, com autor e licença, a partir da Wikimedia Commons.

Roda no GitHub Actions (o ambiente de trabalho não alcança a Wikipédia). Para cada candidatura de
dados/candidatos.csv:
  1. acha o verbete na Wikipédia em português (wikipedia_titulo; sem ele, o nome e "nome (político)");
  2. confere no Wikidata que o item é uma pessoa (P31 = Q5) de nacionalidade brasileira (P27 = Q155),
     para um homônimo nunca virar a foto de ninguém;
  3. usa a imagem declarada no próprio item (P18), e não a primeira figura do verbete, que pode
     ser um logotipo ou um mapa;
  4. baixa uma miniatura da Commons, recorta quadrada pelo alto (onde costuma estar o rosto) e
     grava em mural/fotos/<slug>.jpg;
  5. registra autor, licença e página da imagem em dados/fotos-presidenciaveis.csv, porque a
     licença livre obriga a dar o crédito.

Candidatura sem verbete confirmado ou sem imagem no Wikidata fica sem foto, e o site mostra o
número de urna como antes. Nada é adivinhado.

    python3 coleta/fotos_presidenciaveis.py
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, "mural", "fotos")
SAIDA = os.path.join(RAIZ, "dados", "fotos-presidenciaveis.csv")
UA = {"User-Agent": "observatorio-2026/1.0 (https://muraldoscandidatos.com; fotos com credito)"}
LADO = 240


def slug(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def pedir(url, params=None, tentativas=3):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except Exception as e:
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))


def api(host, **params):
    params.update(format="json", formatversion="2")
    return json.loads(pedir(f"https://{host}/w/api.php", params))


def sem_html(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    return re.sub(r"\s+", " ", t).strip()


def item_do_verbete(titulo):
    d = api("pt.wikipedia.org", action="query", prop="pageprops", redirects="1", titles=titulo)
    for p in d.get("query", {}).get("pages", []):
        pp = p.get("pageprops") or {}
        if p.get("missing") or "disambiguation" in pp:
            return None, None
        return pp.get("wikibase_item"), p.get("title")
    return None, None


def valores(claims, prop):
    out = []
    for c in claims.get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
        elif v is not None:
            out.append(v)
    return out


def main():
    from PIL import Image
    os.makedirs(PASTA, exist_ok=True)
    cands = list(csv.DictReader(io.open(os.path.join(RAIZ, "dados", "candidatos.csv"), encoding="utf-8-sig")))
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d")
    linhas, faltas = [], []
    for c in cands:
        nome = c["candidato"]
        tit = re.sub(r"\s*\(URL can[oô]nico.*\)$", "", c.get("wikipedia_titulo") or "").strip()
        tentativas = [tit] if tit else [nome, f"{nome} (político)"]
        achado = None
        for t in tentativas:
            try:
                q, pagina = item_do_verbete(t)
            except Exception as e:
                print(f"{nome}: erro no verbete {t!r}: {e}")
                continue
            if not q:
                continue
            ent = json.loads(pedir("https://www.wikidata.org/w/api.php",
                                   {"action": "wbgetentities", "ids": q, "props": "claims", "format": "json"}))
            claims = ent["entities"][q].get("claims", {})
            if "Q5" not in valores(claims, "P31") or "Q155" not in valores(claims, "P27"):
                print(f"{nome}: {pagina} ({q}) não é pessoa brasileira no Wikidata, descartado")
                continue
            imgs = valores(claims, "P18")
            if not imgs:
                print(f"{nome}: {pagina} ({q}) sem imagem no Wikidata")
                continue
            achado = (pagina, q, imgs[0])
            break
        if not achado:
            faltas.append(nome)
            continue
        pagina, q, arquivo = achado
        d = api("commons.wikimedia.org", action="query", prop="imageinfo", titles="File:" + arquivo,
                iiprop="url|extmetadata", iiurlwidth="480")
        info = d["query"]["pages"][0]["imageinfo"][0]
        meta = info.get("extmetadata", {})
        g = lambda k: sem_html((meta.get(k) or {}).get("value", ""))
        bruto = pedir(info.get("thumburl") or info["url"])
        im = Image.open(io.BytesIO(bruto)).convert("RGB")
        w, h = im.size
        lado = min(w, h)
        # retrato em pé: o quadrado sai do alto (um quinto da sobra acima), onde fica o rosto
        x0 = (w - lado) // 2
        y0 = int((h - lado) * 0.2) if h > w else 0
        im = im.crop((x0, y0, x0 + lado, y0 + lado)).resize((LADO, LADO), Image.LANCZOS)
        nome_arq = slug(nome) + ".jpg"
        im.save(os.path.join(PASTA, nome_arq), "JPEG", quality=82, optimize=True, progressive=True)
        linhas.append({"candidato": nome, "arquivo": "mural/fotos/" + nome_arq, "arquivo_commons": arquivo,
                       "pagina_commons": info.get("descriptionurl", ""), "autor": g("Artist") or g("Credit"),
                       "licenca": g("LicenseShortName"), "url_licenca": g("LicenseUrl"),
                       "verbete": pagina, "wikidata": q, "coletado_em": agora})
        print(f"{nome}: {arquivo} | {g('Artist')[:60]} | {g('LicenseShortName')}")
    cols = ["candidato", "arquivo", "arquivo_commons", "pagina_commons", "autor", "licenca", "url_licenca",
            "verbete", "wikidata", "coletado_em"]
    with io.open(SAIDA, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} fotos; sem foto: {', '.join(faltas) or 'nenhum'}")


if __name__ == "__main__":
    main()
