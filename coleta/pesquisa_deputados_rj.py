# -*- coding: utf-8 -*-
"""Coleta a única pesquisa nominal de deputado registrada no TSE que o RJ tem em 2026.

Por que existe um coletor só para isto: disputa proporcional quase não tem pesquisa por
nome. Governador e senador têm 96 rodadas de 17 institutos; deputado, no Rio, tem UMA, e
São Paulo não tem nenhuma. A pesquisa é a Prefab Future contratada pelo Diário do Rio,
registro RJ-02770/2026, campo presencial de 24 a 29 de julho de 2026, 2.000 entrevistas,
margem de 2,19 pontos e confiança de 95%.

E ela não publica percentual. Publica quem ficou entre os 30 mais citados espontaneamente
em cada cargo, em ordem alfabética, sem número e sem classificação. Isso é dado de
pertencimento a um conjunto, não intenção de voto: dá para dizer "foi lembrado" e não dá
para dizer "tem x%". O coletor guarda exatamente isso e nada além.

Roda no runner do GitHub: do contêiner do Claude o domínio do jornal responde bloqueado no
proxy de saída, a mesma razão de a coleta da Wikipédia morar lá.

O que sai é PROPOSTA, em dados/rjsp/_pesquisa-deputados-rj.csv, com o HTML bruto guardado
ao lado para auditoria. Cada nome citado é resolvido contra a candidatura registrada por
(nome de urna, partido, cargo) exigindo acerto único: proporcional é onde homônimo mais
aparece, e atribuir "entre os mais citados" à pessoa errada é errar sobre gente de verdade.
Quem não resolver sozinho sai com o motivo, para conferência humana.

Uso: python3 coleta/pesquisa_deputados_rj.py
"""
import csv, io, os, re, sys, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DEP = os.path.join(RAIZ, "dados", "rjsp")
UA = "observatorio-2026/0.3 (coleta automática; contato: figuered0o0808@gmail.com)"

# A matéria original e dois espelhos. O espelho não vira dado: serve para acusar divergência,
# porque lista de nome lida de uma página só, sem ninguém conferindo, é fonte frágil demais
# para carimbar a reputação de 60 candidatos.
FONTES = [
    "https://diariodorio.com/pesquisa-mostra-os-nomes-mais-citados-para-deputado-estadual-e-federal-do-rj-em-2026/",
    "https://diariodorio.com/pesquisa-diario-do-rio-prefab-revela-os-candidatos-a-deputado-mais-citados-no-rio/",
    "https://rlagosnoticias.com.br/politica/pesquisa-prefab-revela-os-nomes-mais-citados-para-deputado-federal-e-estadual-no-rio-em-2026-confira-a-lista/",
]

FICHA = {
    "instituto": "Prefab Future",
    "contratante": "Diário do Rio",
    "registro_tse": "RJ-02770/2026",
    "campo_inicio": "2026-07-24",
    "campo_fim": "2026-07-29",
    "entrevistas": "2000",
    "margem": "2.19",
    "confianca": "95",
    "coleta": "presencial",
    "tipo": "espontanea",
}
# Partidos com registro no TSE em 2026, para o extrator não confundir "(PL)" de partido com
# qualquer outra sigla entre parênteses no meio do texto.
PARTIDOS = {"PT","PL","PSD","MDB","PP","UNIÃO","UNIAO","PSDB","PDT","PSB","PSOL","REDE","PCdoB",
            "PCDOB","REPUBLICANOS","PODE","PODEMOS","PRD","AVANTE","SOLIDARIEDADE","PMB","DC",
            "PRTB","AGIR","PSTU","PCO","UP","NOVO","CIDADANIA","PV","PMN","MOBILIZA","PATRIOTA",
            "UNIÃO BRASIL","UNIAO BRASIL"}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").upper().strip()


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"})
    with urllib.request.urlopen(req, timeout=60) as r:
        bruto = r.read()
    for cod in ("utf-8", "latin-1"):
        try:
            return bruto.decode(cod)
        except UnicodeDecodeError:
            continue
    return bruto.decode("utf-8", "replace")


def texto_de(html):
    h = re.sub(r"(?is)<(script|style|nav|footer|aside)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?is)<br\s*/?>|</(p|li|h[1-6]|div|tr)>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = (h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8211;", "-")
          .replace("&#8217;", "'").replace("&quot;", '"'))
    return re.sub(r"[ \t]+", " ", h)


def citados(txt):
    """Nomes no formato 'Fulano de Tal (SIGLA)', separados por cargo pelo subtítulo da lista."""
    achados = {"depfed": [], "depest": []}
    cargo = None
    for linha in txt.split("\n"):
        alvo = sem_acento(linha)
        if "DEPUTADO FEDERAL" in alvo and len(linha) < 200:
            cargo = "depfed"
        elif "DEPUTADO ESTADUAL" in alvo and len(linha) < 200:
            cargo = "depest"
        if cargo is None:
            continue
        for nome, sigla in re.findall(r"([A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][\w'’.\- ÁÂÃÀÉÊÍÓÔÕÚÜÇáâãàéêíóôõúüç]{1,48}?)"
                                      r"\s*\(([A-Za-zÇç ]{2,16})\)", linha):
            if sem_acento(sigla) not in {sem_acento(p) for p in PARTIDOS}:
                continue
            nome = nome.strip(" .-–—")
            if nome and nome not in [n for n, _ in achados[cargo]]:
                achados[cargo].append((nome, sigla.strip().upper()))
    return achados


def universo():
    """Todas as candidaturas registradas de deputado no RJ, para resolver cada nome citado."""
    caminho = os.path.join(DEP, "candidatos-rjsp.csv")
    linhas = list(csv.DictReader(io.open(caminho, encoding="utf-8-sig")))
    fora = []
    for l in linhas:
        if (l.get("uf") or "").strip().upper() != "RJ":
            continue
        c = sem_acento(l.get("cargo", ""))
        cargo = "depfed" if "FEDERAL" in c else ("depest" if "ESTADUAL" in c or "DISTRITAL" in c else None)
        if cargo:
            fora.append({"cargo": cargo, "id_tse": l.get("id_tse", ""),
                         "nome_urna": l.get("nome_urna", ""), "nome_completo": l.get("nome_completo", ""),
                         "partido": (l.get("partido") or "").strip().upper(), "slug": l.get("slug", "")})
    return fora


def resolver(nome, sigla, cargo, univ):
    """Acerto único por (nome de urna, partido, cargo). Sem acerto único, ninguém entra."""
    alvo, sig = sem_acento(nome), sem_acento(sigla)
    mesmo_cargo = [c for c in univ if c["cargo"] == cargo]
    exatos = [c for c in mesmo_cargo if sem_acento(c["nome_urna"]) == alvo]
    com_partido = [c for c in exatos if sem_acento(c["partido"]) == sig]
    if len(com_partido) == 1:
        return com_partido[0], "nome de urna e partido conferem"
    if len(exatos) == 1:
        return exatos[0], "nome de urna único no cargo, partido divergente da matéria"
    if len(exatos) > 1:
        return None, "homônimo: %d candidaturas com esse nome de urna" % len(exatos)
    porpartido = [c for c in mesmo_cargo
                  if sem_acento(c["partido"]) == sig and sem_acento(c["nome_completo"]).startswith(alvo)]
    if len(porpartido) == 1:
        return porpartido[0], "nome completo começa pelo citado, partido confere"
    # O caso que mais aparece aqui não é nome inventado: é a matéria pôr o candidato no cargo
    # errado. Já aconteceu na curadoria (notas/curadoria-deputados-rjsp-2026-09-07.md) e
    # continua acontecendo. Dizer qual é o cargo registrado poupa a conferência humana, e
    # continua não entrando sozinho: quem manda sobre cargo é o registro, não o jornal.
    noutro = [c for c in univ if c["cargo"] != cargo and sem_acento(c["nome_urna"]) == alvo]
    if len(noutro) == 1:
        outro = {"depfed": "deputado federal", "depest": "deputado estadual"}[noutro[0]["cargo"]]
        return None, "a matéria lista neste cargo, mas o registro no TSE é de %s (%s)" % (
            outro, noutro[0]["partido"])
    return None, "sem candidatura registrada correspondente"


def main():
    univ = universo()
    hoje = datetime.now(timezone(timedelta(hours=-3))).date().isoformat()
    paginas, erros = [], []
    for url in FONTES:
        try:
            html = baixar(url)
            paginas.append((url, html))
        except Exception as e:                                   # rede é rede
            erros.append("%s -> %s" % (url, e))
    if not paginas:
        sys.exit("nenhuma fonte respondeu:\n  " + "\n  ".join(erros))

    io.open(os.path.join(DEP, "_pesquisa-deputados-rj.html"), "w", encoding="utf-8").write(
        "\n\n<!-- ===== %s ===== -->\n\n".join(h for _, h in paginas))

    por_fonte = [(url, citados(texto_de(html))) for url, html in paginas]
    principal_url, principal = por_fonte[0]

    # divergência entre matéria e espelho não é detalhe: é sinal de que o extrator leu errado
    avisos = []
    for url, outro in por_fonte[1:]:
        for cargo in ("depfed", "depest"):
            a = {sem_acento(n) for n, _ in principal[cargo]}
            b = {sem_acento(n) for n, _ in outro[cargo]}
            if a and b and (a - b or b - a):
                avisos.append("%s (%s): só na principal %s | só no espelho %s"
                              % (cargo, url, sorted(a - b)[:6], sorted(b - a)[:6]))

    saida = []
    for cargo in ("depfed", "depest"):
        for nome, sigla in principal[cargo]:
            achou, motivo = resolver(nome, sigla, cargo, univ)
            saida.append({
                "uf": "RJ", "cargo": cargo,
                "nome_citado": nome, "partido_citado": sigla,
                "id_tse": achou["id_tse"] if achou else "",
                "slug": achou["slug"] if achou else "",
                "nome_urna": achou["nome_urna"] if achou else "",
                "status": "resolvido" if achou else "conferir",
                "motivo": motivo,
                "medida": "citado espontaneamente entre os mais lembrados",
                "posicao": "",           # a matéria publica em ordem alfabética, sem classificação
                "percentual": "",        # não publicado; célula vazia é indisponível, nunca zero
                "fonte": "Prefab Future / Diário do Rio, registro TSE RJ-02770/2026",
                "fonte_url": principal_url, "data_acesso": hoje, **FICHA,
            })

    cols = ["uf","cargo","nome_citado","partido_citado","id_tse","slug","nome_urna","status","motivo",
            "medida","posicao","percentual","instituto","contratante","registro_tse","campo_inicio",
            "campo_fim","entrevistas","margem","confianca","coleta","tipo","fonte","fonte_url","data_acesso"]
    with io.open(os.path.join(DEP, "_pesquisa-deputados-rj.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(saida)

    ok = sum(1 for l in saida if l["status"] == "resolvido")
    print("citados lidos: %d (federal %d, estadual %d) | resolvidos por id_tse: %d | conferir: %d"
          % (len(saida), len(principal["depfed"]), len(principal["depest"]), ok, len(saida) - ok))
    for a in avisos:
        print("AVISO divergência entre fontes:", a)
    for e in erros:
        print("AVISO fonte não respondeu:", e)
    if not saida:
        sys.exit("nenhum nome extraído: a matéria mudou de formato, o extrator precisa de revisão")


if __name__ == "__main__":
    main()
