# -*- coding: utf-8 -*-
"""Varredura geral do mural: percorre os 27 estados e todas as suas disputas, os temas claro/escuro,
desktop/mobile e uma amostra de dossiês, procurando qualquer erro de console. Não sabe
nada sobre bugs específicos (isso é o papel de regressao_bugs_conhecidos.py) - é uma
rede de segurança ampla para pegar efeito colateral inesperado depois de qualquer edição
em _template.html ou _gerar_mural.py.

Roda contra o mural já gerado (não regenera nada) e para com aviso se ele estiver mais antigo que as
fontes (testes/_frescor.py). Uso:
    python3 testes/varredura_geral.py
"""
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

# mural-inteiro.html, e não mural.html: desde que a Visão geral virou a parte aberta e o resto
# passou a pedir conta, mural.html é só a carga pública. O mural inteiro num arquivo só continua
# sendo gerado para conferência e é contra ele que estes testes rodam, senão eles testariam a
# tela de cadastro em vez do mural. A trava em si tem bloco próprio na regressão.
URL = (Path(__file__).resolve().parent.parent / "mural" / "mural-inteiro.html").as_uri()
# mural-inteiro.html é ignorado pelo git e pode estar velho: o teste para antes de abrir o navegador
# se ele for mais antigo que o template, o gerador ou os CSVs, ou se o DATA.meta divergir do de
# mural.html (T0.2; ver testes/_frescor.py)
import sys as _sys_fr
_sys_fr.path.insert(0, str(Path(__file__).resolve().parent))
import _frescor
_frescor.exigir()
ok, fail = [], []

# As disputas de cada estado. Deputado estadual e federal saíram do site em 17/9/2026 (a pedido do
# Francisco); os dados e coletores continuam no repositório, só não entram na geração do mural.
CARGOS_ESPERADOS = ["governador", "senador"]

# Os estados com 2º turno de governador saem de totais.csv (linha de turno 2 para governador), como no
# gerador, e não da página: é o oráculo do painel do 2º turno estadual (13/10/2026). Os dois nomes vêm
# de candidatos.csv (situação "2º turno" no 1º turno). Sem os CSVs, vale a regra de antes.
import csv as _csv
import io as _io
_RES = Path(__file__).resolve().parent.parent / "dados" / "resultados"
UF2T, FIN2T = None, {}
if (_RES / "totais.csv").exists() and (_RES / "candidatos.csv").exists():
    UF2T = sorted({x["abrangencia"].upper() for x in _csv.DictReader(_io.open(_RES / "totais.csv", encoding="utf-8-sig"))
                   if x["turno"] == "2" and x["cargo"] == "governador"})
    for x in _csv.DictReader(_io.open(_RES / "candidatos.csv", encoding="utf-8-sig")):
        if x["turno"] == "1" and x["cargo"] == "governador" and x["situacao"].strip().lower() == "2º turno":
            FIN2T.setdefault(x["abrangencia"].upper(), []).append(x["nome_urna"])

# Hosts de recurso externo que o mural pede (as fontes do Google). Num ambiente sem rede o
# Chromium registra "Failed to load resource" para eles; isso não é bug do mural.
FONTES_EXTERNAS = ("fonts.googleapis.com", "fonts.gstatic.com")


def externo(m):
    """Mensagem de console causada por um recurso de fora da página, não por erro do mural.
    Exceções de JS chegam pelo evento pageerror e continuam contando como falha."""
    url = (m.location or {}).get("url") or ""
    host = urlsplit(url).hostname or ""
    return host in FONTES_EXTERNAS


def check(nome, cond, detalhe=""):
    (ok if cond else fail).append((nome, detalhe))
    print(("OK  " if cond else "FAIL"), nome, ("-", detalhe) if detalhe else "")


def ruim(e):
    # ignora bloqueios de rede esperados num sandbox sem egress (fontes do Google etc.)
    return "ERR_TUNNEL" not in e[1] and "ERR_NAME_NOT_RESOLVED" not in e[1] and "fonts.google" not in e[1]


def lancar(p):
    # o Chromium do runner do GitHub às vezes morre com SIGSEGV ao abrir (21/9/2026, antes de
    # qualquer verificação); uma segunda tentativa resolve, e a rodada não derruba a publicação
    try:
        return p.chromium.launch(headless=True)
    except Exception as e:
        print("aviso: o navegador caiu ao abrir (%s); tentando de novo" % type(e).__name__)
        return p.chromium.launch(headless=True)


def novo_ctx(p, viewport=(1400, 900), color_scheme=None):
    b = lancar(p)
    kw = {"viewport": {"width": viewport[0], "height": viewport[1]}}
    if color_scheme:
        kw["color_scheme"] = color_scheme
    ctx = b.new_context(**kw)
    page = ctx.new_page()
    # as fontes do Google nunca são pedidas de verdade: o teste não depende de rede
    for padrao in ("**/fonts.googleapis.com/**", "**/fonts.gstatic.com/**"):
        page.route(padrao, lambda r: r.abort())
    errs = []
    page.on("console", lambda m: errs.append((m.type, m.text)) if m.type == "error" and not externo(m) else None)
    page.on("pageerror", lambda e: errs.append(("pageerror", str(e))))
    return b, page, errs


with sync_playwright() as p:
    # ---- 1. varredura completa: 27 estados x 2 cargos, desktop, tema claro
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(500)
    ufs = page.evaluate("Object.keys(UF)")
    check("27 estados carregados", len(ufs) == 27, len(ufs))

    por_combo = page.evaluate("""(ufs) => {
        const out = {};
        trocarEscopo('uf');
        for (const uf of ufs) {
            for (const cargo of cargosDe(uf)) {
                trocarUF(uf); trocarCargoUF(cargo);
                const el = document.querySelector('#e-fold-2t'), p2 = document.querySelector('#e-p2t');
                out[uf+'-'+cargo] = {
                    hidden: el.hidden,
                    open: el.open,
                    p2t: !p2.hidden, h3: document.querySelector('#e-h-2t').textContent,
                    tem2t: (UF[uf].polls2||[]).length > 0,
                    cargoAtivo: ufCargo,
                    botoes: [...document.querySelectorAll('#ufb-cargos button')].map(b => b.dataset.cargo),
                    cards: document.querySelectorAll('#e-wall .card').length,
                };
            }
        }
        return out;
    }""", ufs)
    novos = [e for e in errs if ruim(e)]
    check(f"varredura de {len(por_combo)} combinações estado/cargo sem novo erro de console", len(novos) == 0, novos[:10])

    # cada estado mostra exatamente as mesmas disputas, as de CARGOS_ESPERADOS
    cargos_por_uf = page.evaluate("(ufs) => Object.fromEntries(ufs.map(u => [u, cargosDe(u)]))", ufs)
    fora = {u: c for u, c in cargos_por_uf.items() if c != CARGOS_ESPERADOS}
    check(f"os 27 estados com as mesmas disputas ({', '.join(CARGOS_ESPERADOS)})", not fora, fora)
    # o seletor desenhado bate com a lista de cargos, e a troca de cargo nunca cai noutro
    seletor = [(k, v) for k, v in por_combo.items() if v["botoes"] != cargos_por_uf[k.rsplit("-", 1)[0]]]
    check("o seletor de disputa traz um botão por cargo do estado", not seletor, seletor[:4])
    trocou = [(k, v["cargoAtivo"]) for k, v in por_combo.items() if not k.startswith(v["cargoAtivo"]) and not k.endswith(v["cargoAtivo"])]
    check("trocar de disputa leva ao cargo pedido, em todos os estados", not trocou, trocou[:4])

    problema_2t = []
    if UF2T is None:
        # sem resultado: as simulações de segundo turno abrem sozinhas para governador com dados, e
        # ficam ocultas no resto
        for k, v in por_combo.items():
            uf, cargo = k.rsplit("-", 1)
            if cargo == "governador" and v["tem2t"]:
                if v["hidden"] or not v["open"]:
                    problema_2t.append((k, v))
            else:
                if not v["hidden"]:
                    problema_2t.append((k, v))
        check("2º turno auto-aberto só p/ governador com dados, oculto no resto", len(problema_2t) == 0, problema_2t[:10])
    else:
        # com resultado: nos estados de totais.csv com 2º turno, o painel do confronto aparece com
        # exatamente os dois nomes no título, e os outros pares ficam numa dobra fechada; no resto,
        # painel e dobra ficam ocultos
        import unicodedata as _ud
        sa = lambda t: "".join(ch for ch in _ud.normalize("NFD", str(t).lower()) if _ud.category(ch) != "Mn")
        for k, v in por_combo.items():
            uf, cargo = k.rsplit("-", 1)
            if cargo == "governador" and uf in UF2T:
                nomes = FIN2T.get(uf, [])
                h3 = sa(v["h3"])
                if not v["p2t"] or len(nomes) != 2 or not all(sa(n) in h3 for n in nomes) or h3.count(" x ") != 1 or v["open"] and not v["hidden"]:
                    problema_2t.append((k, v))
            elif v["p2t"] or not v["hidden"]:
                problema_2t.append((k, v))
        check(f"2º turno estadual: painel do confronto com os dois nomes só nos estados de totais.csv ({', '.join(UF2T)}), outros pares numa dobra fechada, oculto no resto",
              len(problema_2t) == 0, problema_2t[:10])

    # rodadas registradas (tabela longa) começa fechada por padrão
    tb_aberta = page.evaluate("document.querySelector('#e-fold-tb').open")
    check("rodadas registradas continua fechada por padrão", tb_aberta is False, tb_aberta)
    b.close()

    # ---- 2. dossiês de estado: abre o primeiro candidato de governador em vários estados
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(500)
    # a amostra inclui os estados com 2º turno de governador (os dois finalistas de cada um) e o eleito
    # de cada estado da lista, e o texto do dossiê não pode ter "undefined" nem "NaN" (13/10/2026)
    amostra = page.evaluate("""(uf2t) => {
        const out = [];
        trocarEscopo('uf');
        const ufs = [...new Set(['SP','CE','MG','PR','PA','RS','BA','AM', ...uf2t])];
        const vistos = new Set();
        const abre = (uf, slug) => { if (vistos.has(slug)) return; vistos.add(slug); openDossieUF(slug); const d = document.querySelector('#dossie');
            out.push([uf, slug, d.open, /undefined|NaN/.test(d.textContent)]); d.close(); };
        for (const uf of ufs) {
            if (!UF[uf]) continue;
            trocarUF(uf); trocarCargoUF('governador');
            const c = UF[uf].gov[0];
            if (c) abre(uf, c.slug);
            const A = resGov('1', uf);
            for (const x of (A ? A.c.filter(r => r[0] && (r[6] === 'eleito' || r[6] === '2t')) : [])) abre(uf, x[0]);
        }
        return out;
    }""", UF2T or [])
    novos = [e for e in errs if ruim(e)]
    check(f"dossiês de estado ({len(amostra)} amostras, com os finalistas do 2º turno e os eleitos) sem erro novo", len(novos) == 0, novos[:10])
    check("todos os dossiês de estado abriram", all(a[2] for a in amostra), amostra)
    check("nenhum dossiê de estado com 'undefined' ou 'NaN'", not [a for a in amostra if a[3]], [a for a in amostra if a[3]])
    b.close()

    # ---- 3. abas nacionais + dossiês nacionais: desde 13/10/2026, todos os presidenciáveis (os do
    # 2º turno, os não eleitos e os que ficaram fora da urna), sem "undefined" nem "NaN" no texto
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(500)
    r = page.evaluate("""() => {
        trocarEscopo('br');
        // as editorias saem da barra desenhada, e não de uma lista escrita aqui
        const abas = [...document.querySelectorAll('#tabs-editorias button[role=tab]')].map(b => b.dataset.aba);
        for (const a of abas) irPara(a);
        const ruins = [];
        for (const c of C) { openDossie(c.nome); const d = document.querySelector('#dossie');
            if (!d.open || /undefined|NaN/.test(d.textContent)) ruins.push(c.nome); d.close(); }
        const telas = ['#v-candidatos', '#v-lado', '#v-partidos'].filter(sel => /undefined|NaN/.test(document.querySelector(sel).textContent));
        return {abas: abas.length, n: C.length, ruins, telas};
    }""")
    novos = [e for e in errs if ruim(e)]
    check("abas nacionais + %d dossiês nacionais sem erro novo" % r["n"], r["abas"] >= 8 and len(novos) == 0, {"abas": r["abas"], "erros": novos[:10]})
    check("dossiês nacionais, Candidatos, Lado a lado e Partidos sem 'undefined' nem 'NaN'", not r["ruins"] and not r["telas"], r)
    b.close()

    # ---- 4. mobile (390px), tema claro
    b, page, errs = novo_ctx(p, viewport=(390, 844))
    page.goto(URL)
    page.wait_for_timeout(500)
    page.evaluate("""() => {
        trocarEscopo('uf'); trocarUF('SP'); trocarCargoUF('governador');
        trocarUF('RJ'); trocarCargoUF('senador');
        trocarEscopo('br'); irPara('pesquisas'); irPara('partidos');
    }""")
    novos = [e for e in errs if ruim(e)]
    check("mobile 390px sem erro novo", len(novos) == 0, novos[:10])
    b.close()

    # ---- 5. tema escuro (prefers-color-scheme: dark), desktop
    b, page, errs = novo_ctx(p, color_scheme="dark")
    page.goto(URL)
    page.wait_for_timeout(500)
    escuro = page.evaluate("temaEscuroAgora()")
    page.evaluate("""() => {
        trocarEscopo('uf'); trocarUF('MG'); trocarCargoUF('governador');
        trocarUF('BA'); trocarCargoUF('senador');
        trocarEscopo('br'); irPara('tempo');
    }""")
    novos = [e for e in errs if ruim(e)]
    check("tema escuro (SO) detectado", escuro is True, escuro)
    check("tema escuro sem erro novo", len(novos) == 0, novos[:10])
    b.close()

print()
print(f"{len(ok)} OK, {len(fail)} FAIL")
if fail:
    print("FALHAS:")
    for n, d in fail:
        print(" -", n, d)
    raise SystemExit(1)
