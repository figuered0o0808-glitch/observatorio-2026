# -*- coding: utf-8 -*-
"""Teste do guarda de dados (testes/guarda_dados.py).

Monta um repositório git temporário com cópias de alguns CSVs pequenos do projeto (série diária,
Instagram estadual, pageviews nacionais, candidatos, redes-fontes), um recorte de três UFs do
consolidado estadual e do dump JSON da Wikipédia, um recorte do Pará do CSV bruto da Wikipédia e
um recorte do pageviews estadual, commita tudo e depois aplica uma mutação por teste: linha
removida, vazio que vira 0, arquivo sem BOM, quebra LF ou CR solta, data futura ou inválida,
chave duplicada, fonte vazia, arquivo intocável alterado, queda de contagem nos regravados, UF
que some, rodada nova com data futura, dump com ERRO. O guarda tem de reprovar cada uma delas e
aprovar o acréscimo legítimo, o zero que vem da fonte, a tabela ou coluna que a Wikipédia insere
no meio da página (o que desloca a numeração das linhas antigas sem mudar dado) e a alteração
liberada por --permitir.

Só biblioteca padrão e o git da máquina. Nada em dados/ é tocado: os arquivos são copiados para a
pasta temporária (em GUARDA_TESTE_DIR, se definida, senão na pasta temporária do sistema) e o
guarda é apontado para lá com --raiz. GUARDA_MANTER=1 deixa a pasta no fim, para inspeção.

Uso:
    python3 testes/test_guarda.py
"""
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARDA = os.path.join(RAIZ, "testes", "guarda_dados.py")
DADOS = os.path.join(RAIZ, "dados")
BOM = b"\xef\xbb\xbf"

COPIAS = (
    "dados/serie-diaria.csv",
    "dados/estados/instagram-estados.csv",
    "dados/wikipedia-pageviews.csv",
    "dados/candidatos.csv",
    "dados/redes-fontes.csv",
)
UFS_RECORTE = ("AC", "AL", "AP")


def carregar_guarda():
    spec = importlib.util.spec_from_file_location("guarda_dados", GUARDA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ler_csv_bytes(dados):
    linhas = list(csv.reader(io.StringIO(dados.decode("utf-8-sig"), newline="")))
    return linhas[0], linhas[1:]


def csv_bytes(cabecalho, linhas, bom=True, crlf=True):
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n" if crlf else "\n")
    w.writerow(cabecalho)
    w.writerows(linhas)
    dados = buf.getvalue().encode("utf-8")
    return (BOM + dados) if bom else dados


def git(pasta, *args):
    p = subprocess.run(["git", "-C", pasta, "-c", "user.name=teste", "-c", "user.email=teste@example.com"] + list(args),
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout


class Repositorio:
    """Repositório temporário com os arquivos do recorte commitados em HEAD."""

    def __init__(self):
        base = os.environ.get("GUARDA_TESTE_DIR")
        if base:
            os.makedirs(base, exist_ok=True)
        self.pasta = tempfile.mkdtemp(prefix="guarda-", dir=base or None)
        os.makedirs(os.path.join(self.pasta, "dados", "estados"))
        with open(os.path.join(self.pasta, ".gitattributes"), "wb") as f:
            f.write(b"* -text\n")
        for rel in COPIAS:
            shutil.copyfile(os.path.join(RAIZ, rel), os.path.join(self.pasta, rel))
        self._recorte_csv("dados/estados/pesquisas-estados-consolidado.csv", lambda l, h: l[h.index("uf")] in UFS_RECORTE)
        self._recorte_csv("dados/estados/wikipedia-estados.csv", lambda l, h: l[h.index("uf")] == "AC")
        # o Pará tem em HEAD seis linhas de segundo turno com campo_fim em novembro e dezembro de 2026
        # (erro de ano da própria página); elas não podem virar 'linha nova' quando a tabela se desloca
        self._recorte_csv("dados/estados/pesquisas-estados-wiki.csv", lambda l, h: l[h.index("uf")] == "PA")
        with open(os.path.join(DADOS, "estados", "_wiki-pesquisas-estados.json"), encoding="utf-8") as f:
            dump = json.load(f)
        paginas = {t: x for t, x in dump["paginas"].items() if t.endswith(("no Acre", "em Alagoas", "no Amapá"))}
        assert len(paginas) == 3, sorted(paginas)
        self.escrever_json("dados/estados/_wiki-pesquisas-estados.json",
                           {"coletado": dump["coletado"], "fonte": dump["fonte"], "paginas": paginas})
        # um dump fora do escopo do guarda, para conferir que só gera aviso
        self.escrever_json("dados/estados/_wikipedia-estados.json", {"coletado": "2026-09-02", "series": {}})
        git(self.pasta, "init", "-q")
        git(self.pasta, "add", "-A")
        git(self.pasta, "commit", "-q", "-m", "recorte para o teste do guarda")

    def _recorte_csv(self, rel, filtro):
        with open(os.path.join(RAIZ, rel), "rb") as f:
            cab, linhas = ler_csv_bytes(f.read())
        recorte = [l for l in linhas if filtro(l, cab)]
        assert len(recorte) > 100, rel
        self.escrever(rel, csv_bytes(cab, recorte))

    def caminho(self, rel):
        return os.path.join(self.pasta, rel)

    def escrever(self, rel, dados):
        os.makedirs(os.path.dirname(self.caminho(rel)), exist_ok=True)
        with open(self.caminho(rel), "wb") as f:
            f.write(dados)

    def escrever_json(self, rel, obj):
        self.escrever(rel, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def ler(self, rel):
        with open(self.caminho(rel), "rb") as f:
            return f.read()

    def ler_csv(self, rel):
        return ler_csv_bytes(self.ler(rel))

    def ler_json(self, rel):
        return json.loads(self.ler(rel).decode("utf-8"))

    def restaurar(self):
        git(self.pasta, "checkout", "-q", "--", ".")
        git(self.pasta, "clean", "-fdq")

    def remover(self):
        shutil.rmtree(self.pasta, ignore_errors=True)


class Guarda(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = carregar_guarda()
        cls.hoje = cls.mod.hoje_brasilia()
        cls.repo = Repositorio()

    @classmethod
    def tearDownClass(cls):
        if not os.environ.get("GUARDA_MANTER"):
            cls.repo.remover()

    def setUp(self):
        self.repo.restaurar()

    def rodar(self, *args):
        p = subprocess.run([sys.executable, GUARDA, "--raiz", self.repo.pasta, "--hoje", self.hoje.isoformat()] + list(args),
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.stderr, "", p.stderr)
        return p.returncode, p.stdout

    def aprova(self, *args):
        rc, saida = self.rodar(*args)
        self.assertEqual(rc, 0, saida)
        self.assertNotIn("FALHA", saida)
        return saida

    def reprova(self, trecho, *args, arquivo=None):
        rc, saida = self.rodar(*args)
        self.assertEqual(rc, 1, saida)
        linhas = [l for l in saida.splitlines() if l.startswith("FALHA") and trecho in l and (arquivo is None or arquivo in l)]
        self.assertTrue(linhas, "esperava FALHA com %r%s; saída:\n%s" % (trecho, (" em " + arquivo) if arquivo else "", saida))
        return saida

    def dia(self, delta):
        return (self.hoje + dt.timedelta(days=delta)).isoformat()

    # linhas de acréscimo usadas em vários testes
    def linha_pageviews(self, delta, candidato="Augusto Cury", pageviews="123", fonte=None):
        if fonte is None:
            fonte = "Wikimedia REST API, pageviews per-article, all-access, agente user (coleta própria %s)" % self.hoje.isoformat()
        return [self.dia(delta), candidato, candidato, pageviews, fonte, "https://pt.wikipedia.org/wiki/Augusto_Cury", ""]

    def acrescentar(self, rel, novas, **kw):
        cab, linhas = self.repo.ler_csv(rel)
        self.repo.escrever(rel, csv_bytes(cab, linhas + novas, **kw))
        return cab, linhas

    # sem alteração e acréscimo legítimo

    def test_sem_alteracao_passa(self):
        saida = self.aprova()
        self.assertIn("OK    dados/serie-diaria.csv: sem alteração em relação a HEAD", saida)
        self.assertIn("0 falhas", saida)

    def test_acrescimo_legitimo_passa(self):
        cab, antes = self.acrescentar("dados/wikipedia-pageviews.csv", [self.linha_pageviews(-1), self.linha_pageviews(-1, "Lula", "4411")])
        self.acrescentar("dados/estados/instagram-estados.csv", [[self.dia(0), "AC", "ac-gov-alan-rick", "alanrickm", "83001", "0", "Alan Rick", "ok",
                                                                   "coleta própria, perfil público do Instagram via navegador, %s" % self.hoje]])
        self.acrescentar("dados/serie-diaria.csv", [[self.dia(0), "Lula", "instagram", "9000000", "", "", "", "coleta própria %s" % self.hoje, "https://www.instagram.com/lulaoficial/", ""]])
        saida = self.aprova()
        self.assertIn("dados/wikipedia-pageviews.csv: contagem %d -> %d (+2)" % (len(antes), len(antes) + 2), saida)
        self.assertIn("dados/wikipedia-pageviews.csv: 2 linha(s) nova(s) com data válida até %s" % self.dia(1), saida)
        self.assertIn("dados/estados/instagram-estados.csv: 1 linha(s) nova(s) com fonte preenchida", saida)

    def test_data_de_amanha_passa_pela_tolerancia(self):
        self.acrescentar("dados/wikipedia-pageviews.csv", [self.linha_pageviews(1)])
        self.aprova()

    def test_zero_vindo_da_fonte_passa(self):
        """0 devolvido pela Wikimedia é valor observado; só vazio virando 0 é barrado."""
        fonte = "Wikimedia REST API, pageviews per-article, all-access, agente user, coleta própria %s" % self.hoje
        self.acrescentar("dados/estados/wikipedia-estados.csv", [[self.dia(-1), "AC", "ac-gov-alan-rick", "Alan Rick", "0", fonte]])
        saida = self.aprova()
        self.assertIn("dados/estados/wikipedia-estados.csv: 1 linha(s) nova(s) com data válida", saida)

    # mutações que o guarda tem de reprovar

    def test_linha_removida_reprova(self):
        cab, linhas = self.repo.ler_csv("dados/serie-diaria.csv")
        self.repo.escrever("dados/serie-diaria.csv", csv_bytes(cab, linhas[:50] + linhas[51:]))
        saida = self.reprova("chave(s) de HEAD desapareceram", arquivo="dados/serie-diaria.csv")
        self.assertIn("dados/serie-diaria.csv: contagem caiu de %d para %d" % (len(linhas), len(linhas) - 1), saida)

    def test_vazio_vira_zero_reprova(self):
        cab, linhas = self.repo.ler_csv("dados/serie-diaria.csv")
        col = cab.index("seguidores")
        alvo = next(l for l in linhas if l[col] == "")
        alvo[col] = "0"
        self.repo.escrever("dados/serie-diaria.csv", csv_bytes(cab, linhas))
        saida = self.reprova("viraram zero", arquivo="dados/serie-diaria.csv")
        self.assertIn("coluna seguidores", saida)
        self.assertIn("mudaram de conteúdo", saida)

    def test_vazio_vira_zero_ponto_zero_no_regravado_reprova(self):
        rel = "dados/estados/pesquisas-estados-consolidado.csv"
        cab, linhas = self.repo.ler_csv(rel)
        col = cab.index("contratante")
        alvo = next(l for l in linhas if l[col] == "")
        alvo[col] = "0.0"
        self.repo.escrever(rel, csv_bytes(cab, linhas))
        saida = self.reprova("viraram zero", arquivo=rel)
        self.assertIn("coluna contratante", saida)

    def test_linha_existente_alterada_reprova(self):
        cab, linhas = self.repo.ler_csv("dados/serie-diaria.csv")
        linhas[3][cab.index("observacao")] = "texto trocado"
        self.repo.escrever("dados/serie-diaria.csv", csv_bytes(cab, linhas))
        self.reprova("1 linha(s) existente(s) mudaram de conteúdo", arquivo="dados/serie-diaria.csv")

    def test_sem_bom_reprova(self):
        dados = self.repo.ler("dados/estados/instagram-estados.csv")
        self.assertTrue(dados.startswith(BOM))
        self.repo.escrever("dados/estados/instagram-estados.csv", dados[3:])
        self.reprova("não começa com o BOM", arquivo="dados/estados/instagram-estados.csv")

    def test_lf_solto_reprova(self):
        dados = self.repo.ler("dados/estados/instagram-estados.csv")
        self.repo.escrever("dados/estados/instagram-estados.csv", dados.replace(b"\r\n", b"\n"))
        saida = self.reprova("LF sem CR", arquivo="dados/estados/instagram-estados.csv")
        self.assertIn("começa com o BOM", saida)

    def test_cr_solto_reprova(self):
        """Arquivo só com CR (sem LF nenhum) não é CRLF."""
        dados = self.repo.ler("dados/estados/instagram-estados.csv")
        self.repo.escrever("dados/estados/instagram-estados.csv", dados.replace(b"\r\n", b"\r"))
        saida = self.reprova("CR sem LF", arquivo="dados/estados/instagram-estados.csv")
        self.assertNotIn("quebras de linha CRLF", saida)

    def test_sem_crlf_no_fim_reprova(self):
        dados = self.repo.ler("dados/estados/instagram-estados.csv")
        self.assertTrue(dados.endswith(b"\r\n"))
        self.repo.escrever("dados/estados/instagram-estados.csv", dados[:-2])
        self.reprova("não termina em CRLF", arquivo="dados/estados/instagram-estados.csv")

    def test_data_futura_reprova(self):
        self.acrescentar("dados/wikipedia-pageviews.csv", [self.linha_pageviews(2)])
        saida = self.reprova("posterior a %s" % self.dia(1), arquivo="dados/wikipedia-pageviews.csv")
        self.assertIn(self.dia(2), saida)

    def test_data_invalida_reprova(self):
        cab, linhas = self.repo.ler_csv("dados/wikipedia-pageviews.csv")
        ruim1 = self.linha_pageviews(-1)
        ruim1[0] = "2026-02-30"
        ruim2 = self.linha_pageviews(-1, "Lula")
        ruim2[0] = "06/09/2026"
        self.repo.escrever("dados/wikipedia-pageviews.csv", csv_bytes(cab, linhas + [ruim1, ruim2]))
        saida = self.reprova("fora de AAAA-MM-DD", arquivo="dados/wikipedia-pageviews.csv")
        self.assertIn("'2026-02-30'", saida)
        self.assertIn("'06/09/2026'", saida)

    def test_chave_duplicada_reprova(self):
        cab, linhas = self.repo.ler_csv("dados/wikipedia-pageviews.csv")
        self.repo.escrever("dados/wikipedia-pageviews.csv", csv_bytes(cab, linhas + [list(linhas[10])]))
        saida = self.reprova("chave(s) duplicada(s)", arquivo="dados/wikipedia-pageviews.csv")
        self.assertIn(linhas[10][0], saida)

    def test_fonte_vazia_reprova(self):
        self.acrescentar("dados/wikipedia-pageviews.csv", [self.linha_pageviews(-1, fonte="")])
        self.reprova("fonte vazia", arquivo="dados/wikipedia-pageviews.csv")

    def test_cabecalho_alterado_reprova(self):
        cab, linhas = self.repo.ler_csv("dados/estados/instagram-estados.csv")
        self.repo.escrever("dados/estados/instagram-estados.csv", csv_bytes(cab + ["extra"], [l + [""] for l in linhas]))
        self.reprova("cabeçalho mudou", arquivo="dados/estados/instagram-estados.csv")

    def test_arquivo_removido_reprova(self):
        os.remove(self.repo.caminho("dados/serie-diaria.csv"))
        self.reprova("arquivo removido", arquivo="dados/serie-diaria.csv")

    def test_csv_novo_sem_regra_reprova(self):
        self.repo.escrever("dados/estados/novo.csv", csv_bytes(["data", "valor", "fonte"], [[self.dia(0), "1", "x"]]))
        self.reprova("sem regra no guarda", arquivo="dados/estados/novo.csv")

    # arquivos que a automação não toca

    def test_intocavel_alterado_reprova_e_permitir_libera(self):
        cab, linhas = self.repo.ler_csv("dados/candidatos.csv")
        linhas[0][cab.index("ocupacao")] = "outra ocupação"
        self.repo.escrever("dados/candidatos.csv", csv_bytes(cab, linhas))
        self.reprova("só muda por decisão humana", arquivo="dados/candidatos.csv")
        saida = self.aprova("--permitir", "dados/candidatos.csv")
        self.assertIn("AVISO dados/candidatos.csv: conteúdo alterado; aceito por --permitir", saida)
        self.assertIn("OK    dados/candidatos.csv: começa com o BOM", saida)

    def test_permitir_ainda_exige_a_forma(self):
        cab, linhas = self.repo.ler_csv("dados/candidatos.csv")
        self.repo.escrever("dados/candidatos.csv", csv_bytes(cab, linhas, bom=False))
        self.reprova("não começa com o BOM", "--permitir", "dados/candidatos.csv", arquivo="dados/candidatos.csv")

    def test_arquivo_sem_bom_em_head_fica_dispensado_do_bom(self):
        rel = "dados/redes-fontes.csv"
        dados = self.repo.ler(rel)
        self.assertFalse(dados.startswith(BOM))
        self.repo.escrever(rel, dados + b"x,y,z,w,v,u,t,s,r,q\r\n")
        self.reprova("só muda por decisão humana", arquivo=rel)
        saida = self.aprova("--permitir", rel)
        self.assertIn("AVISO dados/redes-fontes.csv: sem BOM, como já estava em HEAD", saida)

    # regravados: consolidado estadual

    def test_regravado_aceita_queda_pequena_e_recusa_grande(self):
        rel = "dados/estados/pesquisas-estados-consolidado.csv"
        cab, linhas = self.repo.ler_csv(rel)
        n = len(linhas)
        pouco = int(n * 0.01)
        self.repo.escrever(rel, csv_bytes(cab, linhas[:10] + linhas[10 + pouco:]))
        saida = self.aprova()
        self.assertIn("%s: contagem %d -> %d" % (rel, n, n - pouco), saida)
        muito = int(n * 0.05) + 1
        self.repo.escrever(rel, csv_bytes(cab, linhas[:10] + linhas[10 + muito:]))
        self.reprova("contagem caiu", arquivo=rel)

    def test_regravado_uf_que_some_reprova(self):
        rel = "dados/estados/pesquisas-estados-consolidado.csv"
        cab, linhas = self.repo.ler_csv(rel)
        col = cab.index("uf")
        sem_ap = [l for l in linhas if l[col] != "AP"]
        # a queda em linhas pode ficar dentro dos 2%, então o teste força a regra da UF
        self.assertLess(len(linhas) - len(sem_ap), len(linhas) * 0.5)
        self.repo.escrever(rel, csv_bytes(cab, sem_ap + [l for l in linhas if l[col] == "AC"]))
        saida = self.reprova("UF(s) presentes em HEAD sumiram: AP", arquivo=rel)
        self.assertNotIn("sumiram: AC", saida)

    def test_regravado_revid_novo_passa(self):
        rel = "dados/estados/pesquisas-estados-consolidado.csv"
        cab, linhas = self.repo.ler_csv(rel)
        col = cab.index("revid")
        for l in linhas:
            l[col] = "99999999"
        self.repo.escrever(rel, csv_bytes(cab, linhas))
        saida = self.aprova()
        self.assertIn("%s: nenhuma linha nova" % rel, saida)

    def test_regravado_linha_nova_com_data_futura_reprova(self):
        rel = "dados/estados/pesquisas-estados-consolidado.csv"
        cab, linhas = self.repo.ler_csv(rel)
        nova = list(linhas[0])
        nova[cab.index("data_ref")] = self.dia(3)
        self.repo.escrever(rel, csv_bytes(cab, linhas + [nova]))
        self.reprova("data_ref posterior a", arquivo=rel)
        nova[cab.index("data_ref")] = self.dia(-1)
        self.repo.escrever(rel, csv_bytes(cab, linhas + [nova]))
        saida = self.aprova()
        self.assertIn("%s: 1 linha(s) nova(s) com data_ref válida" % rel, saida)

    # regravado: CSV bruto da Wikipédia, com chave posicional (secao, tabela, ordem_col)

    def test_regravado_tabela_e_coluna_deslocadas_passam(self):
        """A Wikipédia insere uma tabela ou uma coluna no meio da página: tabela e ordem_col das linhas
        seguintes mudam sem que nenhum dado mude, e o HEAD do Pará já traz campo_fim em 2026-11/12."""
        rel = "dados/estados/pesquisas-estados-wiki.csv"
        cab, linhas = self.repo.ler_csv(rel)
        ct, cc, cf = cab.index("tabela"), cab.index("ordem_col"), cab.index("campo_fim")
        self.assertGreaterEqual(sum(1 for l in linhas if l[cf] > self.dia(1)), 6)
        deslocadas = 0
        for l in linhas:
            if int(l[ct]) >= 6:
                l[ct] = str(int(l[ct]) + 1)
                deslocadas += 1
            if l[ct] == "1":
                l[cc] = str(int(l[cc]) + 1)
                deslocadas += 1
        self.assertGreater(deslocadas, 100)
        self.repo.escrever(rel, csv_bytes(cab, linhas))
        saida = self.aprova()
        self.assertIn("%s: nenhuma linha nova" % rel, saida)
        self.assertIn("%s: contagem %d -> %d (+0.0%%)" % (rel, len(linhas), len(linhas)), saida)

    def test_regravado_wiki_rodada_nova_com_data_futura_reprova(self):
        rel = "dados/estados/pesquisas-estados-wiki.csv"
        cab, linhas = self.repo.ler_csv(rel)
        nova = list(linhas[0])
        nova[cab.index("instituto_bruto")] = "Instituto Inventado"
        nova[cab.index("campo_inicio")] = self.dia(18)
        nova[cab.index("campo_fim")] = self.dia(20)
        self.repo.escrever(rel, csv_bytes(cab, linhas + [nova]))
        saida = self.reprova("1 linha(s) nova(s) com campo_fim posterior a %s" % self.dia(1), arquivo=rel)
        self.assertIn(self.dia(20), saida)
        nova[cab.index("campo_inicio")] = self.dia(-5)
        nova[cab.index("campo_fim")] = self.dia(-3)
        self.repo.escrever(rel, csv_bytes(cab, linhas + [nova]))
        saida = self.aprova()
        self.assertIn("%s: 1 linha(s) nova(s) com campo_fim válida" % rel, saida)
        self.assertIn("%s: 1 linha(s) nova(s) com pagina preenchida" % rel, saida)

    def test_regravado_wiki_vazio_vira_zero_reprova(self):
        rel = "dados/estados/pesquisas-estados-wiki.csv"
        cab, linhas = self.repo.ler_csv(rel)
        col = cab.index("outros")
        alvo = next(l for l in linhas if l[col] == "")
        alvo[col] = "0.0"
        self.repo.escrever(rel, csv_bytes(cab, linhas))
        saida = self.reprova("viraram zero", arquivo=rel)
        self.assertIn("coluna outros", saida)

    # regravado: dump JSON das páginas da Wikipédia

    def test_dump_pagina_que_some_reprova(self):
        rel = "dados/estados/_wiki-pesquisas-estados.json"
        j = self.repo.ler_json(rel)
        titulo_ap = next(t for t in j["paginas"] if t.endswith("no Amapá"))
        del j["paginas"][titulo_ap]
        self.repo.escrever_json(rel, j)
        self.reprova("UF(s) presentes em HEAD sumiram ou vieram com ERRO: AP", arquivo=rel)

    def test_dump_pagina_com_erro_reprova(self):
        rel = "dados/estados/_wiki-pesquisas-estados.json"
        j = self.repo.ler_json(rel)
        titulo_al = next(t for t in j["paginas"] if t.endswith("em Alagoas"))
        j["paginas"][titulo_al] = "ERRO HTTP 503 ao ler a página"
        self.repo.escrever_json(rel, j)
        saida = self.reprova("sumiram ou vieram com ERRO: AL", arquivo=rel)
        self.assertIn("1 página(s) com ERRO no dump novo", saida)

    def test_dump_aceita_queda_pequena_e_recusa_grande(self):
        rel = "dados/estados/_wiki-pesquisas-estados.json"
        j = self.repo.ler_json(rel)
        titulo_ac = next(t for t in j["paginas"] if t.endswith("no Acre"))
        total = sum(t.count("\n") + 1 for t in j["paginas"].values())
        linhas_ac = j["paginas"][titulo_ac].split("\n")
        corte = int(total * 0.01)
        j["paginas"][titulo_ac] = "\n".join(linhas_ac[:-corte])
        self.repo.escrever_json(rel, j)
        self.aprova()
        corte = int(total * 0.05) + 1
        self.assertLess(corte, len(linhas_ac))
        j["paginas"][titulo_ac] = "\n".join(linhas_ac[:-corte])
        self.repo.escrever_json(rel, j)
        self.reprova("texto compacto caiu", arquivo=rel)

    def test_dump_invalido_reprova(self):
        rel = "dados/estados/_wiki-pesquisas-estados.json"
        self.repo.escrever(rel, b'{"paginas": ')
        self.reprova("JSON inválido", arquivo=rel)
        self.repo.escrever_json(rel, {"coletado": "x", "fonte": "y"})
        self.reprova("sem a chave 'paginas'", arquivo=rel)

    # fora do escopo e erros de uso

    def test_dump_fora_do_escopo_so_avisa(self):
        self.repo.escrever_json("dados/estados/_wikipedia-estados.json", {"coletado": "2026-09-06", "series": {"x": "0906:1"}})
        saida = self.aprova()
        self.assertIn("AVISO dados/estados/_wikipedia-estados.json: alterado, fora do escopo do guarda (modificado)", saida)

    def test_ref_inexistente_sai_com_2(self):
        rc, saida = self.rodar("--ref", "nao-existe")
        self.assertEqual(rc, 2, saida)
        self.assertIn("não existe no repositório", saida)

    def test_comparacao_com_outra_ref(self):
        """Com --ref apontando para um commit anterior, o acréscimo já commitado conta como linha nova."""
        self.acrescentar("dados/wikipedia-pageviews.csv", [self.linha_pageviews(-1)])
        git(self.repo.pasta, "add", "-A")
        git(self.repo.pasta, "commit", "-q", "-m", "acréscimo")
        try:
            saida = self.aprova("--ref", "HEAD~1")
            self.assertIn("dados/wikipedia-pageviews.csv: 1 linha(s) nova(s) com data válida", saida)
            self.assertIn("OK    dados/wikipedia-pageviews.csv: sem alteração em relação a HEAD", self.aprova())
        finally:
            git(self.repo.pasta, "reset", "-q", "--hard", "HEAD~1")


class Unidades(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = carregar_guarda()

    def test_uf_do_titulo(self):
        f = self.mod.uf_do_titulo
        self.assertEqual(f("Pesquisas eleitorais para a eleição estadual de 2026 em Mato Grosso do Sul"), "MS")
        self.assertEqual(f("Pesquisas eleitorais para a eleição estadual de 2026 em Mato Grosso"), "MT")
        self.assertEqual(f("Pesquisas eleitorais para a eleição distrital de 2026 no Distrito Federal"), "DF")
        self.assertIsNone(f("Pesquisas de opinião para a eleição presidencial no Brasil em 2026"))

    def test_zero_reconhecido(self):
        z = self.mod.RE_ZERO
        for v in ("0", "0.0", "00", "0.00"):
            self.assertTrue(z.match(v), v)
        for v in ("", "0.5", "10", "-0", "0,0", "a"):
            self.assertFalse(z.match(v), v)

    def test_classificacao_cobre_os_csvs_do_projeto(self):
        """Todo CSV hoje em dados/ e dados/estados/ tem regra no guarda."""
        conhecidos = set(self.mod.CSV_ACRESCIMO) | set(self.mod.CSV_REGRAVADO) | set(self.mod.INTOCAVEIS)
        existentes = set()
        for pasta in self.mod.PASTAS:
            for nome in os.listdir(os.path.join(RAIZ, pasta)):
                if nome.endswith(".csv"):
                    existentes.add(pasta + "/" + nome)
        self.assertEqual(existentes - conhecidos, set(), "CSV sem regra no guarda")
        self.assertEqual(conhecidos - existentes, set(), "regra para CSV que não existe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
