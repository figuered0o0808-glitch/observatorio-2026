"""Gera a marca tipográfica do Mural dos Candidatos como SVG vetorial.

Letras de MURAL em Archivo (largura 72, peso 900) convertidas em contornos,
mais o filete que vira curva de apuração. Tudo em unidades da fonte (UPM 1000)
e depois escalado pelo viewBox.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "archivo.ttf")
INST = os.path.join(HERE, "archivo-72-900.ttf")


def _baixar_fonte():
    if not os.path.exists(SRC):
        import urllib.request
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf"
        urllib.request.urlretrieve(url, SRC)


def instancia(wdth=72, wght=900):
    _baixar_fonte()
    path = INST if (wdth, wght) == (72, 900) else os.path.join(HERE, f"archivo-{wdth}-{wght}.ttf")
    if not os.path.exists(path):
        f = TTFont(SRC)
        instantiateVariableFont(f, {"wdth": wdth, "wght": wght}, inplace=True)
        f.save(path)
    return path


@dataclass
class Glifo:
    nome: str
    x: float
    y: float
    adv: float
    d: str
    xmin: float
    xmax: float


def shape(texto: str, tracking: float = 0.0, wdth=72, wght=900) -> list[Glifo]:
    path = instancia(wdth, wght)
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(texto)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": False})
    tt = TTFont(path)
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    out = []
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        nome = order[info.codepoint]
        g = gs[nome]
        pen = SVGPathPen(gs)
        g.draw(pen)
        bp = BoundsPen(gs)
        g.draw(bp)
        xmin, ymin, xmax, ymax = bp.bounds or (0, 0, pos.x_advance, 0)
        out.append(Glifo(nome, x + pos.x_offset, pos.y_offset, pos.x_advance, pen.getCommands(), xmin, xmax))
        x += pos.x_advance + tracking
    return out


@dataclass
class Marca:
    """Parâmetros da marca em unidades da fonte (1000/em, caixa alta 686)."""
    texto: str = "MURAL"
    tracking: float = 0.0
    filete_gap: float = 62.0      # distância da linha de base ao topo do filete
    filete: float = 56.0          # espessura do filete e da curva
    curva: list[tuple[float, float]] = field(default_factory=lambda: [
        # pontos relativos ao fim do filete (x) e à linha central do filete (y, para cima)
        (130, 0), (330, 300), (470, 210), (800, 720)])
    ponta: str = "ponto"          # ponto | seta
    ponto_r: float = 76.0
    margem: float = 60.0


def montar(m: Marca):
    gl = shape(m.texto, m.tracking)
    xmin = gl[0].x + gl[0].xmin
    ultimo = gl[-1]
    xmax = ultimo.x + ultimo.xmax
    yc = m.filete_gap + m.filete / 2          # centro do filete (abaixo da base, coords y para baixo)
    # caminho do filete + curva (coordenadas SVG: y cresce para baixo; base em y=0)
    pts = [(xmin, yc), (xmax, yc)]
    for dx, dy in m.curva:
        pts.append((xmax + dx, yc - dy))
    return gl, xmin, xmax, yc, pts


def svg(m: Marca, tinta="#14161A", cor="#C8102E", fundo=None, escala=0.1, id_prefix="mk", so_letras=False, com_texto=False):
    gl, xmin, xmax, yc, pts = montar(m)
    capH = 686
    topo = -capH - m.margem
    # extensão vertical: do topo da caixa alta (ou do ponto, se subir mais) até o filete
    ys = [p[1] for p in pts]
    ymin_curva = min(ys) - (m.ponto_r if m.ponta == "ponto" else m.filete)
    topo = min(topo, ymin_curva - m.margem)
    base = yc + m.filete / 2 + m.margem
    esq = xmin - m.margem
    xs = [p[0] for p in pts]
    dir_ = max(xs) + (m.ponto_r if m.ponta == "ponto" else m.filete * 1.6) + m.margem
    w = dir_ - esq
    h = base - topo
    partes = []
    partes.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{esq:.0f} {topo:.0f} {w:.0f} {h:.0f}" width="{w*escala:.1f}" height="{h*escala:.1f}" role="img" aria-label="Mural dos Candidatos">')
    if fundo:
        partes.append(f'<rect x="{esq:.0f}" y="{topo:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{fundo}"/>')
    # letras
    d_letras = []
    for g in gl:
        # transformar: transladar x, inverter y
        pen = SVGPathPen(None)
        tp = TransformPen(pen, (1, 0, 0, -1, g.x, g.y))
        # redesenhar a partir do glyph set para aplicar a transformação
        d_letras.append(_glyph_d(g, tp, pen))
    partes.append(f'<path id="{id_prefix}-letras" fill="{tinta}" fill-rule="nonzero" d="{" ".join(d_letras)}"/>')
    if not so_letras:
        d = "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in pts)
        partes.append(f'<path id="{id_prefix}-curva" d="{d}" fill="none" stroke="{cor}" stroke-width="{m.filete:.0f}" stroke-linejoin="round" stroke-linecap="butt"/>')
        px, py = pts[-1]
        if m.ponta == "ponto":
            partes.append(f'<circle id="{id_prefix}-ponto" cx="{px:.0f}" cy="{py:.0f}" r="{m.ponto_r:.0f}" fill="{cor}"/>')
        else:
            # seta: triângulo alinhado ao último segmento
            import math
            (ax, ay), (bx, by) = pts[-2], pts[-1]
            ang = math.atan2(by - ay, bx - ax)
            L = m.filete * 2.6
            W = m.filete * 1.5
            tip = (bx + math.cos(ang) * L * 0.55, by + math.sin(ang) * L * 0.55)
            base_c = (bx - math.cos(ang) * L * 0.45, by - math.sin(ang) * L * 0.45)
            nx, ny = -math.sin(ang), math.cos(ang)
            p1 = (base_c[0] + nx * W, base_c[1] + ny * W)
            p2 = (base_c[0] - nx * W, base_c[1] - ny * W)
            partes.append(f'<path id="{id_prefix}-seta" d="M{tip[0]:.0f} {tip[1]:.0f} L{p1[0]:.0f} {p1[1]:.0f} L{p2[0]:.0f} {p2[1]:.0f} Z" fill="{cor}" stroke="{cor}" stroke-width="{m.filete*0.5:.0f}" stroke-linejoin="round"/>')
    partes.append("</svg>")
    return "\n".join(partes), (esq, topo, w, h)


_GS = None


def _glyph_d(g: Glifo, tp, pen):
    global _GS
    if _GS is None:
        _GS = TTFont(instancia()).getGlyphSet()
    _GS[g.nome].draw(tp)
    return pen.getCommands()


if __name__ == "__main__":
    m = Marca()
    s, box = svg(m)
    print(box)
    open(os.path.join(HERE, "teste.svg"), "w").write(s)
