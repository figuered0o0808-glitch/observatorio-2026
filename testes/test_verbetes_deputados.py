# -*- coding: utf-8 -*-
"""O aceite de verbete de deputado, contra os casos que já erraram de verdade.

A primeira versão do casador aceitou Eduardo Bolsonaro para Marcelo e para Renato
Bolsonaro e recusou Chico Alencar, Delegada Martha Rocha e Marco Feliciano, que têm
verbete. Estes dezesseis casos são os que a rodada de 9/9/2026 devolveu, com a
introdução real de cada verbete congelada em fixtures: dez que têm de ser aceitos e
seis que têm de ser recusados. Sem rede.
"""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "coleta"))
import wikipedia_verbetes_deputados as W  # noqa: E402

FIXTURE = os.path.join(RAIZ, "testes", "fixtures", "verbetes-deputados-2026-09-09.json")


class Verbetes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as f:
            cls.casos = json.load(f)

    def test_cada_caso_conhecido(self):
        for c in self.casos:
            with self.subTest(c["urna"]):
                cand = {"nome_completo": c["completo"], "nome_urna": c["urna"],
                        "uf": c["uf"], "partido": c["partido"]}
                p = W.pontuar(c["titulo"], c["intro"], cand)
                self.assertEqual(p >= 8, c["aceita"],
                                 "%s -> %s deu %d" % (c["urna"], c["titulo"], p))

    def test_homonimo_com_sobrenome_a_mais_nunca_passa(self):
        """Sobrenome no título que o candidato não tem derruba, mesmo com texto convincente."""
        cand = {"nome_completo": "LUIZ FERNANDO TEIXEIRA FERREIRA", "nome_urna": "LUIZ FERNANDO",
                "uf": "SP", "partido": "PT"}
        intro = ("Luiz Fernando Machado (Jundiaí, 1974) é um político brasileiro, "
                 "filiado ao PT, deputado por São Paulo.")
        self.assertLess(W.pontuar("Luiz Fernando Machado", intro, cand), 8)

    def test_pagina_de_desambiguacao_nunca_passa(self):
        cand = {"nome_completo": "CONRADO FERNANDES ANTUNES", "nome_urna": "CONRADO",
                "uf": "RJ", "partido": "DC"}
        self.assertEqual(W.pontuar("Conrado", "Conrado pode referir-se a:", cand), -20)

    def test_uma_letra_de_diferenca_conta_como_o_mesmo_nome(self):
        """O TSE grafa Brito e o verbete Britto; a pessoa é a mesma."""
        self.assertTrue(W.perto("brito", {"britto", "antonia"}))
        self.assertFalse(W.perto("brito", {"barreto", "antonia"}))
        self.assertFalse(W.perto("reis", {"real"}))   # curto demais para tolerar diferença


if __name__ == "__main__":
    unittest.main(verbosity=2)
