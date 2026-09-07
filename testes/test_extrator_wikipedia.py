# -*- coding: utf-8 -*-
"""Oráculo do extrator de texto compacto da Wikipédia (coleta/wikipedia_pesquisas_estados.py).

O coletor de navegador que gerou dados/estados/_wiki-pesquisas-estados.json em 02/09/2026 não foi
versionado; o que existe é o dump que ele produziu e, em testes/fixtures/wikipedia/, o HTML real
(action=parse&prop=text) das mesmas 27 revisões, além da revisão atual de cada página. Este teste
reconstrói o texto compacto a partir desse HTML e exige igualdade byte a byte com o dump, página
por página. Falha se qualquer uma das 27 divergir.

Também confere que o modo de produção (que descarta <style> e <script>) só difere do dump nos
fragmentos de CSS que vazavam para dentro das células, que dados/estados/_parse_wiki.py continua
reproduzindo pesquisas-estados-wiki.csv byte a byte, e que o caminho online do coletor (listagem,
revisões, reaproveitamento só de dump gravado pelo próprio script, erro próprio da página, erro
transitório da API mantendo o texto anterior, espera em 429 e maxlag, dump anterior corrompido,
gravação atômica) se comporta como descrito, usando respostas simuladas montadas com as mesmas
fixtures. Só biblioteca padrão; roda em poucos segundos e não toca em dados/.

Uso:
    python3 testes/test_extrator_wikipedia.py
"""
import gzip
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(RAIZ, "testes", "fixtures", "wikipedia")
# O oráculo é o dump que o navegador gerou em 02/09/2026, congelado aqui junto das fixtures do
# HTML das mesmas revisões. Não pode ser o arquivo de produção: a coleta automática regrava o dump
# a cada rodada, e o teste passaria a comparar revisões diferentes (falhava assim em 7/9/2026).
DUMP = os.path.join(RAIZ, "testes", "fixtures", "wikipedia", "dump-navegador-2026-09-02.json.gz")
# Também congelado: o CSV que _parse_wiki.py produzia do dump de 02/09. O de produção é
# reescrito a cada coleta e não serve de oráculo.
CSV_WIKI = os.path.join(RAIZ, "testes", "fixtures", "wikipedia", "pesquisas-estados-wiki-2026-09-02.csv.gz")
PARSE_WIKI = os.path.join(RAIZ, "dados", "estados", "_parse_wiki.py")
COLETOR = os.path.join(RAIZ, "coleta", "wikipedia_pesquisas_estados.py")

# o CSS de tooltip que o navegador deixava dentro das células e o extrator novo descarta
CSS_VAZADO = re.compile(r"\.mw-parser-output[^{]*\{[^}]*\}")


def abrir_dump(caminho):
    """Lê o dump congelado (.json.gz) ou um .json solto."""
    if caminho.endswith(".gz"):
        import gzip
        with gzip.open(caminho, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def carregar_coletor():
    spec = importlib.util.spec_from_file_location("wikipedia_pesquisas_estados", COLETOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ler_gz(nome):
    with gzip.open(os.path.join(FIXTURES, nome), "rt", encoding="utf-8") as f:
        return f.read()


def primeira_diferenca(esperado, obtido):
    a, b = esperado.split("\n"), obtido.split("\n")
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return "linha %d\n  dump:   %r\n  gerado: %r" % (i + 1, x[:200], y[:200])
    return "número de linhas: dump %d, gerado %d" % (len(a), len(b))


def resposta_http(corpo, cabecalhos=None):
    """Objeto que imita o retorno de urlopen: gerenciador de contexto com read() e headers."""
    r = mock.MagicMock()
    r.__enter__.return_value = r
    r.read.return_value = json.dumps(corpo).encode("utf-8")
    r.headers = cabecalhos or {}
    return r


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = carregar_coletor()
        with open(os.path.join(FIXTURES, "indice.json"), encoding="utf-8") as f:
            cls.indice = json.load(f)["estaduais"]
        cls.dump = abrir_dump(DUMP)
        cls.paginas = cls.dump["paginas"]

    def dump_do_script(self):
        """O que o script grava a partir do dump do navegador: mesmas páginas sem o CSS vazado, mais revisoes."""
        return {"coletado": self.dump["coletado"], "fonte": self.dump["fonte"],
                "paginas": {t: CSS_VAZADO.sub("", x) for t, x in self.paginas.items()},
                "revisoes": {t: {"pageid": None, "revid": self.indice[t]["revid_dump"]} for t in self.paginas}}


class OraculoTextoCompacto(Base):
    def test_fixtures_cobrem_o_dump(self):
        self.assertEqual(len(self.paginas), 27)
        self.assertEqual(set(self.paginas), set(self.indice))
        for titulo, e in self.indice.items():
            self.assertEqual(self.mod.revid_do_texto(self.paginas[titulo]), e["revid_dump"], titulo)

    def test_27_paginas_byte_a_byte(self):
        """Modo fiel ao navegador (manter_style=True): igualdade exata com o dump de 02/09."""
        falhas = []
        for titulo, esperado in self.paginas.items():
            e = self.indice[titulo]
            obtido = self.mod.texto_compacto(ler_gz(e["arquivo_dump"]), titulo, e["revid_dump"], manter_style=True)
            if obtido != esperado:
                falhas.append("%s: %s" % (titulo, primeira_diferenca(esperado, obtido)))
        self.assertEqual(falhas, [], "\n".join(falhas))

    def test_modo_producao_so_remove_css_vazado(self):
        """Sem <style>, o texto só difere do dump nos fragmentos '.mw-parser-output ...{...}'."""
        falhas = []
        com_css = 0
        for titulo, esperado in self.paginas.items():
            e = self.indice[titulo]
            obtido = self.mod.texto_compacto(ler_gz(e["arquivo_dump"]), titulo, e["revid_dump"])
            if CSS_VAZADO.search(esperado):
                com_css += 1
            if obtido != CSS_VAZADO.sub("", esperado):
                falhas.append("%s: %s" % (titulo, primeira_diferenca(CSS_VAZADO.sub("", esperado), obtido)))
            self.assertIsNone(CSS_VAZADO.search(obtido), titulo)
        self.assertEqual(falhas, [], "\n".join(falhas))
        self.assertEqual(com_css, 17, "o dump de 02/09 tem CSS vazado em 17 páginas")

    def test_revisao_atual_parseia_as_27(self):
        for titulo, e in self.indice.items():
            txt = self.mod.texto_compacto(ler_gz(e["arquivo_atual"]), titulo, e["revid_atual"])
            linhas = txt.split("\n")
            self.assertEqual(linhas[0], "@@PAGE %s revid=%s" % (titulo, e["revid_atual"]))
            self.assertTrue(any(l.startswith("## ") for l in linhas), titulo)
            self.assertIsNone(re.search(r"\[\d+\]", txt), titulo + ": referência [n] no texto")
            self.assertIsNone(CSS_VAZADO.search(txt), titulo)
            self.assertNotIn("\xa0", txt, titulo)

    def test_regras_do_extrator_em_html_minimo(self):
        html = (
            '<div class="mw-parser-output"><h2>Governador</h2><h3>2026</h3><h5>Agosto</h5>'
            '<table class="wikitable sortable"><caption> Legenda\n</caption><tbody>'
            '<tr><th rowspan="2">Instituto<sup class="reference"><a>[1]</a></sup></th><th colspan="2">Datas</th>'
            '<th><style>.x{color:red}</style>Cen.</th></tr>'
            '<tr><th><a>Fulano</a><br /><small>PL</small></th><th></th><td> </td></tr>'
            '<tr><td rowspan="2">Quaest</td><td>1\xa0a\n3 de agosto</td><td>1&#160;500</td><td>1</td></tr>'
            '</tbody></table>'
            '<h4>Julho</h4><table class="wikitable"><tr><td>x</td></tr></table>'
            '<table class="navbox"><tr><td>fora</td></tr></table></div>'
        )
        txt = self.mod.texto_compacto(html, "Página", 7)
        self.assertEqual(txt.split("\n"), [
            "@@PAGE Página revid=7",
            "## Governador > 2026 > Agosto",
            "CAP Legenda",
            "H:Instituto | H:Datas | H:Datas | H:Cen.",
            "H:Instituto | H:FulanoPL | H: | ",
            "Quaest | 1 a 3 de agosto | 1 500 | 1",
            "Quaest",
            "## Governador > 2026 > Julho",
            "x",
        ])
        self.assertIn("H:.x{color:red}Cen.", self.mod.texto_compacto(html, "Página", 7, manter_style=True))


class ParseWiki(Base):
    def test_parse_wiki_reproduz_o_csv_byte_a_byte(self):
        import gzip
        with tempfile.TemporaryDirectory() as d:
            entrada = os.path.join(d, "_wiki-pesquisas-estados.json")
            with open(entrada, "w", encoding="utf-8") as f:
                json.dump(abrir_dump(DUMP), f, ensure_ascii=False)
            saida = os.path.join(d, "pesquisas-estados-wiki.csv")
            r = subprocess.run([sys.executable, PARSE_WIKI, entrada, saida], capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(saida, "rb") as f:
                gerado = f.read()
        with gzip.open(CSV_WIKI, "rb") as f:
            esperado = f.read()
        self.assertTrue(gerado.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n", gerado[:200])
        self.assertEqual(gerado, esperado, "_parse_wiki.py não reproduz mais pesquisas-estados-wiki.csv")

    def test_parse_wiki_sem_argumentos_usa_caminhos_relativos(self):
        with open(PARSE_WIKI, encoding="utf-8") as f:
            fonte = f.read()
        self.assertNotIn("/home/claude", fonte)
        self.assertIn("os.path.dirname(os.path.abspath(__file__))", fonte)


class ModoFixtures(Base):
    def test_cli_grava_dump_no_formato_do_navegador(self):
        with tempfile.TemporaryDirectory() as d:
            saida = os.path.join(d, "wiki.json")
            r = subprocess.run([sys.executable, COLETOR, "--fixtures", FIXTURES, "--revisao", "dump", "--saida", saida],
                               capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(saida, "rb") as f:
                bruto = f.read()
        self.assertNotIn(b"\n", bruto, "o dump é JSON de uma linha")
        j = json.loads(bruto.decode("utf-8"))
        self.assertEqual(list(j)[:3], ["coletado", "fonte", "paginas"])
        self.assertEqual(j["fonte"], self.dump["fonte"])
        self.assertRegex(j["coletado"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-03:00$")
        self.assertEqual(list(j["paginas"]), list(self.paginas), "ordem das páginas é a do dump anterior")
        for titulo, texto in self.paginas.items():
            self.assertEqual(j["paginas"][titulo], CSS_VAZADO.sub("", texto), titulo)
            self.assertEqual(j["revisoes"][titulo]["revid"], self.indice[titulo]["revid_dump"])

    def test_cli_anterior_corrompido_aborta_sem_gravar(self):
        with tempfile.TemporaryDirectory() as d:
            ruim = os.path.join(d, "ruim.json")
            with open(ruim, "w", encoding="utf-8") as f:
                f.write('{"coletado": "x", "paginas": {')
            saida = os.path.join(d, "wiki.json")
            r = subprocess.run([sys.executable, COLETOR, "--fixtures", FIXTURES, "--revisao", "dump", "--saida", saida, "--anterior", ruim],
                               capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("dump anterior ilegível", r.stdout)
            self.assertNotIn("Traceback", r.stderr)
            self.assertFalse(os.path.exists(saida), "nada gravado")
            self.assertEqual(sorted(os.listdir(d)), ["ruim.json"], "nenhum .tmp sobrando")

    def test_cli_anterior_vazio_coleta_sem_dump_e_nao_deixa_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            saida = os.path.join(d, "wiki.json")
            r = subprocess.run([sys.executable, COLETOR, "--fixtures", FIXTURES, "--revisao", "atual", "--saida", saida, "--anterior", ""],
                               capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("dump anterior: nenhum", r.stdout)
            self.assertEqual(os.listdir(d), ["wiki.json"], "o .tmp foi trocado pelo arquivo final")
            with open(saida, encoding="utf-8") as f:
                j = json.load(f)
            self.assertEqual(len(j["paginas"]), 27)
            self.assertEqual(list(j["paginas"]), list(self.indice), "sem dump anterior, a ordem é a da listagem")

    def test_ler_dump_sem_paginas_e_invalido(self):
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "x.json")
            with open(arq, "w", encoding="utf-8") as f:
                f.write('{"coletado": "x"}')
            with self.assertRaises(self.mod.DumpInvalido):
                self.mod.ler_dump(arq)
        self.assertIsNone(self.mod.ler_dump(""))
        self.assertIsNone(self.mod.ler_dump(os.path.join(d, "nao-existe.json")))


class Simulada:
    """Respostas da MediaWiki API montadas a partir das fixtures, para exercitar o caminho online sem rede."""

    def __init__(self, indice, falhar_parse=(), redirecionar=None, extra_prefixsearch=()):
        self.indice = indice
        self.falhar_parse = set(falhar_parse)
        self.redirecionar = redirecionar or {}
        self.extra = list(extra_prefixsearch)
        self.chamadas = []
        self.pageids = {t: 7000000 + i for i, t in enumerate(sorted(indice))}

    def __call__(self, params):
        self.chamadas.append(params)
        acao = params["action"]
        if acao == "query" and params.get("list") == "prefixsearch":
            titulos = [t for t in sorted(indice_sem_df(self.indice), reverse=True)]
            res = [{"ns": 0, "title": t, "pageid": self.pageids[t]} for t in titulos]
            res += self.extra
            return {"query": {"prefixsearch": res}}
        if acao == "query" and params.get("prop") == "info":
            pedidos = params["titles"].split("|")
            pages, redirects = [], []
            for t in pedidos:
                alvo = self.redirecionar.get(t, t)
                if alvo != t:
                    redirects.append({"from": t, "to": alvo})
                if alvo in self.indice:
                    pages.append({"pageid": self.pageids[alvo], "ns": 0, "title": alvo, "lastrevid": self.indice[alvo]["revid_atual"]})
                else:
                    pages.append({"ns": 0, "title": alvo, "missing": True})
            return {"query": {"redirects": redirects, "pages": pages}}
        if acao == "parse":
            t = params["page"]
            if t in self.falhar_parse or t not in self.indice:
                return {"error": {"code": "missingtitle", "info": "The page you specified doesn't exist."}}
            e = self.indice[t]
            return {"parse": {"title": t, "pageid": self.pageids[t], "revid": e["revid_atual"], "text": ler_gz(e["arquivo_atual"])}}
        raise AssertionError("chamada inesperada: %r" % params)


def indice_sem_df(indice):
    return [t for t in indice if "Distrito Federal" not in t]


class CaminhoOnline(Base):
    def coletar(self, sim, anterior, tudo=False):
        with mock.patch.object(self.mod.Api, "get", lambda api, params: sim(params)):
            return self.mod.coletar_online(anterior, tudo=tudo, pausa=0, log=lambda *a: None)

    def test_reaproveita_paginas_sem_mudanca_e_mantem_a_ordem(self):
        sim = Simulada(self.indice)
        anterior = self.dump_do_script()
        paginas, revisoes, resumo = self.coletar(sim, anterior)
        self.assertEqual(list(paginas), list(self.paginas))
        iguais = [t for t, e in self.indice.items() if e["revid_atual"] == e["revid_dump"]]
        self.assertEqual(len(iguais), 5)
        self.assertEqual(resumo["reaproveitada"], 5)
        self.assertEqual(resumo["reparseada"], 22)
        self.assertEqual(resumo["erro"], 0)
        # 1 prefixsearch + 1 prop=info + 22 parses
        self.assertEqual(sum(1 for c in sim.chamadas if c["action"] == "parse"), 22)
        self.assertEqual(len(sim.chamadas), 24)
        for t in iguais:
            self.assertEqual(paginas[t], anterior["paginas"][t])
        for t in self.indice:
            self.assertEqual(revisoes[t], {"pageid": sim.pageids[t], "revid": self.indice[t]["revid_atual"]})
            self.assertEqual(self.mod.revid_do_texto(paginas[t]), self.indice[t]["revid_atual"])
        self.assertIn(self.mod.TITULO_DF, paginas)

    def test_tudo_reparseia_mesmo_sem_mudanca(self):
        sim = Simulada(self.indice)
        paginas, _, resumo = self.coletar(sim, self.dump_do_script(), tudo=True)
        self.assertEqual(resumo["reparseada"], 27)
        self.assertEqual(resumo["reaproveitada"], 0)

    def test_dump_do_navegador_e_reparseado_inteiro_mesmo_sem_tudo(self):
        # o dump de 02/09 não tem a chave revisoes; na primeira coleta real nada é reaproveitado,
        # para as páginas sem mudança também perderem o CSS vazado
        sim = Simulada(self.indice)
        paginas, _, resumo = self.coletar(sim, self.dump)
        self.assertEqual(resumo["reparseada"], 27)
        self.assertEqual(resumo["reaproveitada"], 0)
        self.assertEqual(list(paginas), list(self.paginas))
        for t, x in paginas.items():
            self.assertNotIn(".mw-parser-output", x, t)

    def test_texto_anterior_com_css_vazado_e_reparseado(self):
        anterior = self.dump_do_script()
        com_css = [t for t, e in self.indice.items() if e["revid_atual"] == e["revid_dump"] and CSS_VAZADO.search(self.paginas[t])]
        self.assertEqual(len(com_css), 2, "Acre e Amapá não mudaram desde 02/09 e tinham CSS no dump")
        for t in com_css:
            anterior["paginas"][t] = self.paginas[t]
        sim = Simulada(self.indice)
        paginas, _, resumo = self.coletar(sim, anterior)
        self.assertEqual(resumo["reaproveitada"], 3)
        self.assertEqual(resumo["reparseada"], 24)
        for t in com_css:
            self.assertNotIn(".mw-parser-output", paginas[t])

    def test_sem_dump_anterior_parseia_tudo_na_ordem_da_listagem(self):
        sim = Simulada(self.indice)
        paginas, _, resumo = self.coletar(sim, None)
        self.assertEqual(resumo["reparseada"], 27)
        self.assertEqual(list(paginas)[-1], self.mod.TITULO_DF, "o DF entra por último, acrescentado à listagem")

    def test_http_200_com_erro_vira_ERRO_da_pagina(self):
        alvo = "Pesquisas eleitorais para a eleição estadual de 2026 em Roraima"
        sim = Simulada(self.indice, falhar_parse=[alvo])
        paginas, revisoes, resumo = self.coletar(sim, self.dump, tudo=True)
        self.assertTrue(paginas[alvo].startswith("ERRO missingtitle: "), paginas[alvo])
        self.assertIsNone(revisoes[alvo]["revid"])
        self.assertEqual(resumo["erro"], 1)
        self.assertEqual(list(paginas), list(self.paginas))

    def test_falha_de_rede_mantem_texto_anterior(self):
        alvo = "Pesquisas eleitorais para a eleição estadual de 2026 em Roraima"
        sim = Simulada(self.indice)
        original = sim.__call__

        def com_falha(params):
            if params["action"] == "parse" and params["page"] == alvo:
                raise self.mod.ErroApi("falha de rede em parse: simulada")
            return original(params)
        with mock.patch.object(self.mod.Api, "get", lambda api, params: com_falha(params)):
            paginas, revisoes, resumo = self.mod.coletar_online(self.dump, tudo=True, pausa=0, log=lambda *a: None)
        self.assertEqual(paginas[alvo], self.paginas[alvo])
        self.assertEqual(revisoes[alvo]["revid"], self.indice[alvo]["revid_dump"])
        self.assertEqual(resumo["mantida_por_falha"], 1)

    def test_maxlag_esgotado_mantem_texto_anterior(self):
        # o parse de Roraima passa pelo Api.get de verdade, com urlopen devolvendo maxlag em todas as tentativas
        alvo = "Pesquisas eleitorais para a eleição estadual de 2026 em Roraima"
        sim = Simulada(self.indice)
        anterior = self.dump_do_script()
        api_real = self.mod.Api(log=lambda *a: None)
        get_real = self.mod.Api.get  # guardado antes do patch da classe
        maxlag = {"error": {"code": "maxlag", "info": "Waiting for a database server: 6 seconds lagged"}}
        esperas = []

        def get(api, params):
            if params["action"] == "parse" and params["page"] == alvo:
                with mock.patch.object(self.mod.urllib.request, "urlopen", side_effect=lambda *a, **k: resposta_http(maxlag, {"Retry-After": "5"})), \
                        mock.patch.object(self.mod.time, "sleep", esperas.append):
                    return get_real(api_real, params)
            return sim(params)
        with mock.patch.object(self.mod.Api, "get", get):
            paginas, revisoes, resumo = self.mod.coletar_online(anterior, tudo=True, pausa=0, log=lambda *a: None)
        self.assertEqual(esperas, [5, 5, 5, 5])
        self.assertEqual(api_real.requisicoes, self.mod.TENTATIVAS)
        self.assertEqual(paginas[alvo], anterior["paginas"][alvo], "texto anterior mantido, não 'ERRO maxlag'")
        self.assertEqual(revisoes[alvo]["revid"], self.indice[alvo]["revid_dump"])
        self.assertEqual(resumo["mantida_por_falha"], 1)
        self.assertEqual(resumo["erro"], 0)
        self.assertEqual(resumo["reparseada"], 26)

    def test_erro_interno_da_api_mantem_texto_anterior(self):
        alvo = "Pesquisas eleitorais para a eleição estadual de 2026 no Acre"
        sim = Simulada(self.indice)
        anterior = self.dump_do_script()
        api_real = self.mod.Api(log=lambda *a: None)
        get_real = self.mod.Api.get  # guardado antes do patch da classe
        interno = {"error": {"code": "internal_api_error_DBQueryError", "info": "[abc] Exception caught: A database query error has occurred."}}

        def get(api, params):
            if params["action"] == "parse" and params["page"] == alvo:
                with mock.patch.object(self.mod.urllib.request, "urlopen", side_effect=lambda *a, **k: resposta_http(interno)), \
                        mock.patch.object(self.mod.time, "sleep"):
                    return get_real(api_real, params)
            return sim(params)
        with mock.patch.object(self.mod.Api, "get", get):
            paginas, _, resumo = self.mod.coletar_online(anterior, tudo=True, pausa=0, log=lambda *a: None)
        self.assertEqual(paginas[alvo], anterior["paginas"][alvo])
        self.assertEqual(resumo["mantida_por_falha"], 1)
        self.assertEqual(resumo["erro"], 0)

    def test_pagina_que_sumiu_da_wikipedia_vira_ERRO(self):
        indice = dict(self.indice)
        sumida = "Pesquisas eleitorais para a eleição estadual de 2026 no Amapá"
        del indice[sumida]
        sim = Simulada(indice)
        paginas, _, resumo = self.coletar(sim, self.dump)
        self.assertTrue(paginas[sumida].startswith("ERRO página não encontrada"))
        self.assertEqual(resumo["erro"], 1)
        self.assertEqual(list(paginas), list(self.paginas), "a página ausente fica no lugar, marcada com ERRO")

    def test_subpagina_e_outros_namespaces_sao_ignorados(self):
        extra = [{"ns": 0, "title": "Pesquisas eleitorais para a eleição estadual de 2026 em São Paulo/Primeiro turno", "pageid": 1},
                 {"ns": 1, "title": "Discussão:Pesquisas eleitorais para a eleição estadual de 2026 em São Paulo", "pageid": 2},
                 {"ns": 0, "title": "Pesquisas eleitorais para a eleição estadual de 2026 (índice)", "pageid": 3}]
        sim = Simulada(self.indice, extra_prefixsearch=extra)
        avisos = []
        with mock.patch.object(self.mod.Api, "get", lambda api, params: sim(params)):
            titulos = self.mod.listar_titulos(self.mod.Api(), log=avisos.append)
        self.assertEqual(len(titulos), 27)
        self.assertEqual(len(avisos), 2)
        self.assertTrue(any("subpágina" in a for a in avisos))

    def test_redirecionamento_grava_sob_o_titulo_novo(self):
        antigo = "Pesquisas eleitorais para a eleição estadual de 2026 no Amapá"
        novo = "Pesquisas eleitorais para a eleição estadual de 2026 no Estado do Amapá"
        indice = dict(self.indice)
        indice[novo] = indice.pop(antigo)
        sim = Simulada(indice, redirecionar={antigo: novo})
        paginas, revisoes, resumo = self.coletar(sim, self.dump)
        self.assertNotIn(antigo, paginas)
        self.assertIn(novo, paginas)
        self.assertEqual(list(paginas).index(novo), list(self.paginas).index(antigo), "mantém a posição")
        self.assertEqual(len(paginas), 27)
        self.assertEqual(resumo["erro"], 0)


class Cliente(Base):
    """Espera em 429 e maxlag, sem rede: urlopen e time.sleep simulados."""

    def resposta(self, corpo, cabecalhos=None):
        return resposta_http(corpo, cabecalhos)

    def test_espera_retry_after_em_429_e_maxlag(self):
        api = self.mod.Api(log=lambda *a: None)
        erro429 = urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "7"}, io.BytesIO(b""))
        respostas = [erro429, self.resposta({"error": {"code": "maxlag", "info": "lag"}}, {"Retry-After": "3"}), self.resposta({"query": {}})]

        def urlopen(req, timeout=0):
            self.assertEqual(req.get_header("User-agent"), self.mod.UA)
            self.assertIn("maxlag=5", req.full_url)
            r = respostas.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch.object(self.mod.urllib.request, "urlopen", urlopen), mock.patch.object(self.mod.time, "sleep") as sl:
            j = api.get({"action": "query"})
        self.assertEqual(j, {"query": {}})
        self.assertEqual([c.args[0] for c in sl.call_args_list], [7, 3])
        self.assertEqual(api.requisicoes, 3)

    def test_maxlag_em_todas_as_tentativas_levanta_ErroApi(self):
        api = self.mod.Api(log=lambda *a: None)
        lag = self.resposta({"error": {"code": "maxlag", "info": "Waiting for a database server: 6 seconds lagged"}}, {"Retry-After": "2"})
        with mock.patch.object(self.mod.urllib.request, "urlopen", return_value=lag), mock.patch.object(self.mod.time, "sleep") as sl:
            with self.assertRaises(self.mod.ErroApi) as cm:
                api.get({"action": "parse", "page": "x"})
        self.assertIn("maxlag persistente", str(cm.exception))
        self.assertEqual([c.args[0] for c in sl.call_args_list], [2, 2, 2, 2])
        self.assertEqual(api.requisicoes, self.mod.TENTATIVAS)

    def test_erro_interno_e_readonly_sao_transitorios_e_missingtitle_nao(self):
        self.assertEqual(self.mod.erro_transitorio({"error": {"code": "internal_api_error_DBQueryError", "info": ""}}), "internal_api_error_DBQueryError")
        self.assertEqual(self.mod.erro_transitorio({"error": {"code": "readonly", "info": ""}}), "readonly")
        self.assertIsNone(self.mod.erro_transitorio({"error": {"code": "missingtitle", "info": ""}}))
        self.assertIsNone(self.mod.erro_transitorio({"parse": {}}))
        api = self.mod.Api(log=lambda *a: None)
        interno = self.resposta({"error": {"code": "internal_api_error_DBQueryError", "info": "x"}})
        with mock.patch.object(self.mod.urllib.request, "urlopen", return_value=interno), mock.patch.object(self.mod.time, "sleep") as sl:
            with self.assertRaises(self.mod.ErroApi):
                api.get({"action": "parse", "page": "x"})
        self.assertEqual(sl.call_count, self.mod.TENTATIVAS - 1)
        # erro próprio da página é devolvido como corpo, sem repetir
        faltando = self.resposta({"error": {"code": "missingtitle", "info": "x"}})
        with mock.patch.object(self.mod.urllib.request, "urlopen", return_value=faltando), mock.patch.object(self.mod.time, "sleep") as sl:
            j = api.get({"action": "parse", "page": "x"})
        self.assertEqual(j["error"]["code"], "missingtitle")
        self.assertEqual(sl.call_count, 0)

    def test_http_500_e_repetido(self):
        api = self.mod.Api(log=lambda *a: None)
        erro = urllib.error.HTTPError("u", 500, "Internal Server Error", {}, io.BytesIO(b""))
        respostas = [erro, self.resposta({"query": {}})]

        def urlopen(req, timeout=0):
            r = respostas.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch.object(self.mod.urllib.request, "urlopen", urlopen), mock.patch.object(self.mod.time, "sleep") as sl:
            j = api.get({"action": "query"})
        self.assertEqual(j, {"query": {}})
        self.assertEqual([c.args[0] for c in sl.call_args_list], [5])

    def test_http_404_nao_e_repetido(self):
        api = self.mod.Api(log=lambda *a: None)
        erro = urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b""))
        with mock.patch.object(self.mod.urllib.request, "urlopen", side_effect=erro), mock.patch.object(self.mod.time, "sleep") as sl:
            with self.assertRaises(self.mod.ErroApi):
                api.get({"action": "query"})
        self.assertEqual(sl.call_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
