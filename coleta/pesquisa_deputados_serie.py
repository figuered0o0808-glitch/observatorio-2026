# -*- coding: utf-8 -*-
"""Série de pesquisas nominais de deputado no RJ: Vetor Arrow para o Agenda do Poder.

Isto é o que faltava para o proporcional. A parceria Agenda do Poder / Instituto Vetor Arrow
registrou no TRE-RJ uma série de rodadas de intenção de voto espontânea para deputado
estadual e federal, 14 mil entrevistas por rodada, com etapas em julho, três em agosto,
quatro em setembro e uma em outubro. Ao contrário da Prefab, essas rodadas publicam
PERCENTUAL e posição, e são várias ao longo do tempo, que é exatamente o que o agregador do
mural precisa: peso por data, comparação entre rodadas e dispersão para medir incerteza.

ATENÇÃO, e isto muda o que se pode fazer com o dado: a série é CUMULATIVA. Cada divulgação
soma as entrevistas das rodadas anteriores (14.510 em junho, 14.404 em julho, 14.605 na
primeira de agosto, 14.671 na segunda, "totalizando 58.190"). Rodada cumulativa não é
observação independente: jogar isso no agregador do mural, que pesa rodadas por data
supondo independência, contaria as mesmas entrevistas várias vezes e amorteceria a
tendência por construção. Por isso cada linha carrega a coluna `cumulativa` e o total
acumulado, e quem for usar tem de tratar a série como acumulado, não como rodadas soltas.
A coleta também é por telefone (URA), com menção espontânea.

Cada rodada tem seu próprio número de registro (já apareceram RJ-04533/2026 e RJ-06966/2026),
então o registro é lido do texto de cada matéria, nunca carimbado de fora. Rodada sem registro
legível não vira dado: pesquisa eleitoral divulgada sem registro é justamente o que não se
deve reproduzir.

Roda no runner do GitHub: os domínios respondem bloqueados no proxy do contêiner.

O que sai é PROPOSTA, em dados/rjsp/_serie-deputados-rj.csv, com o HTML bruto ao lado. Cada
nome é resolvido contra a candidatura registrada por id_tse, com o mesmo resolvedor estreito
do outro coletor (nome de urna, ou nome civil dentro do nome completo, sempre com partido e
cargo conferindo e acerto único).

Uso: python3 coleta/pesquisa_deputados_serie.py [--offline]
"""
import csv, io, os, re, sys, urllib.request
from datetime import datetime, timezone, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from pesquisa_deputados_rj import (DEP, UA, baixar, sem_acento, texto_de, universo, resolver)

FONTES = [
    {"url": "https://agendadopoder.com.br/conheca-os-10-pre-candidatos-a-deputado-estadual-que-lideram-as-intencoes-de-voto-no-rio/",
     "uf": "RJ", "cargo": "depest"},
    {"url": "https://agendadopoder.com.br/conheca-os-10-pre-candidatos-a-deputado-federal-que-lideram-as-intencoes-de-voto-no-rio/",
     "uf": "RJ", "cargo": "depfed"},
    {"url": "https://natividadefm.com.br/2026/07/18/pesquisa-aponta-nomes-mais-citados-para-a-camara-federal-no-rio-de-janeiro/",
     "uf": "RJ", "cargo": "depfed"},
    {"url": "https://redecatolicanews.com.br/2026/06/13/pesquisa-aponta-rosenverg-reis-na-lideranca-da-corrida-para-deputado-federal-no-rj/",
     "uf": "RJ", "cargo": "depfed"},
    # Rodadas seguintes. O Agenda do Poder publica o ranking dentro de um gráfico; os espelhos
    # às vezes o transcrevem em texto, e é de onde o número tem chance de sair legível.
    {"url": "https://agendadopoder.com.br/vetor-arrow-canella-assume-a-lideranca-entre-os-candidatos-a-deputado-estadual/",
     "uf": "RJ", "cargo": "depest"},
    {"url": "https://agendadopoder.com.br/vetor-arrow-canella-e-o-destaque-entre-os-candidatos-a-deputado-estadual-veja-o-ranking-dos-mais-citados/",
     "uf": "RJ", "cargo": "depest"},
    {"url": "https://mancheterio.com.br/ceciliano-canela-e-rosenverg-aparecem-entre-os-candidatos-a-deputado-estadual-mais-citados-em-pesquisa-vettor-arrow-veja-o-ranking/",
     "uf": "RJ", "cargo": "depest"},
    {"url": "https://www.osulfluminense.com/post/rosenverg-reis-lidera-nova-rodada-de-pesquisa-para-deputado-estadual-no-rio",
     "uf": "RJ", "cargo": "depest"},
]

MESES = {"janeiro":1,"fevereiro":2,"marco":3,"abril":4,"maio":5,"junho":6,"julho":7,
         "agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12}
SIGLA = r"[A-Za-zÁÂÃÀÉÊÍÓÔÕÚÜÇáâãàéêíóôõúüç ]{2,16}"
NOME = r"[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][\w'’.\- ÁÂÃÀÉÊÍÓÔÕÚÜÇáâãàéêíóôõúüç]{1,48}?"


def ficha_de(txt):
    """Ficha técnica lida do texto da própria matéria. Sem registro, a rodada não entra."""
    f = {}
    m = re.search(r"\b([A-Z]{2}-\d{4,6}/20\d\d)\b", txt)
    if m: f["registro"] = m.group(1)

    m = re.search(r"([\d][\d.\s]{0,9})\s*mil\s+(?:eleitores|entrevistas|pessoas)", txt, re.I)
    if m:
        f["n"] = str(int(float(m.group(1).replace(".", "").strip()) * 1000))
    else:
        m = re.search(r"([\d][\d.]{2,9})\s*(?:eleitores|entrevistas|entrevistados|pessoas)", txt, re.I)
        if m: f["n"] = m.group(1).replace(".", "")

    m = re.search(r"margem de erro[^\d]{0,30}([\d]+[,.]?\d*)", txt, re.I)
    if m: f["margem"] = m.group(1).replace(",", ".")
    m = re.search(r"(?:confian[çc]a)[^\d]{0,20}(\d{2})\s*%", txt, re.I)
    if m: f["confianca"] = m.group(1)

    m = re.search(r"de\s+(\d{1,2})\s+a\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(20\d\d))?", txt, re.I)
    if m:
        mes = MESES.get(sem_acento(m.group(3)).lower())
        ano = m.group(4) or "2026"
        if mes:
            f["de"] = "%s-%02d-%02d" % (ano, mes, int(m.group(1)))
            f["ate"] = "%s-%02d-%02d" % (ano, mes, int(m.group(2)))

    m = re.search(r"totalizando\s+([\d.]+)\s*(?:mil\s+)?(?:entrevistas|eleitores)", txt, re.I)
    if m: f["acumulado"] = m.group(1).replace(".", "")
    f["cumulativa"] = "1" if re.search(r"cumulativ|acumulad", txt, re.I) else ""
    f["coleta"] = "telefone (URA)" if re.search(r"\bURA\b|IVR", txt) else (
        "presencial" if re.search(r"presencia", txt, re.I) else "")
    f["tipo"] = "espontanea" if re.search(r"espont[âa]nea", txt, re.I) else (
        "estimulada" if re.search(r"estimulad", txt, re.I) else "")
    m = re.search(r"(Vetor Arrow|Vetor|Prefab Future|Prefab|Quaest|Datafolha|Paraná Pesquisas)", txt, re.I)
    if m: f["inst"] = m.group(1)
    return f


# NOME é não-guloso e tudo que vem depois dele é opcional, então sozinho ele casa uma letra
# só e o filtro de tamanho descartava tudo. Para posição é preciso um padrão de nome próprio
# de verdade: duas a quatro palavras capitalizadas, aceitando "de", "da", "dos" no meio.
MAI = "A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ"
MIN = "a-záâãàéêíóôõúüç"
PALAVRA = rf"(?:[{MAI}][{MIN}'’]+|[{MAI}]{{2,4}})"
NOME_PROPRIO = rf"{PALAVRA}(?:\s+(?:d[aeo]s?\s+)?{PALAVRA}){{1,3}}"

# Maiúsculas que não são nome de gente e por isso não invalidam a leitura da posição.
INSTITUCIONAIS = {"FEDERACAO", "PARTIDO", "UNIAO", "PROGRESSISTA", "ALERJ", "ASSEMBLEIA",
                  "CAMARA", "SENADO", "REDE", "BAIXADA", "FLUMINENSE", "RIO", "JANEIRO",
                  "ESTADO", "INSTITUTO", "VETOR", "ARROW", "NA", "NO", "ELE", "ELA", "OS",
                  "REPUBLICANOS", "SOLIDARIEDADE", "AVANTE", "PODEMOS", "CIDADANIA"}

ORDINAIS = {"primeiro":1,"primeira":1,"segundo":2,"segunda":2,"terceiro":3,"terceira":3,
            "quarto":4,"quarta":4,"quinto":5,"quinta":5,"sexto":6,"sexta":6,"setimo":7,
            "setima":7,"oitavo":8,"oitava":8,"nono":9,"nona":9,"decimo":10,"decima":10}
POS_RE = (r"(?:em|no|na|ao|para\s+o|para\s+a)\s+(%s)\b(?!\s*(?:lugar|colocacao|posicao|posto)?\s*[a-z]{4,})"
          r"|(?:o|a|na|no|em)?\s*(%s)\s*(?:lugar|colocacao|posicao|posto)") % ("|".join(ORDINAIS), "|".join(ORDINAIS))


def posicoes(txt):
    """Posição no ranking, que é o que estas rodadas publicam para deputado.

    Descoberta que custou algumas tentativas: a série do Vetor Arrow publica PERCENTUAL para
    governador e Senado ("Paes lidera com 28,9%") e apenas ORDEM para deputado ("consolidado
    em primeiro lugar", "assumiu o terceiro lugar", "aparece na nona colocação"). Os espelhos
    da rodada de agosto trazem zero por cento no texto inteiro. Então o dado do proporcional
    aqui é ordinal, e ordinal é o que vai ser guardado: não se inventa percentual a partir de
    posição, e o gráfico honesto disso é evolução de ranking, não barra de intenção de voto.

    Só entra afirmação explícita, do tipo "<Nome> ... <ordinal> lugar", com o ordinal perto do
    nome. Posição implícita ("seguido por fulano") NÃO é lida: inferir que o seguinte é o
    próximo colocado parece óbvio e erra sempre que o texto cita alguém no meio da frase.
    """
    achados, conflitos = {}, []
    limpo = re.sub(r"\s+", " ", txt)
    alvo = sem_acento(limpo)
    for m in re.finditer(rf"({NOME_PROPRIO})\s*(?:\(({SIGLA})\))?", limpo):
        nome = m.group(1).strip(" .-–—")
        if len(nome) < 5 or " " not in nome:
            continue
        # "Federação PSOL-Rede" casa o padrão de nome próprio e disputava o mesmo lugar com o
        # candidato ao lado, fazendo os dois serem descartados pela regra de duplicado
        if sem_acento(nome.split()[0]) in INSTITUCIONAIS:
            continue
        # sem_acento devolve MAIÚSCULAS, e a versão anterior comparava a janela já
        # maiusculizada contra [A-Z]{2,}, o que barrava toda linha. A janela do ordinal é
        # sem acento e minúscula; a de checar nome vizinho é o texto como veio.
        crua = limpo[m.end(): m.end() + 130]
        # o partido vem entre parênteses logo depois do nome, e "Federação União Progressista"
        # é maiúscula sem ser gente. Tirar o parêntese e ignorar palavra institucional evita
        # descartar metade dos citados por causa da pontuação da frase.
        crua = re.sub(r"\([^)]*\)", " ", crua)
        janela = sem_acento(crua).lower()
        g = re.search(POS_RE, janela)
        if not g:
            continue
        # o ordinal tem de vir antes de outro nome próprio, senão é a posição do vizinho
        antes = crua[:g.start()]
        vizinho = [w for w in re.findall(rf"\b[{MAI}][{MIN}]{{2,}}", antes)
                   if sem_acento(w) not in INSTITUCIONAIS]
        if vizinho:
            continue
        pos = ORDINAIS[g.group(1) or g.group(2)]
        chave = sem_acento(nome)
        if chave in achados and achados[chave][0] != pos:
            conflitos.append((nome, achados[chave][0], pos))
            continue
        achados[chave] = (pos, nome, (m.group(2) or "").strip().upper())
    porpos = {}
    for pos, nome, sig in achados.values():
        porpos.setdefault(pos, []).append((nome, sig))
    # duas pessoas no mesmo lugar significa leitura errada, não empate: nenhuma das duas entra
    saida = [(nome, sig, pos) for pos, lst in porpos.items() if len(lst) == 1
             for nome, sig in lst]
    dup = {p: [n for n, _ in l] for p, l in porpos.items() if len(l) > 1}
    return sorted(saida, key=lambda x: x[2]), conflitos, dup


def main():
    univ = universo()
    hoje = datetime.now(timezone(timedelta(hours=-3))).date().isoformat()
    bruto_path = os.path.join(DEP, "_serie-deputados-rj.html")
    lidas, erros = [], []
    if "--offline" in sys.argv:
        bruto = io.open(bruto_path, encoding="utf-8").read()
        partes = re.split(r"<!-- ===== (\S+) ===== -->", bruto)[1:]
        porurl = dict(zip(partes[0::2], partes[1::2]))
        lidas = [(f, porurl[f["url"]]) for f in FONTES if f["url"] in porurl]
        print("modo offline: %d páginas do bruto guardado" % len(lidas))
    else:
        for f in FONTES:
            try:
                lidas.append((f, baixar(f["url"])))
            except Exception as e:
                erros.append("%s -> %s" % (f["url"], e))
    for e in erros:
        print("AVISO fonte não respondeu:", e)
    if lidas and "--offline" not in sys.argv:
        io.open(bruto_path, "w", encoding="utf-8").write(
            "\n\n".join("<!-- ===== %s ===== -->\n%s" % (f["url"], h) for f, h in lidas))
    if not lidas:
        sys.exit("nenhuma fonte respondeu")

    saida = []
    print("== o que cada fonte trouxe ==")
    for f, html in lidas:
        txt = texto_de(html)
        fi = ficha_de(txt)
        pc, conflitos, dup = posicoes(txt)
        print("  %s | registro=%s campo=%s..%s n=%s margem=%s tipo=%s inst=%s | com posição=%d"
              % (f["cargo"], fi.get("registro", "-"), fi.get("de", "-"), fi.get("ate", "-"),
                 fi.get("n", "-"), fi.get("margem", "-"), fi.get("tipo", "-"),
                 fi.get("inst", "-"), len(pc)))
        for n, a, b in conflitos:
            print("    AVISO %s aparece em %dº e %dº na mesma matéria" % (n, a, b))
        for p, ns in sorted(dup.items()):
            print("    AVISO %dº lugar com mais de um nome (%s): nenhum entra" % (p, ", ".join(ns)))
        print("    " + f["url"])
        imgs = imagens_da_pesquisa(html, f["url"]) if "--offline" not in sys.argv else []
        if imgs:
            print("    gráficos guardados para transcrição: " + ", ".join(imgs))
        if not fi.get("registro"):
            print("    PULADA: sem número de registro legível no texto")
            continue
        if not pc:
            continue
        for nome, sig, v in pc:   # v é a POSIÇÃO no ranking, não percentual
            achou, motivo = resolver(nome, sig, f["cargo"], univ)
            saida.append({
                "uf": f["uf"], "cargo": f["cargo"], "registro_tse": fi["registro"],
                "campo_inicio": fi.get("de", ""), "campo_fim": fi.get("ate", ""),
                "instituto": fi.get("inst", ""), "entrevistas": fi.get("n", ""),
                "margem": fi.get("margem", ""), "confianca": fi.get("confianca", ""),
                "tipo": fi.get("tipo", ""), "natureza": "registrada",
                "cumulativa": fi.get("cumulativa", ""), "acumulado": fi.get("acumulado", ""),
                "coleta": fi.get("coleta", ""),
                "nome_citado": nome, "partido_citado": sig,
                "posicao": str(v),
                "percentual": "",      # não publicado para deputado; vazio é indisponível
                "medida": "posição no ranking de citações espontâneas",
                "id_tse": achou["id_tse"] if achou else "",
                "slug": achou["slug"] if achou else "",
                "nome_urna": achou["nome_urna"] if achou else "",
                "status": ("resolvido" if achou
                           else "nao_registrado" if "sem candidatura registrada no RJ" in motivo
                           else "conferir"),
                "motivo": motivo, "fonte_url": f["url"], "data_acesso": hoje,
            })

    cols = ["uf","cargo","registro_tse","campo_inicio","campo_fim","instituto","entrevistas",
            "acumulado","cumulativa","coleta","margem","confianca","tipo","natureza","medida",
            "nome_citado","partido_citado","posicao","percentual","id_tse","slug","nome_urna",
            "status","motivo","fonte_url","data_acesso"]
    with io.open(os.path.join(DEP, "_serie-deputados-rj.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(saida)

    rodadas = sorted({(l["registro_tse"], l["cargo"], l["campo_fim"]) for l in saida})
    ok = sum(1 for l in saida if l["status"] == "resolvido")
    print("\nrodadas com registro e percentual: %d | linhas: %d | resolvidas por id_tse: %d"
          % (len(rodadas), len(saida), ok))
    for r in rodadas:
        print("   registro %s | %s | campo até %s" % r)
    if not saida:
        print("nenhum percentual extraído; o HTML bruto ficou salvo para revisão")


if __name__ == "__main__":
    main()
