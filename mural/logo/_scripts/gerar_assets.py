"""Escreve os arquivos da marca lapidada em observatorio-2026/mural/logo/ (SVG + PNG)."""
import os, glob, json
from marca_final import marca, monograma, CURVA_ICONE
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # a pasta logo/
os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, "mural-*")):
    os.remove(f)

INK, RED, PAPER = "#14161A", "#C8102E", "#F5F5F2"
INK_D, RED_D, GROUND_D = "#F1F1EF", "#FF5163", "#0F1013"

svgs = {}
svgs["mural-marca.svg"], _ = marca(INK, RED)
svgs["mural-marca-escuro.svg"], _ = marca(INK_D, RED_D, fundo="#14161A")
svgs["mural-marca-preta.svg"], _ = marca(INK, INK)
svgs["mural-marca-branca.svg"], _ = marca("#FFFFFF", "#FFFFFF")
svgs["mural-assinatura.svg"], _ = marca(INK, RED, subtitulo=True)
svgs["mural-assinatura-escuro.svg"], _ = marca(INK_D, RED_D, subtitulo=True, fundo="#14161A")
svgs["mural-monograma.svg"] = monograma(INK_D, RED_D, fundo="#14161A")
svgs["mural-monograma-claro.svg"] = monograma(INK, RED)
svgs["mural-avatar.svg"] = monograma(INK_D, RED_D, fundo="#14161A", forma="circulo")
svgs["mural-icone.svg"] = monograma(INK_D, RED_D, fundo="#14161A", curva=CURVA_ICONE)
svgs["mural-favicon.svg"] = monograma(INK_D, RED_D, fundo="#14161A", com_curva=False)
for nome, s in svgs.items():
    open(os.path.join(OUT, nome), "w", encoding="utf-8").write(s + "\n")

# trecho inline para o masthead do mural (cores por variáveis CSS, sem margem)
inline, box = marca(css_vars=True, margem=24, id_prefix="mm")
inline = inline.replace(' role="img" aria-label="Mural dos Presidenciáveis"', ' class="mark" role="img" aria-label="Mural"')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "masthead-inline.svg"), "w", encoding="utf-8").write(inline)

# PNGs via Chromium
pngs = [
    ("mural-marca-2400.png", svgs["mural-marca.svg"], 2400, None, True),
    ("mural-marca-escuro-2400.png", svgs["mural-marca-escuro.svg"], 2400, None, False),
    ("mural-assinatura-2400.png", svgs["mural-assinatura.svg"], 2400, None, True),
    ("mural-assinatura-escuro-2400.png", svgs["mural-assinatura-escuro.svg"], 2400, None, False),
    ("mural-avatar-1000.png", svgs["mural-avatar.svg"], 1000, 1000, True),
    ("mural-avatar-400.png", svgs["mural-avatar.svg"], 400, 400, True),
    ("mural-icone-512.png", svgs["mural-monograma.svg"], 512, 512, True),
    ("mural-icone-192.png", svgs["mural-icone.svg"], 192, 192, True),
    ("mural-favicon-32.png", svgs["mural-icone.svg"], 32, 32, True),
    ("mural-favicon-16.png", svgs["mural-favicon.svg"], 16, 16, True),
]
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for nome, s, w, h, transp in pngs:
        # altura proporcional ao viewBox quando não informada
        vb = s.split('viewBox="')[1].split('"')[0].split()
        vw, vh = float(vb[2]), float(vb[3])
        hh = h or round(w * vh / vw)
        s2 = s.replace("<svg ", f'<svg width="{w}" height="{hh}" ', 1)
        pg = b.new_page(viewport={"width": w, "height": hh}, device_scale_factor=1)
        pg.set_content(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:transparent}}svg{{display:block}}</style>{s2}')
        pg.locator("svg").screenshot(path=os.path.join(OUT, nome), omit_background=transp)
        pg.close()
    b.close()

print(sorted(os.listdir(OUT)))
