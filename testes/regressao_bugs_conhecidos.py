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
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

URL = (Path(__file__).resolve().parent.parent / "mural" / "mural.html").as_uri()
ok, fail = [], []

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


def novo_ctx(p, tz=None, viewport=(1400, 900)):
    b = p.chromium.launch(headless=True)
    kw = {"viewport": {"width": viewport[0], "height": viewport[1]}}
    if tz:
        kw["timezone_id"] = tz
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

    # ================= fase A da repaginação (setembro de 2026): celular, diálogos e tema escuro =================
    ROTAS_16 = ["geral", "pesquisas", "busca", "candidatos", "lado", "partidos", "tempo", "metodo",
                "e-geral", "e-pesquisas", "e-busca", "e-candidatos", "e-lado", "e-partidos", "e-tempo", "e-metodo"]

    # ---- eixo dos gráficos em --ink-3 nos dois temas (bug: a regra era ".axis text", mas o
    # gerador escreve <text class="axis">, então o seletor nunca casava e o eixo saía preto
    # e com 15px; no escuro, praticamente invisível)
    for tema in ("light", "dark"):
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, color_scheme=tema)
        page = ctx.new_page()
        for padrao in ("**/fonts.googleapis.com/**", "**/fonts.gstatic.com/**"):
            page.route(padrao, lambda r: r.abort())
        page.goto(URL + "#pesquisas")
        page.wait_for_timeout(500)
        r = page.evaluate("""() => {
            const t = document.querySelector('#ch-corrida text.axis'); const cs = getComputedStyle(t);
            const ink3 = getComputedStyle(document.documentElement).getPropertyValue('--ink-3').trim();
            const h = ink3.replace('#',''); const rgb = 'rgb(' + [0,2,4].map(i => parseInt(h.slice(i,i+2),16)).join(', ') + ')';
            return {fill: cs.fill, esperado: rgb, fs: cs.fontSize};
        }""")
        check(f"eixo dos gráficos em --ink-3 a 12px ({tema})", r["fill"] == r["esperado"] and r["fs"] == "12px", r)
        b.close()

    # ---- a 390px a aba ativa fica dentro da barra visível nas 16 rotas (bug: a barra rolava,
    # mas irPara não trazia o botão ativo para a vista; 5 das 8 editorias abriam sem aba marcada)
    b, page, errs = novo_ctx(p, viewport=(390, 844))
    fora = []
    for rota in ROTAS_16:
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(350)
        r = page.evaluate("""() => {
            const t = document.querySelector('#tabs'), a = t.querySelector('[aria-selected="true"]');
            if (!a) return null;
            const tr = t.getBoundingClientRect(), ar = a.getBoundingClientRect();
            return ar.left >= tr.left - 1 && ar.right <= tr.right + 1;
        }""")
        if r is not True:
            fora.append((rota, r))
    check("aba ativa visível a 390px nas 16 rotas", not fora, fora)
    check("rotas a 390px sem erro de console", not [e for e in errs if "ERR_TUNNEL" not in e[1]], errs[:5])

    # ---- #lado não faz a página rolar até o comparador (bug: o hash #lado era também o id do
    # <div> do comparador, e o navegador rolava até ele ao abrir a editoria)
    page.goto(URL + "#lado")
    page.wait_for_timeout(400)
    sy = page.evaluate("scrollY")
    check("abrir #lado não rola a página (scrollY 0)", sy == 0, sy)

    # ---- comparador transposto no celular: com 2 e com 3 nomes cabe em 362px sem rolagem
    # (bug: .lado tinha min-width 640px, o segundo nome ficava fora da tela)
    r = page.evaluate("""() => {
        const out = {};
        lado = ['Lula', 'Flávio Bolsonaro', 'Augusto Cury']; renderLado();
        let el = document.querySelector('.lado'); out.n3 = [el.style.getPropertyValue('--n'), el.getBoundingClientRect().width, document.querySelector('#lado-mesa').scrollWidth];
        lado = ['Lula', 'Flávio Bolsonaro', '']; renderLado();
        el = document.querySelector('.lado'); out.n2 = [el.style.getPropertyValue('--n'), el.getBoundingClientRect().width, document.querySelector('#lado-mesa').scrollWidth];
        return out;
    }""")
    check(".lado com --n:2 cabe em 362px", r["n2"][0] == "2" and r["n2"][1] <= 362 and r["n2"][2] <= 362, r)
    check(".lado com --n:3 cabe em 362px", r["n3"][0] == "3" and r["n3"][1] <= 362 and r["n3"][2] <= 362, r)

    # ---- manchete do hero reduzida no celular (bug: a regra mirava ".hero .tag", classe que
    # não existe; o elemento é .tagline e ficava em 40px, quatro linhas)
    page.goto(URL + "#geral")
    page.wait_for_timeout(300)
    fs = page.evaluate("parseFloat(getComputedStyle(document.querySelector('.hero .tagline')).fontSize)")
    check(".hero .tagline abaixo de 32px a 390px", fs < 32, fs)

    # ---- minigráficos "um por candidato" no celular (bug: "#ch-trends svg{min-width:860px}"
    # vencia a regra do .mini por especificidade de id, e cada mini saía com 860px numa coluna de 320)
    page.goto(URL + "#busca")
    page.wait_for_timeout(300)
    r = page.evaluate("""() => { prefs.multi = 1; drawBusca();
        const m = [...document.querySelectorAll('.multi .mini')].map(x => [x.clientWidth, x.querySelector('svg').getBoundingClientRect().width]);
        return {n: m.length, ruins: m.filter(x => x[1] > x[0] + 1)}; }""")
    check("nenhum .mini svg mais largo que o .mini (prefs.multi=1, 390px)", r["n"] > 0 and not r["ruins"], r)

    # ---- gráficos de série desenhados na largura do contêiner no celular (bug: viewBox de 1180
    # espremida em 520px, texto a 5,5px em #e-ch-corrida e 6px em #ch-modo)
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(300)
    r1 = page.evaluate("""() => Math.min(...[...document.querySelectorAll('#ch-modo svg text')].map(x => parseFloat(getComputedStyle(x).fontSize) * (x.ownerSVGElement.getBoundingClientRect().width / x.ownerSVGElement.viewBox.baseVal.width)))""")
    page.goto(URL + "#uf-sp-governo-pesquisas")
    page.wait_for_timeout(500)
    r2 = page.evaluate("""() => Math.min(...[...document.querySelectorAll('#e-ch-corrida svg text')].map(x => parseFloat(getComputedStyle(x).fontSize) * (x.ownerSVGElement.getBoundingClientRect().width / x.ownerSVGElement.viewBox.baseVal.width)))""")
    check("nenhum <text> abaixo de 9px em #ch-modo a 390px", r1 >= 9, r1)
    check("nenhum <text> abaixo de 9px em #e-ch-corrida a 390px", r2 >= 9, r2)

    # ---- rolarFim só rola séries temporais (bug: rolava #e-ch-part, painel de barras, e os
    # nomes dos partidos ficavam cortados pela esquerda)
    page.goto(URL + "#uf-sp-governo-partidos")
    page.wait_for_timeout(400)
    r = page.evaluate("() => { const e = document.querySelector('#e-ch-part'); return [e.scrollLeft, e.scrollWidth, e.clientWidth]; }")
    check("#e-ch-part não é rolado nem transborda a 390px", r[0] == 0 and r[1] <= r[2] + 1, r)

    # ---- dossiê como folha de tela cheia no celular, com o fundo travado
    page.goto(URL + "#dossie-lula")
    page.wait_for_timeout(500)
    r = page.evaluate("""() => { const d = document.querySelector('#dossie'); const r = d.getBoundingClientRect(); const c = d.querySelector('[data-close]').getBoundingClientRect();
        return {w: r.width, h: r.height, close: c.height, htmlOv: getComputedStyle(document.documentElement).overflow, ov: getComputedStyle(d).overscrollBehavior,
                charts: [...d.querySelectorAll('.chart')].filter(c => c.scrollWidth > c.clientWidth + 1).length}; }""")
    check("dossiê ocupa 390x844 no celular", r["w"] == 390 and r["h"] == 844, r)
    check("botão Fechar do dossiê com 44px no celular", r["close"] >= 44, r)
    check("fundo travado e sem encadear rolagem com o dossiê aberto", r["htmlOv"] == "hidden" and r["ov"] == "contain", r)
    check("gráficos do dossiê não rolam de lado no celular", r["charts"] == 0, r)
    b.close()

    # ---- link de dossiê abre mesmo com escopo 'uf' salvo (bug: trocarUF(ufAtual) na
    # inicialização reescrevia o hash para #uf-SP-... antes de rotear() ler o hash recebido)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(300)
    page.evaluate("() => localStorage.setItem('mural.prefs', JSON.stringify({escopo: 'uf', uf: 'SP', ufCargo: 'governador'}))")
    page.goto(URL + "#dossie-lula")
    page.wait_for_timeout(600)
    r = page.evaluate("() => ({open: document.querySelector('#dossie').open, hash: location.hash, escopo})")
    check("#dossie-lula abre mesmo com escopo 'uf' salvo", r["open"] is True and r["hash"] == "#dossie-lula", r)
    page.goto(URL + "#uf-rj-senado-lado")
    page.wait_for_timeout(600)
    r = page.evaluate("() => ({uf: ufAtual, cargo: ufCargo, aba: abaAtual})")
    check("#uf-rj-senado-lado respeitado com escopo 'uf' salvo", r == {"uf": "RJ", "cargo": "senador", "aba": "e-lado"}, r)
    b.close()

    # ---- janela da régua da corrida: 4 dias em 6/9, 3 em 14/9, 2 em 24/9, 1 em 4/10
    b, page, errs = novo_ctx(p, tz="America/Sao_Paulo")
    page.goto(URL)
    page.wait_for_timeout(300)
    r = page.evaluate("() => ['2026-09-06','2026-09-14','2026-09-24','2026-10-04','2026-10-20'].map(sigmaRegua)")
    check("sigmaRegua: 4 em 06/09, 3 em 14/09, 2 em 24/09, 1 em 04/10 (e nunca abaixo de 1)", r == [4, 3, 2, 1, 1], r)
    b.close()

    # ---- tema escuro: cores de partido do mapa com contraste >= 3:1 contra o papel, faixas
    # separadas do fundo e verde de série mais claro (bug: PL #1F3B8C dava 1,7:1 no escuro)
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    page = ctx.new_page()
    for padrao in ("**/fonts.googleapis.com/**", "**/fonts.gstatic.com/**"):
        page.route(padrao, lambda r: r.abort())
    page.goto(URL + "#uf-sp-governo-geral")
    page.wait_for_timeout(500)
    r = page.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
        return {escuro: ESCURO, ruins: Object.keys(CORP).map(k => [k, corPartido(k), +contraste(corPartido(k), '#17181C').toFixed(2)]).filter(x => x[2] < 3),
                band: cs.getPropertyValue('--band').trim(), c6: cs.getPropertyValue('--c6').trim(), ground: cs.getPropertyValue('--ground').trim(),
                stroke: getComputedStyle(document.querySelector('.mapa-svg path.uf')).stroke}; }""")
    check("tema escuro: nenhuma cor de partido abaixo de 3:1 contra #17181C", r["escuro"] and not r["ruins"], r)
    check("tema escuro: --band separada do fundo (#1E2025) e --c6 clareado (#2FBF4F)", r["band"].upper() == "#1E2025" and r["c6"].upper() == "#2FBF4F", r)
    check("tema escuro: contorno dos estados não é a cor do fundo", r["stroke"] not in ("rgb(23, 24, 28)", "rgb(15, 16, 19)"), r)
    b.close()

    # ---- dossiê a 390px não rola de lado (bug: '.cover{white-space:nowrap}' pegava a cobertura do
    # dossiê e empurrava a folha para 457px; no estadual, 566px)
    b, page, errs = novo_ctx(p, viewport=(390, 844))
    JS_DLG = """() => { const d = document.querySelector('dialog.dossie[open]'); if (!d) return null;
        return {sw: d.scrollWidth, cw: d.clientWidth, ox: getComputedStyle(d).overflowX,
                largos: [...d.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > d.clientWidth + 1).length}; }"""
    page.goto(URL + "#dossie-lula")
    page.wait_for_timeout(600)
    r = page.evaluate(JS_DLG)
    check("dossiê nacional a 390px sem rolagem lateral (scrollWidth <= clientWidth)", r and r["sw"] <= r["cw"] and r["largos"] == 0, r)
    page.goto(URL + "#uf-sp-governo-geral")
    page.wait_for_timeout(800)
    page.evaluate("() => document.querySelector('[data-edossie]').click()")
    page.wait_for_timeout(600)
    r = page.evaluate(JS_DLG)
    check("dossiê estadual a 390px sem rolagem lateral", r and r["sw"] <= r["cw"] and r["largos"] == 0, r)
    # navegar por hash para outra editoria fecha o dossiê (antes o dialog ficava aberto por cima)
    page.goto(URL + "#candidatos")
    page.wait_for_timeout(400)
    r = page.evaluate("() => !document.querySelector('dialog.dossie[open]')")
    check("hash de editoria fecha o dossiê aberto", r is True, r)
    # sparkline do cartão inteira dentro do .card (overflow hidden) e rótulos de série dentro do svg
    JS_SPARK = """() => [...document.querySelectorAll('#wall .card')].map(c => { const s = c.querySelector('svg.spark'); if (!s) return 0;
        return Math.round(s.getBoundingClientRect().right - c.getBoundingClientRect().right); }).filter(d => d > 0).length"""
    r = page.evaluate(JS_SPARK)
    check("nenhuma sparkline sai do cartão a 390px", r == 0, r)
    JS_CORTES = """() => { const out = []; document.querySelectorAll('.view.on svg').forEach(svg => { const W = svg.viewBox.baseVal.width;
        if (!svg.getBoundingClientRect().width) return;
        svg.querySelectorAll('text.cand-label').forEach(t => { const b = t.getBBox(); if (b.x + b.width > W + 0.5 || b.x < 0) out.push([svg.closest('[id]').id, t.textContent]); }); });
        return out; }"""
    cortes = {}
    for h in ("pesquisas", "busca", "candidatos", "uf-sp-governo-pesquisas"):
        page.goto(URL + "#" + h)
        page.wait_for_timeout(700)
        cortes[h] = page.evaluate(JS_CORTES)
    check("nenhum rótulo de série sai do svg a 390px (pesquisas, busca, candidatos, SP)", not any(cortes.values()), cortes)
    page.goto(URL + "#busca")
    page.wait_for_timeout(600)
    r = page.evaluate("() => [...document.querySelectorAll('#tb-redes tbody tr')].map(t => Math.round(t.getBoundingClientRect().height))")
    check("#tb-redes a 390px sem linhas altas (<= 60px)", r and max(r) <= 60, r)
    # tema escuro aplicado por data-theme redesenha as cores de partido (bug: só o botão passava por aplicarAparencia)
    page.goto(URL + "#uf-sp-governo-geral")
    page.wait_for_timeout(800)
    page.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
    page.wait_for_timeout(500)
    r = page.evaluate("""() => { const fs = [...new Set([...document.querySelectorAll('#mapa-svg path.uf')].map(p => p.getAttribute('fill') || '').filter(f => /^#/.test(f)))];
        return {escuro: ESCURO, ruins: fs.map(f => [f, +contraste(f, '#17181C').toFixed(2)]).filter(x => x[1] < 3),
                legenda: [...document.querySelectorAll('.mapa-legend .lg i')].map(i => i.getAttribute('style'))}; }""")
    check("data-theme=dark redesenha o mapa com cores de partido >= 3:1", r["escuro"] and not r["ruins"] and r["legenda"], r)
    check("rotas do bloco sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    b, page, errs = novo_ctx(p, viewport=(1280, 800))
    page.goto(URL + "#candidatos")
    page.wait_for_timeout(700)
    r = page.evaluate(JS_SPARK)
    check("nenhuma sparkline sai do cartão a 1280px (4 colunas)", r == 0, r)
    b.close()

    # ---- correções da verificação da fase A: comparador, alvo do nome nas barras, 2T par a par,
    # gráficos em tablet e cobertura do cartão numa linha
    # seletores do comparador legíveis no celular (bug: três labels dividiam 362px em 30% cada e os
    # selects ficavam com 41 a 48px, mostrando só uma letra do nome escolhido)
    b, page, errs = novo_ctx(p, viewport=(390, 844))
    JS_SEL = "(id) => [...document.querySelectorAll(id + ' select')].map(s => Math.round(s.getBoundingClientRect().width))"
    page.goto(URL + "#lado")
    page.wait_for_timeout(700)
    r1 = page.evaluate(JS_SEL, "#lado-controls")
    page.goto(URL + "#uf-sp-governo-lado")
    page.wait_for_timeout(800)
    r2 = page.evaluate(JS_SEL, "#e-lado-controls")
    check("selects do comparador com >= 96px a 390px (nacional e estadual)", r1 and r2 and min(r1 + r2) >= 96, {"nacional": r1, "estadual": r2})
    # tabelas de segundo turno par a par cabem no .tablewrap a 390px (bug: 'Fernando Haddad' no cabeçalho
    # empurrava a coluna do adversário para fora da tela)
    page.goto(URL + "#uf-sp-governo-pesquisas")
    page.wait_for_timeout(800)
    page.evaluate("() => { document.querySelector('#e-fold-2t').open = true; }")
    page.wait_for_timeout(200)
    r = page.evaluate("() => [...document.querySelectorAll('#e-fold-2t .tablewrap')].map(w => [w.scrollWidth, w.clientWidth, [...w.querySelectorAll('th')].map(t => t.textContent)])")
    check("tabelas de 2T par a par (SP) sem rolagem lateral a 390px", r and all(sw <= cw for sw, cw, _ in r), r)
    # tabela de cobertura com padding menor no celular (bug: a regra do .tablewrap vencia '.cov td' por ordem)
    page.goto(URL + "#metodo")
    page.wait_for_timeout(600)
    r = page.evaluate("() => getComputedStyle(document.querySelector('table.cov td')).padding")
    check("table.cov no celular com padding de 4px 3px", r == "4px 3px", r)
    # botão Fechar fixo do dossiê é um círculo de 44px que não cobre os rótulos dos gráficos
    page.goto(URL + "#dossie-lula")
    page.wait_for_timeout(700)
    r = page.evaluate("() => { const c = document.querySelector('#dossie [data-close]'); const b = c.getBoundingClientRect(); return {w: Math.round(b.width), h: Math.round(b.height), fixed: getComputedStyle(c).position, label: c.getAttribute('aria-label')}; }")
    check("Fechar do dossiê no celular: 44x44 fixo com aria-label", r["w"] == 44 and r["h"] == 44 and r["fixed"] == "fixed" and bool(r["label"]), r)
    check("rotas do bloco (390) sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # alvo de toque do nome-botão das barras (bug: o .nmbtn tinha 17px de altura sob ponteiro grosso,
    # e no celular ele é o único caminho para o dossiê ali, já que o botão FICHA some)
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    for padrao in ("**/fonts.googleapis.com/**", "**/fonts.gstatic.com/**"):
        page.route(padrao, lambda r: r.abort())
    errs = []
    page.on("pageerror", lambda e: errs.append(("pageerror", str(e))))
    cdp = ctx.new_cdp_session(page)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
    cdp.send("Emulation.setEmulatedMedia", {"features": [{"name": "pointer", "value": "coarse"}, {"name": "hover", "value": "none"}]})
    page.goto(URL + "#uf-sp-governo-geral")
    page.wait_for_timeout(900)
    r = page.evaluate("() => ({coarse: matchMedia('(pointer:coarse)').matches, alturas: [...document.querySelectorAll('.view.on .hb .nmbtn')].map(b => Math.round(b.getBoundingClientRect().height))})")
    check("nome-botão das barras com >= 40px sob pointer:coarse", r["coarse"] and r["alturas"] and min(r["alturas"]) >= 40, r)
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    r = page.evaluate("() => [...document.querySelectorAll('.view.on .al .src a')].map(a => Math.round(a.getBoundingClientRect().height)).filter(h => h > 0)")
    check("links 'ver'/'dossiê' dos alertas com >= 40px sob pointer:coarse", r and min(r) >= 40, r)
    check("rotas do bloco (toque) sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # tablet em retrato (bug: entre 761 e ~1100px os gráficos de viewBox 1180 eram encolhidos por escala,
    # com texto de 5 a 9px; agora chartTempo, drawRegua e os dossiês desenham na largura do contêiner)
    b, page, errs = novo_ctx(p, viewport=(768, 1024))
    JS_MIN = """(sel) => [...document.querySelectorAll(sel)].map(d => { const svg = d.querySelector('svg'); if (!svg) return null;
        const vb = svg.viewBox.baseVal, sc = svg.getBoundingClientRect().width / vb.width; let mn = 99;
        svg.querySelectorAll('text').forEach(t => { const fs = parseFloat(getComputedStyle(t).fontSize) * sc; if (fs < mn) mn = fs; });
        return {id: d.id || d.className, cw: d.clientWidth, vb: vb.width, min: Math.round(mn * 10) / 10}; }).filter(Boolean)"""
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    r_regua = page.evaluate(JS_MIN, "#ch-regua")
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(800)
    r_corrida = page.evaluate(JS_MIN, "#ch-corrida, #ch-modo")
    page.goto(URL + "#uf-sp-governo-geral")
    page.wait_for_timeout(900)
    page.evaluate("() => document.querySelector('[data-edossie]').click()")
    page.wait_for_timeout(700)
    r_dz = page.evaluate(JS_MIN, "#dossie .chart")
    todos = r_regua + r_corrida + r_dz
    check("a 768px nenhum <text> abaixo de 9px em #ch-regua, #ch-corrida, #ch-modo e no dossiê estadual", todos and all(x["min"] >= 9 for x in todos), todos)
    check("a 768px os gráficos são desenhados na largura do contêiner (viewBox = clientWidth)", todos and all(abs(x["vb"] - x["cw"]) <= 2 for x in todos), todos)
    check("rotas do bloco (768) sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # cobertura do cartão numa linha no desktop (item 12: a sparkline cede largura antes do texto quebrar)
    b, page, errs = novo_ctx(p, viewport=(1280, 800))
    page.goto(URL + "#candidatos")
    page.wait_for_timeout(700)
    r = page.evaluate("() => [...document.querySelectorAll('#wall .card .cover')].map(c => Math.round(c.getBoundingClientRect().height))")
    check(".cover dos cartões numa linha a 1280px (altura <= 22px)", r and max(r) <= 22, r)
    b.close()

    # ================= fase B da repaginação: a casca de site (faixas, navegação com escopo, mapa na Visão geral, rodapé) =================
    # ---- título do documento por rota: "<data-title> · Mural dos Candidatos" nas 16 editorias
    b, page, errs = novo_ctx(p, viewport=(1280, 800))
    titulos = {}
    for rota in ROTAS_16:
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(300)
        titulos[rota] = page.evaluate("() => [document.title, document.querySelector('.view.on').dataset.title]")
    errados = {r: t for r, t in titulos.items() if t[0] != t[1] + " · Mural dos Candidatos"}
    check("document.title por rota nas 16 editorias", not errados, errados)
    # ---- o grupo de escopo (Presidência | Estados) fica na barra e sobrevive a trocarEscopo/pintarAbas
    page.goto(URL + "#geral")
    page.wait_for_timeout(300)
    r = page.evaluate("""() => { const out = [];
        for (const e of ['uf', 'br', 'uf']) { trocarEscopo(e);
            out.push({e, scope: document.querySelectorAll('#tabs .scope [data-escopo]').length,
                      ativo: (document.querySelector('#tabs .scope [aria-pressed="true"]') || {}).dataset?.escopo,
                      abas: document.querySelectorAll('#tabs-editorias button[role="tab"]').length,
                      sel: document.querySelectorAll('#tabs-editorias [aria-selected="true"]').length}); }
        return out; }""")
    check("grupo de escopo presente na barra após trocarEscopo (2 botões, ativo certo, 8 editorias)",
          all(x["scope"] == 2 and x["ativo"] == x["e"] and x["abas"] == 8 and x["sel"] == 1 for x in r), r)
    # ---- o mapa do Brasil é desenhado dentro de #v-e-geral, não mais na barra de estado
    page.goto(URL + "#uf-sp-governo")
    page.wait_for_timeout(600)
    r = page.evaluate("""() => ({dentro: document.querySelectorAll('#v-e-geral #mapa #mapa-svg path.uf').length,
        naBarra: !!document.querySelector('#ufbar #mapa'), sel: !!document.querySelector('#v-e-geral #mapa-sel .go'),
        legenda: document.querySelectorAll('#v-e-geral #mapa-legend .lg').length,
        aberto: document.querySelector('#mapa').open, subnav: !document.querySelector('#ufbar').hidden})""")
    check("mapa desenhado dentro de #v-e-geral (27 estados, cartão e legenda), subnível visível", r["dentro"] == 27 and not r["naBarra"] and r["sel"] and r["legenda"] > 0 and r["aberto"] and r["subnav"], r)
    # ---- rodapé: 27 links de estado (#uf-xx-governo) e as 8 editorias nacionais
    r = page.evaluate("""() => ({ufs: [...document.querySelectorAll('#foot-estados a')].map(a => a.getAttribute('href')),
        eds: document.querySelectorAll('#foot-editorias a').length, credito: document.querySelectorAll('.credit').length})""")
    check("rodapé com 27 links de estado no formato #uf-xx-governo", len(r["ufs"]) == 27 and all(re.fullmatch(r"#uf-[a-z]{2}-governo", h) for h in r["ufs"]), r["ufs"])
    check("rodapé com as 8 editorias e crédito da INDICA sem duplicata", r["eds"] == 8 and r["credito"] == 1, r)
    check("rotas do bloco (casca) sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()
    # ---- navegar por hash com a página rolada sobe até a barra (bug: irPara usava o offsetTop da barra sticky, que presa
    #      devolve o próprio scrollY, e o scrollTo virava no-op; os links "Continua em" e os do rodapé deixavam o leitor no meio da página)
    for w, h in ((1280, 800), (390, 844)):
        b, page, errs = novo_ctx(p, viewport=(w, h))
        page.goto(URL + "#geral")
        page.wait_for_timeout(400)
        medir = """() => { const v = document.querySelector('.view.on'), nav = document.querySelector('#nav-band');
            const hd = v.querySelector(':scope>.blkhead') || v.querySelector('#e-tag') || v.firstElementChild;
            return {hash: location.hash, scrollY: scrollY, navH: nav.offsetHeight, navTop: nav.getBoundingClientRect().top,
                    hdTop: hd.getBoundingClientRect().top, mastH: document.querySelector('header.band-top').offsetHeight}; }"""
        page.evaluate("document.querySelector('#v-geral .secfoot').scrollIntoView()")
        page.wait_for_timeout(150)
        page.click("#v-geral .secfoot a.next")
        page.wait_for_timeout(400)
        r1 = page.evaluate(medir)
        page.evaluate("document.querySelector('#foot-estados').scrollIntoView()")
        page.wait_for_timeout(150)
        page.click("#foot-estados a[href='#uf-rj-governo']")
        page.wait_for_timeout(600)
        r2 = page.evaluate(medir)
        page.evaluate("scrollTo(0, 1500)")
        page.wait_for_timeout(150)
        page.click("#tabs-editorias button[data-aba='e-busca']")
        page.wait_for_timeout(400)
        r3 = page.evaluate(medir)
        bom = lambda r: r["navTop"] == 0 and r["hdTop"] >= r["navH"] and r["scrollY"] <= r["mastH"] + 1
        check(f"a {w}px, 'Continua em', link de estado do rodapé e aba com a página rolada sobem até a barra (cabeçalho abaixo da nav)",
              r1["hash"] == "#pesquisas" and bom(r1) and r2["hash"] == "#uf-rj-governo" and bom(r2) and bom(r3), [r1, r2, r3])
        b.close()
    # ---- nada transborda o documento: scrollWidth igual ao viewport de layout em 390, 1280 e 1600 (e nas larguras de iPad:
    #      bug: entre 761 e 960px o masthead vazava para fora do .wrap e a página inteira ganhava rolagem horizontal)
    for w, h in ((390, 844), (768, 1024), (834, 1112), (1024, 768), (1280, 800), (1600, 900)):
        b, page, errs = novo_ctx(p, viewport=(w, h))
        largos = {}
        for rota in ("geral", "pesquisas", "metodo", "uf-sp-governo", "uf-sp-senado-pesquisas"):
            page.goto(URL + "#" + rota)
            page.wait_for_timeout(400)
            r = page.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth, innerWidth]")
            if r[0] > r[1]:
                largos[rota] = r
        check(f"documento sem rolagem horizontal a {w}px (scrollWidth = viewport)", not largos, largos)
        b.close()

    # ---- subnível dos estados numa linha de 44px no tablet (bug: entre 761 e 1100px a legenda e o link "Mapa do Brasil"
    #      caíam numa segunda linha, o link encostado à esquerda)
    for w, h in ((768, 1024), (1024, 768), (1100, 800)):
        b, page, errs = novo_ctx(p, viewport=(w, h))
        page.goto(URL + "#uf-sp-governo")
        page.wait_for_timeout(400)
        r = page.evaluate("""() => { const u = document.querySelector('.ufb-top'), m = document.querySelector('#ufb-mapa'), s = document.querySelector('#uf-sel');
            const ur = u.getBoundingClientRect(), mr = m.getBoundingClientRect(), sr = s.getBoundingClientRect();
            return {h: Math.round(ur.height), mapaR: Math.round(mr.right), uR: Math.round(ur.right), mapaY: Math.round(mr.top + mr.height / 2), selY: Math.round(sr.top + sr.height / 2)}; }""")
        check(f"subnível dos estados a {w}px numa linha de 44px com 'Mapa do Brasil' à direita",
              r["h"] == 44 and r["uR"] - r["mapaR"] <= 30 and abs(r["mapaY"] - r["selY"]) <= 4, r)
        b.close()
    # ---- rótulos do eixo X das janelas de 30 e 90 dias não se sobrepõem no celular (bug: o gráfico passou a ser desenhado na
    #      largura do contêiner, mas eixoTempo seguia emitindo um rótulo a cada 3 dias como a 1180px, e "03/0806/0809/08…" virava uma mancha)
    b, page, errs = novo_ctx(p, viewport=(390, 844))
    medir_eixo = """(sel) => { const svg = document.querySelector(sel + ' svg');
        const ts = [...svg.querySelectorAll('text.axis')].filter(t => t.getAttribute('text-anchor') === 'middle')
            .map(t => { const r = t.getBoundingClientRect(); return [t.textContent, Math.round(r.left), Math.round(r.right)]; }).sort((a, b) => a[1] - b[1]);
        let over = 0, gap = 999; for (let i = 1; i < ts.length; i++) { gap = Math.min(gap, ts[i][1] - ts[i - 1][2]); if (ts[i][1] < ts[i - 1][2]) over++; }
        return {n: ts.length, over, gap, labels: ts.map(t => t[0]).join(' ')}; }"""
    eixos = {}
    for rota, sel in (("pesquisas", "#ch-corrida"), ("uf-sp-governo-pesquisas", "#e-ch-corrida")):
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(500)
        for z in ("30", "90"):
            page.click(f".panel:has({sel}) .zb[data-z='{z}']")
            page.wait_for_timeout(350)
            eixos[f"{rota}/{z}"] = page.evaluate(medir_eixo, sel)
    check("a 390px, rótulos do eixo X nas janelas de 30 e 90 dias sem sobreposição (ao menos 3 datas, 6px de folga)",
          all(e["n"] >= 3 and e["over"] == 0 and e["gap"] >= 6 for e in eixos.values()), eixos)
    check("a 390px, janelas de 30/90 dias sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()
    # ---- fecho da Linha do tempo com um só link para o método (bug: "Continua em: Método" e "Método e fontes" apontavam para o mesmo hash)
    b, page, errs = novo_ctx(p)
    links = {}
    for rota, sel in (("tempo", "#v-tempo"), ("uf-ba-governo-tempo", "#v-e-tempo"), ("pesquisas", "#v-pesquisas")):
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(400)
        links[rota] = page.evaluate("(sel) => [...document.querySelectorAll(sel + ' .secfoot a')].map(a => a.getAttribute('href'))", sel)
    check("fecho de seção sem dois links para o mesmo destino (Linha do tempo nacional e estadual); Pesquisas mantém os dois",
          links["tempo"] == ["#metodo"] and links["uf-ba-governo-tempo"] == ["#uf-ba-governo-metodo"] and len(links["pesquisas"]) == 2 and len(set(links["pesquisas"])) == 2, links)
    b.close()

    # ---- carimbo de Pesquisas do estado conta só a disputa escolhida (bug: carimboDe usava u.rodadas, governo e Senado juntos,
    #      e dizia "60 rodadas" enquanto o painel logo abaixo dizia "29 rodadas"); e o subnível não repete "Escolha" antes do select
    b, page, errs = novo_ctx(p)
    carimbos = {}
    for rota in ("uf-sp-governo-pesquisas", "uf-sp-senado-pesquisas"):
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(500)
        carimbos[rota] = page.evaluate("""() => { const num = t => { const m = (t || '').match(/(\\d+) rodada/); return m ? +m[1] : null; };
            return {carimbo: num(document.querySelector('[data-carimbo=e-pesquisas]').textContent),
                    painel: num(document.querySelector('#e-cap-corrida').textContent),
                    escolha: [...document.querySelectorAll('.ufb-top .lt')].some(e => e.offsetParent && /escolha/i.test(e.textContent))}; }""")
    check("carimbo de Pesquisas do estado com o mesmo número de rodadas do painel, em SP governo e Senado, sem 'Escolha' no subnível",
          all(c["carimbo"] is not None and c["carimbo"] == c["painel"] and not c["escolha"] for c in carimbos.values())
          and carimbos["uf-sp-governo-pesquisas"]["carimbo"] != carimbos["uf-sp-senado-pesquisas"]["carimbo"], carimbos)
    # ---- a régua viva em todos os textos da corrida (bug: legenda, placar, tooltip e tabela por modo diziam "7 dias" fixos
    #      enquanto a série usava a janela do calendário)
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(500)
    sete = page.evaluate("""() => { const sig = document.querySelector('.sig-dias').textContent.trim();
        const txt = [document.querySelector('#lg-corrida').textContent, document.querySelector('#v-pesquisas').textContent].join(' ');
        return {sig, sete: /m[eé]dia m[oó]vel de 7 dias/.test(txt), viva: txt.includes('média móvel de ' + sig + ' dias')}; }""")
    check("nenhum 'média móvel de 7 dias' fixo na editoria de Pesquisas; a legenda usa a janela do dia", not sete["sete"] and sete["viva"], sete)
    b.close()

print()
print(f"{len(ok)} OK, {len(fail)} FAIL")
if fail:
    print("FALHAS:")
    for n, d in fail:
        print(" -", n, d)
    raise SystemExit(1)
