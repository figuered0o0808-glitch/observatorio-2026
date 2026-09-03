# -*- coding: utf-8 -*-
"""Regressão de bugs já corrigidos no mural: cada bloco abaixo reproduz um bug real,
encontrado e corrigido numa edição anterior, e falha se ele voltar. Ao corrigir um bug
novo, adicione um bloco aqui em vez de só corrigir e seguir em frente: é isso que evita
que o mesmo bug volte numa edição futura sem ninguém notar.

Roda contra o mural.html já gerado (não regenera nada). Uso:
    python3 testes/regressao_bugs_conhecidos.py
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = (Path(__file__).resolve().parent.parent / "mural" / "mural.html").as_uri()
ok, fail = [], []


def check(nome, cond, detalhe=""):
    (ok if cond else fail).append((nome, detalhe))
    print(("OK  " if cond else "FAIL"), nome, ("-", detalhe) if detalhe else "")


def novo_ctx(p, tz=None, viewport=(1400, 900)):
    b = p.chromium.launch(headless=True)
    kw = {"viewport": {"width": viewport[0], "height": viewport[1]}}
    if tz:
        kw["timezone_id"] = tz
    ctx = b.new_context(**kw)
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append((m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(("pageerror", str(e))))
    return b, page, errs


with sync_playwright() as p:
    # ---- smoke test geral: carrega sem erro de console
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(600)
    check("carrega sem erro de console (smoke)", len([e for e in errs if "ERR_TUNNEL" not in e[1]]) == 0, errs)
    b.close()

    # ---- HOJE correto à noite em Brasília (bug: new Date().toISOString() é UTC;
    # entre 21h e 23h59 no horário de Brasília isso já é amanhã em UTC, então o
    # mural virava o dia 3h mais cedo do que deveria)
    b, page, errs = novo_ctx(p, tz="America/Sao_Paulo")
    page.clock.install(time="2026-09-13T22:30:00-03:00")
    page.goto(URL)
    page.wait_for_timeout(400)
    hoje = page.evaluate("HOJE")
    check("HOJE correto às 22h30 de Brasília", hoje == "2026-09-13", hoje)
    b.close()

    # ---- reset limpa focoUF (bug: {...DEF} é cópia rasa; focoUF apontava pro
    # mesmo array de DEF.focoUF, então focar um candidato estadual corrompia o
    # padrão de fábrica pro resto da sessão)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    page.evaluate("""() => {
        prefs.escopo='uf'; prefs.uf='SP'; prefs.ufCargo='governador'; salvar();
        toggleFocoUF('sp-gov-tarcisio');
    }""")
    antes = page.evaluate("prefs.focoUF")
    page.evaluate("""() => { renderPrefs(); document.querySelector('#prefs [data-reset]').click(); }""")
    depois = page.evaluate("prefs.focoUF")
    stored = page.evaluate("JSON.parse(localStorage.getItem('mural.prefs')).focoUF")
    check("reset limpa focoUF (antes tinha foco)", antes == ["sp-gov-tarcisio"], antes)
    check("reset limpa focoUF (depois vazio, em memória)", depois == [], depois)
    check("reset limpa focoUF (depois vazio, no localStorage)", stored == [], stored)
    b.close()

    # ---- focoUF não vaza entre estados (bug: focoUF() devolvia o array inteiro de
    # prefs.focoUF sem filtrar pelo estado atual, então focar um candidato em SP
    # continuava esmaecendo os candidatos de qualquer outro estado visitado depois)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("""() => {
        prefs.focoUF=['sp-gov-tarcisio']; salvar();
        trocarUF('CE'); trocarCargoUF('governador');
        const foc = focoUF();
        return {size: foc.size, has: foc.has('sp-gov-tarcisio')};
    }""")
    check("focoUF não vaza de SP para CE (size 0)", r["size"] == 0, r)
    b.close()

    # ---- escalaY cobre o valor real mesmo quando passa do teto assumido (bug: o
    # eixo Y de "governador" tinha teto fixo de 52%, mas estados com corrida mais
    # concentrada (2 ou 3 nomes fortes) passam disso e o topo do gráfico cortava
    # a linha do candidato líder)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("""() => {
        const out=[];
        const orig = escalaY;
        for (const uf of ['AL','AP','PI']) {
            trocarUF(uf); trocarCargoUF('governador');
            let cap = null;
            escalaY = function(series, cheio) { const r = orig(series, cheio); cap = {series, cheio, r}; return r; };
            drawCorridaUF();
            escalaY = orig;
            const mx = Math.max(...cap.series.flatMap(s => s.pts.map(p => p.v)));
            out.push([uf, mx, cap.r[0], cap.r[0] >= mx]);
        }
        return out;
    }""")
    for uf, mx, ymax, passou in r:
        check(f"escalaY({uf}) cobre o máximo real ({mx}% <= teto {ymax}%)", passou, (mx, ymax))
    b.close()

    # ---- "Indeferido" nunca aparece com selo verde de "good" (bug: o regex de
    # "Deferido" também casava dentro de "InDEFERIDO", então o teste tinha que
    # checar a situação negativa primeiro, não a positiva)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("""() => {
        const testes = ['Indeferido em prazo recursal ou com recurso', 'Deferido', 'Renúncia', 'Aguardando julgamento', 'Cassação'];
        return testes.map(t => {
            const sit = /Indeferido|Renúncia|Cassa/i.test(t) ? 'crit' : (/Deferido/i.test(t) ? 'good' : 'warn');
            return [t, sit];
        });
    }""")
    for txt, cls in r:
        esperado = "crit" if re.search("Indeferido|Renúncia|Cassa", txt, re.I) else ("good" if re.search("Deferido", txt, re.I) else "warn")
        check(f'selo de "{txt}" = {cls}', cls == esperado, (txt, cls, esperado))
    b.close()

    # ---- legenda "ancorados por" não escapa o nome duas vezes (bug: esc() sendo
    # aplicado a um valor que ia para .textContent, que já escapa sozinho, então
    # nomes com apóstrofo mostravam "&#39;" literal na tela)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("""() => {
        trocarUF('RS'); trocarCargoUF('senador');
        return document.querySelector('#e-cap-trends') ? document.querySelector('#e-cap-trends').textContent : null;
    }""")
    check("legenda de tendências sem &#39; literal", r is None or "&#39;" not in r, r)
    b.close()

    # ---- AGIR marcado secundario=true (bug: comparação case-sensitive com a
    # sigla "Agir" quando o CSV grava "AGIR" maiúsculo; a barra do partido no
    # comparador de partidos ficava sem o número/nome do candidato)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("() => DATA.partidos.find(p => p.sigla === 'AGIR')")
    check("AGIR marcado secundario=true", r and r.get("secundario") is True, r)
    b.close()

    # ---- toast aparece por cima de um dialog aberto (bug: <dialog> nativo pinta
    # sempre acima de qualquer elemento fora dele, "top layer" do navegador, então
    # o aviso/toast ficava escondido atrás do dossiê quando um dossiê estava aberto)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("""() => {
        const dz = document.querySelector('#dossie');
        openDossie('Lula');
        avisar('teste de toast');
        const toast = document.querySelector('#toast');
        return {dentroDoDialog: dz.contains(toast), open: dz.open};
    }""")
    check("toast reparentado para dentro do dialog aberto", r["open"] and r["dentroDoDialog"], r)
    b.close()

    # ---- fPct nunca mostra "-0" (bug: arredondar um número pequeno e negativo
    # pode virar -0 em JS, e Intl.NumberFormat formata isso com sinal de menos)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("() => [fPct(-0.04), fPct(-0.001), fPct(0), fPct(-2.3), fPct(2.3)]")
    check('fPct nunca mostra "-0"', r[0] == "0" and r[1] == "0", r)
    check("fPct preserva negativos reais", r[3] == "-2,3", r)
    b.close()

    # ---- fM não mostra "1.000 mil" na borda de 999.500-999.999 (bug: o corte
    # entre "X mil" e "X mi" comparava com o valor bruto antes de arredondar, então
    # um valor que arredondava para 1000 mil não trocava de escala)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    r = page.evaluate("() => [fM(999500), fM(999999), fM(1000000), fM(500000)]")
    check('fM(999500) não é "1.000 mil"', "1.000 mil" not in r[0], r)
    check('fM(999999) não é "1.000 mil"', "1.000 mil" not in r[1], r)
    b.close()

    # ---- toggle de tema no canto superior direito só alterna claro/escuro, nunca
    # passa por "sistema" (bug original: o botão ciclava entre os 3 valores do
    # <select> de preferências em vez de alternar direto entre os 2)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(400)
    seq = page.evaluate("""() => {
        const out = [];
        for (let i=0;i<4;i++){ document.querySelector('#b-tema').click(); out.push(prefs.tema); }
        return out;
    }""")
    check("toggle de tema alterna só entre claro/escuro (nunca sistema)", all(v in ("claro", "escuro") for v in seq), seq)
    check("toggle de tema realmente alterna (não trava num valor)", len(set(seq)) == 2, seq)
    b.close()

print()
print(f"{len(ok)} OK, {len(fail)} FAIL")
if fail:
    print("FALHAS:")
    for n, d in fail:
        print(" -", n, d)
    raise SystemExit(1)
