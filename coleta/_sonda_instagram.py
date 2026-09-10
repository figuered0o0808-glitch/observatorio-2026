# -*- coding: utf-8 -*-
"""Sonda: o que o Instagram responde de onde este script estiver rodando.

Não coleta nada nem grava arquivo. Serve para decidir com prova, e não de memória, se dá
para ler o número de seguidores de um perfil público sem sessão aberta. Testa os caminhos
que o roteiro de coleta/navegador_estados.md usa no navegador logado e mais alguns.

Uso: python3 coleta/_sonda_instagram.py [perfil1 perfil2 ...]
"""
import json, re, sys, urllib.error, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
APP_ID = "936619743392459"


def tentar(rotulo, url, cabecalhos):
    try:
        req = urllib.request.Request(url, headers=cabecalhos)
        with urllib.request.urlopen(req, timeout=25) as r:
            corpo = r.read(240000).decode("utf-8", "ignore")
            achou = None
            m = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', corpo)
            if m: achou = "edge_followed_by=" + m.group(1)
            if not achou:
                m = re.search(r'content="([^"]*?(?:seguidores|Followers)[^"]*)"', corpo)
                if m: achou = "meta: " + m.group(1)[:70]
            print("  %-28s %s %d bytes  %s" % (rotulo, r.status, len(corpo), achou or "sem número no corpo"))
            return bool(achou)
    except urllib.error.HTTPError as e:
        print("  %-28s HTTP %s  %s" % (rotulo, e.code, (e.reason or "")[:40]))
    except Exception as e:
        print("  %-28s %s: %s" % (rotulo, type(e).__name__, str(e)[:60]))
    return False


def main():
    perfis = sys.argv[1:] or ["lula", "jandirafeghali"]
    ok = 0
    for p in perfis:
        print("perfil @%s" % p)
        base = {"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"}
        api = dict(base, **{"x-ig-app-id": APP_ID})
        ok += tentar("HTML público", "https://www.instagram.com/%s/" % p, base)
        ok += tentar("api web_profile_info (www)",
                     "https://www.instagram.com/api/v1/users/web_profile_info/?username=%s" % p, api)
        ok += tentar("api web_profile_info (i.)",
                     "https://i.instagram.com/api/v1/users/web_profile_info/?username=%s" % p, api)
        ok += tentar("__a=1", "https://www.instagram.com/%s/?__a=1&__d=dis" % p, base)
    print("\ncaminhos que devolveram número: %d" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
