# -*- coding: utf-8 -*-
"""Varredura geral do mural: percorre os 27 estados x 2 cargos, os temas claro/escuro,
desktop/mobile e uma amostra de dossiês, procurando qualquer erro de console. Não sabe
nada sobre bugs específicos (isso é o papel de regressao_bugs_conhecidos.py) - é uma
rede de segurança ampla para pegar efeito colateral inesperado depois de qualquer edição
em _template.html ou _gerar_mural.py.

Roda contra o mural.html já gerado (não regenera nada). Uso:
    python3 testes/varredura_geral.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = (Path(__file__).resolve().parent.parent / "mural" / "mural.html").as_uri()
ok, fail = [], []


def check(nome, cond, detalhe=""):
    (ok if cond else fail).append((nome, detalhe))
    print(("OK  " if cond else "FAIL"), nome, ("-", detalhe) if detalhe else "")


def ruim(e):
    # ignora bloqueios de rede esperados num sandbox sem egress (fontes do Google etc.)
    return "ERR_TUNNEL" not in e[1] and "ERR_NAME_NOT_RESOLVED" not in e[1] and "fonts.google" not in e[1]


def novo_ctx(p, viewport=(1400, 900), color_scheme=None):
    b = p.chromium.launch(headless=True)
    kw = {"viewport": {"width": viewport[0], "height": viewport[1]}}
    if color_scheme:
        kw["color_scheme"] = color_scheme
    ctx = b.new_context(**kw)
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append((m.type, m.text)) if m.type == "error" else None)
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
            for (const cargo of ['governador','senador']) {
                trocarUF(uf); trocarCargoUF(cargo);
                const el = document.querySelector('#e-fold-2t');
                out[uf+'-'+cargo] = {
                    hidden: el.hidden,
                    open: el.open,
                    tem2t: (UF[uf].polls2||[]).length > 0,
                };
            }
        }
        return out;
    }""", ufs)
    novos = [e for e in errs if ruim(e)]
    check(f"varredura de {len(ufs)*2} combinações estado/cargo sem novo erro de console", len(novos) == 0, novos[:10])

    # segundo turno só deve abrir sozinho para governador com dados de 2º turno
    problema_2t = []
    for k, v in por_combo.items():
        uf, cargo = k.rsplit("-", 1)
        if cargo == "governador" and v["tem2t"]:
            if v["hidden"] or not v["open"]:
                problema_2t.append((k, v))
        else:
            if not v["hidden"]:
                problema_2t.append((k, v))
    check("2º turno auto-aberto só p/ governador com dados, oculto no resto", len(problema_2t) == 0, problema_2t[:10])

    # rodadas registradas (tabela longa) começa fechada por padrão
    tb_aberta = page.evaluate("document.querySelector('#e-fold-tb').open")
    check("rodadas registradas continua fechada por padrão", tb_aberta is False, tb_aberta)
    b.close()

    # ---- 2. dossiês de estado: abre o primeiro candidato de governador em vários estados
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(500)
    amostra = page.evaluate("""() => {
        const out = [];
        trocarEscopo('uf');
        const ufs = ['SP','CE','MG','PR','PA','RS','BA','AM'];
        for (const uf of ufs) {
            trocarUF(uf); trocarCargoUF('governador');
            const c = UF[uf].gov[0];
            if (c) { openDossieUF(c.slug); out.push([uf, c.slug, document.querySelector('#dossie').open]); document.querySelector('#dossie').close(); }
        }
        return out;
    }""")
    novos = [e for e in errs if ruim(e)]
    check("dossiês de estado (8 amostras) sem erro novo", len(novos) == 0, novos[:10])
    check("todos os dossiês de estado abriram", all(a[2] for a in amostra), amostra)
    b.close()

    # ---- 3. abas nacionais + dossiê nacional
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(500)
    r = page.evaluate("""() => {
        trocarEscopo('br');
        const abas = ['geral','pesquisas','busca','candidatos','lado','partidos','tempo','metodo'];
        for (const a of abas) irPara(a);
        openDossie('Lula'); document.querySelector('#dossie').close();
        openDossie('Flávio Bolsonaro'); document.querySelector('#dossie').close();
        return abas.length;
    }""")
    novos = [e for e in errs if ruim(e)]
    check("abas nacionais + 2 dossiês sem erro novo", len(novos) == 0, novos[:10])
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
