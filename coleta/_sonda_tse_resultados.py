# -*- coding: utf-8 -*-
"""Sonda da divulgação de resultados do TSE (resultados.tse.jus.br): acha os códigos da eleição
de 2026 no arquivo de configuração e testa os formatos de arquivo de resultado. Não grava nada.

    python3 coleta/_sonda_tse_resultados.py
"""
import json, sys, urllib.request

BASE = "https://resultados.tse.jus.br/oficial"
UA = {"User-Agent": "Mozilla/5.0 (observatorio-2026)", "Accept": "application/json"}


def pedir(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def resumo(obj, prof=0, max_itens=6):
    """Esqueleto do JSON: chaves e alguns valores, para ver o formato."""
    pad = "  " * prof
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:40]:
            if isinstance(v, (dict, list)):
                print("%s%s:" % (pad, k)); resumo(v, prof + 1, max_itens)
            else:
                print("%s%s = %r" % (pad, k, v))
    elif isinstance(obj, list):
        print("%s[lista com %d]" % (pad, len(obj)))
        for v in obj[:max_itens]:
            resumo(v, prof + 1, max_itens)


def main():
    cfg = json.loads(pedir(BASE + "/comum/config/ele-c.json"))
    eleicoes = []
    for pl in cfg.get("pl", []):
        if pl.get("c") != "ele2026":
            continue
        for e in pl.get("e", []):
            cargos = sorted({(cp.get("cd"), cp.get("ds")) for a in e.get("abr", []) for cp in a.get("cp", [])})
            ufs = [a.get("cd") for a in e.get("abr", [])]
            print("pleito %s (%s) eleição %s t%s tp%s cdt2=%s | %s | cargos %s | abrangências %d: %s"
                  % (pl.get("cd"), pl.get("dt"), e.get("cd"), e.get("t"), e.get("tp"), e.get("cdt2"), e.get("nm"),
                     cargos, len(ufs), " ".join(ufs[:30])))
            eleicoes.append((pl.get("cd"), e.get("cd"), e.get("t"), cargos, ufs))
    for pl, cd, t, cargos, ufs in eleicoes:
        e6 = str(cd).zfill(6)
        for cargo, _ in cargos[:4]:
            c4 = str(cargo).zfill(4)
            for uf in (["br"] if "br" in ufs else []) + [u for u in ufs if u != "br"][:2]:
                for tipo, pasta in (("r", "dados-simplificados"), ("u", "dados"), ("v", "dados")):
                    url = "%s/ele2026/%s/%s/%s/%s-c%s-e%s-%s.json" % (BASE, cd, pasta, uf, uf, c4, e6, tipo)
                    try:
                        b = pedir(url)
                        print("=" * 90); print("OK", url, len(b), "bytes")
                        resumo(json.loads(b))
                        break
                    except Exception as ex:
                        print("--", url, repr(ex)[:80])
    sys.stdout.flush()


if __name__ == "__main__":
    main()
