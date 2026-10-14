# -*- coding: utf-8 -*-
"""Frescor do mural que os testes de navegador abrem (T0.2 do plano do 2º turno).

mural/mural-inteiro.html é ignorado pelo git e os dois scripts de navegador o leem como está. Um
arquivo velho, de antes da última mudança no template, no gerador ou nos dados, calibra o teste
contra a página errada: um teste novo passa olhando o mural antigo, ou falha por um bug que já foi
corrigido. Por isso os dois scripts param antes de abrir o navegador quando ele está mais antigo que
as fontes, ou quando o DATA.meta dele diverge do de mural.html (os dois saem da mesma geração).
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _meta(html):
    """O objeto "meta" de DATA, lido do HTML gerado, ou None se não houver."""
    i = html.find('"meta":')
    if i < 0:
        return None
    j = html.find("{", i)
    prof, k, aspas, esc = 0, j, False, False
    while k < len(html):
        ch = html[k]
        if aspas:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': aspas = False
        elif ch == '"': aspas = True
        elif ch == "{": prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                try:
                    return json.loads(html[j:k + 1])
                except ValueError:
                    return None
        k += 1
    return None


def fontes(raiz=RAIZ):
    """Arquivos de que o mural sai: template, gerador, leitor do TSE e os CSVs de dados/."""
    raiz = Path(raiz)
    fixos = [raiz / "mural" / n for n in ("_template.html", "_gerar_mural.py", "_resultados.py")]
    return [f for f in fixos if f.exists()] + sorted((raiz / "dados").rglob("*.csv"))


def problemas(raiz=RAIZ):
    """Lista de motivos para não testar o mural-inteiro.html de agora; vazia quando ele está em dia."""
    raiz = Path(raiz)
    inteiro, publico = raiz / "mural" / "mural-inteiro.html", raiz / "mural" / "mural.html"
    if not inteiro.exists():
        return ["mural/mural-inteiro.html não existe"]
    out = []
    t = inteiro.stat().st_mtime
    novos = [f for f in fontes(raiz) if f.stat().st_mtime > t]
    if novos:
        nomes = ", ".join(str(f.relative_to(raiz)) for f in novos[:5])
        out.append("mural/mural-inteiro.html é mais antigo que %d arquivo(s) de que ele sai: %s%s"
                   % (len(novos), nomes, " ..." if len(novos) > 5 else ""))
    if publico.exists():
        m_i = _meta(inteiro.read_text(encoding="utf-8"))
        m_p = _meta(publico.read_text(encoding="utf-8"))
        if m_i is None or m_p is None or m_i != m_p:
            out.append("o DATA.meta de mural/mural-inteiro.html não é o de mural/mural.html: os dois não saíram da mesma geração")
    return out


def exigir(raiz=RAIZ):
    """Encerra o script com a explicação quando o mural está velho."""
    ps = problemas(raiz)
    if ps:
        raise SystemExit("mural desatualizado, os testes não rodam contra ele:\n  - " + "\n  - ".join(ps)
                         + "\nRode python3 mural/_gerar_mural.py (ou ./testes/verificar.sh, que regenera) e repita.")
