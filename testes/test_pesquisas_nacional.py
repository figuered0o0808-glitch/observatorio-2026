# -*- coding: utf-8 -*-
"""Testes de coleta/wikipedia_pesquisas_nacional.py sobre a fixture
testes/fixtures/wikipedia/nacional-atual.html.gz (revisão 72935890 da página
"Pesquisas de opinião para a eleição presidencial no Brasil em 2026").

Os valores esperados foram lidos no wikitext dessa mesma revisão. O CSV real em
dados/ só é lido; toda gravação acontece numa cópia em pasta temporária.

Uso:
    python3 testes/test_pesquisas_nacional.py
    python3 -m unittest testes.test_pesquisas_nacional
"""
import contextlib
import csv
import io
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coleta"))
import wikipedia_pesquisas_nacional as wpn  # noqa: E402

FIXTURE = RAIZ / "testes" / "fixtures" / "wikipedia" / "nacional-atual.html.gz"
# CSV congelado no estado de 6/9/2026, antes da primeira coleta automática. O de produção não
# serve de referência: assim que o robô grava as rodadas de setembro elas deixam de ser novas e
# os testes das rodadas novas passariam a falhar sozinhos (aconteceu em 7/9/2026).
CSV_CONGELADO = RAIZ / "testes" / "fixtures" / "wikipedia" / "pesquisas-registradas-2026-09-06.csv.gz"


def csv_de_referencia(tmp):
    """Descomprime o CSV congelado num diretório temporário e devolve o caminho."""
    import gzip, shutil
    destino = Path(tmp) / "pesquisas-registradas.csv"
    with gzip.open(CSV_CONGELADO, "rb") as e, open(destino, "wb") as s:
        shutil.copyfileobj(e, s)
    return destino
REVID = 72935890

# Rodadas novas da tabela de setembro do 1º turno, lidas no wikitext da revisão 72935890.
# Os zeros são valores observados na tabela ("0%"), distintos de célula ausente ("-").
ESPERADO = {
    "Instituto Veritá": {
        "pagina": "Veritá", "campo": ("2026-09-01", "2026-09-04"), "divulgacao": "2026-09-06",
        "metodologia": "n=3804", "margem": "2.0", "cenarios": 1,
        "c1": {"Lula": 38.4, "Flávio Bolsonaro": 38.9, "Augusto Cury": 12.2, "Renan Santos": 3.7,
               "Ronaldo Caiado": 1.9, "Pablo Marçal": 1.3, "Romeu Zema": 0.3, "Samara Martins": 0.2,
               "Clariana Barão": 0.3, "Hertz Dias": 0.4, "Edmilson Costa": 0.3, "não sabe": 2},
        "ausentes_c1": {"Wilson Grassi", "Rui Costa Pimenta", "outros"},
        "t2": {"Lula": 43.1, "Flávio Bolsonaro": 48.5},
    },
    "Datafolha": {
        "pagina": "Datafolha", "campo": ("2026-09-01", "2026-09-02"), "divulgacao": "2026-09-03",
        "metodologia": "n=2002", "margem": "2.0", "cenarios": 1,
        "c1": {"Lula": 38, "Flávio Bolsonaro": 33, "Augusto Cury": 8, "Renan Santos": 3, "Ronaldo Caiado": 4,
               "Romeu Zema": 2, "Samara Martins": 1, "Wilson Grassi": 0, "Clariana Barão": 0,
               "Hertz Dias": 2, "Edmilson Costa": 1, "Rui Costa Pimenta": 1, "não sabe": 9},
        "ausentes_c1": {"Pablo Marçal", "outros"},
        "t2": {"Lula": 46, "Flávio Bolsonaro": 44},
    },
    "PoderData": {
        "pagina": "PoderData/Aya", "campo": ("2026-08-30", "2026-09-02"), "divulgacao": "2026-09-03",
        "metodologia": "n=3000", "margem": "1.8", "cenarios": 1,
        "c1": {"Lula": 37, "Flávio Bolsonaro": 34, "Augusto Cury": 10, "Renan Santos": 3, "Ronaldo Caiado": 2,
               "Pablo Marçal": 2, "Romeu Zema": 1, "Samara Martins": 1, "Wilson Grassi": 0,
               "Clariana Barão": 1, "Hertz Dias": 2, "Edmilson Costa": 1, "Rui Costa Pimenta": 1, "não sabe": 7},
        "ausentes_c1": {"outros"},
        "t2": {"Lula": 45, "Flávio Bolsonaro": 46},
    },
    "Quaest": {
        "pagina": "Quaest", "campo": ("2026-08-30", "2026-09-01"), "divulgacao": "2026-09-02",
        "metodologia": "n=2004", "margem": "2.0", "cenarios": 2,
        "c1": {"Lula": 37, "Flávio Bolsonaro": 30, "Augusto Cury": 10, "Renan Santos": 3, "Ronaldo Caiado": 1,
               "Pablo Marçal": 1, "Romeu Zema": 1, "Samara Martins": 0, "Wilson Grassi": 0, "Clariana Barão": 0,
               "Hertz Dias": 0, "Edmilson Costa": 0, "Rui Costa Pimenta": 0, "não sabe": 18},
        "ausentes_c1": {"outros"},
        "c2": {"Lula": 37, "Flávio Bolsonaro": 29, "Augusto Cury": 10, "Renan Santos": 3, "Ronaldo Caiado": 1,
               "Romeu Zema": 1, "Samara Martins": 1, "Wilson Grassi": 0, "Clariana Barão": 0, "Hertz Dias": 0,
               "Edmilson Costa": 0, "Rui Costa Pimenta": 0, "não sabe": 18},
        "ausentes_c2": {"Pablo Marçal", "outros"},
        "t2": {"Lula": 42, "Flávio Bolsonaro": 41},
    },
    "Futura Inteligência (100% Cidades)": {
        "pagina": "Apex/Futura", "campo": ("2026-08-27", "2026-09-01"), "divulgacao": "2026-09-03",
        "metodologia": "n=2000", "margem": "2.2", "cenarios": 1,
        "c1": {"Lula": 38.7, "Flávio Bolsonaro": 33.6, "Augusto Cury": 9.9, "Renan Santos": 2.8,
               "Ronaldo Caiado": 3.5, "Pablo Marçal": 2.7, "Romeu Zema": 1.6, "Samara Martins": 0.4,
               "Wilson Grassi": 0.3, "Hertz Dias": 0.1, "Rui Costa Pimenta": 0.3, "não sabe": 6.1},
        "ausentes_c1": {"Clariana Barão", "Edmilson Costa", "outros"},
        "t2": {"Lula": 45.6, "Flávio Bolsonaro": 45.2},
    },
}
AGREGADORES = {"UOL", "PollingData", "Poll+Trend", "Plano Político", "ABC Dados"}

HTML = None
LINHAS_CSV = None
NOVAS = PRESENTES = RES = None
TMP_REF = None
CSV_REF = None


def setUpModule():
    global HTML, LINHAS_CSV, NOVAS, PRESENTES, RES, TMP_REF, CSV_REF
    TMP_REF = tempfile.TemporaryDirectory()
    CSV_REF = csv_de_referencia(TMP_REF.name)
    HTML, _ = wpn.carregar_html(FIXTURE, REVID)
    LINHAS_CSV = wpn.ler_csv(CSV_REF)
    NOVAS, PRESENTES, RES = wpn.processar(HTML, REVID, LINHAS_CSV, hoje=date(2026, 9, 6))


def tearDownModule():
    if TMP_REF is not None:
        TMP_REF.cleanup()


def por_cenario(linhas):
    """{rotulo do cenário -> {candidato -> float}} a partir das linhas de 13 colunas."""
    saida = {}
    for l in linhas:
        saida.setdefault(l[5], {})[l[6]] = float(l[7])
    return saida


class Setembro(unittest.TestCase):
    def rodadas_setembro(self):
        return {r["instituto"]: r for r in NOVAS if r["campo_fim"] >= "2026-09-01"}

    def test_cinco_rodadas_novas_em_setembro(self):
        self.assertEqual(set(self.rodadas_setembro()), set(ESPERADO))

    def test_ficha_de_cada_rodada(self):
        rod = self.rodadas_setembro()
        for inst, esp in ESPERADO.items():
            r = rod[inst]
            with self.subTest(inst):
                self.assertEqual(r["instituto_pagina"], esp["pagina"])
                self.assertEqual((r["campo_inicio"], r["campo_fim"]), esp["campo"])
                self.assertEqual(r["data_divulgacao"], esp["divulgacao"])
                self.assertEqual(r["margem"], esp["margem"])
                self.assertEqual(len(r["cenarios"]), esp["cenarios"])
                self.assertTrue(r["url"].startswith("http"), r["url"])
                self.assertEqual(r["registro"], "")

    def test_numeros_de_cada_cenario(self):
        rod = self.rodadas_setembro()
        for inst, esp in ESPERADO.items():
            linhas = wpn.linhas_da_rodada(rod[inst], REVID)
            cen = por_cenario(linhas)
            with self.subTest(inst):
                self.assertEqual(cen["1º turno"], esp["c1"])
                self.assertFalse(esp["ausentes_c1"] & set(cen["1º turno"]))
                if esp["cenarios"] == 2:
                    self.assertEqual(cen["1º turno, cenário 2"], esp["c2"])
                    self.assertFalse(esp["ausentes_c2"] & set(cen["1º turno, cenário 2"]))
                else:
                    self.assertNotIn("1º turno, cenário 2", cen)
                self.assertEqual(cen[wpn.CENARIO_2T], esp["t2"])
                self.assertEqual(set(cen), {"1º turno", wpn.CENARIO_2T} | ({"1º turno, cenário 2"} if esp["cenarios"] == 2 else set()))

    def test_contrato_das_linhas(self):
        rod = self.rodadas_setembro()
        for inst, esp in ESPERADO.items():
            for l in wpn.linhas_da_rodada(rod[inst], REVID):
                with self.subTest(inst=inst, cenario=l[5], candidato=l[6]):
                    self.assertEqual(len(l), len(wpn.COLUNAS))
                    self.assertEqual(l[0], inst)
                    self.assertRegex(l[1], r"^\d{4}-\d{2}-\d{2}$")
                    self.assertRegex(l[2], r"^\d{4}-\d{2}-\d{2}$")
                    self.assertRegex(l[3], r"^\d{4}-\d{2}-\d{2}$")
                    self.assertEqual(l[4], esp["metodologia"])
                    self.assertRegex(l[7], r"^\d+(\.\d+)?$")
                    self.assertEqual(l[8], "")   # rejeição: a página não traz
                    self.assertEqual(l[9], esp["margem"])
                    self.assertEqual(l[10], "")  # registro no TSE: a página não traz
                    self.assertTrue(l[11].startswith("http"))
                    self.assertTrue(l[12].startswith("compilação da Wikipédia, revisão 72935890"), l[12])
                    self.assertNotIn("\n", l[12])

    def test_observacao_dos_cenarios_da_quaest(self):
        linhas = wpn.linhas_da_rodada(self.rodadas_setembro()["Quaest"], REVID)
        obs1 = {l[12] for l in linhas if l[5] == "1º turno" and l[6] == "Lula"}
        obs2 = {l[12] for l in linhas if l[5] == "1º turno, cenário 2" and l[6] == "Lula"}
        self.assertEqual(obs1, {"compilação da Wikipédia, revisão 72935890, cenário 1"})
        self.assertEqual(obs2, {"compilação da Wikipédia, revisão 72935890, cenário 2 (sem Pablo Marçal)"})
        obs_ns = {l[12] for l in linhas if l[6] == "não sabe"}
        for o in obs_ns:
            self.assertIn("indecisos e absentos", o)

    def test_zero_observado_fica_e_ausencia_nao_vira_linha(self):
        linhas = wpn.linhas_da_rodada(self.rodadas_setembro()["Datafolha"], REVID)
        c1 = por_cenario(linhas)["1º turno"]
        self.assertEqual(c1["Wilson Grassi"], 0.0)
        self.assertNotIn("Pablo Marçal", c1)  # célula "-" na tabela


class Dedup(unittest.TestCase):
    def test_real_time_big_data_ja_presente(self):
        rtbd = [r for r in PRESENTES if r["instituto"] == "Real Time Big Data" and r["campo_fim"] == "2026-08-31"]
        self.assertEqual(len(rtbd), 1)
        self.assertEqual(rtbd[0]["presente_como"], ("Real Time Big Data", "2026-08-31", "2026-09-01"))
        self.assertFalse([r for r in NOVAS if r["instituto"] == "Real Time Big Data"])

    def test_nenhuma_rodada_nova_repete_rodada_do_csv(self):
        existentes = wpn.rodadas_existentes(LINHAS_CSV)
        for r in NOVAS:
            with self.subTest(r["instituto"], fim=r["campo_fim"]):
                self.assertIsNone(wpn.rodada_presente(r, existentes))

    def test_rodadas_de_agosto_conhecidas_sao_reconhecidas(self):
        presentes = {(r["instituto"], r["campo_fim"]) for r in PRESENTES}
        for chave in [("BTG/Nexus", "2026-08-30"), ("AtlasIntel/Bloomberg", "2026-08-30"),
                      ("PoderData", "2026-08-26"), ("Datafolha", "2026-08-20"),
                      ("Futura Inteligência (100% Cidades)", "2026-08-07"), ("Ideia (Meio/Ideia)", "2026-08-03"),
                      ("Quaest", "2026-08-13"), ("CNT/MDA", "2026-08-09"), ("Indexa/Broadcast", "2026-08-23")]:
            self.assertIn(chave, presentes)

    def test_desde_limita_a_primeira_carga(self):
        novas, _, _ = wpn.processar(HTML, REVID, LINHAS_CSV, hoje=date(2026, 9, 6), desde="2026-09-01")
        self.assertEqual({r["instituto"] for r in novas}, set(ESPERADO))

    def test_campo_no_futuro_nao_entra(self):
        novas, _, res = wpn.processar(HTML, REVID, LINHAS_CSV, hoje=date(2026, 9, 3))
        self.assertNotIn("Instituto Veritá", {r["instituto"] for r in novas if r["campo_fim"] >= "2026-09-01"})
        self.assertTrue(any("futuro" in a for a in res["avisos"]))


class Estrutura(unittest.TestCase):
    def test_agregadores_nao_entram(self):
        nomes = {r["instituto_pagina"] for r in RES["primeiro"] + RES["segundo"]}
        self.assertFalse(AGREGADORES & nomes)
        self.assertTrue(any(m == "seção de agregadores" for _, m in RES["descartes"]))

    def test_so_2026_e_so_primeiro_turno(self):
        for r in RES["primeiro"]:
            self.assertTrue(r["campo_fim"].startswith("2026"), r)
            self.assertTrue(r["secao"].startswith("Primeiro turno"), r["secao"])
        self.assertEqual(len(RES["primeiro"]), 26)  # 5 de setembro + 21 de agosto

    def test_colunas_lidas_por_tabela(self):
        # a tabela de agosto tem os candidatos noutra ordem; um mesmo valor não pode trocar de dono
        ago = {(r["instituto_pagina"], r["campo_fim"]): r for r in RES["primeiro"]}
        atlas = ago[("AtlasIntel", "2026-08-30")]["cenarios"][0]["candidatos"]
        self.assertIn(("Lula", "43.4"), atlas)
        self.assertIn(("Renan Santos", "7.6"), atlas)
        self.assertIn(("Augusto Cury", "7.8"), atlas)

    def test_referencia_resolve_url_e_data(self):
        ref = RES["refs"]["cite_note-8"]
        self.assertTrue(ref["url"].startswith("https://francesnews.com.br/"))
        self.assertEqual(ref["data"], "2026-09-06")
        ref_quaest = RES["refs"]["cite_note-:139-11"]  # data antes do título, como autor (data)
        self.assertTrue(ref_quaest["url"].startswith("https://www.gazetadopovo.com.br/"))
        self.assertEqual(ref_quaest["data"], "2026-09-02")

    def test_referencia_sem_data_de_publicacao_fica_vazia(self):
        # citação só com 'Consultado em 3 de setembro de 2026': data de acesso não é divulgação
        ref = RES["refs"]["cite_note-7"]
        self.assertTrue(ref["url"].startswith("https://www.economist.com/"))
        self.assertEqual(ref["data"], "")
        for nid in ("cite_note-2", "cite_note-AgregadorUOL-1", "cite_note-:112-89"):
            self.assertEqual(RES["refs"][nid]["data"], "", nid)

    def test_referencia_prefere_o_coins_ao_texto(self):
        # rft.date do COinS vale mais que a primeira data por extenso depois do título
        self.assertEqual(RES["refs"]["cite_note-Futura1-204"]["data"], "2023-07-31")  # texto: 13 de outubro de 2024
        self.assertEqual(RES["refs"]["cite_note-:27-172"]["data"], "2025-10-27")  # texto: 31 de outubro de 2025
        self.assertEqual(RES["refs"]["cite_note-103"]["data"], "2026-06-23")
        # trocar o rft.date muda a data devolvida: prova de que o COinS é lido
        html2 = HTML.replace("rft.date=2026-09-06", "rft.date=2026-09-26")
        self.assertEqual(wpn.referencias(wpn.arvore(html2))["cite_note-8"]["data"], "2026-09-26")
        # nenhuma nota diverge do COinS e nenhuma nota sem COinS ganha data
        raiz = wpn.arvore(HTML)
        for li in raiz.iterar():
            if li.tag != "li" or not li.attrs.get("id", "").startswith("cite_note-"):
                continue
            rft = ""
            for sp in li.iterar():
                if sp.tag == "span" and "Z3988" in sp.classe:
                    m = re.search(r"rft\.date=(\d{4}-\d{2}-\d{2})", sp.attrs.get("title", ""))
                    rft = m.group(1) if m else rft
            self.assertEqual(RES["refs"][li.attrs["id"]]["data"], rft, li.attrs["id"])

    def test_citacao_no_futuro_cai_no_fim_do_campo(self):
        html2 = HTML.replace("rft.date=2026-09-06", "rft.date=2026-09-26")
        novas, _, _ = wpn.processar(html2, REVID, LINHAS_CSV, hoje=date(2026, 9, 6))
        verita = [r for r in novas if r["instituto_pagina"] == "Veritá" and r["campo_fim"] == "2026-09-04"][0]
        self.assertEqual(verita["data_divulgacao"], "2026-09-04")
        self.assertIn("citação datada de 2026-09-26, no futuro", verita["nota"])
        self.assertIn("no futuro", wpn.linhas_da_rodada(verita, REVID)[0][12])

    def test_html_local_com_erro_da_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            erro = Path(tmp) / "erro.json"
            erro.write_text(json.dumps({"error": {"code": "missingtitle", "info": "nope"}}), encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                wpn.carregar_html(erro, REVID)
            self.assertIn("nope", str(cm.exception))
            sem = Path(tmp) / "sem.json"
            sem.write_text(json.dumps({"batchcomplete": True}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                wpn.carregar_html(sem, REVID)

    def test_api_com_corpo_nao_json_repete_e_desiste(self):
        class Resp:
            def __init__(self, corpo):
                self.corpo, self.headers = corpo, {}

            def read(self):
                return self.corpo.encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        seq = ["<html>Access Denied</html>", json.dumps({"parse": {"text": "<p>oi</p>", "revid": 5}})]
        esperas = []
        urlopen, sleep = wpn.urllib.request.urlopen, wpn.time.sleep
        wpn.urllib.request.urlopen = lambda req, timeout=0: Resp(seq.pop(0))
        wpn.time.sleep = esperas.append
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(wpn.baixar_pagina(tentativas=3)[:2], ("<p>oi</p>", 5))
                self.assertEqual(esperas, [5])
                seq[:] = ["<html>Access Denied</html>"] * 3
                with self.assertRaises(RuntimeError) as cm:
                    wpn.baixar_pagina(tentativas=3)
            self.assertIn("não respondeu JSON", str(cm.exception))
        finally:
            wpn.urllib.request.urlopen, wpn.time.sleep = urlopen, sleep


class Funcoes(unittest.TestCase):
    def test_datas(self):
        self.assertEqual(wpn.datas("1 Set - 4 Set", 2026), ("2026-09-01", "2026-09-04"))
        self.assertEqual(wpn.datas("30 Ago - 2 Set", 2026), ("2026-08-30", "2026-09-02"))
        self.assertEqual(wpn.datas("27 Ago - 1 Set", 2026), ("2026-08-27", "2026-09-01"))
        self.assertEqual(wpn.datas("10 Set - 14 - Set", 2026), ("2026-09-10", "2026-09-14"))
        self.assertEqual(wpn.datas("28 Dez - 3 Jan", 2026), ("2025-12-28", "2026-01-03"))
        self.assertEqual(wpn.datas("15 e 19 de agosto", 2026), ("2026-08-15", "2026-08-19"))
        self.assertEqual(wpn.datas("13 a 19 março de 2025", 2026), ("2025-03-13", "2025-03-19"))
        self.assertEqual(wpn.datas("novembro", 2026), ("", ""))

    def test_valor(self):
        self.assertEqual(wpn.valor("38,4%"), "38.4")
        self.assertEqual(wpn.valor("38%"), "38")
        self.assertEqual(wpn.valor("0%"), "0")
        self.assertEqual(wpn.valor("1%%"), "1")
        self.assertEqual(wpn.valor("2,0"), "2.0")
        for ausente in ("-", "—", "–", "N/A", "", "<1%", "?"):
            self.assertIsNone(wpn.valor(ausente), ausente)

    def test_amostra(self):
        self.assertEqual(wpn.amostra("3 804"), "3804")
        self.assertEqual(wpn.amostra("2\xa0002"), "2002")
        self.assertEqual(wpn.amostra("—"), "")

    def test_institutos(self):
        csv_inst = wpn.institutos_do_csv(LINHAS_CSV)
        self.assertEqual(wpn.nome_canonico("Apex/Futura", csv_inst), "Futura Inteligência (100% Cidades)")
        self.assertEqual(wpn.nome_canonico("Genial/Quaest", csv_inst), "Quaest")
        self.assertEqual(wpn.nome_canonico("PoderData/Aya", csv_inst), "PoderData")
        self.assertEqual(wpn.nome_canonico("Nexus/BTG Pactual", csv_inst), "BTG/Nexus")
        self.assertEqual(wpn.nome_canonico("Veritá", csv_inst), "Instituto Veritá")
        self.assertEqual(wpn.nome_canonico("Vox Brasil", csv_inst), "Vox Brasil")
        self.assertTrue(wpn.casa_instituto("Nexus/BTG Pactual", "BTG/Nexus"))
        self.assertTrue(wpn.casa_instituto("Meio/Ideia", "Ideia (Meio/Ideia)"))
        self.assertFalse(wpn.casa_instituto("Vox Brasil", "American Analytics (Times Brasil)"))
        self.assertFalse(wpn.casa_instituto("Datafolha", "PoderData"))
        # palavra em comum não casa nem renomeia: instituto novo fica com o nome da página
        for novo, parecido in (("Big Data Consultoria", "Real Time Big Data"),
                               ("Instituto Real", "Real Time Big Data"),
                               ("Ideia Big Data", "Real Time Big Data"),
                               ("Nexus Pesquisas", "BTG/Nexus"),
                               ("Times Brasil", "American Analytics (Times Brasil)"),
                               ("Meio", "Ideia (Meio/Ideia)")):
            self.assertFalse(wpn.casa_instituto(novo, parecido), novo)
            self.assertEqual(wpn.nome_canonico(novo, csv_inst), novo)
            self.assertIn(parecido, wpn.parecidos(novo, csv_inst))
        # e o aviso chega ao log para o dono decidir
        avisos = [a for a in RES["avisos"] if a.startswith("instituto novo para o CSV")]
        self.assertEqual(len(avisos), 2)
        self.assertTrue(any("'Palver'" in a for a in avisos) and any("'Vox Brasil'" in a for a in avisos))


class Gravacao(unittest.TestCase):
    def test_acrescenta_no_fim_preservando_bom_e_crlf(self):
        original = CSV_REF.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "pesquisas-registradas.csv"
            argv = ["--html", str(FIXTURE), "--revid", str(REVID), "--csv", str(CSV_REF), "--saida", str(destino)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(wpn.main(argv + ["--dry-run"]), 0)
                self.assertFalse(destino.exists())  # dry-run não cria nem toca a saída
                with self.assertRaises(SystemExit):  # --saida nunca aponta para dados/
                    wpn.main(argv[:-1] + [str(RAIZ / "dados" / "x.csv")])
                self.assertFalse((RAIZ / "dados" / "x.csv").exists())
                self.assertEqual(wpn.main(argv), 0)
            gravado = destino.read_bytes()
            self.assertTrue(gravado.startswith(original))
            self.assertEqual(gravado.count(b"\xef\xbb\xbf"), 1)
            self.assertEqual(gravado.count(b"\n"), gravado.count(b"\r\n"))
            self.assertTrue(gravado.endswith(b"\r\n"))
            with open(destino, encoding="utf-8-sig", newline="") as f:
                linhas = list(csv.DictReader(f))
            novas = linhas[len(LINHAS_CSV):]
            esperadas = sum(len(wpn.linhas_da_rodada(r, REVID)) for r in NOVAS)
            self.assertEqual(len(novas), esperadas)
            self.assertTrue(all(len(l) == 13 for l in novas))
            verita = [l for l in novas if l["instituto"] == "Instituto Veritá" and l["data_campo_fim"] == "2026-09-04" and l["cenario"] == "1º turno"]
            self.assertEqual({l["candidato"]: l["percentual"] for l in verita}["Lula"], "38.4")
            self.assertFalse([l for l in novas if l["instituto"] == "Real Time Big Data"])
            # segunda execução: nada muda
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(wpn.main(argv), 0)
            self.assertEqual(destino.read_bytes(), gravado)
        self.assertEqual(CSV_REF.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
