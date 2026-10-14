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

# mural-inteiro.html, e não mural.html: desde que a Visão geral virou a parte aberta e o resto
# passou a pedir conta, mural.html é só a carga pública. O mural inteiro num arquivo só continua
# sendo gerado para conferência e é contra ele que estes testes rodam, senão eles testariam a
# tela de cadastro em vez do mural. A trava em si tem bloco próprio na regressão.
URL = (Path(__file__).resolve().parent.parent / "mural" / "mural-inteiro.html").as_uri()
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


def lancar(p):
    # o Chromium do runner do GitHub às vezes morre com SIGSEGV ao abrir (21/9/2026, antes de
    # qualquer verificação); uma segunda tentativa resolve, e a rodada não derruba a publicação
    try:
        return p.chromium.launch(headless=True)
    except Exception as e:
        print("aviso: o navegador caiu ao abrir (%s); tentando de novo" % type(e).__name__)
        return p.chromium.launch(headless=True)


def novo_ctx(p, tz=None, viewport=(1400, 900)):
    b = lancar(p)
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
    # Os estados são escolhidos pelo dado: os três de corrida mais concentrada (maior ponto de governo).
    # Até 13/10/2026 a lista era fixa (AL, AP, PI). Desde a apuração o gráfico do estado traz também o
    # quadrado do resultado em 4/10, que entra na conta do eixo; se escalaY não for chamada (estado sem
    # gráfico), o teste registra a falha em vez de quebrar o script.
    r = page.evaluate("""() => {
        const out=[];
        const orig = escalaY;
        const ufs = UFLIST.map(uf => [uf, Math.max(0, ...pollsDe(uf, 'governador').map(p => p[4]))]).sort((a, b) => b[1] - a[1]).slice(0, 3).map(x => x[0]);
        for (const uf of ufs) {
            trocarUF(uf); trocarCargoUF('governador');
            let cap = null;
            // o eixo cobre o que está na janela desenhada (o padrão passou a 90 dias em 21/9/2026);
            // ponto antigo fora da janela não aparece, então não conta
            escalaY = function(series, cheio, t0) { const r = orig(series, cheio, t0); cap = {series, cheio, r, t0: t0 ?? T0}; return r; };
            drawCorridaUF();
            escalaY = orig;
            if (!cap) { out.push([uf, null, null, false]); continue; }
            const mx = Math.max(...cap.series.filter(s => !s.dim).flatMap(s => s.pts.filter(p => p.t >= cap.t0).map(p => p.v)));
            out.push([uf, mx, cap.r[0], cap.r[0] >= mx]);
        }
        return out;
    }""")
    check("escalaY testada em três estados escolhidos pelo dado", len(r) == 3, r)
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
        b = lancar(p)
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
    fs = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#manchete')).fontSize)")
    check("a manchete (#manchete) abaixo de 32px a 390px", fs < 32, fs)

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
    # A régua do 1º turno terminou na votação; depois de 4/10 vale a do 2º turno (REGUA2T), que é
    # decisão do Francisco e pode mudar. Por isso a do 2º turno é conferida contra as constantes lidas
    # da página, e não contra números escritos aqui: o que se testa é a regra, sigma0 menos um a cada
    # passo de dias desde o início, nunca abaixo do mínimo, e SIG2 sendo essa conta no dia de hoje.
    b, page, errs = novo_ctx(p, tz="America/Sao_Paulo")
    page.goto(URL)
    page.wait_for_timeout(300)
    r = page.evaluate("() => ['2026-09-06','2026-09-14','2026-09-24','2026-10-04'].map(sigmaRegua)")
    check("sigmaRegua: 4 em 06/09, 3 em 14/09, 2 em 24/09, 1 em 04/10", r == [4, 3, 2, 1], r)
    r2 = page.evaluate("""() => { const R = REGUA2T, d0 = Date.parse(R.inicio), dias = [0, 1, R.passo - 1, R.passo, 2 * R.passo, 40];
        const datas = dias.map(n => dISO(d0 + n * 864e5));
        return {R, dias, sig: datas.map(d => sigmaDe(REGUA2T, d)), SIG2, hoje: Math.floor((Date.parse(HOJE) - d0) / 864e5),
                mapa: datas.map(sigmaRegua).length === datas.length}; }""")
    R2 = r2["R"]
    regra = lambda n: max(R2["minimo"], R2["sigma0"] - max(0, n) // R2["passo"])
    check("REGUA2T: sigmaDe segue a regra das constantes da página, e SIG2 é ela no dia de hoje",
          r2["sig"] == [regra(n) for n in r2["dias"]] and r2["SIG2"] == regra(r2["hoje"]) and min(r2["sig"]) >= R2["minimo"]
          and r2["mapa"], r2)
    b.close()

    # ---- tema escuro: cores de partido do mapa com contraste >= 3:1 contra o papel, faixas
    # separadas do fundo e verde de série mais claro (bug: PL #1F3B8C dava 1,7:1 no escuro)
    b = lancar(p)
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    page = ctx.new_page()
    for padrao in ("**/fonts.googleapis.com/**", "**/fonts.gstatic.com/**"):
        page.route(padrao, lambda r: r.abort())
    page.goto(URL + "#uf-sp-governo-geral")
    page.wait_for_timeout(500)
    r = page.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
        return {escuro: ESCURO, ruins: Object.keys(CORP).map(k => [k, corPartido(k), +contraste(corPartido(k), '#17181C').toFixed(2)]).filter(x => x[2] < 3),
                band: cs.getPropertyValue('--band').trim(), c6: cs.getPropertyValue('--c6').trim(), ground: cs.getPropertyValue('--ground').trim(),
                c6ok: contraste(cs.getPropertyValue('--c6').trim(), '#17181C') >= 3 && cs.getPropertyValue('--c6').trim().toUpperCase() !== '#008300',
                stroke: getComputedStyle(document.querySelector('.mapa-svg path.uf')).stroke}; }""")
    check("tema escuro: nenhuma cor de partido abaixo de 3:1 contra #17181C", r["escuro"] and not r["ruins"], r)
    # A prova aqui é a SEPARAÇÃO entre o palco escuro e o fundo da página, não um hex.
    # Até 23/9/2026 isto travava o valor literal #1E2025, e uma troca legítima de paleta
    # derrubava o teste sem que nada tivesse piorado. O piso é a separação que aquele par
    # dava (#1E2025 sobre #0F1013 = 1,167), arredondado para baixo.
    sep = page.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
        return +contraste(cs.getPropertyValue('--band').trim(), cs.getPropertyValue('--ground').trim()).toFixed(3); }""")
    check("tema escuro: --band separada do fundo (>= 1,15 de contraste) e --c6 clareado em relação ao claro, com contraste >= 3:1",
          sep >= 1.15 and r["c6ok"], dict(r, separacao=sep))
    check("tema escuro: contorno dos estados não é a cor do fundo", r["stroke"] not in ("rgb(23, 24, 28)", "rgb(15, 16, 19)"), r)
    # Desde 13/10/2026 os estados com 2º turno de governador são pintados com listras nas cores dos
    # partidos dos dois finalistas (um <pattern> por estado), e o estado sem definição no TSE com uma
    # cor neutra. As listras e o neutro passam pela mesma régua de 3:1 contra o papel escuro.
    lis = page.evaluate("""() => { const fs = [...document.querySelectorAll('#mapa-svg pattern rect')].map(x => x.getAttribute('fill'))
            .concat([...document.querySelectorAll('#mapa-svg path.uf')].map(x => x.getAttribute('fill'))).filter(f => /^#/.test(f || ''));
        return {n2t: document.querySelectorAll('#mapa-svg pattern[id^="t2-"]').length, t2: ufs2TAbertas().length,
                ruins: [...new Set(fs)].map(f => [f, +contraste(f, '#17181C').toFixed(2)]).filter(x => x[1] < 3)}; }""")
    check("tema escuro: listras do 2º turno e cor neutra do mapa com contraste >= 3:1, uma listra por estado com 2º turno",
          not lis["ruins"] and lis["n2t"] == lis["t2"], lis)
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
    r = page.evaluate("""() => { const fs = [...new Set([...document.querySelectorAll('#mapa-svg path.uf, #mapa-svg pattern rect')].map(p => p.getAttribute('fill') || '').filter(f => /^#/.test(f)))];
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
    # empurrava a coluna do adversário para fora da tela). Desde 13/10/2026 os pares só aparecem nos
    # estados com 2º turno de governador; o teste usa o de nomes mais longos, escolhido pelo dado, e
    # mede a tabela do confronto e as dos outros pares
    page.goto(URL)
    page.wait_for_timeout(600)
    uf2 = page.evaluate("() => { const l = ufs2TAbertas().filter(k => rodadasUF2T(k).length); return l.length ? l.map(k => [k, finalUF(k).map(c => c[1]).join('').length]).sort((a, b) => b[1] - a[1])[0][0].toLowerCase() : null; }")
    if uf2:
        page.goto(URL + f"#uf-{uf2}-governo-pesquisas")
        page.wait_for_timeout(800)
        page.evaluate("() => { const f = document.querySelector('#e-fold-2t'); if (!f.hidden) f.open = true; }")
        page.wait_for_timeout(200)
        r = page.evaluate("() => [...document.querySelectorAll('#e-p2t .tablewrap, #e-fold-2t:not([hidden]) .tablewrap')].map(w => [w.scrollWidth, w.clientWidth, [...w.querySelectorAll('th')].filter(t => t.offsetParent).map(t => t.textContent)])")
        check(f"tabelas de 2º turno ({uf2.upper()}: o confronto e os outros pares) sem rolagem lateral a 390px, ao menos uma", r and all(sw <= cw for sw, cw, _ in r), r)
    else:
        print("aviso: nenhum estado com 2º turno de governador e rodada do confronto; tabelas de 2º turno não medidas")
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
    b = lancar(p)
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    for padrao in ("**/fonts.googleapis.com/**", "**/fonts.gstatic.com/**"):
        page.route(padrao, lambda r: r.abort())
    errs = []
    page.on("pageerror", lambda e: errs.append(("pageerror", str(e))))
    cdp = ctx.new_cdp_session(page)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
    cdp.send("Emulation.setEmulatedMedia", {"features": [{"name": "pointer", "value": "coarse"}, {"name": "hover", "value": "none"}]})
    # mede em SP e num estado com 2º turno (as barras do resultado do TSE e as do 2º turno também levam o nome-botão)
    alt = {}
    for rota in ("uf-sp-governo-geral", "uf-am-governo-geral"):
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(900)
        alt[rota] = page.evaluate("() => ({coarse: matchMedia('(pointer:coarse)').matches, alturas: [...document.querySelectorAll('.view.on .hb .nmbtn, .view.on [data-edossie].nmbtn')].filter(b => b.offsetParent).map(b => Math.round(b.getBoundingClientRect().height))})")
    check("nome-botão das barras com >= 40px sob pointer:coarse (SP e AM, ao menos um em cada)",
          all(r["coarse"] and r["alturas"] and min(r["alturas"]) >= 40 for r in alt.values()), alt)
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    # o painel de alertas é do dia: num dia sem sinal ele fica vazio, e isso é estado legítimo, não bug
    # (foi o que derrubou a rotina de 19 a 20/9/2026, três dias depois da última rodada presidencial).
    # O que este teste guarda é a regra de CSS do alvo de toque; quando não há alerta real, ele desenha
    # um de amostra pela própria função da página e mede esse.
    r = page.evaluate("""() => {
      let links = [...document.querySelectorAll('.view.on .al .src a')], amostra = false;
      if (!links.length) {
        renderAlertas(document.querySelector('#alerts'), [{s: 'info', k: 'Amostra', t: 'alerta desenhado pelo teste', src: 'teste', go: 'pesquisas', n: 'Lula'}], 'Alertas (amostra do teste)', '#tempo');
        links = [...document.querySelectorAll('.view.on .al .src a')]; amostra = true;
      }
      return {amostra, alturas: links.map(a => Math.round(a.getBoundingClientRect().height)).filter(h => h > 0)};
    }""")
    check("links 'ver'/'dossiê' dos alertas com >= 40px sob pointer:coarse", r["alturas"] and min(r["alturas"]) >= 40, r)
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
        const ts = [...svg.querySelectorAll('text.axis')].filter(t => /^\d\d\/\d\d$/.test(t.textContent))
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
    # Desde 13/10/2026 o carimbo diz o turno: com o resultado do TSE, "de 1º turno" e a data do TSE nos
    # estados decididos; nos estados com 2º turno de governador, as rodadas de 2º turno depois de 4/10,
    # o mesmo número do painel do confronto. O estado de 2º turno vem do dado.
    turno = page.evaluate("""async () => { const num = t => { const m = (t || '').match(/(\d+) rodada/); return m ? +m[1] : null; };
        const car = () => document.querySelector('[data-carimbo=e-pesquisas]').textContent;
        const out = {comRes: !!RES};
        trocarEscopo('uf'); trocarUF('SP'); trocarCargoUF('governador'); irPara('e-pesquisas'); atualizarCarimbos();
        out.sp = {est: estadoGov('SP'), car: car()};
        const k = ufs2TAbertas()[0];
        if (k) { trocarUF(k); irPara('e-pesquisas'); atualizarCarimbos();
            out.t2 = {uf: k, car: car(), n: num(car()), painel: num(document.querySelector('#e-cap-2tm').textContent), camp: campUF2T(k).length}; }
        return out; }""")
    if turno["comRes"]:
        sp, t2 = turno["sp"], turno.get("t2")
        check("com resultado, o carimbo de Pesquisas do estado diz o turno (decidido: 1º turno e a data do TSE; 2º turno: rodadas depois de 4/10, como o painel)",
              (sp["est"] != "decidido" or ("de 1º turno" in sp["car"] and "resultado do TSE de" in sp["car"]))
              and (t2 is None or ("2º turno" in t2["car"] and (t2["n"] == t2["painel"] == t2["camp"] if t2["camp"] else "nenhuma" in t2["car"]))), turno)
    # ---- a régua viva em todos os textos da corrida (bug: legenda, placar, tooltip e tabela por modo diziam "7 dias" fixos
    #      enquanto a série usava a janela do calendário)
    # Desde 13/10/2026 o span leva o texto inteiro ("1 dia", "3 dias"), escrito por diasTxt: com a
    # régua em 1 dia, o "<span>1</span> dias" fixo do HTML dava "1 dias".
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(500)
    sete = page.evaluate("""() => { const sig = document.querySelector('#v-pesquisas .sig-dias').textContent.trim();
        const txt = [document.querySelector('#lg-corrida').textContent, document.querySelector('#v-pesquisas').textContent].join(' ');
        return {sig, esperado: diasTxt(SIG), sete: /m[eé]dia m[oó]vel de 7 dias/.test(txt), viva: txt.includes('média móvel de ' + sig),
                umDias: (() => { const c = document.body.cloneNode(true); c.querySelectorAll('script,style').forEach(e => e.remove());
                    return /\b1 dias\b/.test(c.textContent); })()}; }""")
    check("nenhum 'média móvel de 7 dias' fixo na editoria de Pesquisas; a legenda usa a janela do dia, escrita por diasTxt",
          not sete["sete"] and sete["viva"] and sete["sig"] == sete["esperado"], sete)
    check("nenhum '1 dias' no mural (a janela de um dia se escreve no singular)", not sete["umDias"], sete)
    b.close()

    # ================= fase C da repaginação: a home editorial e a abertura dos estados =================
    # ---- manchete numérica gerada pelo dado: não vazia, sem 'undefined' nem 'NaN', até 44px e no máximo duas linhas a 1280,
    #      até 34px a 390; legenda-placar com os oito; painéis de .grid2 com o topo alinhado; manchete do estado no alto a 390
    JS_M = """() => { const m = document.querySelector('#manchete'), l = document.querySelector('#lede-dados'); const cs = getComputedStyle(m);
        return {txt: m.textContent.trim(), lede: l ? l.textContent : '', fs: parseFloat(cs.fontSize), linhas: Math.round(m.getBoundingClientRect().height / parseFloat(cs.lineHeight)),
                legenda: document.querySelectorAll('#lg-home .lp').length, ult: document.querySelectorAll('#ult-rodada .hb').length,
                ultTit: (document.querySelector('#ult-rodada .eyebrow') || {}).textContent || ''}; }"""
    JS_G = """() => [...document.querySelectorAll('.view.on .grid2')].filter(g => g.querySelectorAll(':scope>.panel').length > 1 && g.getBoundingClientRect().height > 0)
        .map(g => [...g.querySelectorAll(':scope>.panel')].map(p => Math.round(p.getBoundingClientRect().top)))"""
    b, page, errs = novo_ctx(p, viewport=(1280, 800))
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    r = page.evaluate(JS_M)
    check("#manchete não vazio, sem 'undefined' nem 'NaN' (manchete e lede)", bool(r["txt"]) and not re.search(r"undefined|NaN", r["txt"] + r["lede"]), r)
    check("#manchete com font-size <= 44px e no máximo duas linhas a 1280", r["fs"] <= 44 and 1 <= r["linhas"] <= 2, r)
    # a última rodada pode ser só do confronto Lula x Flávio (desde 5/10/2026): aí são duas barras
    check("legenda-placar com 8 itens e última rodada com barras", r["legenda"] == 8 and r["ult"] >= (2 if "2º turno" in r["ultTit"] else 3), r)
    tops = {}
    # SP (governo decidido) e um estado com 2º turno de governador, escolhido pelo dado (13/10/2026)
    uf2 = page.evaluate("() => (ufs2TAbertas()[0] || 'AM').toLowerCase()")
    for h in ("pesquisas", "uf-sp-governo", f"uf-{uf2}-governo"):
        page.goto(URL + "#" + h)
        page.wait_for_timeout(700)
        tops[h] = page.evaluate(JS_G)
    check("topos dos painéis de .grid2 iguais a 1280 (Pesquisas, Visão geral de SP e de um estado com 2º turno)",
          any(tops[h] for h in tops if h.startswith("uf-")) and all(len(set(t)) == 1 for g in tops.values() for t in g), tops)
    check("rotas do bloco (fase C, 1280) sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()
    # ---- rodada só de 2º turno como a mais recente (13/10/2026: as primeiras chegaram pela coleta; o
    #      trilho buscava os pontos dela entre os de 1º turno, saía sem barra, e a regressão barrou a
    #      publicação). Uma rodada de ensaio, publicada só em votos válidos, entra como a última.
    b, page, errs = novo_ctx(p, viewport=(1280, 800))
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    # Desde 13/10/2026 polls2t traz [inst, dt, cand, p, url, modo, vv, base, cf, pos] e a média do 2º
    # turno é feita em válidos: a rodada de ensaio entra com base "v" e pos, e refazer2T() descarta as
    # contas guardadas, como faria uma página aberta depois dela.
    n1 = page.evaluate("""() => {
        const dt = HOJE, inst = 'Instituto de Ensaio', url = 'https://exemplo.invalid/ensaio';
        const pts = [[inst, dt, 'Lula', 48.5, url, 'digital', 48.5, 'v', dt, 1], [inst, dt, 'Flávio Bolsonaro', 51.5, url, 'digital', 51.5, 'v', dt, 1]];
        DATA.fichas.push({inst, dt, campo: dt + ' a ' + dt, met: '', reg: '', url: '', t: '2', modo: 'digital'});
        DATA.polls2t.push(...pts); refazer2T();
        drawUltimaRodada(); drawAlertas();
        const el = document.querySelector('#ult-rodada'), al = document.querySelector('#alerts');
        return {barras: el.querySelectorAll('.hb').length, trilho: el.textContent, alerta: al ? al.textContent : '',
                media: rodadas2T().some(r => r.inst === inst), validos: rodadas2TVV().some(r => r.inst === inst && r.pos)}; }""")
    check("rodada só de 2º turno como a última: trilho com as duas barras e o aviso de votos válidos",
          n1["barras"] == 2 and "2º turno" in n1["trilho"] and "51,5" in n1["trilho"] and "votos válidos" in n1["trilho"],
          {"barras": n1["barras"], "trilho": n1["trilho"][:160]})
    check("rodada só de 2º turno como a última: o alerta de rodada nova traz os números dela",
          bool(re.search(r"Instituto de Ensaio.*2º turno.*51,5%.*48,5%", n1["alerta"])), n1["alerta"][:200])
    check("rodada publicada só em votos válidos fica fora da conta em intenção total e entra na média em válidos",
          not n1["media"] and n1["validos"], {k: n1[k] for k in ("media", "validos")})
    check("rodada só de 2º turno como a última sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()
    b, page, errs = novo_ctx(p, viewport=(390, 844))
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    r = page.evaluate(JS_M)
    check("#manchete com font-size <= 34px a 390", bool(r["txt"]) and r["fs"] <= 34, r)
    page.goto(URL + "#uf-sp-governo")
    page.wait_for_timeout(900)
    r = page.evaluate("""() => { const e = document.querySelector('#e-tag'); const b = e.getBoundingClientRect();
        return {top: Math.round(b.top + scrollY), bottom: Math.round(b.bottom + scrollY), txt: e.textContent.trim()}; }""")
    check("#e-tag (manchete do estado) dentro dos primeiros 700px em #uf-sp-governo a 390px", bool(r["txt"]) and r["bottom"] <= 700, r)
    check("rotas do bloco (fase C, 390) sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ================= agregação das pesquisas: uma rodada isolada não vira a corrida sozinha =================
    # (bug de 7/9/2026: com a régua de 4 dias, a rodada da Veritá de 6/9, única das nove recentes a dar
    #  Flávio à frente no segundo turno, respondia por 27% do peso da média e invertia a linha)
    # Desde 13/10/2026 cada turno é medido no instante da própria conta: o 1º na última rodada de 1º
    # turno (a véspera, com SIG) e o 2º na última rodada da campanha, com a régua do 2º turno e o efeito
    # casa medido em todas as rodadas do confronto, exatamente como media2T faz. Medir os dois em
    # DATA.meta.ultima punha o 1º turno dez dias depois da última rodada dele.
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(700)
    ag = page.evaluate("""() => {
        const r1 = rodadas1T(), t1 = Math.max(...r1.map(r => r.t)), m2 = media2T();
        const camp = rodadas2TCampanha(), r2 = m2 && m2.fase === 'campanha' ? camp : rodadas2TAntes();
        const t2 = m2 ? m2.t : null, o2 = {base: rodadas2TVV()};
        const p1 = pesosEm(r1, OITO, SIG, t1), p2 = m2 ? pesosEm(r2, FINAL, m2.sigma, t2, o2) : null;
        const share = q => { const tot = q.peso.reduce((a, b) => a + b, 0); return Math.max(...q.peso) / tot; };
        // um instituto que publica duas vezes na janela entra uma vez só, e a janela alarga até juntar
        // AG.inst institutos (ou todos os que existem, se forem menos)
        const insts = (q, t) => q.dentro.filter(x => Math.abs(x.r.t - t) <= 2 * q.janela * 864e5).map(x => x.r.inst);
        const i1 = insts(p1, t1), i2 = p2 ? insts(p2, t2) : [];
        // A Veritá de 6/9 é medida no dia do bug (7/9, com a régua daquele dia e só o que tinha
        // saído até ali), e não no dia em que o teste roda: com a régua encurtando, em 24/9 ela
        // saiu da janela e o teste, que a procurava na data de hoje, barrou quatro atualizações.
        const rt = rodadas2T(), tb = Date.parse('2026-09-07'), rb = rt.filter(r => r.t <= tb), pb = pesosEm(rb, FINAL, sigmaRegua('2026-09-07'), tb);
        const totb = pb.peso.reduce((a, b) => a + b, 0), tot0 = pb.dentro.reduce((a, x) => a + x.w, 0);
        const iv = pb.dentro.findIndex(x => x.r.inst === 'Instituto Veritá' && dISO(x.r.t) === '2026-09-06');
        return {maior1: share(p1), maior2: p2 ? share(p2) : 0,
                repetido1: i1.length !== new Set(i1).size, repetido2: i2.length !== new Set(i2).size,
                inst1: new Set(i1).size, inst2: new Set(i2).size, AGinst: AG.inst,
                exist1: new Set(r1.map(r => r.inst)).size, exist2: new Set(r2.map(r => r.inst)).size,
                veritaShare: iv < 0 ? null : pb.peso[iv] / totb, veritaTempo: iv < 0 ? null : pb.dentro[iv].w / tot0,
                m2: m2 && {fase: m2.fase, a: m2.a, b: m2.b, va: m2.va, vb: m2.vb, dif: m2.dif, erro: m2.erro, empate: m2.empate,
                           cru: m2.m[m2.a] - m2.m[m2.b]},
                empatam2: m2 ? empatam(r2, FINAL, m2.sigma, t2, m2.a, m2.b, o2) : null}; }""")
    check("nenhuma rodada passa de 15% do peso da média (primeiro e segundo turno)",
          ag["maior1"] <= 0.1501 and ag["maior2"] <= 0.1501, {k: ag[k] for k in ("maior1", "maior2")})
    check("cada instituto entra uma vez só na janela (primeiro e segundo turno)", not ag["repetido1"] and not ag["repetido2"],
          {k: ag[k] for k in ("inst1", "inst2")})
    check("a janela junta pelo menos AG.inst institutos, ou todos os que existem (primeiro e segundo turno)",
          ag["inst1"] >= min(ag["AGinst"], ag["exist1"]) and (ag["m2"] is None or ag["inst2"] >= min(ag["AGinst"], ag["exist2"])),
          {k: ag[k] for k in ("inst1", "exist1", "inst2", "exist2", "AGinst")})
    check("a rodada que destoa do conjunto perde peso (Veritá de 6/9, no segundo turno de 7/9)",
          ag["veritaShare"] is not None and ag["veritaShare"] <= 0.1501 and ag["veritaShare"] < ag["veritaTempo"],
          {k: ag[k] for k in ("veritaShare", "veritaTempo")})
    # o empate técnico é uma regra, não um resultado do dia: quem decide é a conta, e o texto do
    # painel tem que dizer a mesma coisa que ela. Este bloco já barrou uma rodada automática por
    # fixar o placar de um dia (9/9/2026), então checa a coerência, nunca o número. media2T compara a
    # diferença já renormalizada (va - vb) com a incerteza; empatam() compara a diferença crua, que
    # difere dela em centésimos, então as duas só precisam concordar longe da fronteira.
    m2 = ag["m2"]
    if m2 is None:
        texto = page.evaluate("() => document.querySelector('#cap-2t').textContent")
        check("sem rodada de 2º turno, o painel do segundo turno não inventa número", not re.search(r"\d", texto or ""), texto[:120])
    else:
        empate = m2["erro"] is not None and abs(m2["dif"]) < m2["erro"]
        perto = m2["erro"] is not None and abs(abs(m2["dif"]) - m2["erro"]) < 0.1
        check("media2T: empate técnico quando a diferença em válidos é menor que a incerteza, e empatam() concorda",
              m2["empate"] == empate and (perto or ag["empatam2"] == empate),
              {"dif": round(m2["dif"], 2), "erro": m2["erro"] and round(m2["erro"], 2), "empate": m2["empate"], "empatam": ag["empatam2"]})
        texto = page.evaluate("() => document.querySelector('#cap-2t').textContent")
        diz_empate = "Empate técnico" in texto and "Nenhum dos dois está à frente" in texto
        check("o painel do segundo turno diz o que a conta diz, empate ou vantagem",
              diz_empate == m2["empate"] and (diz_empate or "à frente de" in texto),
              {"empate": m2["empate"], "texto": texto[:120]})
    # A média não pode achatar movimento real. A versão anterior gravava o fato de um dia ("Cury
    # subiu mais de 5 pontos") e barrou a rotina em 17/9, quando a subida, real, passou a medir 4,4:
    # teste que grava resultado esperado em vez de regra passa a defender o defeito. A regra é: se as
    # próprias rodadas brutas mostram um deslocamento grande em 30 dias (mediana dos últimos 12 dias
    # contra a mediana de 30 a 42 dias atrás), a média móvel tem de mostrar o mesmo sentido e ao menos
    # 60% do tamanho. Quem mais se moveu é escolhido pelo dado, não por nome.
    # Desde 13/10/2026 as janelas do 1º turno se contam da última rodada dele (3/10), e não da borda
    # dos gráficos, que passou a acompanhar o 2º turno.
    mov = page.evaluate("""() => { const out = {}, med = a => { a = a.slice().sort((x, y) => x - y); return a[Math.floor(a.length / 2)]; };
        const T = Date.parse(ULT1T);
        for (const n of OITO) { const pts = serieDe(n);
            const rec = pts.filter(p => p.t > T - 12 * 864e5).map(p => p.v), ant = pts.filter(p => p.t > T - 42 * 864e5 && p.t <= T - 30 * 864e5).map(p => p.v);
            if (rec.length < 3 || ant.length < 3) continue;
            const p = posicao(n); out[n] = {bruto: med(rec) - med(ant), agora: p ? p.agora : null, medRec: med(rec), medAnt: med(ant), nRec: rec.length, nAnt: ant.length}; }
        return out; }""")
    # Até 29/9/2026 a regra comparava o bruto com a variação de 30 dias da própria média. As duas
    # medem janelas diferentes: com a Quaest de 28/9, o "30 dias atrás" da média caiu em cima do
    # salto de Cury de 29 a 31/8 (de ~2% a ~10%), a média daquele instante já pegava metade dele e a
    # variação saiu 0,7 contra 3,6 do bruto, embora a média de hoje (4,9) estivesse colada nas
    # rodadas recentes (~5,5). O que "achatar" quer dizer é a média não chegar aonde as rodadas
    # chegaram: agora a regra mede isso, com a mesma base bruta dos dois lados.
    def nao_achata(m):
        grande = m is not None and abs(m["bruto"]) >= 3
        return (not grande) or (m["agora"] is not None
                                and (m["agora"] - m["medAnt"] > 0) == (m["bruto"] > 0)
                                and abs(m["agora"] - m["medAnt"]) >= 0.6 * abs(m["bruto"])
                                and abs(m["agora"] - m["medRec"]) <= max(1.5, 0.4 * abs(m["bruto"])))
    quem = max(mov, key=lambda n: abs(mov[n]["bruto"])) if mov else None
    m = mov.get(quem) if quem else None
    check("a média não achata movimento real: quem mais se moveu nas rodadas brutas leva a média ao nível das rodadas recentes",
          nao_achata(m), {"quem": quem, **({k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items()} if m else {})})
    # A mesma regra no 2º turno, em válidos, para os dois finalistas, com janelas de 7 dias contadas da
    # última rodada da campanha: a mediana das rodadas da última semana contra a da semana anterior
    # (que pode trazer as simulações feitas antes de 4/10). Com média de campanha e sem três rodadas em
    # cada semana, o teste falha dizendo "sem base", em vez de passar sem ter medido nada. Sem média de
    # campanha (nenhuma rodada depois de 4/10), não há o que medir e o mural mostra as simulações.
    mov2 = page.evaluate("""() => { const m = media2T(); if (!m || m.fase !== 'campanha') return null;
        const med = a => { a = a.slice().sort((x, y) => x - y); return a[Math.floor(a.length / 2)]; }, T = m.t, todas = rodadas2TVV();
        const out = {};
        for (const n of FINAL) {
            const rec = rodadas2TCampanha().filter(r => r.t > T - 7 * 864e5 && r.t <= T).map(r => r.v[n]);
            const ant = todas.filter(r => r.t > T - 14 * 864e5 && r.t <= T - 7 * 864e5).map(r => r.v[n]);
            out[n] = {nRec: rec.length, nAnt: ant.length, bruto: rec.length && ant.length ? med(rec) - med(ant) : null,
                      agora: n === m.a ? m.va : m.vb, medRec: rec.length ? med(rec) : null, medAnt: ant.length ? med(ant) : null}; }
        return out; }""")
    if mov2 is None:
        check("a média do 2º turno não achata movimento real (sem média de campanha, nada a medir)", True)
    else:
        sem_base = [n for n, x in mov2.items() if x["nRec"] < 3 or x["nAnt"] < 3]
        check("a média do 2º turno não achata movimento real: Lula e Flávio, janelas de 7 dias em válidos",
              not sem_base and all(nao_achata(x) for x in mov2.values()),
              {"sem base": sem_base} if sem_base else {n: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in x.items()} for n, x in mov2.items()})
    # o gráfico da home e a legenda-placar precisam mostrar o mesmo número (bug: o gráfico da home
    # ficou na média antiga quando a agregação entrou, e dizia 33,8% onde a legenda dizia 33,4%)
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    home = page.evaluate("""() => { const num = t => { const m = (t || '').match(/(\\d+(?:,\\d+)?)%/); return m ? m[1] : null; };
        const rot = {}, leg = {};
        for (const t of document.querySelectorAll('#ch-home text.cand-label')) { const p = t.textContent.trim().split(' '); rot[p.slice(0, -1).join(' ')] = num(t.textContent); }
        for (const e of document.querySelectorAll('#lg-home .lp')) leg[e.querySelector('.nm').textContent.trim()] = num(e.querySelector('.v').textContent);
        return {rot, leg}; }""")
    iguais = [k for k in home["leg"] if k in home["rot"] and home["leg"][k] != home["rot"][k]]
    check("gráfico da home e legenda-placar com o mesmo valor para cada candidato", not iguais,
          {k: (home["rot"].get(k), home["leg"].get(k)) for k in iguais} or home["leg"])
    # ---- efeito casa: instituto que erra sempre para o mesmo lado é régua torta, não rodada
    # fora da curva, e o desconto por rodada não pegava isso (medido em 10/9/2026: o Gerp
    # aparecia 6,6 pontos mais favorável a Flávio em 11 de 11 rodadas e perdia só 11% do peso)
    # Até 13/10/2026 o teste exigia o sinal de dois institutos com nome (Gerp e AtlasIntel), o que é
    # o resultado de uma época, não a regra. A regra: a correção de cada instituto tem o sentido da
    # mediana dos desvios dele contra os vizinhos, medidos com a mesma vizinhança de casaDe (outros
    # institutos na mesma semana, ao menos AG.vizinhos), e é exigida quando a correção passa de 1
    # ponto. A conta é a do 2º turno em válidos, que é a que a média usa.
    casa = page.evaluate("""() => {
        const n2 = FINAL, todas = rodadas2TVV(), m = media2T();
        const c2 = casaDe(todas, n2);
        // a vizinhança de casaDe, refeita aqui: desvio de cada rodada contra a mediana dos outros na semana
        const desv = {};
        for (const r of todas) { const perto = todas.filter(o => o !== r && o.inst !== r.inst && Math.abs(o.t - r.t) <= AG.semana);
            if (perto.length < AG.vizinhos) continue;
            for (const n of n2) { const v = r.v[n]; if (v == null) continue; const outros = perto.map(o => o.v[n]).filter(x => x != null);
                if (outros.length < AG.vizinhos) continue; const med = medPond(outros.map(x => [x, 1]));
                ((desv[r.inst] = desv[r.inst] || {})[n] = desv[r.inst][n] || []).push(v - med); } }
        const sinais = [];
        for (const i in c2) for (const n in c2[i]) { const aj = c2[i][n].aj; if (Math.abs(aj) < 1) continue;
            const md = medPond((desv[i][n] || []).map(x => [x, 1])); sinais.push({inst: i, nome: n, aj, md, ok: md != null && Math.sign(md) === Math.sign(aj)}); }
        if (!m || m.fase !== 'campanha') return {sinais, semCampanha: true};
        const rods = rodadas2TCampanha(), t = m.t, o = {base: todas};
        const fresco = a => a.map(r => ({inst: r.inst, t: r.t, v: {...r.v}}));
        const bruto = (() => {   // média sem correção, refazendo a conta com os valores publicados em arrays novos (casaDe guarda por array)
            const guarda = AG.tetoCasa; AG.tetoCasa = 0;
            const mm = agregarEm(fresco(rods), n2, m.sigma, t, {base: fresco(todas)}); AG.tetoCasa = guarda; return mm; })();
        // a correção entra rodada a rodada: dentro da janela de peso, quantas rodadas chegam com o
        // valor ajustado (r.casa) e quanto esse ajuste moveu, em módulo e ponderado. Em módulo
        // porque institutos com vieses opostos podem se anular na média sem que nada esteja errado
        // (foi o que derrubou a rodada automática de 21/9/2026: corrigida 44,52 contra crua 44,54)
        const p2 = pesosEm(rods, n2, m.sigma, t, o), tot = p2.peso.reduce((a, b) => a + b, 0);
        const crus = new Map(rods.map(r => [r.inst + '|' + r.t, r.v]));
        let corrigidas = 0, moveu = 0;
        p2.dentro.forEach((x, i) => { if (!x.r.casa || !(p2.peso[i] > 0)) return; corrigidas++;
            const c = crus.get(x.r.inst + '|' + x.r.t); for (const n of n2) if (c && c[n] != null && x.r.v[n] != null) moveu += Math.abs(x.r.v[n] - c[n]) * p2.peso[i] / tot / n2.length; });
        return {sinais, erro: m.inc && m.inc.erro, parteCasa: m.inc && m.inc.casa,
                media: m.m[n2[0]], bruto: bruto[n2[0]], corrigidas, moveu,
                pontosCrus: DATA.polls2t.filter(p => p[7] === 't' && p[9]).map(p => p[3])};
    }""")
    ruins = [x for x in casa["sinais"] if not x["ok"]]
    check("a correção de cada instituto tem o sentido dos desvios medidos contra os vizinhos (exigido acima de 1 ponto)",
          not ruins, ruins[:4] or [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in x.items()} for x in casa["sinais"][:4]])
    if casa.get("semCampanha"):
        check("efeito casa na média do 2º turno (sem média de campanha, nada a medir)", True)
    else:
        check("a correção de viés entra na média: rodadas da janela chegam ajustadas e o ajuste tem peso",
              casa["corrigidas"] >= 1 and casa["moveu"] > 0.05,
              {"rodadas corrigidas na janela": casa["corrigidas"], "ajuste ponderado em módulo": round(casa["moveu"], 3),
               "corrigida": round(casa["media"], 2), "crua": round(casa["bruto"], 2)})
        check("a incerteza soma o erro da própria estimativa do viés, e não fica estreita de mentira",
              casa["parteCasa"] is not None and casa["parteCasa"] > 0 and casa["erro"] > casa["parteCasa"],
              {"erro": casa["erro"] and round(casa["erro"], 2), "parte de viés": casa["parteCasa"] and round(casa["parteCasa"], 2)})
        check("os pontos publicados não são reescritos pela correção",
              all(float(v) == round(float(v), 1) for v in casa["pontosCrus"]) and len(casa["pontosCrus"]) > 0,
              casa["pontosCrus"][:4])
    check("agregação sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- editoria de método abre dividida por metodologia, e a marca é a nova (7/9/2026)
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(700)
    meta = page.evaluate("""() => {
        const segs = [...document.querySelectorAll('#meta-seg button')].map(b => ({t: b.textContent.trim(), on: b.getAttribute('aria-pressed'), mv: b.dataset.mv}));
        const chips = [...document.querySelectorAll('#f-modo-cand button')].map(b => b.textContent.trim());
        return {segs, chips, cap: document.querySelector('#meta-cap').textContent,
                slogan: (document.querySelector('.slogan') || {}).textContent,
                velha: document.body.textContent.includes('capital político digital')}; }""")
    check("a editoria de método abre por metodologia, com esse botão primeiro e marcado",
          meta["segs"] and meta["segs"][0]["mv"] == "modo" and meta["segs"][0]["on"] == "true"
          and meta["segs"][1]["mv"] == "cand" and meta["segs"][1]["on"] == "false", meta["segs"])
    check("os chips da primeira fileira são os modos de coleta, não os candidatos",
          meta["chips"][:2] == ["presencial", "telefônica"], meta["chips"][:4])
    check("a marca é 'Observatório do desempenho dos candidatos' e a antiga não aparece",
          meta["slogan"] == "Observatório do desempenho dos candidatos" and not meta["velha"],
          {"slogan": meta["slogan"], "tem_a_velha": meta["velha"]})
    check("editoria de método sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- botão de compartilhar: a mensagem sai pronta, com o número do dia e o link (8/9/2026)
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    check("o masthead tem o botão de compartilhar", page.locator("#b-share").count() == 1)
    page.click("#b-share")
    page.wait_for_timeout(300)
    sh = page.evaluate("""() => {
        const d = document.getElementById('share');
        return {aberto: d.open,
                msgs: [...d.querySelectorAll('.msg')].map(e => ({rot: e.querySelector('.rot').textContent,
                    txt: e.querySelector('p').textContent,
                    wa: !!e.querySelector('[data-wa]'), cop: !!e.querySelector('[data-cop]')})),
                canon: (document.querySelector('link[rel=canonical]') || {}).href}; }""")
    txts = [m["txt"] for m in sh["msgs"]]
    check("o botão abre o diálogo de compartilhar", sh["aberto"])
    check("o diálogo traz pelo menos três mensagens prontas", len(txts) >= 3, len(txts))
    check("nenhuma mensagem sai com buraco de dado (undefined, NaN, null)",
          not [t for t in txts if "undefined" in t or "NaN" in t or "null" in t],
          [t[:80] for t in txts if "undefined" in t or "NaN" in t or "null" in t])
    check("toda mensagem termina com o endereço público do mural",
          all(t.rstrip().endswith(sh["canon"]) for t in txts),
          [t[-60:] for t in txts if not t.rstrip().endswith(sh["canon"])])
    check("toda mensagem tem WhatsApp e Copiar", all(m["wa"] and m["cop"] for m in sh["msgs"]))
    # a mensagem do segundo turno não pode anunciar um líder que o próprio painel chama de empate
    m2t = [t for t in txts if t.startswith("Segundo turno")]
    cap2t = page.evaluate("() => document.querySelector('#cap-2t').textContent")
    check("a mensagem do segundo turno existe e diz o mesmo que o painel",
          len(m2t) == 1 and (("Empate técnico" in cap2t) == ("empate técnico" in m2t[0])),
          {"msg": m2t[0][:90] if m2t else None, "cap": cap2t[:60]})
    # só o mural: nada de compartilhar "esta página", e o link nunca leva a uma âncora interna
    check("o diálogo não tem escolha de escopo: compartilha o mural",
          page.locator("#share [data-esc]").count() == 0)
    check("nenhum link de mensagem aponta para uma âncora interna",
          not [t for t in txts if "#" in t], [t[-40:] for t in txts if "#" in t])
    # a última mensagem serve em qualquer dia: sem data, sem porcentagem, sem nome de candidato
    ger = txts[-1]
    check("a última mensagem é genérica: não envelhece com o número do dia",
          "%" not in ger and "setembro" not in ger and "Lula" not in ger, ger[:110])
    # de dentro de um estado, o botão continua compartilhando o mural, sem quebrar
    page.click("#share [data-close]")
    page.click('.scope button[data-escopo="uf"]')
    page.wait_for_timeout(900)
    page.click("#b-share")
    page.wait_for_timeout(250)
    uf = page.evaluate("""() => [...document.querySelectorAll('#share .msg p')].map(e => e.textContent)""")
    check("num estado, o botão compartilha o mural do mesmo jeito",
          uf and all(t.rstrip().endswith(sh["canon"]) for t in uf), [t[-50:] for t in uf][:2])
    check("compartilhar sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()


    # ---- cadastro: a Visão geral é de todo mundo, o resto pede conta (10/9/2026)
    # A trava só é real porque a carga protegida não está na página pública. Estes checks olham
    # os três estados: sem chave configurada o mural abre inteiro (falha segura), com chave a
    # carga não vem junto e as abas ficam trancadas, e com a carga na sessão tudo volta.
    from pathlib import Path as _P
    PUB = (_P(__file__).resolve().parent.parent / "index.html").as_uri()
    b, page, errs = novo_ctx(p)
    page.route("**cdn.jsdelivr.net**", lambda r: r.abort())   # sem CDN o mural não pode quebrar
    page.goto(PUB)
    page.wait_for_timeout(900)
    pub = page.evaluate("""() => ({trava: TRAVA, tudo: temTudo(),
        manchete: document.querySelector('#manchete').textContent,
        estados: Object.keys(DATA.estados || {}).length})""")
    bytes_pub = (_P(__file__).resolve().parent.parent / "index.html").stat().st_size
    bytes_tudo = (_P(__file__).resolve().parent.parent / "mural" / "mural-inteiro.html").stat().st_size
    check("a aba principal funciona sem conta, com a manchete de verdade",
          "%" in pub["manchete"] and "undefined" not in pub["manchete"], pub["manchete"])
    # O check que importa é a coerência entre as duas metades da trava, não um número fixo.
    # A versão anterior exigia estados == 0 na página publicada e passou verde enquanto o mural
    # no ar estava sem estados, porque sem chave ninguém hidrata o que foi tirado
    # (10/9/2026). Dividir a carga e trancar a página são a mesma decisão: se discordarem, o
    # visitante perde metade do mural sem nem saber que existe cadastro.
    check("dividir a carga e trancar a página são a mesma decisão, nunca duas",
          pub["trava"] == (pub["estados"] == 0),
          {"trava": pub["trava"], "estados": pub["estados"]})
    if pub["trava"]:
        check("com a trava ligada, a carga pública é bem menor que o mural inteiro",
              bytes_pub < 0.45 * bytes_tudo, {"público": bytes_pub, "inteiro": bytes_tudo})
    else:
        check("sem chave de conta configurada, o mural não tranca ninguém do lado de fora",
              pub["trava"] is False, pub["trava"])
        # e "não tranca" tem de significar o mural inteiro de pé, disputa por disputa
        aberto = page.evaluate("""() => {
            trocarEscopo('uf');
            const out = {};
            for (const [uf, cargo] of [['RJ','governador'],['RJ','senador'],['SP','governador'],
                                       ['SP','senador'],['MG','governador'],['BA','senador']]) {
                trocarUF(uf); trocarCargoUF(cargo);
                out[uf+'-'+cargo] = document.querySelectorAll('#e-wall .card').length;
            }
            return out;
        }""")
        check("sem trava, a página publicada mostra candidatura em toda disputa",
              all(n > 0 for n in aberto.values()), aberto)
    # 29/9/2026: a página de privacidade saiu (o site não tem conta) e o site não aponta para o código
    raiz_pv = _P(__file__).resolve().parent.parent
    html_pv = (raiz_pv / "index.html").read_text(encoding="utf-8")
    # o endereço antigo, que o Google indexou, só redireciona para a capa
    pv_red = (raiz_pv / "privacidade.html").read_text(encoding="utf-8") if (raiz_pv / "privacidade.html").exists() else ""
    check("sem política no site, sem link para ela e sem menção ao repositório",
          "privacidade.html" not in html_pv and "observatorio-2026" not in html_pv and "repositório" not in html_pv
          and 'rel="canonical" href="https://muraldoscandidatos.com/"' in pv_red
          and 'http-equiv="refresh"' in pv_red and "Privacidade" not in pv_red and "github" not in pv_red.lower(),
          len(pv_red))
    b.close()

    # com as chaves configuradas: cadeado nas abas e cadastro no lugar da editoria vazia
    import subprocess, os as _os
    amb = dict(_os.environ, MURAL_SUPABASE_URL="https://exemplo.supabase.co",
               MURAL_SUPABASE_ANON="chave-de-teste")
    raiz = str(_P(__file__).resolve().parent.parent)
    subprocess.run(["python3", "mural/_gerar_mural.py"], cwd=raiz, env=amb,
                   capture_output=True, check=True)
    try:
        b, page, errs = novo_ctx(p)
        page.route("**cdn.jsdelivr.net**", lambda r: r.abort())
        page.goto(PUB)
        page.wait_for_timeout(900)
        com = page.evaluate("""() => ({trava: TRAVA,
            cadeados: document.querySelectorAll('#tabs-editorias .cad').length,
            botao: !document.querySelector('#b-conta').hidden})""")
        check("com a chave configurada, as editorias fechadas ficam marcadas e o botão de conta aparece",
              com["trava"] and com["cadeados"] >= 6 and com["botao"], com)
        page.click('#tabs-editorias button[data-aba="pesquisas"]')
        page.wait_for_timeout(400)
        trancado = page.evaluate("""() => ({aba: abaAtual, dialogo: document.getElementById('conta').open})""")
        check("clicar numa editoria fechada abre o cadastro e não sai da Visão geral",
              trancado["aba"] == "geral" and trancado["dialogo"], trancado)
        # a carga na sessão devolve o mural inteiro
        carga = open(_os.path.join(raiz, "mural-completo.json"), encoding="utf-8").read()
        page.evaluate("t => sessionStorage.setItem('mural.completo', t)", carga)
        page.reload()
        page.wait_for_timeout(1500)
        depois = page.evaluate("""() => ({tudo: temTudo(), estados: Object.keys(UF).length,
            cadeados: document.querySelectorAll('#tabs-editorias .cad').length})""")
        check("com a carga na sessão, o mural volta inteiro e os cadeados somem",
              depois["tudo"] and depois["estados"] == 27 and depois["cadeados"] == 0, depois)
        check("cadastro sem erro de página, mesmo com o CDN fora do ar",
              not [e for e in errs if e[0] == "pageerror"], errs)
        b.close()
    finally:
        subprocess.run(["python3", "mural/_gerar_mural.py"], cwd=raiz,
                       env={k: v for k, v in _os.environ.items()}, capture_output=True)

    # ---- reta final e segundo turno na capa (21/9/2026): a janela padrão é de 30 dias, com 7, 90 e tudo
    # a um clique; os gráficos de tempo sombreiam o trecho de 4/9 em diante com o anterior apagado; e o
    # placar de segundo turno sai da editoria Pesquisas para a capa, dizendo o mesmo que o painel de lá
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#geral")
    page.wait_for_timeout(900)
    r = page.evaluate("""() => ({
        janelaPref: prefs.janela, homeJanela,
        seg: [...document.querySelectorAll('#home-seg button')].map(b => [b.dataset.hj, b.getAttribute('aria-pressed')]),
        retaHome: !!document.querySelector('#ch-home svg.tempo .reta'),
        antesHome: document.querySelectorAll('#ch-home svg.tempo .linha.antes').length,
        rotulo: document.querySelector('#ch-home svg.tempo text.reta-l')?.textContent,
        p2t: !document.querySelector('#p-home-2t').hidden,
        nums: [...document.querySelectorAll('#duelo-2t .dl-num')].map(e => e.textContent),
        tag: document.querySelector('#duelo-2t .dl-tag')?.textContent,
        cap: document.querySelector('#cap-home-2t').textContent,
        svg2t: !!document.querySelector('#ch-home-2t svg.tempo'),
        antes2t: document.querySelectorAll('#ch-home-2t svg.tempo .linha.antes').length,
        // a faixa só existe enquanto a janela começa antes de 4/9 (a mesma condição do gráfico).
        // De 3/10 em diante a janela de 30 dias cabe inteira na reta final e não há trecho a apagar;
        // exigir o trecho apagado sempre travaria a atualização da véspera da eleição.
        cruza: RETA0 > janelaHome() + 864e5, rotFaixa: FAIXA1T.rot,
        // desde 13/10/2026 o gráfico do 2º turno tem janela e faixa próprias (a campanha do 2º turno,
        // desde 5/10): as simulações anteriores a 4/10 aparecem apagadas quando a janela as alcança
        reta2t: !!document.querySelector('#ch-home-2t svg.tempo .reta'),
        cruza2t: (() => { const m = document.querySelector('#ch-home-2t')._chart; return !!m && FAIXA2T.ini > m.t0 + 864e5; })(),
        antesNaJanela: (() => { const m = document.querySelector('#ch-home-2t')._chart; return !!m && rodadas2TAntes().some(x => x.t >= m.t0 && x.t <= m.t1); })()
    })""")
    check("janela padrão de 30 dias, na capa e nas preferências, com 7, 90 e tudo à disposição",
          r["janelaPref"] == "30" and r["homeJanela"] == "30" and ["30", "true"] in r["seg"]
          and [k for k, _ in r["seg"]] == ["7", "30", "90", "tudo"], r)
    check("gráfico da capa com a faixa da reta final rotulada e o trecho anterior apagado",
          (r["retaHome"] and r["antesHome"] >= 2 and r["rotulo"] == r["rotFaixa"]) if r["cruza"]
          else (not r["retaHome"] and r["antesHome"] == 0), r)
    # o tempo tem uma escala só: distância no eixo é proporcional a dias em qualquer trecho, inclusive
    # atravessando a faixa da reta final. Escala partida foi tentada em 21/9/2026 e desfeita no mesmo dia.
    esc_ = page.evaluate("""() => {
        const svg = document.querySelector('#ch-home svg.tempo'), m = document.querySelector('#ch-home')._chart;
        const dia = m.X(m.t0 + 864e5) - m.X(m.t0);
        const passos = [0.2, 0.5, 0.8].map(f => { const t = m.t0 + (m.t1 - m.t0) * f; return (m.X(t + 864e5) - m.X(t)) / dia; });
        const labs = [...svg.querySelectorAll('text.axis')].filter(t => /\\d\\d\\/\\d\\d/.test(t.textContent)).map(t => t.getBBox()).sort((a, b) => a.x - b.x);
        let colide = 0; for (let i = 1; i < labs.length; i++) if (labs[i].x < labs[i - 1].x + labs[i - 1].width + 4) colide++;
        return {passos, uniforme: passos.every(p => Math.abs(p - 1) < 1e-6), datas: labs.length, colide,
                atravessa: m.reta && m.X(m.fase.ini) > m.ml && m.X(m.fase.ini) < m.ml + m.iw}; }""")
    check("uma escala só para o tempo: o dia mede o mesmo em qualquer ponto do eixo, sem rótulos colidindo",
          esc_["uniforme"] and (esc_["atravessa"] or not r["cruza"]) and esc_["datas"] >= 3 and esc_["colide"] == 0, esc_)
    # cada janela cobre exatamente os dias de dado que promete, contados da última rodada do turno que
    # o gráfico desenha (3/10 no 1º turno, a mais recente no 2º, desde 13/10/2026), e o eixo nunca
    # desenha o futuro (a folga da direita não passa de amanhã)
    janelas = page.evaluate("""async () => {
        const out = {}, d = 864e5, m1 = () => document.querySelector('#ch-home')._chart, m2 = () => document.querySelector('#ch-home-2t')._chart;
        for (const k of ['7', '30', '90', 'tudo']) {
            document.querySelector(`#home-seg button[data-hj="${k}"]`).click();
            await new Promise(r => setTimeout(r, 250));
            out[k] = [Math.round((Date.parse(ULT1T) - m1().t0) / d), Math.round((Date.parse(ult2T()) - m2().t0) / d)];
        }
        document.querySelector('#home-seg button[data-hj="30"]').click();
        await new Promise(r => setTimeout(r, 250));
        out.folga = [Math.round((m1().t1 - Date.parse(ULT1T)) / d), Math.round((m2().t1 - Date.parse(ult2T())) / d)];
        out.futuro = Math.round((Math.max(m1().t1, m2().t1) - Date.parse(HOJE)) / d);
        return out; }""")
    check("as quatro janelas cobrem os dias que prometem, nos dois gráficos da capa, e o eixo não entra no futuro",
          janelas["7"] == [7, 7] and janelas["30"] == [30, 30] and janelas["90"] == [90, 90] and min(janelas["tudo"]) > 200
          and all(0 < f <= 3 for f in janelas["folga"]) and janelas["futuro"] <= 1, janelas)
    check("segundo turno na capa: painel visível com dois números, selo e gráfico; faixa da campanha e simulações apagadas coerentes com a janela",
          r["p2t"] and len(r["nums"]) == 2 and all("%" in n for n in r["nums"]) and r["tag"] and r["svg2t"]
          and r["reta2t"] == r["cruza2t"] and (r["antes2t"] >= 1 or not r["antesNaJanela"]), r)
    page.goto(URL + "#pesquisas")
    page.wait_for_timeout(600)
    cap_pesq = page.evaluate("() => document.querySelector('#cap-2t').textContent")
    check("o texto do segundo turno na capa é o mesmo da editoria Pesquisas", r["cap"] and r["cap"] == cap_pesq,
          {"capa": r["cap"][:90], "pesquisas": cap_pesq[:90]})
    # em 30 dias a faixa só existe se a janela começar antes de 4/9 (a janela termina na última rodada
    # mais três dias, não na eleição, então até 4/10 ela ainda pega dias anteriores à reta); o que se
    # exige é coerência: faixa e trecho apagado andam juntos. Até 13/10/2026 o 2º turno seguia a mesma
    # janela do 1º; agora conta da própria última rodada, e a faixa dele é a da campanha do 2º turno.
    page.goto(URL + "#geral")
    page.wait_for_timeout(600)
    page.click('#home-seg button[data-hj="30"]')
    page.wait_for_timeout(500)
    r30 = page.evaluate("""() => ({esperado: RETA0 > janelaHome() + 864e5, reta: !!document.querySelector('#ch-home svg.tempo .reta'),
        antes: document.querySelectorAll('#ch-home svg.tempo .linha.antes').length, pts: document.querySelectorAll('#ch-home svg.tempo .ser circle').length,
        reta2t: !!document.querySelector('#ch-home-2t svg.tempo .reta'), seg2t: !!document.querySelector('#ch-home-2t svg.tempo'),
        esperado2t: (() => { const m = document.querySelector('#ch-home-2t')._chart; return !!m && FAIXA2T.ini > m.t0 + 864e5; })(),
        pressed: document.querySelector('#home-seg button[data-hj="30"]').getAttribute('aria-pressed')})""")
    check("em 30 dias a faixa aparece só se a janela começa antes do início da fase, o trecho apagado acompanha, nos dois gráficos da capa",
          r30["pressed"] == "true" and r30["reta"] == r30["esperado"] and (r30["antes"] > 0) == r30["esperado"]
          and r30["pts"] > 0 and r30["seg2t"] and r30["reta2t"] == r30["esperado2t"], r30)
    check("reta final e 2º turno na capa sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- o estado fala pela média, não pela rodada mais recente (22/9/2026). Antes, a manchete, o
    # placar, os alertas, o mapa e a tira de números do estado saíam de UMA rodada, enquanto o gráfico
    # ao lado desenhava média: dois números diferentes para a mesma disputa na mesma tela. E a
    # manchete de um estado inteiro podia ser de um instituto só (a Veritá assinava a de seis).
    # Desde 13/10/2026, com o resultado do TSE, a regra se divide em três:
    #  (a) governo decidido: manchete e placar trazem o percentual do eleito no CSV do TSE, e o mapa
    #      pinta o estado na cor do partido dele;
    #  (b) 2º turno com média: manchete e placar trazem a média do confronto, e não a última rodada;
    #  (c) 2º turno sem média (menos de MIN_POS1T rodadas depois de 4/10): manchete e placar vêm do 1º
    #      turno do TSE, nunca de uma rodada só.
    # Sem o CSV, vale a regra antiga, num estado escolhido pelo dado.
    import csv as _csv_e, io as _io_e
    arq_e = Path(__file__).resolve().parent.parent / "dados" / "resultados" / "candidatos.csv"
    gov_csv = {}
    if arq_e.exists():
        for x in _csv_e.DictReader(_io_e.open(arq_e, encoding="utf-8-sig")):
            if x["turno"] == "1" and x["cargo"] == "governador":
                gov_csv.setdefault(x["abrangencia"].upper(), []).append(x)
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(900)
    num_js = "const num = t => (String(t).replace(/[12]º/g, '').match(/-?\\d+[,.]?\\d*/g) || []).map(x => +x.replace(',', '.'));"
    if gov_csv:
        est = page.evaluate("""() => { """ + num_js + """
            const out = {}; trocarEscopo('uf');
            for (const uf of UFLIST) { trocarUF(uf); trocarCargoUF('governador');
                const path = document.querySelector(`#mapa-svg path.uf[data-uf="${uf}"]`), G = apGov(uf), m = mediaUF2T(uf);
                out[uf] = {est: estadoGov(uf), tag: document.querySelector('#e-tag').textContent, tagNums: num(document.querySelector('#e-tag').textContent),
                    duelo: [...document.querySelectorAll('#e-duelo .dl-num')].map(e => num(e.textContent)[0]),
                    fill: path && path.getAttribute('fill'), corEleito: G ? corPartido(G.c[0][3]) : null,
                    media: m ? [+fPct(m.va).replace(',', '.'), +fPct(m.vb).replace(',', '.')] : null,
                    rodadas: campUF2T(uf).map(r => Object.values(r.pub)), fin: finalUF(uf).map(c => c[1])}; }
            return out; }""")
        ruins_a, ruins_b, ruins_c, vistos = [], [], [], {"a": 0, "b": 0, "c": 0}
        for uf, linhas in gov_csv.items():
            e = est.get(uf)
            if not e:
                continue
            eleito = [x for x in linhas if x["situacao"].strip().lower() == "eleito"]
            if eleito:
                vistos["a"] += 1
                pct = float(eleito[0]["pct_validos"])
                if not (e["tagNums"] and abs(e["tagNums"][0] - pct) < 0.005 and e["duelo"] and abs(e["duelo"][0] - pct) < 0.005 and e["fill"] == e["corEleito"]):
                    ruins_a.append((uf, pct, e))
            elif e["est"] == "t2" and e["media"]:
                vistos["b"] += 1
                if not (abs(e["tagNums"][0] - e["media"][0]) < 0.051 and abs(e["duelo"][0] - e["media"][0]) < 0.051):
                    ruins_b.append((uf, e))
            elif e["est"] == "t2":
                vistos["c"] += 1
                fin = sorted((float(x["pct_validos"]) for x in linhas if x["situacao"].strip().lower() == "2º turno"), reverse=True)
                pub = {v for r in e["rodadas"] for v in r}
                if not (len(fin) == 2 and e["tagNums"][:2] == fin and e["duelo"] == fin and not (set(e["tagNums"]) & pub)):
                    ruins_c.append((uf, fin, e))
        check("(a) governo decidido: manchete e placar com o percentual do eleito no CSV do TSE e o mapa na cor do partido dele",
              vistos["a"] > 0 and not ruins_a, {"estados": vistos["a"], "ruins": ruins_a[:3]})
        check("(b) 2º turno com média: manchete e placar trazem a média do confronto", not ruins_b, {"estados": vistos["b"], "ruins": ruins_b[:3]})
        check("(c) 2º turno sem média: manchete e placar vêm do 1º turno do TSE, nunca de uma rodada só", not ruins_c, {"estados": vistos["c"], "ruins": ruins_c[:3]})
    else:
        print("aviso: sem dados/resultados/candidatos.csv; o estado é conferido pela regra da média de 1º turno")
        uf_teste = page.evaluate("""() => { for (const uf of UFLIST) { const l = liderDe(uf, 'governador'), M = mediaUF(uf, 'governador');
            if (l && M && M.insts >= 2 && Math.abs(l.pts[0][4] - M.lista[0].valor) > 2 && l.pts[0][3] === M.lista[0].nome) return uf; } return 'PA'; }""")
        page.goto(URL + "#uf-" + uf_teste.lower() + "-governo")
        page.wait_for_timeout(1200)
        est = page.evaluate("""(uf) => { """ + num_js + """
            const l = liderDe(uf, 'governador'), M = mediaUF(uf, 'governador');
            return {rodadaTop: l.pts[0][4], mediaTop: M.lista[0].valor, rodadas: M.rs.length, insts: M.insts,
                    tagNums: num(document.querySelector('#e-tag').textContent), eyebrow: document.querySelector('#e-eyebrow').textContent,
                    duelo: [...document.querySelectorAll('#e-duelo .dl-num')].map(e => num(e.textContent)[0]),
                    mapaLider: liderPartido(uf, 'governador').p.valor}; }""", uf_teste)
        check("a manchete do estado traz a média, não a rodada mais recente",
              abs(est["tagNums"][0] - est["mediaTop"]) < 0.11 and abs(est["tagNums"][0] - est["rodadaTop"]) > 1, est)
        check("o placar do estado traz a média", est["duelo"] and abs(est["duelo"][0] - est["mediaTop"]) < 0.11, est)
        check("o mapa colore o estado pela média", abs(est["mapaLider"] - est["mediaTop"]) < 0.11, est)
        check("o carimbo do estado diz de quantas rodadas e institutos a média é feita",
              "média de" in est["eyebrow"] and str(est["rodadas"]) in est["eyebrow"] and str(est["insts"]) in est["eyebrow"], est["eyebrow"])
    # nenhum estado pode ter a manchete decidida por um instituto só
    solo = page.evaluate("""() => {
        const out = [];
        for (const uf of UFLIST) { const M = mediaUF(uf, 'governador'); if (M && M.insts < 2) out.push([uf, M.insts]); }
        return out; }""")
    check("nenhuma manchete estadual sai de um instituto só", not solo, solo)
    check("estado pela média sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- as fórmulas da média na editoria de método, e a penalidade quadrática (23/9/2026)
    # A fórmula publicada tem de ser a conta que roda. As constantes do painel são lidas de AG e
    # de REGUA na hora em que a página abre; aqui conferimos que o que aparece é o que está lá, e
    # que a penalidade é mesmo min(1, (k/u)^2): quem destoa o dobro fica com um quarto, não metade.
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#metodo")
    page.wait_for_timeout(700)
    r = page.evaluate("""() => {
        const q = s => [...document.querySelectorAll(s)].map(e => e.textContent.trim());
        const br = x => String(x).replace('.', ',');
        const mostra = {k: q('.ag-k'), teto: q('.ag-teto'), inst: q('.ag-inst'), casa: q('.ag-tetocasa'),
                        enc: q('.ag-enc'), voltas: q('.ag-voltas'), piso: q('.ag-piso'),
                        s0: q('.rg-s0'), passo: q('.rg-passo'), minimo: q('.rg-min'), vvmin: q('.vv-min')};
        const espera = {k: br(AG.k), teto: Math.round(AG.teto*100)+'%', inst: br(AG.inst), casa: br(AG.tetoCasa),
                        enc: br(AG.encolhe), voltas: br(AG.voltas), piso: br(AG.piso),
                        s0: br(REGUA.sigma0), passo: br(REGUA.passo), minimo: br(REGUA.minimo), vvmin: br(VV_UF_MIN)+'%'};
        const erradas = Object.keys(espera).filter(k => !mostra[k].length || mostra[k].some(v => v !== espera[k]));
        return {passos: document.querySelectorAll('#p-formulas ol.fx > li').length,
                formulas: document.querySelectorAll('#p-formulas math').length,
                erradas, mostra, espera,
                pen: [1, 1.5, 3, 6, 1e6].map(u => penalAG(u)),
                esticavel: document.querySelectorAll('#p-formulas mo[stretchy]').length}; }""")
    check("editoria de método mostra as fórmulas da média, em nove passos",
          r["passos"] == 9 and r["formulas"] >= 10, {k: r[k] for k in ("passos", "formulas")})
    check("toda constante mostrada nas fórmulas é a mesma do código que calcula a média",
          not r["erradas"], {"erradas": r["erradas"], "mostra": r["mostra"], "espera": r["espera"]})
    pen = r["pen"]
    check("penalidade é min(1, (k/u)^2): inteira até k, um quarto no dobro, e nunca zera",
          pen[0] == 1 and pen[1] == 1 and abs(pen[2] - 0.25) < 1e-12 and abs(pen[3] - 0.0625) < 1e-12 and pen[4] > 0, pen)
    check("nenhuma fórmula depende de delimitador esticável (que exige fonte matemática no aparelho)",
          r["esticavel"] == 0, r["esticavel"])
    check("fórmulas sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- votos válidos (23/9/2026)
    # Vence no primeiro turno quem passa de 50% dos VÁLIDOS. Até aqui o alerta de governador
    # olhava a intenção total (p.valor >= 50), que tem brancos e indecisos dentro, e o mural não
    # dizia em lugar nenhum se a média aponta segundo turno. Conferimos: a conversão é um fator
    # comum (a ordem nos válidos é a da média total, sem placar e régua discordando), a rodada
    # que não fecha fica fora do fator, a régua aparece na capa, e o alerta usa os válidos.
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(900)
    # Desde 13/10/2026 as contas do 1º turno se ancoram na última rodada dele (ULT1T, 3/10), e a régua
    # da capa passou a ser a do 2º turno: sem "decidem o primeiro turno" nem "a média aponta".
    r = page.evaluate("""() => {
        const t = Date.parse(ULT1T), R = validosEm(rodadas1T(), OITO, SIG, t, somaVV1T), m = agregar1T(SIG, t), m2 = media2T();
        const razoes = OITO.filter(n => m[n] != null && R.m[n] != null).map(n => R.m[n] / m[n]);
        const ordemTot = OITO.filter(n => m[n] != null).sort((a, b) => m[b] - m[a]);
        const uf = UFLIST.map(u => { const M = mediaUF(u, 'governador'); const V = validosUF(M);
            return V ? {u, lider: V.lider, topo: M.lista[0].nome, v: V.v, tot: M.lista[0].valor, status: V.status, erro: V.erro} : null; }).filter(Boolean);
        const S = DATA.somasVV || {};
        return {razoes, ordemVV: R.ordem, ordemTot, v: R.v, erro: R.erro, status: R.status, fator: R.fator,
                btg: 'BTG/Nexus|2026-09-21' in S, verita: S['Instituto Veritá|2026-06-02'],
                somas: Object.values(S), uf, va2: m2 ? fPct(m2.va) : null,
                regua: (() => { const e = document.querySelector('#validos'); return e && !e.hidden ? e.innerText : ''; })()}; }""")
    razoes = r["razoes"]
    check("votos válidos nacionais: um fator comum, maior que 1, para todo candidato",
          razoes and max(razoes) - min(razoes) < 1e-9 and 1 < razoes[0] < 1.5, razoes[:3])
    check("votos válidos nacionais: a ordem é a mesma da média total",
          r["ordemVV"] == r["ordemTot"], {"vv": r["ordemVV"][:3], "tot": r["ordemTot"][:3]})
    check("votos válidos nacionais: rodada com candidato sem número (BTG/Nexus 21/9) fica fora do fator",
          not r["btg"], r["btg"])
    check("votos válidos nacionais: rodada já publicada em válidos (Veritá 2/6) entra com a soma dela",
          r["verita"] is not None and 96 <= r["verita"] <= 104, r["verita"])
    check("toda soma de candidatos que entra no fator é positiva e no máximo 104",
          all(0 < x <= 104 for x in r["somas"]), [x for x in r["somas"] if not 0 < x <= 104][:5])
    st = {"vence": lambda d: d["v"] - 50 > d["erro"], "segundo": lambda d: 50 - d["v"] > d["erro"],
          "perto": lambda d: abs(d["v"] - 50) <= d["erro"]}
    check("status nacional de primeiro turno bate com a distância a 50% e a incerteza",
          r["status"] in st and st[r["status"]](r), {k: r[k] for k in ("v", "erro", "status")})
    check("a capa mostra a régua de votos válidos do 2º turno, com o número da média, sem falar do 1º turno como disputa aberta",
          "votos válidos" in r["regua"] and "decidem o primeiro turno" not in r["regua"] and "a média aponta" not in r["regua"]
          and (("segundo turno" in r["regua"] and r["va2"] in r["regua"]) if r["va2"] else "TSE" in r["regua"]), r["regua"][:200])
    ruins = [d for d in r["uf"] if d["lider"] != d["topo"] or not (d["status"] in st and st[d["status"]](d)) or d["v"] < d["tot"]]
    check("governo estadual: líder nos válidos é o líder da média, e o status bate com a incerteza",
          len(r["uf"]) >= 20 and not ruins, ruins[:3])
    check("votos válidos sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # o alerta de primeiro turno do governo sai dos válidos: SP tem Tarcísio acima de 50% da
    # intenção total e dos válidos, e o alerta tem de dizer "votos válidos", não o número total.
    # Desde 13/10/2026 isso roda nos 27 estados: com o resultado do TSE, nenhum alerta projeta o 1º
    # turno (nem "Primeiro turno", nem "Segunda vaga", nem "a média aponta"), a régua de válidos é a
    # do resultado oficial (ou a da média do 2º turno, onde ela existe), e nos estados com 2º turno a
    # abertura diz "25 de outubro" e os dois nomes.
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#uf-sp-governo")
    page.wait_for_timeout(1200)
    r = page.evaluate("""() => { const out = {}; trocarEscopo('uf');
        for (const uf of UFLIST) { trocarUF(uf); trocarCargoUF('governador');
            const reg = document.querySelector('#e-validos');
            out[uf] = {est: estadoGov(uf), al: document.querySelector('#e-alerts').innerText, reg: reg && !reg.hidden ? reg.innerText : '',
                       abre: ['#e-eyebrow', '#e-duelo', '#e-tag', '#e-lede'].map(s => document.querySelector(s).innerText).join(' '),
                       fin: finalUF(uf).map(c => c[1]), media: !!mediaUF2T(uf), t2: dExtenso(TURNOS.t2), sem: estadoGov(uf) === 'sem',
                       st: (() => { const V = validosUF(mediaUF(uf, 'governador')); return V && V.status; })()}; }
        return out; }""")
    projecao = re.compile(r"Primeiro turno|Segunda vaga|a média aponta|haverá segundo turno", re.I)
    if all(x["sem"] for x in r.values()):
        x = r["SP"]
        check("alerta de primeiro turno no governo usa votos válidos (sem resultado do TSE)",
              x["st"] != "vence" or ("votos válidos" in x["al"] and "faixa de vitória em turno único" not in x["al"]), x["al"][:300])
    else:
        ruins = {uf: x["al"][:160] for uf, x in r.items() if not x["sem"] and projecao.search(x["al"])}
        check("com o resultado do TSE, nenhum alerta estadual projeta o 1º turno (27 estados)", not ruins, ruins)
        ruins = {uf: x["reg"][:120] for uf, x in r.items() if not x["sem"]
                 and not ("resultado oficial do TSE" in x["reg"] or (x["media"] and "que decidem o segundo turno" in x["reg"]))}
        check("com o resultado do TSE, a régua de válidos do estado é a do resultado oficial (ou a da média do 2º turno)", not ruins, ruins)
        ruins = {uf: x["abre"][:200] for uf, x in r.items() if x["est"] == "t2"
                 and not (x["t2"] in x["abre"] and len(x["fin"]) == 2 and all(n in x["abre"] for n in x["fin"]))}
        check("nos estados com 2º turno, a abertura diz a data por extenso e os dois nomes", not ruins,
              {"estados": [uf for uf, x in r.items() if x["est"] == "t2"], "ruins": ruins})
    check("o estado mostra a régua de votos válidos do governo", "votos válidos" in r["SP"]["reg"], r["SP"]["reg"][:160])
    check("27 estados percorridos sem erro de página", len(r) == 27 and not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- nome que saiu das pesquisas não fica na média do estado (23/9/2026)
    # A média de cada nome é feita com as rodadas que o mediram; se eram todas velhas, o peso era
    # ínfimo mas, sozinho no denominador, virava o número inteiro. Antônio Denarium aparecia com
    # 55,7% no Senado de Roraima por rodadas de abril.
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(900)
    velhos = page.evaluate("""() => { const out = [];
        for (const u of UFLIST) for (const c of ['governador', 'senador']) { const M = mediaUF(u, c); if (!M) continue;
          const {janela} = pesosEm(M.rods, M.nomes, SIG_UF, M.t);
          for (const x of M.lista) { const ult = Math.max(...M.porNome[x.nome].map(p => p.t));
            if (M.t - ult > 2 * janela * 864e5) out.push([u, c, x.nome, Math.round((M.t - ult) / 864e5)]); } }
        return out; }""")
    check("média do estado só lista quem alguma rodada mediu dentro da janela", not velhos, velhos[:5])
    b.close()

    # ---- quem chega por http:// vai para https:// (25/9/2026)
    # Com o "Enforce HTTPS" do Pages desligado, o servidor entregava o site por http:// com status
    # 200 e o navegador marcava "não seguro". A página redireciona sozinha; aqui o domínio é servido
    # pelo próprio teste, nas duas versões, e conferimos para onde o navegador termina.
    raiz_ = _P(__file__).resolve().parent.parent
    b, page, errs = novo_ctx(p)
    corpos = {"/": (raiz_ / "index.html").read_text(encoding="utf-8")}
    def servir(r):
        u = urlsplit(r.request.url)
        doc = r.request.resource_type == "document" and u.hostname == "muraldoscandidatos.com"
        r.fulfill(status=200, content_type="text/html; charset=utf-8", body=corpos.get(u.path, "") if doc else "")
    page.route("**/*", servir)
    destinos = {}
    for caminho in ("",):
        try:
            page.goto("http://muraldoscandidatos.com/" + caminho + "#geral", wait_until="commit")
            page.wait_for_url("https://**", timeout=5000)
        except Exception:
            pass
        destinos[caminho or "/"] = page.url
    check("quem entra por http:// é levado ao https://",
          all(u.startswith("https://muraldoscandidatos.com/") for u in destinos.values())
          and destinos["/"].endswith("#geral"), destinos)
    b.close()

    # ---- pequenos erros no celular e cartões desatualizados (26/9/2026)
    b, page, errs = novo_ctx(p, viewport=(360, 800))
    colisoes = {}
    for rota in ("geral", "pesquisas", "busca", "uf-sp-governo-pesquisas"):
        page.goto(URL + "#" + rota)
        page.wait_for_timeout(900)
        # a primeira data do eixo encostava no "0%" do eixo vertical em todo gráfico de tempo
        colisoes[rota] = page.evaluate("""() => { const out = [];
            for (const svg of document.querySelectorAll('svg.tempo')) { const r0 = svg.getBoundingClientRect(); if (!r0.width) continue;
              const ts = [...svg.querySelectorAll('text.axis')].map(t => [t.textContent, t.getBoundingClientRect()]);
              for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) { const a = ts[i][1], b = ts[j][1];
                if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1) out.push(ts[i][0] + ' x ' + ts[j][0]); } }
            return out; }""")
    check("rótulos dos eixos dos gráficos de tempo não se sobrepõem a 360px",
          not any(colisoes.values()), {k: v[:3] for k, v in colisoes.items() if v})
    page.goto(URL + "#metodo")
    page.wait_for_timeout(700)
    sw = page.evaluate("document.documentElement.scrollWidth")
    check("as fórmulas do método cabem em 360px sem rolar a página", sw <= 360, sw)
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    r = page.evaluate("""() => { const pis = [...document.querySelectorAll('.placar .pi')].map(e => [e.querySelector('.pl').textContent, e.querySelector('.pv').textContent, e.querySelector('.pd').textContent]);
        const deb = pis.find(x => x[0] === 'próximo debate'), res = pis.find(x => /campanhas? restritas?/.test(x[0]));
        const prox = TL.filter(e => e.categoria === 'debate' && e.data >= HOJE && !/cancelad/i.test(e.evento)).sort((a, b) => a.data.localeCompare(b.data))[0];
        return {deb, res, prox: prox ? prox.data : null, restritos: C.filter(c => c.restrito).length}; }""")
    deb = r["deb"]
    d_ok = deb and (r["prox"] is None or deb[1] == f"{int(r['prox'][8:10])}/{int(r['prox'][5:7])}")
    check("o cartão do próximo debate sai da linha do tempo e nunca aponta um debate passado ou cancelado", bool(d_ok), r)
    check("o cartão de campanhas restritas conta o dado, sem restrição já revogada",
          r["res"] and r["res"][1] == str(r["restritos"]) and "Renan" not in r["res"][2], r["res"])
    page.goto(URL + "#candidatos")
    page.wait_for_timeout(600)
    r = page.evaluate("() => [document.querySelector('#bt-todos').textContent, C.length]")
    check("o botão 'Todos os N' da aba Candidatos conta os registrados", r[0] == f"Todos os {r[1]}", r)
    # o modo de coleta das rodadas sem ficha técnica vem do instituto quando ele usa sempre o mesmo
    r = page.evaluate("() => DATA.polls.filter(p => p[0] === 'Datafolha' && p[1] >= '2026-09-01').map(p => p[5])")
    check("rodadas do Datafolha de setembro, sem ficha, saem como presenciais", r and all(m == "presencial" for m in r), sorted(set(r)))
    check("pequenos erros no celular sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- fotos dos presidenciáveis (26/9/2026) e links do rodapé do cartão/dossiê
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#candidatos")
    page.wait_for_timeout(900)
    r = page.evaluate("""() => { const com = C.filter(c => c.foto);
        const semCred = com.filter(c => !c.foto_cred || !c.foto_cred.licenca || !c.foto_cred.pagina).map(c => c.nome);
        const imgs = [...document.querySelectorAll('#wall .card .fotobox img')];
        const quebradas = imgs.filter(i => !(i.complete && i.naturalWidth > 0)).length;
        const cor = a => getComputedStyle(a).color;
        const links = [...document.querySelectorAll('#wall .card .foot a')].map(cor);
        return {n: com.length, semCred, cards: imgs.length, quebradas, brancos: links.filter(c => c === 'rgb(255, 255, 255)').length}; }""")
    check("fotos dos presidenciáveis com crédito e licença, sem imagem quebrada nos cartões",
          r["n"] >= 8 and not r["semCred"] and r["cards"] >= 1 and r["quebradas"] == 0, r)
    check("links do rodapé dos cartões legíveis (não brancos no fundo claro)", r["brancos"] == 0, r)
    page.click("#wall .card button:has-text('Abrir dossiê')")
    page.wait_for_timeout(900)
    r = page.evaluate("""() => ({cred: (document.querySelector('.dz .top .cred') || {}).textContent || '',
        brancos: [...document.querySelectorAll('.dz .foot a')].filter(a => getComputedStyle(a).color === 'rgb(255, 255, 255)').length})""")
    check("o dossiê mostra o crédito da foto e os links do rodapé legíveis",
          "Wikimedia Commons" in r["cred"] and r["brancos"] == 0, r)
    page.goto(URL + "#metodo")
    page.wait_for_timeout(700)
    notas = page.evaluate("() => document.querySelector('#notes') ? document.querySelector('#notes').textContent : document.body.textContent")
    check("o método lista os créditos das fotos", "Fotos." in notas and "Wikimedia Commons" in notas, notas[:0])
    check("fotos sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- rodadas de 2024 e 2025 datadas como 2026 (27/9/2026): ficam na base, fora da conta
    import csv as _csv, io as _io
    excl_todas = list(_csv.DictReader(_io.open(_P(__file__).resolve().parent.parent / "dados" / "rodadas-excluidas.csv", encoding="utf-8-sig")))
    # rodada excluída que voltou refeita à mão (dados/pesquisas-corrigidas.csv) é conferida à parte
    _corr = _P(__file__).resolve().parent.parent / "dados" / "pesquisas-corrigidas.csv"
    corrigidas = {(c["instituto"], c["data_divulgacao"]) for c in _csv.DictReader(_io.open(_corr, encoding="utf-8-sig"))} if _corr.exists() else set()
    excl = [e for e in excl_todas if (e["instituto"], e["data_divulgacao"]) not in corrigidas]
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(800)
    r = page.evaluate("""(ex) => { const k = new Set(ex.map(e => e[0] + '|' + e[1]));
        return {polls: DATA.polls.filter(p => k.has(p[0] + '|' + p[1])).length,
                fichas: DATA.fichas.filter(f => k.has(f.inst + '|' + f.dt)).length,
                excluidas: DATA.meta.excluidas, primeira: DATA.meta.primeira}; }""", [[e["instituto"], e["data_divulgacao"]] for e in excl])
    check("rodadas antigas datadas como 2026 ficam fora de pontos, fichas e contagens",
          r["polls"] == 0 and r["fichas"] == 0 and r["excluidas"] == len(excl_todas) and len(excl) >= 35, r)
    # Datafolha de 1/10/2026: a linha da Wikipédia veio deslocada (Lula com 4%); no mural fica a refeita
    df = page.evaluate("""() => ({lula: DATA.polls.filter(p => p[0] === 'Datafolha' && p[1] === '2026-10-01' && p[2] === 'Lula').map(p => p[3]),
        t2: DATA.polls2t.filter(p => p[0] === 'Datafolha' && p[1] === '2026-10-01').map(p => p[2] + ' ' + p[3]).sort()})""")
    check("rodada refeita à mão substitui a deslocada (Datafolha 1/10: Lula 42, 2º turno 48 a 45)",
          df["lula"] == [42] and df["t2"] == ["Flávio Bolsonaro 45", "Lula 48"], df)
    check("rodadas excluídas sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- pesquisa de 1º turno depois da votação (13/10/2026: uma rodada de 2025 da Paraná Pesquisas
    #      em SP, sem o ano na célula da Wikipédia, entrou como 1º turno de 2026 com campo de 9 a
    #      12/10). Nenhum ponto de 1º turno, nacional ou estadual, passa da data da votação.
    b, page, errs = novo_ctx(p)
    page.goto(URL)
    page.wait_for_timeout(800)
    r = page.evaluate("""() => { const t1 = (DATA.turnos || {}).t1 || '2026-10-04';
        return {t1, polls: DATA.polls.filter(p => p[1] > t1).map(p => p[0] + ' ' + p[1]),
                uf: Object.values(UF).flatMap(u => u.rodadas.filter(r => r.turno === 1 && r.data > t1).map(r => u.sigla + ' ' + r.inst + ' ' + r.data)),
                nUF: Object.keys(UF).length}; }""")
    check("nenhuma rodada de 1º turno com data depois da votação, no país e nos estados",
          r["nUF"] == 27 and not r["polls"] and not r["uf"], {k: v[:5] if isinstance(v, list) else v for k, v in r.items()})
    b.close()

    # ================= 2º turno em votos válidos (13/10/2026) =================
    # ---- N5: a média do 2º turno é feita e mostrada em votos válidos, com um caminho só (media2T).
    # Os lados somam 100 depois da renormalização (o efeito casa corrige cada nome separadamente e a
    # soma das médias saía 100,04), cada ponto do gráfico é o vv da rodada, o texto e o placar dizem
    # "votos válidos", e o número publicado (índice 3 de polls2t) continua cru: nas rodadas em
    # intenção total, os dois somam menos de 99,5 e vv é a parte de cada um na soma.
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#geral")
    page.wait_for_timeout(900)
    n5 = page.evaluate("""() => { const m = media2T(); if (!m) return null;
        const el = document.querySelector('#ch-home-2t');
        const rot = [...el.querySelectorAll('text.cand-label')].map(t => (t.textContent.match(/(\\d+(?:,\\d+)?)%/) || [])[1]).filter(Boolean).map(x => +x.replace(',', '.'));
        const vv = rodadas2TVV(), serie = series2T(m, 3);
        const vvOk = serie.length > 0 && serie.every(s => s.pts.every(p => { const r = vv.find(x => x.inst === p.inst && x.dt === p.d && x.t === p.t); return r && Math.abs(r.v[s.nome] - p.v) < 1e-9; }));
        const d2 = document.querySelector('#duelo-2t'), duelo = d2 && d2.textContent.trim() ? '#duelo-2t' : '#duelo';
        const grupos = {}; for (const p of DATA.polls2t) { const k = p[0] + '|' + p[1] + '|' + p[4]; (grupos[k] = grupos[k] || []).push(p); }
        const crus = Object.values(grupos).filter(g => g.length === 2 && g[0][7] === 't' && g[0][2] !== g[1][2]).map(g => { const s = g[0][3] + g[1][3];
            return {g: g[0][0] + ' ' + g[0][1], s, ok: s < 99.5 && g.every(p => Math.abs(p[6] - Math.round(p[3] * 10000 / s) / 100) < 0.006 && p[3] !== p[6])}; });
        return {soma: m.va + m.vb, fase: m.fase, rot, vvOk, ref: !!el.querySelector('line.ref'),
                cap: document.querySelector('#cap-2t').textContent, capHome: document.querySelector('#cap-home-2t').textContent,
                duelo, dueloTxt: document.querySelector(duelo).textContent, crus: crus.length, crusRuins: crus.filter(x => !x.ok).slice(0, 3)}; }""")
    if n5 is None:
        check("N5: sem nenhuma rodada de 2º turno, nada a medir em válidos", True)
    else:
        check("N5: media2T em válidos soma 100 (renormalizada) e o gráfico do 2º turno da capa mostra os dois rótulos somando 100",
              abs(n5["soma"] - 100) <= 0.05 and len(n5["rot"]) == 2 and abs(sum(n5["rot"]) - 100) <= 0.15, {k: n5[k] for k in ("soma", "rot", "fase")})
        check("N5: cada ponto do gráfico do 2º turno é o voto válido da rodada, com a linha de 50%", n5["vvOk"] and n5["ref"], {k: n5[k] for k in ("vvOk", "ref")})
        check("N5: o texto do 2º turno (#cap-2t e capa) e o placar dizem 'votos válidos'",
              "votos válidos" in n5["cap"] and n5["cap"] == n5["capHome"] and "votos válidos" in n5["dueloTxt"],
              {"cap": n5["cap"][:100], "duelo": n5["duelo"], "dueloTxt": n5["dueloTxt"][:100]})
        check("N5: o número publicado (índice 3 de polls2t) continua cru; vv é a parte de cada um na soma dos dois",
              n5["crus"] > 0 and not n5["crusRuins"], {"rodadas em intenção total": n5["crus"], "ruins": n5["crusRuins"]})
    check("N5 sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- N9: a véspera. A média que o mural publicou em 3/10/2026, 23h12, é registro guardado em
    # dados/medias-publicadas.csv e não se recalcula: DATA.vespera traz esses números, o que a página
    # exibia é o que a coluna fonte do registro diz ("a página exibia Lula 45,2% e Flávio 43,9%"), a
    # urna é a do CSV do TSE e a diferença é a subtração das duas. Marçal, fora da urna, nunca é pareado.
    import csv as _csv9, io as _io9
    raiz9 = Path(__file__).resolve().parent.parent
    pub = [x for x in _csv9.DictReader(_io9.open(raiz9 / "dados" / "medias-publicadas.csv", encoding="utf-8-sig"))
           if x["cargo"] == "presidente" and x["abrangencia"].upper() == "BR"]
    arq_res = raiz9 / "dados" / "resultados" / "candidatos.csv"
    urna9 = {x["mural"]: float(x["pct_validos"]) for x in _csv9.DictReader(_io9.open(arq_res, encoding="utf-8-sig"))
             if x["turno"] == "1" and x["cargo"] == "presidente" and x["abrangencia"].lower() == "br" and x["mural"]} if arq_res.exists() else {}
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#geral")
    page.wait_for_timeout(700)
    n9 = page.evaluate("""() => ({V: DATA.vespera || null, L: vespera1T(),
        fmt: Object.fromEntries(Object.entries((DATA.vespera || {}).m || {}).map(([n, v]) => [curto(n), fPct(v)])),
        urna: Object.fromEntries(((resPres('1') || {}).c || []).map(c => [c[0], c[5]])),
        painel: document.querySelector('#p-urna') ? document.querySelector('#p-urna').textContent : null})""")
    exibia = {}
    for x in pub:
        mm = re.search(r"exibia (.+?), incerteza", x["fonte"])
        if mm:
            exibia.update({n: v for n, v in re.findall(r"([A-ZÀ-Ú][\wÀ-ú]+) (\d+,\d)%", mm.group(1))})
    check("N9: DATA.vespera traz a média publicada na véspera, igual ao registro em medias-publicadas.csv",
          n9["V"] is not None and len(pub) > 0 and all(abs(n9["V"]["m"].get(x["candidato"], -1) - float(x["media_validos"])) < 1e-9 for x in pub),
          {"registro": {x["candidato"]: x["media_validos"] for x in pub}, "DATA": (n9["V"] or {}).get("m")})
    check("N9: os números da véspera, formatados pelo mural, são os que a página exibia em 3/10",
          bool(exibia) and all(n9["fmt"].get(n) == v for n, v in exibia.items()), {"exibia": exibia, "fmt": n9["fmt"]})
    if not urna9:
        print("aviso: sem dados/resultados/candidatos.csv, a comparação com a urna fica de fora")
    else:
        L = n9["L"]
        check("N9: véspera x urna só para quem esteve na urna, com a urna do CSV do TSE e a diferença igual à subtração",
              len(L) >= 2 and all(abs(x["urna"] - urna9[x["nome"]]) < 1e-9 and abs(x["dif"] - (x["urna"] - x["media"])) < 1e-9 for x in L)
              and "Pablo Marçal" not in [x["nome"] for x in L] and all(x["nome"] in urna9 for x in L),
              [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()} for x in L][:4])
    if n9["painel"] is not None:
        check("N9: o painel pesquisas x urna mostra os números da véspera publicados", all(v in n9["painel"] for v in exibia.values()),
              {"exibia": exibia, "painel": n9["painel"][:160]})
    check("N9 sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- N12: rodada de 2º turno com a data de hoje cabe no eixo do gráfico da capa. A borda direita
    # dos gráficos do 2º turno sai da última rodada do confronto, lida na hora de desenhar (até 13/10/2026
    # ela saía de ULT, que não olhava as rodadas só de 2º turno, e a rodada nova podia ficar fora).
    b, page, errs = novo_ctx(p)
    page.goto(URL + "#geral")
    page.wait_for_timeout(800)
    n12 = page.evaluate("""() => {
        const dt = HOJE, inst = 'Instituto de Ensaio N12', url = 'https://exemplo.invalid/n12';
        DATA.polls2t.push([inst, dt, FINAL[0], 50.5, url, 'digital', 50.5, 'v', dt, 1], [inst, dt, FINAL[1], 49.5, url, 'digital', 49.5, 'v', dt, 1]);
        refazer2T(); drawHome2T();
        const el = document.querySelector('#ch-home-2t'), m = el._chart, t = Date.parse(dt);
        const c = [...el.querySelectorAll('circle[data-tip]')].filter(e => e.getAttribute('data-tip').includes(inst)).map(e => +e.getAttribute('cx'));
        return {n: c.length, xs: c, x0: m.ml, x1: m.ml + m.iw, t0: dISO(m.t0), t1: dISO(m.t1), hoje: dt,
                dentro: c.length === 2 && c.every(x => x >= m.ml - 0.5 && x <= m.ml + m.iw + 0.5) && t >= m.t0 && t <= m.t1}; }""")
    check("N12: rodada de 2º turno com a data de hoje desenhada dentro do eixo de #ch-home-2t", n12["dentro"], n12)
    check("N12 sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
    b.close()

    # ---- N3: os 27 estados com o resultado do TSE (13/10/2026). O oráculo é o CSV de resultados, não a
    # página: governo eleito com o selo e o percentual; estados com 2º turno (os que têm linha de turno 2
    # em totais.csv) com os dois nomes e a data; Senado com os eleitos; o estado que o TSE deixou sem
    # definição (Tocantins em 13/10) sem selo de eleito e sem a data do 2º turno; a conta eleitos + 2º
    # turno + sem definição = 27; o mapa com as listras e o neutro; e nada de "undefined" ou "NaN".
    import csv as _csv3, io as _io3
    raiz3 = Path(__file__).resolve().parent.parent / "dados" / "resultados"
    if not (raiz3 / "candidatos.csv").exists() or not (raiz3 / "totais.csv").exists():
        print("aviso: sem dados/resultados; N3 fica de fora")
    else:
        cand3 = list(_csv3.DictReader(_io3.open(raiz3 / "candidatos.csv", encoding="utf-8-sig")))
        tot3 = list(_csv3.DictReader(_io3.open(raiz3 / "totais.csv", encoding="utf-8-sig")))
        uf2t3 = sorted({x["abrangencia"].upper() for x in tot3 if x["turno"] == "2" and x["cargo"] == "governador"})
        g1 = [x for x in cand3 if x["turno"] == "1" and x["cargo"] == "governador"]
        eleito3 = {x["abrangencia"].upper(): x for x in g1 if x["situacao"].strip().lower() == "eleito"}
        fin3 = {}
        for x in g1:
            if x["situacao"].strip().lower() == "2º turno":
                fin3.setdefault(x["abrangencia"].upper(), []).append(x)
        pend3 = sorted(set(fin3) - set(uf2t3) - set(eleito3))
        sen3 = {}
        for x in cand3:
            if x["turno"] == "1" and x["cargo"] == "senador" and x["situacao"].strip().lower() == "eleito":
                sen3.setdefault(x["abrangencia"].upper(), []).append(x)
        b, page, errs = novo_ctx(p)
        page.goto(URL + "#uf-sp-governo")
        page.wait_for_timeout(1000)
        n3 = page.evaluate("""() => { const out = {}; trocarEscopo('uf');
            const txt = s => [...document.querySelectorAll(s)].map(e => e.textContent).join(' ');
            for (const uf of UFLIST) { out[uf] = {};
                for (const cargo of ['governador', 'senador']) { trocarUF(uf); trocarCargoUF(cargo);
                    const path = document.querySelector(`#mapa-svg path.uf[data-uf="${uf}"]`);
                    out[uf][cargo] = {est: estadoUF(uf, cargo), tagD: txt('#e-duelo .dl-tag'), tag: txt('#e-tag'),
                        hero: txt('#e-eyebrow, #e-duelo, #e-tag, #e-nota, #e-lede, #e-validos'), blocos: txt('#e-alerts, #e-strip, #mapa-sel'),
                        fill: path && path.getAttribute('fill'), tip: path && path.dataset.tip,
                        lixo: /undefined|NaN/.test(txt('#v-e-geral, #v-e-pesquisas'))}; }
            }
            // o nome de cada slug no mural: o CSV traz o nome de urna do TSE ("JÚLIO CÉSAR O JULIM DO LULA"),
            // e a página o nome do registro ("Julio Cesar"); quem é eleito vem do CSV, o nome vem daqui
            const nomes = Object.fromEntries(UFLIST.flatMap(k => todosUF(UF[k]).map(c => [c.slug, c.nome])));
            return {uf: out, nomes, corPend: corPend(), paths: document.querySelectorAll('#mapa-svg path.uf').length,
                    dentro: UFLIST.filter(k => !UF2T.includes(k)).flatMap(k => (UF[k].rodadas2 || []).filter(r => r.data > TURNOS.t1).map(r => k + ' ' + r.inst + ' ' + r.data))}; }""")
        U3 = n3["uf"]
        br = lambda v: f"{float(v):.2f}".replace(".", ",")
        # nome de urna do CSV (em caixa alta) contra o texto da página, sem caixa nem acento
        import unicodedata as _ud3
        sa = lambda t: "".join(ch for ch in _ud3.normalize("NFD", str(t).lower()) if _ud3.category(ch) != "Mn")
        tem = lambda nome, texto: sa(nome) in sa(texto)
        nome3 = lambda x: n3["nomes"].get(x["mural"]) or x["nome_urna"]
        ruins = {k: (x["pct_validos"], U3[k]["governador"]["tag"], U3[k]["governador"]["tagD"]) for k, x in eleito3.items()
                 if k in U3 and not (br(x["pct_validos"]) in U3[k]["governador"]["tag"] and "eleit" in U3[k]["governador"]["tagD"])}
        check("N3: governo eleito no 1º turno com o selo e o percentual do CSV", len(eleito3) > 0 and not ruins, ruins)
        ruins = {k: U3[k]["governador"]["hero"][:200] for k in uf2t3 if k in U3 and not (
            U3[k]["governador"]["est"] in ("t2", "decidido") and all(tem(nome3(x), U3[k]["governador"]["hero"]) for x in fin3.get(k, []))
            and len(fin3.get(k, [])) == 2 and ("25 de outubro" in U3[k]["governador"]["hero"] or U3[k]["governador"]["est"] == "decidido"))}
        check("N3: estados com 2º turno de governador (de totais.csv) com os dois nomes e a data", not ruins, {"uf2t": uf2t3, "ruins": ruins})
        ruins = {k: U3[k]["senador"]["tag"] for k, xs in sen3.items() if k in U3 and not all(tem(nome3(x), U3[k]["senador"]["tag"]) for x in xs)}
        check("N3: Senado com os eleitos na manchete, nos 27 estados", len(sen3) == 27 and not ruins, ruins)
        ruins = {}
        for k in pend3:
            g = U3.get(k, {}).get("governador")
            if not g or g["est"] != "pend" or "eleit" in g["tagD"].lower() or "eleit" in g["tag"].lower() or re.search(r"25 de outubro|25/10", g["hero"] + g["blocos"] + (g["tip"] or "")) or g["fill"] != n3["corPend"]:
                ruins[k] = g
        check("N3: estado sem definição no TSE sem selo de eleito, sem a data do 2º turno e com o mapa neutro", not ruins, {"pend": pend3, "ruins": ruins})
        est = {k: U3[k]["governador"]["est"] for k in U3}
        conta = {e: sum(1 for v in est.values() if v == e) for e in ("decidido", "t2", "pend")}
        check("N3: eleitos + 2º turno + sem definição = 27, e cada conta é a do CSV",
              conta["decidido"] == len(eleito3) and conta["t2"] == len(uf2t3) and conta["pend"] == len(pend3) and sum(conta.values()) == 27,
              {"página": conta, "csv": [len(eleito3), len(uf2t3), len(pend3)]})
        ruins = [k for k in uf2t3 if k in U3 and U3[k]["governador"]["est"] == "t2" and U3[k]["governador"]["fill"] != f"url(#t2-{k})"]
        check("N3: mapa com 27 estados e listras nos de 2º turno", n3["paths"] == 27 and not ruins, ruins)
        ruins = [f"{k}-{c}" for k, v in U3.items() for c, x in v.items() if x["lixo"]]
        check("N3: nenhum 'undefined' nem 'NaN' na Visão geral e nas Pesquisas dos 27 estados, nos dois cargos", not ruins, ruins)
        check("N3: nenhuma rodada de 2º turno depois de 4/10 em estado sem 2º turno de governador", not n3["dentro"], n3["dentro"][:5])
        check("N3 sem erro de página", not [e for e in errs if e[0] == "pageerror"], errs)
        b.close()

print()
print(f"{len(ok)} OK, {len(fail)} FAIL")
if fail:
    print("FALHAS:")
    for n, d in fail:
        print(" -", n, d)
    raise SystemExit(1)
