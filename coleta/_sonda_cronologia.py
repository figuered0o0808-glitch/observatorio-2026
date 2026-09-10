# -*- coding: utf-8 -*-
"""Sonda: a Wikipédia compila uma cronologia da campanha de 2026 que sirva de fonte?

A linha do tempo do mural (dados/eventos.csv) é curada de imprensa e parou em 1/9/2026.
Antes de propor qualquer coleta, esta sonda pergunta à Wikipédia o que existe: lista as
seções das páginas candidatas e mostra o começo das que parecem cronologia, para a decisão
ser tomada olhando o material.

Não grava nada. Roda no GitHub Actions (do contêiner do Claude a Wikipédia é 403).
"""
import json, re, sys, time, urllib.parse, urllib.request

API = "https://pt.wikipedia.org/w/api.php"
UA = "observatorio-2026/0.3 (coleta automática; contato: figuered0o0808@gmail.com)"
PAGINAS = ["Eleição presidencial no Brasil em 2026"]
PISTA = ("debate", "entrevista")


def pedir(params):
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    for titulo in PAGINAS:
        print("=" * 70)
        print("PÁGINA:", titulo)
        try:
            d = pedir({"action": "parse", "page": titulo, "prop": "sections|revid"})
        except Exception as e:
            print("  não abriu:", type(e).__name__, str(e)[:70]); continue
        if "error" in d:
            print("  não existe:", d["error"].get("code")); continue
        secoes = d["parse"]["sections"]
        print("  revid:", d["parse"].get("revid"), "| seções:", len(secoes))
        interessa = []
        for s in secoes:
            marca = ""
            if any(p in s["line"].lower() for p in PISTA):
                marca = "  <<< pode servir"; interessa.append(s)
            print("   %-2s %s%s" % (s["number"], s["line"][:60], marca))
        for s in interessa[:4]:
            print("\n  --- começo da seção %s (%s):" % (s["number"], s["line"]))
            try:
                t = pedir({"action": "parse", "page": titulo, "prop": "wikitext", "section": s["index"]})
                w = t["parse"]["wikitext"]
                w = re.sub(r"<ref[^>]*>.*?</ref>", "", w, flags=re.S)
                w = re.sub(r"<ref[^>]*/>", "", w)
                linhas = [l for l in w.splitlines() if l.strip()][:40]
                for l in linhas: print("     ", l[:150])
            except Exception as e:
                print("      falhou:", str(e)[:60])
            time.sleep(0.5)
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
