# -*- coding: utf-8 -*-
"""Acrescenta ao plano de lotes do Google Trends estadual as disputas de deputado de RJ e SP.

O plano vive em dados/estados/_trends-estados.json e é o que coleta/google_trends_estados.py
refaz a cada rodada da noite. Aqui só entram lotes novos, com as chaves "UF-depfed#i" e
"UF-depest#i"; os 133 lotes das disputas majoritárias não são tocados.

Duas diferenças em relação às majoritárias, ambas por causa da proporcional:

1. A âncora não pode ser o líder de pesquisa, porque proporcional não tem pesquisa nominal.
   Ela é escolhida à mão por disputa, um nome conhecido o bastante para ter sinal estável e
   não tão grande que zere os outros na escala de 0 a 100 (a lista está em ANCORA, com o
   porquê de cada uma).

2. O termo de busca nem sempre é o nome de urna. "Freixo", "Conrado" e "Barba" sozinhos
   captam qualquer coisa; nome de urna com um token só, ou com apelido antes de um traço,
   vira "primeiro sobrenome" do nome completo. O termo usado fica registrado no plano, e
   _integrar_busca.py continua marcando nome comum como termo ambíguo.

Uso: python3 dados/rjsp/_plano_trends_deputados.py [--conferir]
"""
import csv, io, json, os, re, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
PLANO = os.path.join(os.path.dirname(AQUI), "estados", "_trends-estados.json")
CARGO3 = {"deputado federal": "depfed", "deputado estadual": "depest"}

# âncora de cada disputa: entra como primeiro termo de todos os lotes daquele grupo e é o que
# torna os lotes comparáveis entre si. Escolhida por ser nome conhecido e estável, não o maior.
ANCORA = {
    ("RJ", "depfed"): "CHICO ALENCAR",       # deputado de vários mandatos, busca estável
    ("RJ", "depest"): "CARLOS MINC",         # idem na Alerj
    ("SP", "depfed"): "BALEIA ROSSI",        # presidente de partido, busca estável
    ("SP", "depest"): "ITAMAR BORGES",       # deputado de vários mandatos
}
CORTE = {"de", "da", "do", "dos", "das", "e"}

# Onde a regra automática erra, o termo é escolhido à mão e dito aqui. Regra do observatório:
# entre um termo que capta o candidato e outros milhares de homônimos e um termo que talvez volte
# sem sinal, fica o segundo. Série em branco é "indisponível"; série inflada é número errado.
TERMO_MAO = {
    ("SP", "LUIZ FERNANDO"): "Luiz Fernando Teixeira",   # dois nomes comuns; sem o sobrenome capta qualquer um
    ("SP", "LUIS FABIANO"): "Luis Fabiano Clemente",     # senão volta o jogador de futebol
    ("SP", "CANETA AZUL - MANOEL GOMES"): "Manoel Gomes",  # "Caneta Azul" mede a música, não a candidatura
    ("RJ", "EDMUNDO"): "Edmundo Alves de Souza",         # o nome de urna sozinho é primeiro nome comum
    ("RJ", "FREIXO"): "Marcelo Freixo",
}


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def caixa(t):
    return " ".join(w.lower() if norm(w) in CORTE else w.capitalize() for w in t.split())


def termo_de(c):
    """Termo de busca: o nome de urna quando ele identifica sozinho; senão, nome e sobrenome."""
    if (c["uf"], c["nome_urna"]) in TERMO_MAO:
        return TERMO_MAO[(c["uf"], c["nome_urna"])]
    urna = c["nome_urna"].strip()
    if " - " in urna:                      # apelido antes do traço: fica a parte que é nome
        partes = [p.strip() for p in urna.split(" - ")]
        completo = {norm(t) for t in c["nome_completo"].split()}
        urna = max(partes, key=lambda p: (sum(norm(t) in completo for t in p.split()), len(p.split())))
    toks = [t for t in urna.split() if norm(t) not in CORTE]
    if len(toks) >= 2:
        return caixa(urna)
    inteiros = [t for t in c["nome_completo"].split() if norm(t) not in CORTE]
    escolha = [inteiros[0], inteiros[-1]] if len(inteiros) >= 2 else inteiros
    return caixa(" ".join(escolha))


def main():
    cands = list(csv.DictReader(io.open(os.path.join(AQUI, "candidatos-deputados.csv"), encoding="utf-8-sig")))
    grupos = {}
    for c in cands:
        grupos.setdefault((c["uf"], CARGO3[c["cargo"]]), []).append(c)

    lotes = {}
    for (uf, cargo3), g in sorted(grupos.items()):
        alvo = ANCORA[(uf, cargo3)]
        anc = next((c for c in g if c["nome_urna"] == alvo), None)
        if anc is None:
            print("âncora %r não está na lista de %s %s" % (alvo, uf, cargo3)); return 1
        t_anc = termo_de(anc)
        outros = [c for c in g if c is not anc]
        for i in range(0, len(outros), 4):
            fatia = outros[i:i + 4]
            chave = "%s-%s#%d" % (uf, cargo3, i // 4)
            lotes[chave] = {"kws": [t_anc] + [termo_de(c) for c in fatia],
                            "geo": "BR-" + uf, "csv": ""}
    if "--conferir" in sys.argv:
        for k in sorted(lotes): print(k, lotes[k]["geo"], lotes[k]["kws"])
        print("\n%d lotes novos" % len(lotes)); return 0

    with io.open(PLANO, encoding="utf-8") as f:
        dump = json.load(f)
    antes = len(dump["lotes"])
    dump["lotes"].update({k: v for k, v in lotes.items() if k not in dump["lotes"]})
    with io.open(PLANO, "w", encoding="utf-8", newline="") as f:
        json.dump(dump, f, ensure_ascii=False)
    print("%s: %d lotes (%d antes, %d de deputado)" % (PLANO, len(dump["lotes"]), antes, len(lotes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
