"""Marca lapidada do Mural dos Candidatos: gera SVGs, PNGs e o trecho inline do masthead.

Construção (unidades da fonte, 1000/em, caixa alta 686):
  letras   Archivo largura 72, peso 900, entreletras -8
  filete   110 de espessura, topo a 66 abaixo da linha de base, corre de M a L
  curva    continua o filete: 150 plano, sobe a 290, recua a 215, dispara ao topo
  ponto    raio 115 (diâmetro 2,1x o traço), tangente ao topo da caixa alta (+12 de overshoot)
  subtítulo Archivo largura 80, peso 700, caixa alta, entreletras 0,34 em, altura 14% da palavra
"""
from __future__ import annotations
import os, math
from marca import shape, instancia, Glifo
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = os.path.dirname(os.path.abspath(__file__))
CAPH = 686
STROKE = 110
GAP = 66
R = 115
TRACK = -8
CURVA = [(150, 0), (390, 290), (550, 215), (930, None)]   # None = altura calculada até o topo
OVERSHOOT = 12

_gs_cache = {}

def glyphset(wdth, wght):
    k = (wdth, wght)
    if k not in _gs_cache:
        _gs_cache[k] = TTFont(instancia(wdth, wght)).getGlyphSet()
    return _gs_cache[k]

def letras_d(texto, tracking=0.0, wdth=72, wght=900, escala=1.0, dx=0.0, dy=0.0):
    """Path SVG (y para baixo) das letras, com kerning, e a caixa [xmin, xmax] em unidades já escaladas."""
    gl = shape(texto, tracking, wdth, wght)
    gs = glyphset(wdth, wght)
    ds = []
    for g in gl:
        pen = SVGPathPen(None)
        tp = TransformPen(pen, (escala, 0, 0, -escala, dx + g.x * escala, dy - g.y * escala))
        gs[g.nome].draw(tp)
        ds.append(pen.getCommands())
    xmin = dx + (gl[0].x + gl[0].xmin) * escala
    xmax = dx + (gl[-1].x + gl[-1].xmax) * escala
    return " ".join(ds), xmin, xmax

def curva_pts(xmax, curva=CURVA, stroke=STROKE, gap=GAP, r=R):
    yc = gap + stroke / 2
    pts = [(None, yc)]  # placeholder para xmin, preenchido depois
    pts = [(xmax, yc)]
    for dx, dy in curva:
        if dy is None:
            # centro do ponto: topo do ponto tangente à caixa alta com overshoot
            y = -(CAPH + OVERSHOOT - r)
        else:
            y = yc - dy
        pts.append((xmax + dx, y))
    return yc, pts

def marca(tinta="#14161A", cor="#C8102E", subtitulo=False, cor_sub=None, fundo=None, margem=70,
          largura_px=None, id_prefix="mk", css_vars=False, texto="MURAL", curva=CURVA, r=R, stroke=STROKE,
          gap=GAP, escala_sub=0.155, tracking_sub=300):
    d, xmin, xmax = letras_d(texto, TRACK)
    yc, pts = curva_pts(xmax, curva, stroke, gap, r)
    pts = [(xmin, yc)] + pts
    px, py = pts[-1]
    topo = min(-CAPH - OVERSHOOT, py - r) - margem
    direita = px + r + margem
    esquerda = xmin - margem
    base = yc + stroke / 2 + margem
    sub = ""
    if subtitulo:
        sd, sxmin, sxmax = letras_d("DOS CANDIDATOS", tracking_sub, 80, 700, escala_sub)
        # posicionar: esquerda alinhada ao xmin, base do subtítulo abaixo do filete
        sub_capH = CAPH * escala_sub
        sub_base = yc + stroke / 2 + 150 + sub_capH
        sd, sxmin, sxmax = letras_d("DOS CANDIDATOS", tracking_sub, 80, 700, escala_sub, dx=xmin - sxmin, dy=sub_base)
        base = sub_base + margem
        sub = f'<path id="{id_prefix}-sub" fill="{cor_sub or cor}" d="{sd}"/>'
    w = direita - esquerda
    h = base - topo
    fill_l = "var(--ink)" if css_vars else tinta
    st = "var(--red)" if css_vars else cor
    if css_vars and subtitulo:
        sub = sub.replace(f'fill="{cor_sub or cor}"', 'fill="var(--red)"')
    dims = ""
    if largura_px:
        dims = f' width="{largura_px:.0f}" height="{largura_px * h / w:.1f}"'
    dpath = "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in pts)
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{esquerda:.0f} {topo:.0f} {w:.0f} {h:.0f}"{dims} role="img" aria-label="Mural dos Candidatos">']
    if fundo:
        partes.append(f'<rect x="{esquerda:.0f}" y="{topo:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{fundo}"/>')
    partes.append(f'<path id="{id_prefix}-letras" fill="{fill_l}" d="{d}"/>')
    partes.append(f'<path id="{id_prefix}-curva" d="{dpath}" fill="none" stroke="{st}" stroke-width="{stroke:.0f}" stroke-linejoin="round"/>')
    partes.append(f'<circle id="{id_prefix}-ponto" cx="{px:.0f}" cy="{py:.0f}" r="{r:.0f}" fill="{st}"/>')
    if sub:
        partes.append(sub)
    partes.append("</svg>")
    return "\n".join(partes), (esquerda, topo, w, h)

# Monograma: M + filete + curva encurtada. Ícone: M + subida única. Mínimo: M com filete.
CURVA_MONO = [(110, 0), (300, 290), (430, 215), (700, None)]
CURVA_ICONE = [(120, 0), (640, None)]

def monograma(tinta="#F1F1EF", cor="#FF5163", fundo=None, forma="quadrado", raio=0.2, tamanho=None, curva=CURVA_MONO, r=R, com_curva=True, margem_h=None):
    d, xmin, xmax = letras_d("M", 0)
    yc, pts = curva_pts(xmax, curva, STROKE, GAP, r)
    pts = [(xmin, yc)] + pts
    if not com_curva:
        pts = pts[:2]
    px, py = pts[-1]
    # caixa quadrada centrada no conjunto
    cx_min = xmin
    cx_max = (px + r) if com_curva else xmax
    cy_min = -CAPH - OVERSHOOT
    cy_max = yc + STROKE / 2
    cw, ch = cx_max - cx_min, cy_max - cy_min
    lado = max(cw, ch) * (1.55 if com_curva else 1.7)
    cx, cy = (cx_min + cx_max) / 2, (cy_min + cy_max) / 2 + (30 if com_curva else 0)
    x0, y0 = cx - lado / 2, cy - lado / 2
    dims = f' width="{tamanho}" height="{tamanho}"' if tamanho else ""
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {lado:.0f} {lado:.0f}"{dims} role="img" aria-label="Monograma do Mural">']
    if fundo:
        if forma == "circulo":
            partes.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{lado/2:.0f}" fill="{fundo}"/>')
        else:
            partes.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{lado:.0f}" height="{lado:.0f}" rx="{lado*raio:.0f}" fill="{fundo}"/>')
    partes.append(f'<path fill="{tinta}" d="{d}"/>')
    dpath = "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in pts)
    partes.append(f'<path d="{dpath}" fill="none" stroke="{cor}" stroke-width="{STROKE}" stroke-linejoin="round"/>')
    if com_curva:
        partes.append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="{r:.0f}" fill="{cor}"/>')
    partes.append("</svg>")
    return "\n".join(partes)

if __name__ == "__main__":
    s, box = marca()
    print(box)
