#!/usr/bin/env python3
"""Cruza uma lista curada de nomes (categoria A/B da varredura de imprensa) contra a
ficha completa do TSE em candidatos-rjsp.csv, por token de nome normalizado.
Script pontual (nome com data), não faz parte do pipeline repetivel.
Uso: python3 _cruzar_curados_2026-09-07.py [SP|RJ]
"""
import csv, unicodedata, sys, os

AQUI = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(AQUI, "candidatos-rjsp.csv")

def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper().strip()

def tokens(s):
    return set(norm(s).replace("-", " ").split())

CURADOS_SP = [
    ("estadual", "Ana Carolina Serra"), ("estadual", "Carla Morando"),
    ("estadual", "Thiago Auricchio"), ("estadual", "Oseias de Madureira"),
    ("estadual", "Luiz Fernando Teixeira"), ("estadual", "Teonilio Barba"),
    ("estadual", "Rômulo Fernandes"), ("estadual", "Ediane Maria"),
    ("estadual", "Itamar Borges"), ("estadual", "Capitão Telhada"),
    ("estadual", "Valéria Bolsonaro"), ("estadual", "Paulo Kogos"),
    ("estadual", "Marcelo Bolsonaro"),
    ("federal", "Marco Feliciano"), ("federal", "Erika Hilton"),
    ("federal", "Sâmia Bomfim"), ("federal", "Rosana Valle"),
    ("federal", "Kim Kataguiri"), ("federal", "Baleia Rossi"),
    ("federal", "Renata Abreu"), ("federal", "Jean Wyllys"),
    ("federal", "Lucas Penteado"), ("federal", "Adrilles Jorge"),
    ("federal", "Renato Bolsonaro"), ("federal", "Lucas Pavanato"),
    ("federal", "Rachel Sheherazade"), ("federal", "Silvia Abravanel"),
    ("federal", "Geraldo Luís"), ("federal", "Manoel Gomes"),
    ("federal", "Thiago dos Reis"), ("federal", "MC Gui"),
    ("federal", "Luís Fabiano"),
]

CURADOS_RJ = [
    ("estadual", "Alan Lopes"), ("estadual", "Alexandre Knoploch"),
    ("estadual", "Anderson Moraes"), ("estadual", "Chico Machado"),
    ("estadual", "Delegado Carlos Augusto"), ("estadual", "Dr. Deodalto"),
    ("estadual", "Dr. Pedro Ricardo"), ("estadual", "Fred Pacheco"),
    ("estadual", "Giselle Monteiro"), ("estadual", "Guilherme Delaroli"),
    ("estadual", "India Armelau"), ("estadual", "Jair Bittencourt"),
    ("estadual", "Jorge Felippe Neto"), ("estadual", "Marcelo Dino"),
    ("estadual", "Márcio Gualberto"), ("estadual", "Renan Jordy"),
    ("estadual", "Renato Miranda"), ("estadual", "Valdecy da Saúde"),
    ("estadual", "Martha Rocha"), ("estadual", "Carlos Minc"),
    ("estadual", "Rafael Picciani"), ("estadual", "Luiz Paulo"),
    ("estadual", "Inês Brasil"), ("estadual", "MC Smith"), ("estadual", "Conrado"),
    ("federal", "Chico Alencar"), ("federal", "Talíria Petrone"),
    ("federal", "Tarcísio Motta"), ("federal", "Jandira Feghali"),
    ("federal", "General Pazuello"), ("federal", "Sóstenes Cavalcante"),
    ("federal", "Altineu Cortes"), ("federal", "Soraya Santos"),
    ("federal", "Marcelo Freixo"), ("federal", "Thiago Gagliasso"),
    ("federal", "Benny Briolly"), ("federal", "Gracyanne Barbosa"),
    ("federal", "Antonia Fontenelle"), ("federal", "Edmundo Souza"),
    ("federal", "José de Abreu"), ("federal", "Val Marchiori"),
    ("federal", "Humberto Martins"), ("federal", "Andréa Sorvetão"),
    ("federal", "Cristina Mel"), ("federal", "MC Darlan"),
]

def cruzar(uf, curados):
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))
    uf_rows = [r for r in rows if r["uf"] == uf]
    for cargo_curto, nome in curados:
        cargo_full = "deputado estadual" if cargo_curto == "estadual" else "deputado federal"
        alvo = tokens(nome)
        pool = [r for r in uf_rows if r["cargo"] == cargo_full]
        matches = []
        for r in pool:
            best = max(len(alvo & tokens(r["nome_urna"])), len(alvo & tokens(r["nome_completo"])))
            if best >= max(1, len(alvo) - 1):
                matches.append((best, r))
        matches.sort(key=lambda x: -x[0])
        print(f"\n=== {nome} ({cargo_curto}, {uf}) ===")
        if not matches:
            print("  NENHUM MATCH")
        for score, r in matches[:5]:
            print(f"  score={score} nome_urna={r['nome_urna']!r} nome_completo={r['nome_completo']!r} "
                  f"numero={r['numero']} partido={r['partido']} situacao_tse={r['situacao_tse']} "
                  f"bens_total={r['bens_total']!r} instagram={r['instagram']!r} "
                  f"eleicoes_anteriores={r['eleicoes_anteriores']!r}")

if __name__ == "__main__":
    alvo_uf = sys.argv[1] if len(sys.argv) > 1 else "SP"
    if alvo_uf == "SP":
        cruzar("SP", CURADOS_SP)
    elif alvo_uf == "RJ":
        cruzar("RJ", CURADOS_RJ)
