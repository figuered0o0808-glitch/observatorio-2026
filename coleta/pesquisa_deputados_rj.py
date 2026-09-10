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

# Cada fonte diz o que ela é. Isso não é decoração: pesquisa registrada no TSE e ranking de
# jornal são coisas de peso diferente, e o mural precisa dizer qual está mostrando. "registrada"
# tem número de registro, ficha técnica e responsabilidade legal; "nao_oficial" é levantamento,
# enquete ou lista de redação, sem registro, e entra marcada como tal.
FONTES = [
    {"url": "https://diariodorio.com/pesquisa-mostra-os-nomes-mais-citados-para-deputado-estadual-e-federal-do-rj-em-2026/",
     "uf": "RJ", "natureza": "registrada", "papel": "principal"},
    {"url": "https://diariodorio.com/pesquisa-diario-do-rio-prefab-revela-os-candidatos-a-deputado-mais-citados-no-rio/",
     "uf": "RJ", "natureza": "registrada", "papel": "espelho"},
    {"url": "https://rlagosnoticias.com.br/politica/pesquisa-prefab-revela-os-nomes-mais-citados-para-deputado-federal-e-estadual-no-rio-em-2026-confira-a-lista/",
     "uf": "RJ", "natureza": "registrada", "papel": "espelho"},
    {"url": "https://errejotanoticias.com.br/pesquisa-revela-os-candidatos-a-deputados-mais-citados-no-rio/",
     "uf": "RJ", "natureza": "registrada", "papel": "espelho"},
    {"url": "https://mancheterio.com.br/pesquisa-revela-os-candidatos-a-deputados-mais-citados-no-rio/",
     "uf": "RJ", "natureza": "registrada", "papel": "espelho"},
]

COLS = ["uf","cargo","nome_citado","partido_citado","id_tse","slug","nome_urna","status","motivo",
        "natureza","medida","posicao","percentual","instituto","contratante","registro_tse",
        "campo_inicio","campo_fim","entrevistas","margem","confianca","coleta","tipo","fonte",
        "fonte_url","data_acesso"]

PROMETIDOS = 30      # a matéria diz "os 30 mais citados" em cada cargo

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
                                      r"\s*\(([A-Za-zÁÂÃÀÉÊÍÓÔÕÚÜÇáâãàéêíóôõúüç ]{2,16})\)", linha):
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
    # O jornal escreve o nome civil; o TSE registra o nome de urna, que quase sempre é outro:
    # Marcelo Freixo é "FREIXO", Lindbergh Farias é "LINDBERGH", Daniela Carneiro é "DANIELA DO
    # WAGUINHO". Sem esta passagem, 11 dos 59 citados ficavam de fora, e justamente os mais
    # conhecidos. Continua estreito de propósito: todo token do nome citado tem de estar no nome
    # completo registrado, no mesmo cargo e no mesmo partido, e o acerto tem de ser único.
    # "Henrique Vieira" casa com três nomes completos no RJ e só um é do PSOL e do cargo certo.
    toks = [t for t in alvo.split() if len(t) > 2]
    if toks:
        porcompleto = [c for c in mesmo_cargo
                       if sem_acento(c["partido"]) == sig
                       and all(t in sem_acento(c["nome_completo"]) for t in toks)]
        if len(porcompleto) == 1:
            return porcompleto[0], ("nome civil da matéria dentro do nome completo registrado; "
                                    "concorre como \"%s\"" % porcompleto[0]["nome_urna"])
        if len(porcompleto) > 1:
            return None, "nome civil casa com %d candidaturas do mesmo partido" % len(porcompleto)
    # O caso que mais aparece aqui não é nome inventado: é a matéria pôr o candidato no cargo
    # errado. Já aconteceu na curadoria (notas/curadoria-deputados-rjsp-2026-09-07.md) e
    # continua acontecendo. Dizer qual é o cargo registrado poupa a conferência humana, e
    # continua não entrando sozinho: quem manda sobre cargo é o registro, não o jornal.
    noutro = [c for c in univ if c["cargo"] != cargo and sem_acento(c["nome_urna"]) == alvo]
    if len(noutro) == 1:
        outro = {"depfed": "deputado federal", "depest": "deputado estadual"}[noutro[0]["cargo"]]
        return None, "a matéria lista neste cargo, mas o registro no TSE é de %s (%s)" % (
            outro, noutro[0]["partido"])
    # A pesquisa é de 24 a 29 de julho e o registro de candidatura só fechou em 15 de agosto:
    # nome citado que não aparece em lugar nenhum do registro provavelmente não se candidatou.
    # É a mesma situação que o mural já trata nas majoritárias, onde nome testado que não
    # registrou fica na rodada antiga sem slug, marcado. Não é erro de leitura nem homônimo.
    solto = [c for c in univ if all(t in sem_acento(c["nome_completo"] + " " + c["nome_urna"])
                                    for t in toks)] if toks else []
    if not solto:
        return None, "citado na pesquisa, mas sem candidatura registrada no RJ (o campo foi em julho, antes do registro)"
    return None, "sem candidatura registrada correspondente"


def diagnostico(url, txt, achados):
    """O que a página realmente trouxe. Sem isto, extração vazia é um erro cego."""
    alvo = sem_acento(txt)
    return {
        "url": url, "caracteres": len(txt),
        "diz federal": "DEPUTADO FEDERAL" in alvo,
        "diz estadual": "DEPUTADO ESTADUAL" in alvo,
        "pares Nome (SIGLA)": len(re.findall(r"[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][^()\n]{1,48}\(([A-Za-zÁÂÃÀÉÊÍÓÔÕÚÜÇáâãàéêíóôõúüç ]{2,16})\)", txt)),
        "citados federal": len(achados["depfed"]), "citados estadual": len(achados["depest"]),
    }


def main():
    univ = universo()
    hoje = datetime.now(timezone(timedelta(hours=-3))).date().isoformat()
    lidas, erros = [], []
    # --offline reprocessa o bruto já guardado, sem bater no site outra vez. Serve para corrigir
    # o extrator sem gastar rodada de runner e sem incomodar o jornal a cada tentativa.
    if "--offline" in sys.argv:
        bruto = io.open(os.path.join(DEP, "_pesquisa-deputados-rj.html"), encoding="utf-8").read()
        partes = re.split(r"<!-- ===== (\S+) ===== -->", bruto)[1:]
        porurl = dict(zip(partes[0::2], partes[1::2]))
        for f in FONTES:
            if f["url"] in porurl:
                lidas.append((f, porurl[f["url"]]))
        print("modo offline: %d páginas lidas do bruto guardado" % len(lidas))
    else:
        for f in FONTES:
            try:
                lidas.append((f, baixar(f["url"])))
            except Exception as e:                               # rede é rede
                erros.append("%s -> %s" % (f["url"], e))

    # O bruto é gravado antes de qualquer extração, e a extração não pode derrubar o trabalho
    # de gravá-lo. A primeira rodada deste coletor morreu com "nenhum nome extraído" sem
    # commitar o HTML, e aí não havia como saber por quê. Diagnóstico só serve se sobreviver.
    if lidas and "--offline" not in sys.argv:
        io.open(os.path.join(DEP, "_pesquisa-deputados-rj.html"), "w", encoding="utf-8").write(
            "\n\n".join("<!-- ===== %s ===== -->\n%s" % (f["url"], h) for f, h in lidas))
    for e in erros:
        print("AVISO fonte não respondeu:", e)
    if not lidas:
        sys.exit("nenhuma fonte respondeu")

    por_fonte = [(f, citados(texto_de(h)), texto_de(h)) for f, h in lidas]
    print("== o que cada fonte trouxe ==")
    for f, achados, txt in por_fonte:
        d = diagnostico(f["url"], txt, achados)
        print("  " + " | ".join("%s=%s" % (k, v) for k, v in d.items() if k != "url"))
        print("    " + f["url"])

    principais = [(f, a) for f, a, _ in por_fonte if f["papel"] == "principal" and (a["depfed"] or a["depest"])]
    if not principais:
        principais = [(f, a) for f, a, _ in por_fonte if a["depfed"] or a["depest"]]
    if not principais:
        # Sem nome extraído o CSV sai vazio e o arquivo bruto fica commitado para revisão.
        # Não é sucesso, mas também não é motivo para jogar fora o que foi baixado.
        io.open(os.path.join(DEP, "_pesquisa-deputados-rj.csv"), "w", encoding="utf-8").write(
            ",".join(COLS) + "\r\n")
        print("nenhum nome extraído de nenhuma fonte; o HTML bruto ficou salvo para revisão")
        return
    fonte, principal = principais[0]

    # divergência entre a matéria e o espelho não é detalhe: é sinal de leitura errada
    avisos = []
    for f, outro, _ in por_fonte:
        if f["url"] == fonte["url"]:
            continue
        for cargo in ("depfed", "depest"):
            a = {sem_acento(n) for n, _ in principal[cargo]}
            b = {sem_acento(n) for n, _ in outro[cargo]}
            if a and b and (a - b or b - a):
                avisos.append("%s (%s): só na principal %s | só no espelho %s"
                              % (cargo, f["url"], sorted(a - b)[:6], sorted(b - a)[:6]))

    # A matéria promete 30 por cargo. Espelho concordando não prova leitura certa: os três
    # passam pelo mesmo extrator e erram junto. Foi assim que "Rafael Nobre (União Brasil)"
    # sumiu, porque o "Ã" da sigla não cabia na classe de caracteres. Contagem prometida é a
    # única testemunha independente do meu próprio código.
    for cargo, rotulo in (("depfed", "federal"), ("depest", "estadual")):
        if len(principal[cargo]) != PROMETIDOS:
            avisos.append("li %d nomes de deputado %s e a matéria promete %d: falta nome, o "
                          "extrator precisa de revisão" % (len(principal[cargo]), rotulo, PROMETIDOS))

    saida = []
    for cargo in ("depfed", "depest"):
        for nome, sigla in principal[cargo]:
            achou, motivo = resolver(nome, sigla, cargo, univ)
            saida.append({
                "uf": fonte["uf"], "cargo": cargo,
                "nome_citado": nome, "partido_citado": sigla,
                "id_tse": achou["id_tse"] if achou else "",
                "slug": achou["slug"] if achou else "",
                "nome_urna": achou["nome_urna"] if achou else "",
                "status": ("resolvido" if achou
                           else "nao_registrado" if "sem candidatura registrada no RJ" in motivo
                           else "conferir"),
                "motivo": motivo,
                "natureza": fonte["natureza"],
                "medida": "citado espontaneamente entre os mais lembrados",
                "posicao": "",           # a matéria publica em ordem alfabética, sem classificação
                "percentual": "",        # não publicado; célula vazia é indisponível, nunca zero
                "fonte": "Prefab Future / Diário do Rio, registro TSE RJ-02770/2026",
                "fonte_url": fonte["url"], "data_acesso": hoje, **FICHA,
            })

    with io.open(os.path.join(DEP, "_pesquisa-deputados-rj.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(saida)

    ok = sum(1 for l in saida if l["status"] == "resolvido")
    print("citados lidos: %d (federal %d, estadual %d) | resolvidos por id_tse: %d | conferir: %d"
          % (len(saida), len(principal["depfed"]), len(principal["depest"]), ok, len(saida) - ok))
    for a in avisos:
        print("AVISO divergência entre fontes:", a)


if __name__ == "__main__":
    main()
