# -*- coding: utf-8 -*-
"""Janela do Google Trends (coleta/google_trends.py, inicio_da_janela).

O Trends só devolve pontos diários para janelas de até 269 dias. Em 28/9/2026 a janela fixa
desde 1/1 passou disso, a série virou semanal (3497 -> 520 linhas) e o guarda recusou a coleta.

    python3 -m unittest testes/test_trends_janela.py
"""
import os, sys, unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "coleta"))
import google_trends as g  # noqa: E402


def dias(inicio, fim):
    return (date.fromisoformat(fim) - date.fromisoformat(inicio)).days + 1


class JanelaDiaria(unittest.TestCase):
    def test_comeca_em_janeiro_enquanto_cabe(self):
        self.assertEqual(g.inicio_da_janela("2026-09-20"), "2026-01-01")
        self.assertEqual(g.inicio_da_janela("2026-09-26"), "2026-01-01")

    def test_anda_quando_passa_de_269_dias(self):
        for fim in ("2026-09-27", "2026-09-28", "2026-10-25", "2027-03-01"):
            ini = g.inicio_da_janela(fim)
            self.assertEqual(dias(ini, fim), g.DIAS_DIARIOS, fim)

    def test_desde_posterior_e_respeitado(self):
        self.assertEqual(g.inicio_da_janela("2026-09-28", "2026-06-01"), "2026-06-01")


if __name__ == "__main__":
    unittest.main()
