# -*- coding: utf-8 -*-
"""Testes do coletor de acessos à Wikipédia (coleta/wikipedia_pageviews.py).

O coletor faz acréscimo diário (append) em dados/wikipedia-pageviews.csv e em
dados/estados/wikipedia-estados.csv. Estes testes copiam os dois CSVs e as duas listas de
verbetes para uma pasta de trabalho, rodam o coletor em modo offline com respostas fabricadas
no formato real da REST da Wikimedia (as fixtures pageviews-*.json em testes/fixtures/wikipedia
são a referência) e conferem o contrato: BOM e CRLF preservados, nenhuma linha antiga removida,
alterada ou movida, chaves novas únicas, ordenação, zero da fonte gravado como 0, dia ausente
sem linha, as duas notas fixas do nacional preservadas, fonte com a data da coleta em Brasília,
verbete rejeitado fora da coleta, título de candidatos.csv limpo. Também cobrem a parte de rede
com respostas simuladas (429 com Retry-After, 5xx, 404, erro de rede, cabeçalhos).

Só biblioteca padrão; nunca escreve em dados/. A pasta de trabalho é temporária, a não ser que
a variável PAGEVIEWS_TESTE_DIR aponte para outra.

Uso:
    python3 testes/test_pageviews.py
"""
import csv
import datetime as dt
import importlib.util
import io
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from email.message import Message

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLETOR = os.path.join(RAIZ, "coleta", "wikipedia_pageviews.py")
FIXTURES = os.path.join(RAIZ, "testes", "fixtures", "wikipedia")
ENTRADAS = [
    os.path.join("dados", "candidatos.csv"),
    os.path.join("dados", "wikipedia-pageviews.csv"),
    os.path.join("dados", "estados", "wikipedia-verbetes-estados.csv"),
    os.path.join("dados", "estados", "wikipedia-estados.csv"),
]
# As duas séries de acessos entram congeladas no estado de 6/9/2026, antes da primeira coleta
# automática. Usar o arquivo de produção não funciona: o robô coleta todo dia, a janela que os
# cenários simulam já está lá e não sobra linha nova para medir (falhava assim em 7/9/2026).
CONGELADOS = {
    os.path.join("dados", "wikipedia-pageviews.csv"): os.path.join(FIXTURES, "wikipedia-pageviews-2026-09-06.csv.gz"),
    os.path.join("dados", "estados", "wikipedia-estados.csv"): os.path.join(FIXTURES, "wikipedia-estados-2026-09-06.csv.gz"),
}
NACIONAL = os.path.join("dados", "wikipedia-pageviews.csv")
ESTADUAL = os.path.join("dados", "estados", "wikipedia-estados.csv")
BOM = b"\xef\xbb\xbf"

NOTA_RENAN = ("verbete 'Renan Santos' (fundador do MBL); série corrigida em 1/9 à noite: a coleta "
              "anterior usara por engano o verbete do futebolista Renan dos Santos")
NOTA_SAMARA = "verbete criado em abril de 2026; série começa aqui"


def carregar_coletor():
    spec = importlib.util.spec_from_file_location("wikipedia_pageviews", COLETOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def item(titulo, data, views):
    """Um item no formato exato que a REST devolve (ver testes/fixtures/wikipedia/pageviews-*.json)."""
    return {"project": "pt.wikipedia", "article": titulo.replace(" ", "_"), "granularity": "daily",
            "timestamp": data.replace("-", "") + "00", "access": "all-access", "agent": "user",
            "views": views}


def ler_congelado(rel):
    """Bytes do CSV congelado que serve de estado inicial das cópias."""
    with gzip.open(CONGELADOS[rel], "rb") as f:
        return f.read()


def gravar_resposta(pasta, titulo, pares):
    nome = "pageviews-" + titulo.replace(" ", "_") + ".json"
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
        json.dump({"items": [item(titulo, d, v) for d, v in pares]}, f, ensure_ascii=False)


def ler_bytes(caminho):
    with open(caminho, "rb") as f:
        return f.read()


def ler_linhas(caminho):
    with open(caminho, "r", newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def conferir_bytes(teste, dados):
    teste.assertTrue(dados.startswith(BOM), "CSV sem BOM")
    teste.assertEqual(dados.count(b"\n"), dados.count(b"\r\n"), "há quebra de linha sem CR")
    teste.assertTrue(dados.endswith(b"\r\n"), "última linha sem CRLF")


def conferir_antigas_preservadas(teste, antigas, novas_linhas):
    """Toda linha antiga continua igual, e na mesma ordem relativa, dentro do arquivo novo."""
    posicao = {}
    for i, linha in enumerate(novas_linhas):
        posicao.setdefault(tuple(linha), []).append(i)
    ultimo = -1
    for linha in antigas:
        chave = tuple(linha)
        teste.assertIn(chave, posicao, "linha antiga sumiu ou mudou: %r" % (linha,))
        i = posicao[chave].pop(0)
        teste.assertGreater(i, ultimo, "linha antiga mudou de lugar: %r" % (linha,))
        ultimo = i


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = carregar_coletor()
        base = os.environ.get("PAGEVIEWS_TESTE_DIR")
        if base:
            os.makedirs(base, exist_ok=True)
            cls.base = base
            cls.temporaria = False
        else:
            cls.base = tempfile.mkdtemp(prefix="pageviews-teste-")
            cls.temporaria = True

    @classmethod
    def tearDownClass(cls):
        if cls.temporaria:
            shutil.rmtree(cls.base, ignore_errors=True)

    def montar_copia(self, nome):
        raiz = os.path.join(self.base, nome)
        if os.path.isdir(raiz):
            shutil.rmtree(raiz)
        for rel in ENTRADAS:
            destino = os.path.join(raiz, rel)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            if rel in CONGELADOS:
                with gzip.open(CONGELADOS[rel], "rb") as e, open(destino, "wb") as sa:
                    shutil.copyfileobj(e, sa)
            else:
                shutil.copyfile(os.path.join(RAIZ, rel), destino)
        offline = os.path.join(raiz, "offline")
        os.makedirs(offline)
        return raiz, offline

    def rodar(self, raiz, offline, *args, esperado=0):
        cmd = [sys.executable, COLETOR, "--raiz", raiz, "--offline", offline] + list(args)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, esperado, "código %d\nstdout:\n%s\nstderr:\n%s"
                         % (r.returncode, r.stdout, r.stderr))
        return r.stdout


class FluxoOffline(Base):
    """Execução completa em modo offline, janela 2026-09-01 a 2026-09-05."""

    DESDE, ATE = "2026-09-01", "2026-09-05"

    def preparar(self, nome):
        raiz, offline = self.montar_copia(nome)
        # respostas reais da REST, gravadas em 6/9 (cinco dias, 09-01 a 09-05)
        for nome_fx in ("pageviews-Alan_Rick.json", "pageviews-Augusto_Cury.json"):
            shutil.copyfile(os.path.join(FIXTURES, nome_fx), os.path.join(offline, nome_fx))
        # zero explícito em 09-01, 09-02 ausente, 09-06 fora da janela
        gravar_resposta(offline, "Samara Martins", [("2026-09-01", 0), ("2026-09-03", 812),
                                                    ("2026-09-04", 799), ("2026-09-05", 1043),
                                                    ("2026-09-06", 5000)])
        # título que em candidatos.csv vem poluído com "(URL canônico ...)"
        gravar_resposta(offline, "Pablo Marçal", [("2026-09-0%d" % d, 1500 + d) for d in range(1, 6)])
        # nome exibido diferente do título do verbete
        gravar_resposta(offline, "Luiz Inácio Lula da Silva", [("2026-09-0%d" % d, 4000 + d) for d in range(1, 6)])
        # verbete aceito para AL e rejeitado (homônimo) para PE
        gravar_resposta(offline, "Renan Filho", [("2026-09-0%d" % d, 300 + d) for d in range(1, 6)])
        return raiz, offline

    def setUp(self):
        self.raiz, self.offline = self.preparar("fluxo")
        self.nac_antes = ler_bytes(os.path.join(self.raiz, NACIONAL))
        self.est_antes = ler_bytes(os.path.join(self.raiz, ESTADUAL))
        self.hoje_antes = self.mod.hoje_brasilia()
        self.saida = self.rodar(self.raiz, self.offline, "--desde", self.DESDE, "--ate", self.ATE)
        self.hoje_depois = self.mod.hoje_brasilia()
        self.nac_depois = ler_bytes(os.path.join(self.raiz, NACIONAL))
        self.est_depois = ler_bytes(os.path.join(self.raiz, ESTADUAL))

    def fonte_esperada(self, fonte):
        base = self.mod.FONTE_BASE
        return fonte in (base + self.hoje_antes.isoformat(), base + self.hoje_depois.isoformat())

    def test_bom_e_crlf(self):
        conferir_bytes(self, self.nac_depois)
        conferir_bytes(self, self.est_depois)

    def test_nacional_antigas_preservadas_e_ordenado(self):
        antigas = self._linhas(self.nac_antes)
        depois = self._linhas(self.nac_depois)
        self.assertEqual(depois[0], self.mod.COLUNAS_NACIONAL)
        conferir_antigas_preservadas(self, antigas[1:], depois[1:])
        chaves = [(l[0], l[1]) for l in depois[1:]]
        self.assertEqual(chaves, sorted(chaves), "nacional fora da ordem (data, candidato)")
        self.assertEqual(len(chaves), len(set(chaves)), "chave (data, candidato) repetida")
        # as datas novas vêm depois de 08-31, então o arquivo antigo é prefixo byte a byte do novo
        self.assertTrue(self.nac_depois.startswith(self.nac_antes))

    def test_nacional_linhas_novas(self):
        antigas = {(l[0], l[1]) for l in self._linhas(self.nac_antes)[1:]}
        novas = [l for l in self._linhas(self.nac_depois)[1:] if (l[0], l[1]) not in antigas]
        por = {}
        for l in novas:
            por.setdefault(l[1], {})[l[0]] = l
        # 5 (Cury) + 4 (Samara) + 5 (Pablo) + 5 (Lula) = 19
        self.assertEqual(len(novas), 19, [l[:4] for l in novas])
        self.assertIn("dados/wikipedia-pageviews.csv: 19 linhas acrescentadas", self.saida)
        self.assertEqual(sorted(por), ["Augusto Cury", "Lula", "Pablo Marçal", "Samara Martins"])
        for l in novas:
            self.assertEqual(len(l), 7)
            self.assertTrue(self.fonte_esperada(l[4]), l[4])
            self.assertEqual(l[6], "", "observacao de linha nova deve ser vazia")
            self.assertTrue(self.DESDE <= l[0] <= self.ATE, l[0])
        # fixture real de Cury: os cinco dias, com os valores que a REST devolveu
        self.assertEqual({d: l[3] for d, l in por["Augusto Cury"].items()},
                         {"2026-09-01": "30201", "2026-09-02": "23654", "2026-09-03": "15326",
                          "2026-09-04": "11469", "2026-09-05": "10485"})
        cury = por["Augusto Cury"]["2026-09-01"]
        self.assertEqual(cury[2], "Augusto Cury")
        self.assertEqual(cury[5], "https://pt.wikipedia.org/wiki/Augusto_Cury")
        # zero da fonte fica 0; dia omitido não vira linha; dia fora da janela não entra
        samara = por["Samara Martins"]
        self.assertEqual(sorted(samara), ["2026-09-01", "2026-09-03", "2026-09-04", "2026-09-05"])
        self.assertEqual(samara["2026-09-01"][3], "0")
        self.assertNotIn("2026-09-02", samara)
        self.assertNotIn("2026-09-06", samara)
        # título limpo e URL do verbete com sublinhado, sem percent-encoding
        pablo = por["Pablo Marçal"]["2026-09-03"]
        self.assertEqual(pablo[2], "Pablo Marçal")
        self.assertEqual(pablo[5], "https://pt.wikipedia.org/wiki/Pablo_Marçal")
        self.assertEqual(pablo[3], "1503")
        lula = por["Lula"]["2026-09-05"]
        self.assertEqual(lula[1:4], ["Lula", "Luiz Inácio Lula da Silva", "4005"])
        self.assertEqual(lula[5], "https://pt.wikipedia.org/wiki/Luiz_Inácio_Lula_da_Silva")

    def test_notas_fixas_preservadas(self):
        linhas = self._linhas(self.nac_depois)[1:]
        notas = [l for l in linhas if l[6]]
        self.assertEqual(len(notas), 2)
        por = {(l[0], l[1]): l[6] for l in notas}
        self.assertEqual(por[("2026-01-01", "Renan Santos")], NOTA_RENAN)
        self.assertEqual(por[("2026-04-09", "Samara Martins")], NOTA_SAMARA)

    def test_estadual_antigas_preservadas_e_novas_no_fim(self):
        antigas = self._linhas(self.est_antes)
        depois = self._linhas(self.est_depois)
        self.assertEqual(depois[0], self.mod.COLUNAS_ESTADUAL)
        self.assertTrue(self.est_depois.startswith(self.est_antes), "estadual: o antigo não é prefixo do novo")
        conferir_antigas_preservadas(self, antigas[1:], depois[1:])
        chaves = [(l[0], l[1], l[2]) for l in depois[1:]]
        self.assertEqual(len(chaves), len(set(chaves)), "chave (data, uf, slug) repetida")
        novas = depois[len(antigas):]
        chaves_novas = [(l[0], l[1], l[2]) for l in novas]
        self.assertEqual(chaves_novas, sorted(chaves_novas), "linhas novas fora da ordem (data, uf, slug)")

    def test_estadual_linhas_novas(self):
        antigas = self._linhas(self.est_antes)
        chaves_antigas = {(l[0], l[1], l[2]) for l in antigas[1:]}
        # a base já vai até 09-01 para Alan Rick e Renan Filho de AL: só 09-02 a 09-05 entram
        self.assertIn(("2026-09-01", "AC", "ac-gov-alan-rick"), chaves_antigas)
        self.assertIn(("2026-09-01", "AL", "al-gov-renan-filho"), chaves_antigas)
        novas = self._linhas(self.est_depois)[len(antigas):]
        esperadas = sorted([("2026-09-0%d" % d, "AC", "ac-gov-alan-rick") for d in range(2, 6)]
                           + [("2026-09-0%d" % d, "AL", "al-gov-renan-filho") for d in range(2, 6)])
        self.assertEqual([(l[0], l[1], l[2]) for l in novas], esperadas)
        self.assertIn("dados/estados/wikipedia-estados.csv: 8 linhas acrescentadas", self.saida)
        for l in novas:
            self.assertEqual(len(l), 6)
            self.assertTrue(self.fonte_esperada(l[5]), l[5])
        por = {(l[2], l[0]): l for l in novas}
        self.assertEqual(por[("ac-gov-alan-rick", "2026-09-02")][3:5], ["Alan Rick", "44"])
        self.assertEqual(por[("ac-gov-alan-rick", "2026-09-05")][4], "29")
        self.assertEqual(por[("al-gov-renan-filho", "2026-09-04")][3:5], ["Renan Filho", "304"])
        # pe-gov-renan está rejeitado como homônimo: nada novo para ele, e o histórico fica como está
        self.assertFalse([l for l in novas if l[2] == "pe-gov-renan"])
        self.assertEqual(sum(1 for l in antigas if l[2] == "pe-gov-renan"),
                         sum(1 for l in self._linhas(self.est_depois) if l[2] == "pe-gov-renan"))

    def test_saida_relata_contagens(self):
        self.assertIn("(8 verbetes pedidos)", self.saida)
        self.assertIn("(239 verbetes aceitos pedidos)", self.saida)
        self.assertIn("candidatos sem wikipedia_titulo em candidatos.csv, fora da coleta: "
                      "Clariana Barão; Edmilson Costa; Hertz Dias; Rui Costa Pimenta; Wilson Grassi", self.saida)
        # 8 títulos nacionais + 239 estaduais, sem repetição entre as listas: 247 chamadas, uma por título;
        # seis trouxeram dados (Cury, Samara, Pablo, Lula, Alan Rick, Renan Filho) e 241 caíram em 404
        self.assertIn("chamadas à API: 247; verbetes com dados na janela: 6", self.saida)
        self.assertIn("verbetes sem resposta: 241 (sem dados no período: 241; erro: 0)", self.saida)
        self.assertIn("sem dados: Renan Santos (404, sem dados no período)", self.saida)
        # nenhuma linha de erro (a linha-resumo traz "erro: 0", que não conta)
        self.assertNotIn("\nerro:", self.saida)
        self.assertNotIn("\n  erro:", self.saida)

    def test_segunda_execucao_nao_muda_nada(self):
        saida = self.rodar(self.raiz, self.offline, "--desde", self.DESDE, "--ate", self.ATE)
        self.assertIn("dados/wikipedia-pageviews.csv: 0 linhas acrescentadas", saida)
        self.assertIn("dados/estados/wikipedia-estados.csv: 0 linhas acrescentadas", saida)
        self.assertEqual(ler_bytes(os.path.join(self.raiz, NACIONAL)), self.nac_depois)
        self.assertEqual(ler_bytes(os.path.join(self.raiz, ESTADUAL)), self.est_depois)

    def _linhas(self, dados):
        return list(csv.reader(io.StringIO(dados.decode("utf-8-sig"), newline="")))


class InsercaoNoMeio(Base):
    """Janela antiga: a linha nova entra no lugar certo da ordenação sem mover nenhuma antiga."""

    def test_nacional_insere_ordenado(self):
        raiz, offline = self.montar_copia("meio")
        antes = ler_bytes(os.path.join(raiz, NACIONAL))
        # Samara só tem série a partir de 04-09; 04-02 é chave nova no meio do arquivo
        gravar_resposta(offline, "Samara Martins", [("2026-04-02", 7)])
        gravar_resposta(offline, "Augusto Cury", [("2026-04-02", 999)])  # já existe: não entra
        saida = self.rodar(raiz, offline, "--desde", "2026-04-01", "--ate", "2026-04-03", "--so", "nacional")
        self.assertIn("dados/wikipedia-pageviews.csv: 1 linhas acrescentadas", saida)
        depois = ler_bytes(os.path.join(raiz, NACIONAL))
        conferir_bytes(self, depois)
        la = list(csv.reader(io.StringIO(antes.decode("utf-8-sig"), newline="")))
        ld = list(csv.reader(io.StringIO(depois.decode("utf-8-sig"), newline="")))
        self.assertEqual(len(ld), len(la) + 1)
        conferir_antigas_preservadas(self, la[1:], ld[1:])
        chaves = [(l[0], l[1]) for l in ld[1:]]
        self.assertEqual(chaves, sorted(chaves))
        i = chaves.index(("2026-04-02", "Samara Martins"))
        self.assertEqual(ld[1 + i][3], "7")
        self.assertEqual(chaves[i - 1], ("2026-04-02", "Ronaldo Caiado"))
        self.assertEqual(chaves[i + 1], ("2026-04-03", "Augusto Cury"))
        # o valor 999 para um dia já existente foi ignorado
        for l in ld[1:]:
            if (l[0], l[1]) == ("2026-04-02", "Augusto Cury"):
                self.assertNotEqual(l[3], "999")
        # o estadual não foi tocado (--so nacional)
        self.assertEqual(ler_bytes(os.path.join(raiz, ESTADUAL)), ler_congelado(ESTADUAL))

    def test_estadual_preenche_lacuna_no_fim(self):
        raiz, offline = self.montar_copia("lacuna")
        antes = ler_bytes(os.path.join(raiz, ESTADUAL))
        la = list(csv.reader(io.StringIO(antes.decode("utf-8-sig"), newline="")))
        chaves = {(l[0], l[1], l[2]) for l in la[1:]}
        aceitos = self.mod.verbetes_estaduais(raiz)
        # um verbete aceito cuja série não cobre 2026-01-02 (verbete criado depois ou dia omitido)
        alvo = next((uf, slug, verbete) for uf, slug, verbete in aceitos
                    if ("2026-01-02", uf, slug) not in chaves)
        uf, slug, verbete = alvo
        gravar_resposta(offline, verbete, [("2026-01-02", 0), ("2026-01-03", 3)])
        saida = self.rodar(raiz, offline, "--desde", "2026-01-02", "--ate", "2026-01-02", "--so", "estadual")
        self.assertIn("dados/estados/wikipedia-estados.csv: 1 linhas acrescentadas", saida)
        depois = ler_bytes(os.path.join(raiz, ESTADUAL))
        conferir_bytes(self, depois)
        self.assertTrue(depois.startswith(antes))
        ld = list(csv.reader(io.StringIO(depois.decode("utf-8-sig"), newline="")))
        self.assertEqual(ld[-1][:5], ["2026-01-02", uf, slug, verbete, "0"])
        self.assertEqual(len(ld), len(la) + 1)
        # o nacional não foi tocado (--so estadual)
        self.assertEqual(ler_bytes(os.path.join(raiz, NACIONAL)), ler_congelado(NACIONAL))


class Janela(Base):
    def test_hoje_em_brasilia(self):
        utc = dt.timezone.utc
        # 1h30 UTC de 6/9 ainda é 5/9 em Brasília (UTC-3)
        self.assertEqual(self.mod.hoje_brasilia(dt.datetime(2026, 9, 6, 1, 30, tzinfo=utc)), dt.date(2026, 9, 5))
        self.assertEqual(self.mod.hoje_brasilia(dt.datetime(2026, 9, 6, 3, 30, tzinfo=utc)), dt.date(2026, 9, 6))
        self.assertEqual(self.mod.hoje_brasilia(dt.datetime(2026, 9, 6, 2, 59, tzinfo=utc)), dt.date(2026, 9, 5))

    def test_janela_padrao(self):
        self.assertEqual(self.mod.janela_padrao(dt.date(2026, 9, 6)), (dt.date(2026, 9, 2), dt.date(2026, 9, 5)))
        self.assertEqual(self.mod.janela_padrao(dt.date(2026, 1, 2)), (dt.date(2025, 12, 29), dt.date(2026, 1, 1)))

    def test_ate_hoje_e_recuado_e_desde_invertido_falha(self):
        raiz, offline = self.montar_copia("janela")
        hoje = self.mod.hoje_brasilia()
        saida = self.rodar(raiz, offline, "--ate", hoje.isoformat(), "--so", "nacional")
        self.assertIn("aviso: a API só fecha o dia anterior", saida)
        ontem = hoje - dt.timedelta(days=1)
        self.assertIn("janela %s a %s" % (ontem - dt.timedelta(days=3), ontem), saida)
        self.assertIn("0 linhas acrescentadas", saida)
        saida = self.rodar(raiz, offline, "--desde", "2026-09-05", "--ate", "2026-09-02", esperado=1)
        self.assertIn("erro: --desde 2026-09-05 é posterior a --ate 2026-09-02", saida)
        # nada foi gravado
        self.assertEqual(ler_bytes(os.path.join(raiz, NACIONAL)), ler_congelado(NACIONAL))


class Titulos(Base):
    def test_titulo_limpo(self):
        self.assertEqual(self.mod.titulo_limpo("Pablo Marçal (URL canônico Pablo_Henrique_Costa_Marçal)"), "Pablo Marçal")
        self.assertEqual(self.mod.titulo_limpo("Eduardo Gomes (desambiguação)"), "Eduardo Gomes (desambiguação)")
        self.assertEqual(self.mod.titulo_limpo("  Renan Santos "), "Renan Santos")
        self.assertEqual(self.mod.titulo_limpo(""), "")
        self.assertEqual(self.mod.titulo_limpo(None), "")

    def test_artigo_para_api_e_url(self):
        self.assertEqual(self.mod.artigo_para_api("Luiz Inácio Lula da Silva"), "Luiz_In%C3%A1cio_Lula_da_Silva")
        self.assertEqual(self.mod.artigo_para_api("Flávio Bolsonaro"), "Fl%C3%A1vio_Bolsonaro")
        self.assertEqual(self.mod.artigo_para_api("A/B & C?"), "A%2FB_%26_C%3F")
        self.assertEqual(self.mod.url_verbete("Luiz Inácio Lula da Silva"),
                         "https://pt.wikipedia.org/wiki/Luiz_Inácio_Lula_da_Silva")
        self.assertIn("/pt.wikipedia/all-access/user/{artigo}/daily/{desde}/{ate}", self.mod.REST)

    def test_listas_congeladas(self):
        nac, sem = self.mod.verbetes_nacionais(RAIZ)
        self.assertEqual(dict(nac)["Pablo Marçal"], "Pablo Marçal")
        self.assertEqual(dict(nac)["Lula"], "Luiz Inácio Lula da Silva")
        self.assertEqual(len(nac), 8)
        self.assertEqual(sem, ["Clariana Barão", "Edmilson Costa", "Hertz Dias", "Rui Costa Pimenta", "Wilson Grassi"])
        est = self.mod.verbetes_estaduais(RAIZ)
        slugs = [s for _, s, _ in est]
        self.assertEqual(len(est), 239)
        self.assertIn("al-gov-renan-filho", slugs)
        self.assertNotIn("pe-gov-renan", slugs, "pe-gov-renan aponta para o Renan Filho de AL e está rejeitado")
        self.assertEqual(len(set(slugs)), len(slugs))

    def test_serie_da_resposta(self):
        desde, ate = dt.date(2026, 9, 2), dt.date(2026, 9, 5)
        itens = [item("X", "2026-09-01", 9), item("X", "2026-09-02", 0), item("X", "2026-09-04", 12),
                 item("X", "2026-09-06", 3), {"timestamp": "lixo", "views": 1}, {"timestamp": "2026090300", "views": "7"}]
        self.assertEqual(self.mod.serie_da_resposta(itens, desde, ate), {"2026-09-02": 0, "2026-09-04": 12})


class Gravacao(Base):
    def test_reescrever_os_csvs_reais_nao_muda_um_byte(self):
        for rel, colunas in ((NACIONAL, self.mod.COLUNAS_NACIONAL), (ESTADUAL, self.mod.COLUNAS_ESTADUAL)):
            origem = os.path.join(RAIZ, rel)
            linhas = self.mod.ler_csv(origem, colunas)
            destino = os.path.join(self.base, "roundtrip-" + os.path.basename(rel))
            self.mod.gravar_csv(destino, colunas, linhas)
            self.assertEqual(ler_bytes(destino), ler_bytes(origem), rel)
            self.assertFalse(os.path.exists(destino + ".parcial"))

    def test_entrada_ausente_ou_fora_do_contrato(self):
        raiz, offline = self.montar_copia("entrada")
        os.remove(os.path.join(raiz, NACIONAL))
        saida = self.rodar(raiz, offline, "--so", "nacional", esperado=1)
        self.assertIn("erro: arquivo não encontrado", saida)
        with open(os.path.join(raiz, ESTADUAL), "w", newline="", encoding="utf-8-sig") as f:
            f.write("data,uf,slug,pageviews\r\n")
        saida = self.rodar(raiz, offline, "--so", "estadual", esperado=1)
        self.assertIn("cabeçalho fora do contrato", saida)


class Resposta:
    def __init__(self, corpo):
        self.corpo = corpo

    def read(self):
        return self.corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def erro_http(codigo, cabecalhos=None):
    h = Message()
    for k, v in (cabecalhos or {}).items():
        h[k] = v
    return urllib.error.HTTPError("https://wikimedia.org/x", codigo, "erro", h, io.BytesIO(b""))


class Rede(Base):
    """Cliente REST com respostas simuladas: cabeçalhos, 404, 429 com Retry-After, 5xx, rede."""

    def cliente(self, respostas):
        pedidos, esperas = [], []
        fila = list(respostas)

        def abrir(req, timeout=None):
            pedidos.append(req)
            r = fila.pop(0)
            if isinstance(r, Exception):
                raise r
            return Resposta(r)

        c = self.mod.ClienteRest(pausa=0.3, log=lambda *a: None, dormir=esperas.append, abrir=abrir)
        return c, pedidos, esperas

    def test_cabecalhos_e_url(self):
        corpo = json.dumps({"items": [item("Alan Rick", "2026-09-05", 29)]}).encode("utf-8")
        c, pedidos, esperas = self.cliente([corpo])
        itens, situacao = c.pageviews("Luiz Inácio Lula da Silva", dt.date(2026, 9, 2), dt.date(2026, 9, 5))
        self.assertEqual(situacao, "ok")
        self.assertEqual(itens[0]["views"], 29)
        req = pedidos[0]
        self.assertEqual(req.full_url, "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                         "pt.wikipedia/all-access/user/Luiz_In%C3%A1cio_Lula_da_Silva/daily/20260902/20260905")
        self.assertEqual(req.get_header("User-agent"), self.mod.UA)
        self.assertEqual(req.get_header("Accept"), "application/json")
        self.assertEqual(esperas, [])

    def test_404_nao_e_erro(self):
        c, pedidos, esperas = self.cliente([erro_http(404)])
        self.assertEqual(c.pageviews("X", dt.date(2026, 9, 2), dt.date(2026, 9, 5)), ([], "404"))
        self.assertEqual(esperas, [])

    def test_429_espera_retry_after_e_tenta_de_novo(self):
        corpo = json.dumps({"items": []}).encode("utf-8")
        c, pedidos, esperas = self.cliente([erro_http(429, {"Retry-After": "7"}), corpo])
        self.assertEqual(c.pageviews("X", dt.date(2026, 9, 2), dt.date(2026, 9, 5)), ([], "ok"))
        self.assertEqual(len(pedidos), 2)
        self.assertEqual(esperas, [7, 0.3])

    def test_503_sem_retry_after_usa_espera_padrao(self):
        corpo = json.dumps({"items": []}).encode("utf-8")
        c, pedidos, esperas = self.cliente([erro_http(503), corpo])
        self.assertEqual(c.pageviews("X", dt.date(2026, 9, 2), dt.date(2026, 9, 5))[1], "ok")
        self.assertEqual(esperas, [self.mod.ESPERA_PADRAO, 0.3])

    def test_retry_after_em_data_http_e_teto(self):
        alvo = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=30)
        h = Message()
        h["Retry-After"] = alvo.strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.assertTrue(25 <= self.mod._retry_after(h) <= 31)
        h = Message()
        h["Retry-After"] = "99999"
        self.assertEqual(self.mod._retry_after(h), self.mod.ESPERA_MAXIMA)
        h = Message()
        h["Retry-After"] = "isso não é número"
        self.assertEqual(self.mod._retry_after(h), self.mod.ESPERA_PADRAO)
        self.assertEqual(self.mod._retry_after(None), self.mod.ESPERA_PADRAO)

    def test_5xx_persistente_esgota_tentativas(self):
        c, pedidos, esperas = self.cliente([erro_http(500)] * self.mod.TENTATIVAS)
        self.assertEqual(c.pageviews("X", dt.date(2026, 9, 2), dt.date(2026, 9, 5)), ([], "HTTP 500"))
        self.assertEqual(len(pedidos), self.mod.TENTATIVAS)

    def test_403_nao_insiste(self):
        c, pedidos, esperas = self.cliente([erro_http(403)])
        self.assertEqual(c.pageviews("X", dt.date(2026, 9, 2), dt.date(2026, 9, 5)), ([], "HTTP 403"))
        self.assertEqual(len(pedidos), 1)

    def test_falha_de_rede_tenta_de_novo(self):
        corpo = json.dumps({"items": []}).encode("utf-8")
        c, pedidos, esperas = self.cliente([urllib.error.URLError("sem rede"), corpo])
        self.assertEqual(c.pageviews("X", dt.date(2026, 9, 2), dt.date(2026, 9, 5))[1], "ok")
        self.assertEqual(esperas, [self.mod.ESPERA_PADRAO, 0.3])

    def test_pausa_entre_verbetes(self):
        corpo = json.dumps({"items": []}).encode("utf-8")
        c, pedidos, esperas = self.cliente([corpo, corpo, corpo])
        for t in ("A", "B", "C"):
            c.pageviews(t, dt.date(2026, 9, 2), dt.date(2026, 9, 5))
        self.assertEqual(esperas, [0.3, 0.3])

    def test_coleta_classifica_e_cacheia(self):
        corpo = json.dumps({"items": [item("Renan Filho", "2026-09-03", 5)]}).encode("utf-8")
        c, pedidos, esperas = self.cliente([corpo, erro_http(404), erro_http(403)])
        coleta = self.mod.Coleta(c, dt.date(2026, 9, 2), dt.date(2026, 9, 5))
        self.assertEqual(coleta.serie("Renan Filho"), {"2026-09-03": 5})
        self.assertEqual(coleta.serie("Renan Filho"), {"2026-09-03": 5})  # cache: sem nova chamada
        self.assertEqual(coleta.serie("Ninguém"), {})
        self.assertEqual(coleta.serie("Bloqueado"), {})
        self.assertEqual(len(pedidos), 3)
        self.assertEqual(coleta.com_dados, 1)
        self.assertEqual(coleta.sem_dados, [("Ninguém", "404, sem dados no período")])
        self.assertEqual(coleta.erros, [("Bloqueado", "HTTP 403")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
