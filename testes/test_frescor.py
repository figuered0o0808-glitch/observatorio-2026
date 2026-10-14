# -*- coding: utf-8 -*-
"""A trava de frescor dos testes de navegador (testes/_frescor.py): mural-inteiro.html mais antigo
que as fontes, ou com DATA.meta diferente do de mural.html, impede a regressão e a varredura de rodar
contra a página errada. Monta uma pasta de mentira, sem tocar no mural deste checkout."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _frescor  # noqa: E402

PAGINA = '<script>const DATA={"polls":[],"meta":{"rodadas":%d,"t1":{"ultima":"2026-10-03","obs":"a } dentro"}},"x":1};</script>'


class Frescor(unittest.TestCase):
    def montar(self, rodadas_inteiro=10, rodadas_publico=10):
        d = Path(tempfile.mkdtemp(prefix="frescor-"))
        (d / "mural").mkdir()
        (d / "dados" / "resultados").mkdir(parents=True)
        for n in ("_template.html", "_gerar_mural.py", "_resultados.py"):
            (d / "mural" / n).write_text("x", encoding="utf-8")
        (d / "dados" / "eventos.csv").write_text("data\n", encoding="utf-8")
        (d / "dados" / "resultados" / "totais.csv").write_text("turno\n", encoding="utf-8")
        (d / "mural" / "mural-inteiro.html").write_text(PAGINA % rodadas_inteiro, encoding="utf-8")
        (d / "mural" / "mural.html").write_text(PAGINA % rodadas_publico, encoding="utf-8")
        velho = (d / "mural" / "mural-inteiro.html").stat().st_mtime - 60
        for f in _frescor.fontes(d):
            os.utime(f, (velho, velho))
        return d

    def test_em_dia(self):
        self.assertEqual(_frescor.problemas(self.montar()), [])

    def test_csv_mais_novo(self):
        d = self.montar()
        f = d / "dados" / "resultados" / "totais.csv"
        t = (d / "mural" / "mural-inteiro.html").stat().st_mtime + 60
        os.utime(f, (t, t))
        ps = _frescor.problemas(d)
        self.assertEqual(len(ps), 1)
        self.assertIn("dados/resultados/totais.csv", ps[0])
        with self.assertRaises(SystemExit):
            _frescor.exigir(d)

    def test_template_mais_novo(self):
        d = self.montar()
        t = (d / "mural" / "mural-inteiro.html").stat().st_mtime + 60
        os.utime(d / "mural" / "_template.html", (t, t))
        self.assertIn("mural/_template.html", _frescor.problemas(d)[0])

    def test_meta_divergente(self):
        ps = _frescor.problemas(self.montar(rodadas_inteiro=10, rodadas_publico=11))
        self.assertEqual(len(ps), 1)
        self.assertIn("DATA.meta", ps[0])

    def test_meta_lida_com_chave_dentro_de_texto(self):
        self.assertEqual(_frescor._meta(PAGINA % 3)["t1"]["obs"], "a } dentro")

    def test_sem_mural(self):
        d = self.montar()
        (d / "mural" / "mural-inteiro.html").unlink()
        self.assertTrue(_frescor.problemas(d))


if __name__ == "__main__":
    unittest.main()
