# -*- coding: utf-8 -*-
"""Testes de mural/_resultados.py, a leitura do resultado oficial do TSE para o mural.

As apurações vêm das fixtures de testes/fixtures/resultados (zerado: cópia de dados/resultados
de 13/10/2026, com o 2º turno publicado zerado; parcial: 2º turno com 37,5% das seções; final:
2º turno apurado, números sintéticos). Os números esperados são lidos dos próprios CSVs da
fixture, nunca escritos aqui: o teste confere a regra de leitura, não o resultado de um dia.

No fim, o gerador inteiro roda numa cópia temporária com cada fixture e sem nenhuma, porque o
mural tem de sair inteiro nos quatro casos (sem os CSVs, ele cai no comportamento de pesquisa).

Uso:
    python3 -m unittest testes.test_resultados
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(RAIZ, "testes", "fixtures", "resultados")
sys.path.insert(0, os.path.join(RAIZ, "mural"))
import _resultados as R  # noqa: E402


def ler_csv(pasta, nome):
    with io.open(os.path.join(pasta, nome), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def gravar_csv(pasta, nome, linhas):
    with io.open(os.path.join(pasta, nome), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), lineterminator="\r\n")
        w.writeheader()
        w.writerows(linhas)


class Leitura(unittest.TestCase):
    def ler(self, estado, **kw):
        avisos = []
        res = R.ler_resultados(os.path.join(FIX, estado), avisar=avisos.append, **kw)
        return res, avisos

    def test_normalizar_sit(self):
        f = R.normalizar_sit
        self.assertEqual(f("Eleito"), "eleito")
        self.assertEqual(f("Eleito por QP"), "eleito")
        self.assertEqual(f("2º turno"), "2t")
        self.assertEqual(f("Não eleito"), "nao")
        self.assertEqual(f("NÃO ELEITO"), "nao")
        self.assertEqual(f("Nao eleito"), "nao")
        self.assertEqual(f(""), "")
        self.assertEqual(f("Suplente"), "")

    def test_sem_pasta_devolve_vazio(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(R.ler_resultados(d, avisar=lambda m: None), {})
            self.assertEqual(R.ufs_2t(d), R.UF2T_PADRAO)
            self.assertEqual(R.ufs_pendentes({}, R.UF2T_PADRAO), [])
            self.assertEqual(R.finalistas({}), R.FINALISTAS_PADRAO)
            self.assertIn("nenhuma apuração", R.resumo({}, R.UF2T_PADRAO, [])[0])

    def test_pasta_padrao_segue_a_variavel(self):
        antes = os.environ.get("MURAL_RESULTADOS")
        try:
            os.environ["MURAL_RESULTADOS"] = os.path.join(FIX, "parcial")
            self.assertEqual(R.pasta_padrao(), os.path.join(FIX, "parcial"))
            del os.environ["MURAL_RESULTADOS"]
            self.assertTrue(R.pasta_padrao().endswith(os.path.join("dados", "resultados")))
        finally:
            if antes is not None:
                os.environ["MURAL_RESULTADOS"] = antes

    def test_apuracao_zerada_fica_de_fora(self):
        res, avisos = self.ler("zerado")
        self.assertEqual(avisos, [])
        self.assertEqual(res["fonte"], R.FONTE)
        self.assertEqual(set(res["pres"]), {"1"})
        self.assertEqual(set(res["gov"]), {"1"})
        tot = ler_csv(os.path.join(FIX, "zerado"), "totais.csv")
        zeradas = {(t["cargo"], t["turno"]) for t in tot if int(t["secoes_totalizadas"]) == 0}
        self.assertIn(("presidente", "2"), zeradas)

    def test_abrangencia_em_maiusculas_e_exterior_a_parte(self):
        res, _ = self.ler("zerado")
        p1 = res["pres"]["1"]
        self.assertIn("BR", p1)
        self.assertIn("ZZ", p1)
        self.assertTrue(all(k == k.upper() for k in p1))
        self.assertEqual(set(p1) - set(R.UFS), {"BR", "ZZ"})
        self.assertNotIn("ZZ", R.UFS)

    def test_linhas_e_totais_conferem_com_o_csv(self):
        pasta = os.path.join(FIX, "zerado")
        res, _ = self.ler("zerado")
        br = res["pres"]["1"]["BR"]
        cand = [c for c in ler_csv(pasta, "candidatos.csv") if c["turno"] == "1" and c["cargo"] == "presidente" and c["abrangencia"] == "br"]
        tot = next(t for t in ler_csv(pasta, "totais.csv") if t["turno"] == "1" and t["cargo"] == "presidente" and t["abrangencia"] == "br")
        self.assertEqual(br["est"], "final")
        self.assertEqual(br["tot"]["vv"], int(tot["validos"]))
        self.assertEqual(br["tot"]["st"], int(tot["secoes_totalizadas"]))
        self.assertEqual(br["tot"]["at"], tot["atualizado_tse"])
        self.assertEqual(len(br["c"]), len(cand))
        votos = [x[4] for x in br["c"]]
        self.assertEqual(votos, sorted(votos, reverse=True), "linhas em ordem de votos")
        primeiro = max(cand, key=lambda c: int(c["votos"]))
        self.assertEqual(br["c"][0][0], primeiro["mural"])
        self.assertEqual(br["c"][0][5], float(primeiro["pct_validos"]))
        self.assertTrue(all(isinstance(x[4], int) and isinstance(x[5], float) for x in br["c"]))

    def test_coluna_eleito_nao_e_lida(self):
        """O TSE marca eleito = s também para quem foi ao 2º turno; quem vale é a situação."""
        pasta = os.path.join(FIX, "zerado")
        res, _ = self.ler("zerado")
        cand = [c for c in ler_csv(pasta, "candidatos.csv") if c["turno"] == "1" and c["cargo"] == "presidente" and c["abrangencia"] == "br"]
        no2t = [c["mural"] for c in cand if c["eleito"] == "s"]
        self.assertTrue(no2t)
        sit = {x[0]: x[6] for x in res["pres"]["1"]["BR"]["c"]}
        self.assertTrue(all(sit[n] == "2t" for n in no2t), sit)
        self.assertNotIn("eleito", sit.values())

    def test_parcial_e_final(self):
        parcial, avisos = self.ler("parcial")
        self.assertEqual(avisos, [])
        a = parcial["pres"]["2"]["BR"]
        tot = next(t for t in ler_csv(os.path.join(FIX, "parcial"), "totais.csv")
                   if t["turno"] == "2" and t["cargo"] == "presidente" and t["abrangencia"] == "br")
        self.assertEqual(a["est"], "parcial")
        self.assertEqual(a["tot"]["pst"], float(tot["pct_totalizado"]))
        self.assertTrue(0 < a["tot"]["pst"] < 100)
        self.assertTrue(all(x[6] == "" for x in a["c"]), "na parcial ninguém está eleito")
        self.assertEqual(set(parcial["gov"]["2"]), set(R.ufs_2t(os.path.join(FIX, "parcial"))))
        final, avisos = self.ler("final")
        self.assertEqual(avisos, [])
        f = final["pres"]["2"]["BR"]
        self.assertEqual(f["est"], "final")
        self.assertEqual([x[6] for x in f["c"]], ["eleito", "nao"])
        self.assertTrue(all(sum(1 for x in a["c"] if x[6] == "eleito") == 1 for a in final["gov"]["2"].values()))

    def test_linha_ruim_e_pulada_sem_derrubar(self):
        with tempfile.TemporaryDirectory() as d:
            cand = ler_csv(os.path.join(FIX, "zerado"), "candidatos.csv")
            tot = ler_csv(os.path.join(FIX, "zerado"), "totais.csv")
            # o último colocado no Brasil, com votos ilegíveis: some só ele, e a soma ainda fecha
            br = [c for c in cand if c["turno"] == "1" and c["cargo"] == "presidente" and c["abrangencia"] == "br"]
            ultimo = min(br, key=lambda c: int(c["votos"]))
            ultimo["votos"] = "abc"
            # e uma apuração inteira com seções ilegíveis, que sai do resultado
            t_ac = next(t for t in tot if t["turno"] == "1" and t["cargo"] == "senador" and t["abrangencia"] == "ac")
            t_ac["secoes_totalizadas"] = "x"
            gravar_csv(d, "candidatos.csv", cand)
            gravar_csv(d, "totais.csv", tot)
            avisos = []
            res = R.ler_resultados(d, avisar=avisos.append)
        self.assertEqual(len(avisos), 2, avisos)
        self.assertNotIn(ultimo["mural"], [x[0] for x in res["pres"]["1"]["BR"]["c"]])
        self.assertEqual(len(res["pres"]["1"]["BR"]["c"]), len(br) - 1)
        self.assertNotIn("AC", res["sen"]["1"])
        self.assertIn("AC", res["gov"]["1"])

    def test_soma_conferida_so_na_final(self):
        for estado, fica in (("final", False), ("parcial", True)):
            with tempfile.TemporaryDirectory() as d:
                cand = ler_csv(os.path.join(FIX, estado), "candidatos.csv")
                alvo = next(c for c in cand if c["turno"] == "2" and c["cargo"] == "presidente" and c["abrangencia"] == "br")
                alvo["pct_validos"] = "%.2f" % (float(alvo["pct_validos"]) + 20)
                gravar_csv(d, "candidatos.csv", cand)
                shutil.copy(os.path.join(FIX, estado, "totais.csv"), d)
                avisos = []
                res = R.ler_resultados(d, avisar=avisos.append)
            self.assertEqual("BR" in res["pres"]["2"], fica, estado)
            self.assertEqual(any("somando" in a for a in avisos), not fica, avisos)

    def test_nome_do_mural_quando_ha_par(self):
        res, _ = self.ler("zerado", nomes={"to-gov-professora-dorinha": "Nome do Mural"})
        to = {x[0]: x[1] for x in res["gov"]["1"]["TO"]["c"]}
        self.assertEqual(to["to-gov-professora-dorinha"], "Nome do Mural")
        # sem par no mural, nome de urna em caixa de título
        sem_par = [x for a in res["sen"]["1"].values() for x in a["c"] if not x[0]]
        self.assertTrue(sem_par)
        self.assertTrue(all(x[1] and x[1] != x[1].upper() for x in sem_par), sem_par)


class Derivados(unittest.TestCase):
    """uf2t sai de totais.csv (turno 2, governador); TO, marcado "2º turno" no 1º turno e sem 2º
    turno configurado no TSE, fica em ufPend com os dois nomes e os percentuais."""

    def setUp(self):
        self.pasta = os.path.join(FIX, "zerado")
        self.res = R.ler_resultados(self.pasta, avisar=lambda m: None)

    def test_uf2t_sem_to(self):
        uf2t = R.ufs_2t(self.pasta)
        tot = ler_csv(self.pasta, "totais.csv")
        self.assertEqual(uf2t, sorted({t["abrangencia"].upper() for t in tot if t["turno"] == "2" and t["cargo"] == "governador"}))
        self.assertNotIn("TO", uf2t)
        marcadas = {uf for uf, a in self.res["gov"]["1"].items() if any(x[6] == "2t" for x in a["c"])}
        self.assertIn("TO", marcadas)

    def test_ufpend_com_to(self):
        uf2t = R.ufs_2t(self.pasta)
        pend = R.ufs_pendentes(self.res, uf2t)
        self.assertEqual([p["uf"] for p in pend], ["TO"])
        cand = {c["mural"]: c for c in ler_csv(self.pasta, "candidatos.csv")
                if c["turno"] == "1" and c["cargo"] == "governador" and c["abrangencia"] == "to" and c["situacao"] == "2º turno"}
        self.assertEqual(len(pend[0]["c"]), 2)
        for x in pend[0]["c"]:
            self.assertEqual(x[5], float(cand[x[0]]["pct_validos"]))

    def test_conferencia_das_27_ufs(self):
        uf2t = R.ufs_2t(self.pasta)
        pend = R.ufs_pendentes(self.res, uf2t)
        eleitos, _ = R.eleitos_1t(self.res, "gov")
        self.assertEqual(len(eleitos) + len(uf2t) + len(pend), 27)
        self.assertFalse(set(eleitos) & set(uf2t))
        linhas = R.resumo(self.res, uf2t, pend)
        conf = next(l for l in linhas if l.startswith(("governadores", "AVISO governadores")))
        self.assertTrue(conf.startswith("governadores") and conf.endswith("= 27"), conf)

    def test_finalistas_pelos_votos(self):
        avisos = []
        f = R.finalistas(self.res, avisar=avisos.append)
        br = [c for c in ler_csv(self.pasta, "candidatos.csv")
              if c["turno"] == "1" and c["cargo"] == "presidente" and c["abrangencia"] == "br" and c["situacao"] == "2º turno"]
        self.assertEqual(f, [c["mural"] for c in sorted(br, key=lambda c: -int(c["votos"]))])
        self.assertEqual(avisos, [])

    def test_caixa_de_titulo(self):
        self.assertEqual(R.titulo("SILVIA HELLEN DA SILVA PEREIRA"), "Silvia Hellen da Silva Pereira")
        self.assertEqual(R.municipio_uf("ANÁPOLIS/GO"), "Anápolis (GO)")
        self.assertEqual(R.municipio_uf("São José De Ribamar (MA)"), "São José de Ribamar (MA)")
        self.assertEqual(R.municipio_uf("Garanhuns (PE)"), "Garanhuns (PE)")


def gerar_com(pasta_resultados):
    """Roda o gerador numa cópia temporária de mural/ (lendo dados/ por um link) e devolve o DATA
    do mural inteiro."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "mural"))
        for nome in ("_gerar_mural.py", "_resultados.py", "_template.html"):
            shutil.copy(os.path.join(RAIZ, "mural", nome), os.path.join(d, "mural", nome))
        os.symlink(os.path.join(RAIZ, "dados"), os.path.join(d, "dados"))
        amb = dict(os.environ, MURAL_RESULTADOS=pasta_resultados, MURAL_ATUALIZADO="teste")
        for k in ("MURAL_SUPABASE_URL", "MURAL_SUPABASE_ANON"):
            amb.pop(k, None)
        p = subprocess.run([sys.executable, os.path.join(d, "mural", "_gerar_mural.py")], capture_output=True,
                           text=True, env=amb, cwd=d)
        if p.returncode != 0:
            raise AssertionError("o gerador falhou com %s:\n%s" % (pasta_resultados, p.stderr[-3000:]))
        with io.open(os.path.join(d, "mural", "mural-inteiro.html"), encoding="utf-8") as f:
            html = f.read()
    i = html.index("const DATA = ") + len("const DATA = ")
    return json.JSONDecoder().raw_decode(html[i:])[0], p.stdout


class Gerador(unittest.TestCase):
    """O mural sai inteiro sem resultado, com o 2º turno zerado, com a parcial e com a final."""

    def test_sem_resultado_cai_nas_pesquisas(self):
        with tempfile.TemporaryDirectory() as vazia:
            D, saida = gerar_com(vazia)
        self.assertNotIn("resultados", D)
        self.assertEqual(D["finalistas"], R.FINALISTAS_PADRAO)
        self.assertEqual(D["uf2t"], R.UF2T_PADRAO)
        self.assertEqual(D["ufPend"], [])
        self.assertTrue(all("r1" not in c and not c["fora"] for c in D["candidatos"]))
        com_csv = []
        with io.open(os.path.join(RAIZ, "dados", "candidatos.csv"), encoding="utf-8-sig") as f:
            com_csv = [r["candidato"] for r in csv.DictReader(f)]
        self.assertEqual([c["nome"] for c in D["candidatos"]], com_csv, "sem resultado, a ordem é a do arquivo")
        self.assertTrue(all("r1" not in c for e in D["estados"].values() for c in e["gov"] + e["sen"]))
        self.assertIn("nenhuma apuração", saida)

    def test_segundo_turno_zerado(self):
        D, saida = gerar_com(os.path.join(FIX, "zerado"))
        self.assertEqual(set(D["resultados"]["pres"]), {"1"})
        self.assertIn("polls2t", D)
        C = D["candidatos"]
        fin = [c["nome"] for c in C if c["finalista"]]
        self.assertEqual(fin, D["finalistas"])
        self.assertEqual([c["nome"] for c in C[:2]], D["finalistas"], "os do 2º turno vêm primeiro")
        na_urna = [c for c in C if c.get("r1")]
        self.assertEqual([c["r1"]["votos"] for c in na_urna[2:]], sorted((c["r1"]["votos"] for c in na_urna[2:]), reverse=True))
        fora = [c for c in C if c["fora"]]
        self.assertTrue(fora and all("r1" not in c for c in fora) and C[-len(fora):] == fora)
        for c in na_urna:
            r1 = c["r1"]
            self.assertEqual(r1["de"], len(na_urna))
            self.assertNotEqual(r1["melhor"][0], "ZZ")
            self.assertTrue(all(uf in R.UFS for uf in r1["ufs1"]))
        # nos estados: r1 pelo slug, e fora = 1 para quem não está na apuração
        am = D["estados"]["AM"]
        self.assertTrue(any(c.get("r1") for c in am["gov"]))
        self.assertTrue(all(("r1" in c) != bool(c.get("fora")) for e in D["estados"].values() for c in e["gov"] + e["sen"]))
        self.assertIn("= 27", saida)

    def test_parcial_e_final(self):
        for estado, est in (("parcial", "parcial"), ("final", "final")):
            D, _ = gerar_com(os.path.join(FIX, estado))
            self.assertEqual(D["resultados"]["pres"]["2"]["BR"]["est"], est)
            fin = [c for c in D["candidatos"] if c["finalista"]]
            self.assertTrue(all(c.get("r2") for c in fin), estado)
            self.assertTrue(all(c.get("r2") is None for c in D["candidatos"] if not c["finalista"]), estado)
            for uf in D["uf2t"]:
                gov = [c for c in D["estados"][uf]["gov"] if c.get("r2")]
                self.assertEqual(len(gov), 2, (estado, uf))
            if est == "final":
                self.assertEqual(sorted(c["r2"]["sit"] for c in fin), ["eleito", "nao"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
