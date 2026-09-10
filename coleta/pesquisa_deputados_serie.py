# -*- coding: utf-8 -*-
"""Série de pesquisas nominais de deputado no RJ: Vetor Arrow para o Agenda do Poder.

Isto é o que faltava para o proporcional. A parceria Agenda do Poder / Instituto Vetor Arrow
registrou no TRE-RJ uma série de rodadas de intenção de voto espontânea para deputado
estadual e federal, 14 mil entrevistas por rodada, com etapas em julho, três em agosto,
quatro em setembro e uma em outubro. Ao contrário da Prefab, essas rodadas publicam
PERCENTUAL e posição, e são várias ao longo do tempo, que é exatamente o que o agregador do
mural precisa: peso por data, comparação entre rodadas e dispersão para medir incerteza.

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

    f["tipo"] = "espontanea" if re.search(r"espont[âa]nea", txt, re.I) else (
        "estimulada" if re.search(r"estimulad", txt, re.I) else "")
    m = re.search(r"(Vetor Arrow|Vetor|Prefab Future|Prefab|Quaest|Datafolha|Paraná Pesquisas)", txt, re.I)
    if m: f["inst"] = m.group(1)
    return f


def percentuais(txt, cargo):
    """Triplas (nome, sigla, percentual). Só entra quem tem número: sem número não é medida."""
    achados, vistos = [], set()
    padroes = [
        rf"({NOME})\s*\(({SIGLA})\)[^\d%\n]{{0,24}}(\d{{1,2}}[,.]\d{{1,2}}|\d{{1,2}})\s*%",
        rf"(\d{{1,2}}[,.]\d{{1,2}}|\d{{1,2}})\s*%[^\w\n]{{0,12}}({NOME})\s*\(({SIGLA})\)",
    ]
    for i, pad in enumerate(padroes):
        for g in re.finditer(pad, txt):
            if i == 0:
                nome, sig, pct = g.group(1), g.group(2), g.group(3)
            else:
                pct, nome, sig = g.group(1), g.group(2), g.group(3)
            nome = nome.strip(" .-–— ")
            chave = sem_acento(nome)
            if not nome or chave in vistos:
                continue
            try:
                v = float(pct.replace(",", "."))
            except ValueError:
                continue
            if not (0 < v <= 100):
                continue
            vistos.add(chave)
            achados.append((nome, sig.strip().upper(), v))
    return achados


def imagens_da_pesquisa(html, base):
    """Baixa os gráficos da matéria. Os números do Vetor Arrow saem em imagem, não em texto.

    A matéria traz o registro, a amostra e o instituto por escrito, e manda "confira os
    pré-candidatos com maior intenção de votos" apontando para um JPG. Extrator de texto não
    alcança isso, e OCR de gráfico eu não uso para publicar número atribuído a pessoa de
    verdade: um dígito lido errado vira percentual falso no nome de um candidato, sem
    segunda fonte para desmentir. Então o coletor guarda a imagem no repositório, com a URL
    de origem, e a transcrição é feita por quem consegue olhar, conferindo contra o gráfico
    que fica arquivado ao lado.
    """
    pasta = os.path.join(DEP, "pesquisas-imagens")
    os.makedirs(pasta, exist_ok=True)
    salvas = []
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', html):
        src = m.group(1).split("?")[0]
        alvo = sem_acento(src)
        if "WP-CONTENT/UPLOADS" not in alvo:
            continue
        if not any(k in alvo for k in ("VETOR", "PESQUISA", "DEPUTAD", "INTENCAO", "GRAFICO")):
            continue
        nome = re.sub(r"[^A-Za-z0-9._-]", "-", src.rsplit("/", 1)[-1])[:80]
        destino = os.path.join(pasta, nome)
        if os.path.exists(destino):
            salvas.append(nome); continue
        try:
            req = urllib.request.Request(src, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                dados = r.read()
            if len(dados) > 400:
                io.open(destino, "wb").write(dados)
                salvas.append(nome)
        except Exception as e:
            print("    imagem não baixou:", src[:80], e)
    return salvas


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
        fi, pc = ficha_de(txt), percentuais(txt, f["cargo"])
        print("  %s | registro=%s campo=%s..%s n=%s margem=%s tipo=%s inst=%s | com percentual=%d"
              % (f["cargo"], fi.get("registro", "-"), fi.get("de", "-"), fi.get("ate", "-"),
                 fi.get("n", "-"), fi.get("margem", "-"), fi.get("tipo", "-"),
                 fi.get("inst", "-"), len(pc)))
        print("    " + f["url"])
        imgs = imagens_da_pesquisa(html, f["url"]) if "--offline" not in sys.argv else []
        if imgs:
            print("    gráficos guardados para transcrição: " + ", ".join(imgs))
        if not fi.get("registro"):
            print("    PULADA: sem número de registro legível no texto")
            continue
        if not pc:
            continue
        for nome, sig, v in pc:
            achou, motivo = resolver(nome, sig, f["cargo"], univ)
            saida.append({
                "uf": f["uf"], "cargo": f["cargo"], "registro_tse": fi["registro"],
                "campo_inicio": fi.get("de", ""), "campo_fim": fi.get("ate", ""),
                "instituto": fi.get("inst", ""), "entrevistas": fi.get("n", ""),
                "margem": fi.get("margem", ""), "confianca": fi.get("confianca", ""),
                "tipo": fi.get("tipo", ""), "natureza": "registrada",
                "nome_citado": nome, "partido_citado": sig, "percentual": ("%.2f" % v),
                "id_tse": achou["id_tse"] if achou else "",
                "slug": achou["slug"] if achou else "",
                "nome_urna": achou["nome_urna"] if achou else "",
                "status": ("resolvido" if achou
                           else "nao_registrado" if "sem candidatura registrada no RJ" in motivo
                           else "conferir"),
                "motivo": motivo, "fonte_url": f["url"], "data_acesso": hoje,
            })

    cols = ["uf","cargo","registro_tse","campo_inicio","campo_fim","instituto","entrevistas",
            "margem","confianca","tipo","natureza","nome_citado","partido_citado","percentual",
            "id_tse","slug","nome_urna","status","motivo","fonte_url","data_acesso"]
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
