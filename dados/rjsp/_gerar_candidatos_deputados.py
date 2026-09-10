#!/usr/bin/env python3
"""Le candidatos-rjsp.csv (ficha completa do TSE, 4.538 candidaturas a deputado
estadual e federal em RJ e SP) e escreve candidatos-deputados.csv, so com o
grupo curado de "principais" (decisao do Francisco em 7/9/2026): atuais
parlamentares buscando reeleicao (categoria A) e candidatos novos de forte
repercussao (categoria B). A lista de nomes abaixo vem de
notas/curadoria-deputados-rjsp-2026-09-07.md, ja cruzada e corrigida contra
o TSE (Martha Rocha movida para federal, Val Marchiori movida para SP,
Gracyanne Barbosa e Jose de Abreu excluidos por nao aparecerem no registro).

Segue o mesmo formato de dados/estados/candidatos-estados.csv (slug,
url_tse, fonte por extenso), mais uma coluna `categoria` que nao existe la
porque governador/senador inclui todo mundo registrado; aqui, so o grupo
monitorado entra, entao a categoria da curadoria e informacao relevante.

Uso: python3 _gerar_candidatos_deputados.py
"""
import csv, os, re, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(AQUI, "candidatos-rjsp.csv")
SAIDA = os.path.join(AQUI, "candidatos-deputados.csv")

ELEICAO_TSE = "20322002026"

# (uf, cargo, nome_urna exato no TSE, categoria A|B)
CURADOS = [
    # --- Rio de Janeiro, deputado estadual ---
    ("RJ", "deputado estadual", "ALAN LOPES", "A"),
    ("RJ", "deputado estadual", "ALEXANDRE KNOPLOCH", "A"),
    ("RJ", "deputado estadual", "ANDERSON MORAES", "A"),
    ("RJ", "deputado estadual", "CHICO MACHADO", "A"),
    ("RJ", "deputado estadual", "DELEGADO CARLOS AUGUSTO", "A"),
    ("RJ", "deputado estadual", "DR. DEODALTO", "A"),
    ("RJ", "deputado estadual", "DR. PEDRO RICARDO", "A"),
    ("RJ", "deputado estadual", "FRED PACHECO", "A"),
    ("RJ", "deputado estadual", "GISELLE MONTEIRO", "A"),
    ("RJ", "deputado estadual", "GUILHERME DELAROLI", "A"),
    ("RJ", "deputado estadual", "ÍNDIA ARMELAU", "A"),
    ("RJ", "deputado estadual", "JAIR BITTENCOURT", "A"),
    ("RJ", "deputado estadual", "JORGE FELIPPE NETO", "A"),
    ("RJ", "deputado estadual", "MARCELO DINO", "A"),
    ("RJ", "deputado estadual", "MÁRCIO GUALBERTO", "A"),
    ("RJ", "deputado estadual", "RENAN JORDY", "A"),
    ("RJ", "deputado estadual", "RENATO MIRANDA", "A"),
    ("RJ", "deputado estadual", "VALDECY DA SAÚDE", "A"),
    ("RJ", "deputado estadual", "CARLOS MINC", "A"),
    ("RJ", "deputado estadual", "RAFAEL PICCIANI", "A"),
    ("RJ", "deputado estadual", "LUIZ PAULO", "A"),
    ("RJ", "deputado estadual", "INÊS BRASIL", "B"),
    ("RJ", "deputado estadual", "MC SMITH", "B"),
    ("RJ", "deputado estadual", "CONRADO", "B"),
    # --- Rio de Janeiro, deputado federal ---
    ("RJ", "deputado federal", "CHICO ALENCAR", "A"),
    ("RJ", "deputado federal", "TALÍRIA PETRONE", "A"),
    ("RJ", "deputado federal", "TARCÍSIO MOTTA", "A"),
    ("RJ", "deputado federal", "JANDIRA FEGHALI", "A"),
    ("RJ", "deputado federal", "GENERAL PAZUELLO", "A"),
    ("RJ", "deputado federal", "SÓSTENES CAVALCANTE", "A"),
    ("RJ", "deputado federal", "ALTINEU CORTES", "A"),
    ("RJ", "deputado federal", "SORAYA SANTOS", "A"),
    ("RJ", "deputado federal", "DELEGADA MARTHA ROCHA", "A"),
    ("RJ", "deputado federal", "FREIXO", "B"),
    ("RJ", "deputado federal", "THIAGO GAGLIASSO", "B"),
    ("RJ", "deputado federal", "BENNY BRIOLLY", "B"),
    ("RJ", "deputado federal", "ANTÔNIA FONTENELLE", "B"),
    ("RJ", "deputado federal", "EDMUNDO", "B"),
    ("RJ", "deputado federal", "HUMBERTO MARTINS", "B"),
    ("RJ", "deputado federal", "ANDREA SORVETÃO", "B"),
    ("RJ", "deputado federal", "CRISTINA MEL", "B"),
    ("RJ", "deputado federal", "DARLAN PRAXEDES", "B"),
    # --- São Paulo, deputado estadual ---
    ("SP", "deputado estadual", "ANA CAROLINA SERRA", "A"),
    ("SP", "deputado estadual", "CARLA MORANDO", "A"),
    ("SP", "deputado estadual", "THIAGO AURICCHIO", "A"),
    ("SP", "deputado estadual", "OSEIAS DE MADUREIRA", "A"),
    ("SP", "deputado estadual", "LUIZ FERNANDO", "A"),
    ("SP", "deputado estadual", "BARBA", "A"),
    ("SP", "deputado estadual", "RÔMULO", "A"),
    ("SP", "deputado estadual", "EDIANE MARIA", "A"),
    ("SP", "deputado estadual", "ITAMAR BORGES", "A"),
    ("SP", "deputado estadual", "TELHADINHA - CAPITÃO TELHADA", "A"),
    ("SP", "deputado estadual", "VALERIA BOLSONARO", "A"),
    ("SP", "deputado estadual", "PAULO KOGOS", "B"),
    ("SP", "deputado estadual", "MARCELO BOLSONARO", "B"),
    # --- São Paulo, deputado federal ---
    ("SP", "deputado federal", "PASTOR MARCO FELICIANO", "A"),
    ("SP", "deputado federal", "ERIKA HILTON", "A"),
    ("SP", "deputado federal", "SÂMIA BOMFIM", "A"),
    ("SP", "deputado federal", "ROSANA VALLE", "A"),
    ("SP", "deputado federal", "KIM KATAGUIRI", "A"),
    ("SP", "deputado federal", "BALEIA ROSSI", "A"),
    ("SP", "deputado federal", "RENATA ABREU", "A"),
    ("SP", "deputado federal", "JEAN WYLLYS", "B"),
    ("SP", "deputado federal", "LUCAS PENTEADO", "B"),
    ("SP", "deputado federal", "ADRILLES JORGE", "B"),
    ("SP", "deputado federal", "RENATO BOLSONARO", "B"),
    ("SP", "deputado federal", "LUCAS PAVANATO", "B"),
    ("SP", "deputado federal", "RACHEL SHEHERAZADE", "B"),
    ("SP", "deputado federal", "SILVIA ABRAVANEL", "B"),
    ("SP", "deputado federal", "GERALDO LUÍS", "B"),
    ("SP", "deputado federal", "CANETA AZUL - MANOEL GOMES", "B"),
    ("SP", "deputado federal", "THIAGO DOS REIS", "B"),
    ("SP", "deputado federal", "MC GUI", "B"),
    ("SP", "deputado federal", "LUIS FABIANO", "B"),
    ("SP", "deputado federal", "VAL MARCHIORI", "B"),
]

CARGO_SLUG = {"deputado estadual": "dep-est", "deputado federal": "dep-fed"}


def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def citados_em_pesquisa():
    """Categoria C: quem a pesquisa registrada do RJ mostrou entre os mais lembrados.

    A curadoria A/B saiu da imprensa de setembro. Esta lista sai do eleitor: sao os nomes
    que apareceram espontaneamente na Prefab/Diario do Rio, registro TSE RJ-02770/2026. As
    duas listas quase nao se encontram, e ser lembrado por conta propria numa pesquisa
    registrada e prova mais forte de ser "principal" do que ser citado numa materia. Entra
    por id_tse, nunca por nome, e so quem tem candidatura registrada.

    Devolve {(uf, cargo, id_tse): motivo}.
    """
    caminho = os.path.join(AQUI, "_pesquisa-deputados-rj.csv")
    if not os.path.exists(caminho):
        return {}
    fora = {}
    with open(caminho, encoding="utf-8-sig") as f:
        for l in csv.DictReader(f):
            if l["status"] != "resolvido" or not l["id_tse"]:
                continue
            cargo = "deputado federal" if l["cargo"] == "depfed" else "deputado estadual"
            fora[(l["uf"], cargo, l["id_tse"])] = l["fonte"]
    return fora


def main():
    with open(ENTRADA, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    indice = {(r["uf"], r["cargo"], r["nome_urna"]): r for r in linhas}
    por_id = {(r["uf"], r["cargo"], r["id_tse"]): r for r in linhas}

    citados = citados_em_pesquisa()
    curados = list(CURADOS)
    ja = {(uf, cargo, indice[(uf, cargo, n)]["id_tse"])
          for uf, cargo, n, _ in curados if (uf, cargo, n) in indice}
    novos = 0
    for chave, _fonte in sorted(citados.items()):
        if chave in ja:
            continue
        r = por_id.get(chave)
        if r is None:                       # citado sem candidatura: ja fica de fora na coleta
            continue
        curados.append((chave[0], chave[1], r["nome_urna"], "C"))
        novos += 1

    faltando = []
    saida = []
    for uf, cargo, nome_urna, categoria in curados:
        r = indice.get((uf, cargo, nome_urna))
        if r is None:
            faltando.append((uf, cargo, nome_urna))
            continue
        slug = f"{uf.lower()}-{CARGO_SLUG[cargo]}-{slugify(r['nome_urna'])}"
        url_tse = (
            f"https://divulgacandcontas.tse.jus.br/divulga/#/candidato/"
            f"2026/{ELEICAO_TSE}/{uf}/{r['id_tse']}"
        )
        saida.append({
            "uf": uf,
            "cargo": cargo,
            "categoria": categoria,
            "id_tse": r["id_tse"],
            "nome_urna": r["nome_urna"],
            "nome_completo": r["nome_completo"],
            "numero": r["numero"],
            "partido": r["partido"],
            "coligacao": r["coligacao"],
            "situacao_tse": r["situacao_tse"],
            "totalizacao": r["totalizacao"],
            "bens_total": r["bens_total"],
            "instagram": r["instagram"],
            "slug": slug,
            "url_tse": url_tse,
            "fonte": (
                "TSE DivulgaCandContas (dados/rjsp/candidatos-rjsp.csv, coleta de "
                "7/9/2026); "
                + ("entrou por ser citado espontaneamente na pesquisa Prefab Future / "
                   "Diario do Rio, registro TSE RJ-02770/2026, campo de 24 a 29/7/2026 "
                   "(dados/rjsp/_pesquisa-deputados-rj.csv)"
                   if categoria == "C" else "")
                + ("" if categoria == "C" else "curadoria de imprensa em "
                "notas/varredura-deputados-rj-2026-09-07.md e "
                "notas/varredura-deputados-sp-2026-09-07.md, cruzada e corrigida em "
                "notas/curadoria-deputados-rjsp-2026-09-07.md")
            ),
        })

    if faltando:
        print(f"ATENCAO: {len(faltando)} nomes curados nao encontrados na ficha do TSE:")
        for uf, cargo, nome_urna in faltando:
            print(f"  {uf} {cargo} {nome_urna!r}")

    saida.sort(key=lambda r: (r["uf"], r["cargo"], r["categoria"], r["nome_urna"]))

    campos = [
        "uf", "cargo", "categoria", "id_tse", "nome_urna", "nome_completo",
        "numero", "partido", "coligacao", "situacao_tse", "totalizacao",
        "bens_total", "instagram", "slug", "url_tse", "fonte",
    ]
    with open(SAIDA, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(saida)

    porcat = {}
    for r in saida:
        porcat[r["categoria"]] = porcat.get(r["categoria"], 0) + 1
    print(f"{len(saida)} candidaturas escritas em {SAIDA} "
          f"(por categoria: {dict(sorted(porcat.items()))}; {novos} entraram pela pesquisa)")
    por_disputa = {}
    for r in saida:
        chave = (r["uf"], r["cargo"])
        por_disputa[chave] = por_disputa.get(chave, 0) + 1
    for (uf, cargo), n in sorted(por_disputa.items()):
        print(f"  {uf} {cargo}: {n}")


if __name__ == "__main__":
    main()
