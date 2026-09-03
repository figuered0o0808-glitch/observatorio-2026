# -*- coding: utf-8 -*-
"""Gera os caminhos SVG dos 27 estados a partir do GeoJSON (click_that_hood, IBGE),
com simplificação que preserva as fronteiras compartilhadas:
1) une as fronteiras em arcos únicos, 2) simplifica os arcos, 3) repoligoniza,
4) devolve cada polígono ao estado de origem. Projeção: Mercator simples.
Saída: dados/geo/br-uf-paths.json  {viewBox, ufs:{SIGLA:{d, cx, cy}}}
"""
import json, math, sys, os
from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.ops import unary_union, linemerge, polygonize

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_brazil-states.geojson")  # fonte: https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/brazil-states.geojson
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "br-uf-paths.json")
TOL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.06   # graus
MIN_AREA = 0.02  # graus² (~ 250 km²): ilhas menores somem

j = json.load(open(SRC, encoding="utf-8"))
ufs = {}
for f in j["features"]:
    sig = f["properties"]["sigla"]
    g = shape(f["geometry"]).buffer(0)
    # descarta ilhas pequenas antes de simplificar
    if isinstance(g, MultiPolygon):
        parts = [p for p in g.geoms if p.area >= MIN_AREA] or [max(g.geoms, key=lambda p: p.area)]
        g = MultiPolygon(parts) if len(parts) > 1 else parts[0]
    ufs[sig] = g
print("estados:", len(ufs))

# 1) arcos únicos
bordas = unary_union([g.boundary for g in ufs.values()])
arcos = linemerge(bordas) if bordas.geom_type == "MultiLineString" else bordas
arcos = list(arcos.geoms) if hasattr(arcos, "geoms") else [arcos]
print("arcos:", len(arcos))
# 2) simplifica cada arco
simp = [a.simplify(TOL, preserve_topology=True) for a in arcos]
# 3) repoligoniza
polys = list(polygonize(unary_union(simp)))
print("polígonos:", len(polys))
# 4) devolve cada polígono ao estado (ponto representativo dentro do original)
por_uf = {k: [] for k in ufs}
orfaos = 0
for p in polys:
    rp = p.representative_point()
    dono = None
    for k, g in ufs.items():
        if g.contains(rp):
            dono = k; break
    if dono is None:
        # fallback: menor distância
        dono = min(ufs, key=lambda k: ufs[k].distance(rp)); orfaos += 1
    por_uf[dono].append(p)
print("órfãos realocados:", orfaos)

# projeção Mercator simples
def proj(lon, lat):
    x = lon
    y = math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))
    return x, -y

pts = [proj(x, y) for g in por_uf.values() for p in g for x, y in p.exterior.coords]
minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
W = 1000.0
esc = W / (maxx - minx)
H = (maxy - miny) * esc

def px(x, y):
    X, Y = proj(x, y)
    return round((X - minx) * esc, 1), round((Y - miny) * esc, 1)

out = {"viewBox": f"0 0 {W:.0f} {H:.0f}", "fonte": "IBGE via click_that_hood (GitHub), simplificado com fronteiras compartilhadas", "ufs": {}}
total = 0
for k, plist in por_uf.items():
    ds = []
    for p in plist:
        rings = [p.exterior] + list(p.interiors)
        for r in rings:
            cs = [px(x, y) for x, y in r.coords]
            d = "M" + " ".join(f"{x:g},{y:g}" for x, y in cs[:-1]) + "Z"
            ds.append(d)
    geom = unary_union(plist)
    c = geom.representative_point()
    cx, cy = px(c.x, c.y)
    # ajustes finos de rótulo para estados estreitos
    out["ufs"][k] = {"d": "".join(ds), "cx": cx, "cy": cy}
    total += len("".join(ds))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("viewBox", out["viewBox"], "| tamanho dos paths:", total, "| arquivo:", os.path.getsize(OUT))
