# -*- coding: utf-8 -*-
"""Leitura do resultado oficial do TSE (dados/resultados) para o mural.

Fica fora de _gerar_mural.py porque o gerador é um script de topo, que regrava as páginas quando
é importado; aqui as funções podem ser testadas sozinhas (testes/test_resultados.py).

A pasta padrão é dados/resultados. A variável de ambiente MURAL_RESULTADOS aponta para outra pasta
com os mesmos dois arquivos, e é assim que os testes leem as fixtures de testes/fixtures/resultados.

Nada aqui pode derrubar o gerador: na noite de 25/10/2026 o passo "Regenerar" do atualizar.yml roda
de 20 em 20 minutos sem continue-on-error, e um CSV com uma linha ruim pararia a publicação inteira.
Linha que não converte vira AVISO e fica de fora; arquivo que falta devolve vazio, e o mural cai
no comportamento de pesquisa.
"""
import csv
import io
import os
import re
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_PADRAO = os.path.join(AQUI, "..", "dados", "resultados")
FONTE = "https://resultados.tse.jus.br/oficial/ele2026"
CARGO = {"presidente": "pres", "governador": "gov", "senador": "sen"}
UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO")
# Configuração do 2º turno de governador publicada pelo TSE, conferida em 13/10/2026. Só vale
# quando totais.csv não existe; com o arquivo, a lista sai dele.
UF2T_PADRAO = ["AC", "AM", "DF", "ES", "RN"]
FINALISTAS_PADRAO = ["Flávio Bolsonaro", "Lula"]
# o coletor nacional grava o cenário do 2º turno com este par fixo (CENARIO_2T)
PAR_DO_COLETOR = {"Lula", "Flávio Bolsonaro"}
SOMA_MIN, SOMA_MAX = 99.5, 100.5
PARTICULAS = {"da", "de", "do", "das", "dos", "e", "di", "du"}


def pasta_padrao():
    return os.environ.get("MURAL_RESULTADOS") or PASTA_PADRAO


def _sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def titulo(s):
    """Caixa de título por palavra, com as partículas em minúsculas: 'SILVIA HELLEN DA SILVA' vira
    'Silvia Hellen da Silva'. O TSE grava nome de urna e município em maiúsculas."""
    palavras = " ".join((s or "").split()).lower().split(" ")
    out = []
    for i, p in enumerate(palavras):
        if i and p in PARTICULAS:
            out.append(p)
        else:
            out.append(re.sub(r"(^|[-'’(/])(\w)", lambda m: m.group(1) + m.group(2).upper(), p))
    return " ".join(out).strip()


def municipio_uf(s):
    """'ANÁPOLIS/GO' ou 'Garanhuns (PE)' -> 'Anápolis (GO)', 'Garanhuns (PE)'."""
    s = " ".join((s or "").split())
    m = re.match(r"^(.*?)\s*(?:\(([A-Za-z]{2})\)|[/-]\s*([A-Za-z]{2}))$", s)
    if not m:
        return titulo(s)
    return "%s (%s)" % (titulo(m.group(1)), (m.group(2) or m.group(3)).upper())


def normalizar_sit(txt):
    """Situação do TSE em quatro valores: 'eleito', '2t', 'nao' ou ''.

    "Não eleito" contém "eleito", então o "não" é testado primeiro. A coluna eleito do CSV não é
    lida em lugar nenhum: o TSE marca 's' também para quem foi ao 2º turno, e quem lê 's' como
    eleito anuncia dois presidentes em 4/10."""
    t = _sem_acento(txt).strip()
    if not t:
        return ""
    if re.search(r"\bnao\b", t):
        return "nao"
    if "turno" in t:
        return "2t"
    if "eleit" in t:
        return "eleito"
    return ""


def _avisar(avisar, msg):
    (avisar or (lambda m: print("AVISO resultados:", m)))(msg)


def _ler_csv(caminho, avisar):
    """Linhas do CSV como dicionários, ou None se o arquivo não existe ou não pode ser lido."""
    if not os.path.isfile(caminho):
        return None
    try:
        with io.open(caminho, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        _avisar(avisar, "%s não pôde ser lido (%s)" % (os.path.basename(caminho), e))
        return None


def _int(v, obrigatorio=True):
    v = (v or "").strip()
    if v == "":
        if obrigatorio:
            raise ValueError("vazio")
        return None
    return int(float(v))


def _float(v):
    v = (v or "").strip()
    if v == "":
        raise ValueError("vazio")
    return float(v)


def ler_resultados(pasta=None, nomes=None, avisar=None):
    """DATA.resultados a partir de candidatos.csv e totais.csv, ou {} sem os arquivos.

    Forma: {fonte, pres: {"1": {"BR": A, "AC": A, ..., "ZZ": A}, "2": {...}}, gov: {...}, sen: {...}},
    com A = {est: "final"|"parcial", tot: {sec, st, pst, el, comp, abst, vv, vb, vn, vagas, at},
    c: [[chave, nome, numero, partido, votos, pct, sit], ...]} em ordem de votos.

    Só entra apuração com seção totalizada: antes da votação o TSE publica o 2º turno zerado, e
    zero ali não é resultado. `nomes` leva a chave do mural (nome do presidenciável ou slug
    estadual) ao nome exibido; sem par, vale o nome de urna em caixa de título."""
    pasta = pasta or pasta_padrao()
    nomes = nomes or {}
    tot_l = _ler_csv(os.path.join(pasta, "totais.csv"), avisar)
    cand_l = _ler_csv(os.path.join(pasta, "candidatos.csv"), avisar)
    if tot_l is None or cand_l is None:
        return {}
    totais = {}
    for n, r in enumerate(tot_l, 2):
        try:
            turno, cargo = r["turno"].strip(), CARGO[r["cargo"].strip()]
            ab = r["abrangencia"].strip().upper()
            if turno not in ("1", "2") or not ab:
                raise ValueError("turno ou abrangência inválidos")
            st = _int(r["secoes_totalizadas"])
            if st <= 0:
                continue
            pst = _float(r["pct_totalizado"])
            tot = {"sec": _int(r["secoes"], False), "st": st, "pst": pst,
                   "el": _int(r["eleitorado"], False), "comp": _int(r["comparecimento"], False),
                   "abst": _int(r["abstencao"], False), "vv": _int(r["validos"], False),
                   "vb": _int(r["brancos"], False), "vn": _int(r["nulos"], False),
                   "vagas": _int(r["vagas"], False), "at": (r.get("atualizado_tse") or "").strip()}
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            _avisar(avisar, "totais.csv, linha %d ignorada (%s): %s" % (n, e, dict(r)))
            continue
        totais[(cargo, turno, ab)] = tot
    linhas = {}
    for n, r in enumerate(cand_l, 2):
        try:
            turno, cargo = r["turno"].strip(), CARGO[r["cargo"].strip()]
            ab = r["abrangencia"].strip().upper()
            if (cargo, turno, ab) not in totais:
                continue
            votos, pct = _int(r["votos"]), _float(r["pct_validos"])
            chave = (r.get("mural") or "").strip()
            if chave and chave in nomes:
                nome = nomes[chave]
            elif chave and cargo == "pres":
                nome = chave
            else:
                nome = titulo(r["nome_urna"])
            linha = [chave, nome, (r.get("numero") or "").strip(), (r.get("partido") or "").strip(),
                     votos, pct, normalizar_sit(r.get("situacao"))]
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            _avisar(avisar, "candidatos.csv, linha %d ignorada (%s): %s" % (n, e, dict(r)))
            continue
        linhas.setdefault((cargo, turno, ab), []).append(linha)
    res = {}
    for (cargo, turno, ab), tot in sorted(totais.items()):
        c = sorted(linhas.get((cargo, turno, ab), []), key=lambda x: (-x[4], x[2]))
        if not c:
            _avisar(avisar, "%s %sº turno %s: totais sem nenhum candidato, apuração ignorada" % (cargo, turno, ab))
            continue
        est = "final" if round(tot["pst"], 2) >= 100 else "parcial"
        # Na apuração final os percentuais fecham 100 (arredondados a duas casas); fora da faixa,
        # falta candidato ou a coleta veio pela metade, e um número errado não vai para a capa.
        # A parcial não é conferida: o TSE totaliza seção por seção e a soma oscila.
        soma = sum(x[5] for x in c)
        if est == "final" and not SOMA_MIN <= soma <= SOMA_MAX:
            _avisar(avisar, "%s %sº turno %s: apuração final somando %.2f%%, descartada" % (cargo, turno, ab, soma))
            continue
        res.setdefault(cargo, {}).setdefault(turno, {})[ab] = {"est": est, "tot": tot, "c": c}
    if not res:
        return {}
    return {"fonte": FONTE, **{k: res[k] for k in ("pres", "gov", "sen") if k in res}}


def ufs_2t(pasta=None, avisar=None):
    """UFs com 2º turno de governador: as que têm linha de turno 2 em totais.csv.

    Lidas direto do arquivo, porque antes da votação a apuração do 2º turno existe zerada e
    ler_resultados a omite. Nunca da situação do 1º turno: em 4/10/2026 Tocantins saiu marcado
    "2º turno" e o TSE não configurou 2º turno no estado."""
    tot_l = _ler_csv(os.path.join(pasta or pasta_padrao(), "totais.csv"), avisar)
    if tot_l is None:
        return list(UF2T_PADRAO)
    return sorted({(r.get("abrangencia") or "").strip().upper() for r in tot_l
                   if (r.get("turno") or "").strip() == "2" and (r.get("cargo") or "").strip() == "governador"} - {""})


def ufs_pendentes(res, uf2t):
    """UFs que o 1º turno marcou "2º turno" para governador e que não estão na lista do 2º turno,
    cada uma com os dois nomes e os percentuais (as linhas de A.c com sit '2t')."""
    gov1 = (res or {}).get("gov", {}).get("1", {})
    out = []
    for uf in sorted(gov1):
        if uf not in UFS or uf in uf2t:
            continue
        c = [x for x in gov1[uf]["c"] if x[6] == "2t"]
        if c:
            out.append({"uf": uf, "c": c})
    return out


def finalistas(res, avisar=None):
    """Quem foi ao 2º turno presidencial, por votos; sem resultado, o par fixo do coletor."""
    br = (res or {}).get("pres", {}).get("1", {}).get("BR")
    if not br:
        return list(FINALISTAS_PADRAO)
    f = [x[0] or x[1] for x in br["c"] if x[6] == "2t"]
    if set(f) != PAR_DO_COLETOR:
        _avisar(avisar, "finalistas do TSE (%s) diferentes do par que o coletor nacional grava (%s)"
                % (", ".join(f) or "nenhum", " x ".join(sorted(PAR_DO_COLETOR))))
    return f


def eleitos_1t(res, cargo):
    """UFs com eleito no 1º turno, e quantos eleitos ao todo (o Senado elege dois por UF em 2026)."""
    a1 = (res or {}).get(cargo, {}).get("1", {})
    ufs = sorted(uf for uf, a in a1.items() if uf in UFS and any(x[6] == "eleito" for x in a["c"]))
    n = sum(1 for uf in ufs for x in a1[uf]["c"] if x[6] == "eleito")
    return ufs, n


def resumo(res, uf2t, pend):
    """Linhas para o log do gerador, com a conferência das 27 UFs no governo."""
    if not res:
        return ["resultado do TSE: nenhuma apuração com seção totalizada (o mural fica só com as pesquisas)"]
    linhas = []
    for cargo in ("pres", "gov", "sen"):
        for turno, por_ab in sorted(res.get(cargo, {}).items()):
            est = sorted({a["est"] for a in por_ab.values()})
            linhas.append("resultado do TSE: %s %sº turno em %d abrangências (%s)"
                          % (cargo, turno, len(por_ab), ", ".join(est)))
    gov_uf, _ = eleitos_1t(res, "gov")
    _, n_sen = eleitos_1t(res, "sen")
    total = len(gov_uf) + len(uf2t) + len(pend)
    conf = "governadores: %d eleitos no 1º turno + %d UFs de 2º turno (%s) + %d pendentes no TSE (%s) = %d" % (
        len(gov_uf), len(uf2t), ", ".join(uf2t), len(pend), ", ".join(p["uf"] for p in pend), total)
    if res.get("gov", {}).get("1") and total != 27:
        conf = "AVISO " + conf + ", e não 27"
    linhas.append(conf)
    if res.get("sen", {}).get("1"):
        linhas.append("senadores eleitos no 1º turno: %d" % n_sen)
    return linhas
