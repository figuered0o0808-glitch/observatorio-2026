# -*- coding: utf-8 -*-
"""Sonda de rejeição na imprensa: não grava nada, só imprime o que achou.

A página da Wikipédia que alimenta o mural não traz rejeição, e desde setembro a série parou.
Esta sonda roda no GitHub Actions (o ambiente de trabalho não alcança os sites de notícia):
busca no Bing Notícias (RSS) matérias de rejeição por instituto, abre cada matéria e imprime a
data de publicação, o endereço e as linhas que citam rejeição ou "não votaria" com percentual.
A conferência e a gravação ficam para depois, feitas à mão com a fonte de cada número.

    python3 coleta/_sonda_rejeicao.py "Quaest" "Datafolha" ...
"""
import html, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9"}
CHAVE = re.compile(r"rejei|não votaria|nao votaria|jeito nenhum", re.I)


def pedir(url, t=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read().decode("utf-8", "replace")


def bing(q):
    u = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": "pt-BR", "cc": "BR"})
    out = []
    for it in ET.fromstring(pedir(u)).iter("item"):
        link = it.findtext("link") or ""
        m = re.search(r"[?&]url=([^&]+)", link)
        out.append((urllib.parse.unquote(m.group(1)) if m else link, it.findtext("title") or "", it.findtext("pubDate") or ""))
    return out


def linhas(url):
    t = pedir(url)
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', t)
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    ls, vistos = [], set()
    for l in (x.strip() for x in t.splitlines()):
        if l and len(l) < 600 and l not in vistos and CHAVE.search(l) and re.search(r"\d", l):
            vistos.add(l); ls.append(l)
    return (m.group(1) if m else "?"), ls


def main():
    vistos = set()
    for inst in sys.argv[1:]:
        for q in ('rejeição %s presidente Lula Flávio setembro' % inst, '"%s" rejeição "não votaria" presidente' % inst):
            print("#" * 100); print("BUSCA", q, flush=True)
            try:
                res = bing(q)
            except Exception as e:
                print("ERRO busca", e); continue
            for url, tit, pub in res[:8]:
                if url in vistos:
                    continue
                vistos.add(url)
                try:
                    data, ls = linhas(url)
                except Exception as e:
                    print("  ERRO", url, e); continue
                if not ls:
                    continue
                print("=" * 100); print("URL", url); print("TÍTULO", tit); print("PUBLICADO", data, "|", pub)
                for l in ls[:25]:
                    print("   ", l)
                time.sleep(1)


if __name__ == "__main__":
    main()
