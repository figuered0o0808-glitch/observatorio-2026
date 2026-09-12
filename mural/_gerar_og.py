# -*- coding: utf-8 -*-
"""Cartão de compartilhamento (Open Graph) com os números do dia.

Quando alguém cola o endereço do mural no WhatsApp, no X ou no LinkedIn, o que aparece é a
imagem og:image. Até 12/9 ela era a marca parada; a partir daqui é o mural em miniatura: a
manchete com os três primeiros da média móvel, a curva do ano e a data da edição. É a peça
mais vista da divulgação, porque aparece antes de qualquer clique.

Os números não são recalculados aqui. O cartão é um bloco escondido dentro do próprio mural
(#og-card), preenchido pela mesma função que preenche a manchete da página, e o que este
script faz é abrir o mural no Chromium, mandar montar o bloco e fotografá-lo em 1200x630.
Assim o cartão nunca diverge da página: se a média muda, o cartão muda junto, e não existe
uma segunda implementação da metodologia para sair de sincronia.

Falha segura: qualquer erro deixa o PNG anterior no lugar e o script termina com código 0.
Cartão é vitrine, não dado; não pode derrubar a publicação.

Uso: python3 mural/_gerar_og.py
"""
import os, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(AQUI, "mural-inteiro.html")
OUT = os.path.join(AQUI, "logo", "mural-og-1200x630.png")
TMP = OUT + ".novo"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("AVISO cartão não gerado: Playwright ausente; mantido o anterior")
        return 0
    if not os.path.exists(HTML):
        print("AVISO cartão não gerado: %s não existe; rode _gerar_mural.py antes" % HTML)
        return 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            pg.goto("file://" + HTML)
            pg.wait_for_timeout(1200)
            ok = pg.evaluate("() => typeof montarOG === 'function' && montarOG()")
            if not ok:
                raise RuntimeError("montarOG() não existe no mural ou não conseguiu montar o cartão")
            # espera as fontes da web (Archivo) chegarem; sem rede o Chromium cai na fonte do sistema
            # e o cartão sai igual, só com outra tipografia
            try:
                pg.wait_for_function("document.fonts.status === 'loaded'", timeout=8000)
            except Exception:
                pass
            pg.wait_for_timeout(500)
            pg.locator("#og-card").screenshot(path=TMP, type="png")
            b.close()
        tam = os.path.getsize(TMP)
        if tam < 15000:
            raise RuntimeError("PNG saiu com %d bytes, pequeno demais para ser o cartão" % tam)
        os.replace(TMP, OUT)
        print("cartão gravado em %s (%d bytes)" % (os.path.relpath(OUT, os.path.dirname(AQUI)), tam))
    except Exception as e:
        if os.path.exists(TMP):
            os.remove(TMP)
        print("AVISO cartão não gerado, mantido o anterior:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
