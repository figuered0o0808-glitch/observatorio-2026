#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcilia os CSVs de uma pasta de trabalho externa com os do repositório.

Em 21/9/2026 descobrimos duas bases vivendo em paralelo: o snapshot das 8h e das 20h escrevia
numa pasta do Cowork que não é um clone deste repositório (histórias git sem ancestral comum,
então rebase e merge estão fora), enquanto a rotina automática do repositório coletava pesquisas,
Wikipédia e Trends, mas não o Instagram próprio nem as candidaturas no TSE. As duas divergiram.

Este script traz o dado de lá para cá arquivo a arquivo, com a regra certa para cada um, e
CONFERE ANTES DE ESCREVER. Sem --aplicar ele não toca em nada: só relata o que faria.

    python3 coleta/_reconciliar_cowork.py "~/documentos observatório 2026"
    python3 coleta/_reconciliar_cowork.py "~/documentos observatório 2026" --aplicar

Depois de aplicar, rode testes/guarda_dados.py e testes/verificar.sh antes de commitar. A forma
dos arquivos (BOM e CRLF) é preservada como está no repositório, porque a guarda cobra isso.
"""
import csv, io, os, sys

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Superconjunto: a pasta externa contém tudo o que o repositório tem, e mais. O script confere
# que isso é verdade linha a linha antes de copiar; se não for, recusa e diz o que se perderia.
SUPERCONJUNTO = {
    "dados/serie-diaria.csv": ("data", "candidato", "plataforma"),
    "dados/wikipedia-pageviews.csv": ("data", "candidato"),
    "dados/trends-2026.csv": ("data", "lote", "termo"),
}
# União por chave: os dois lados têm linhas exclusivas e nenhuma pode sumir.
UNIAO = {
    "dados/eventos.csv": ("data", "candidato", "evento"),
    "dados/pesquisas-registradas.csv": ("instituto", "data_divulgacao", "cenario", "candidato"),
}
# Conferência humana: campos de ficha que mudam por reconciliação, não por acréscimo. O script
# mostra a diferença campo a campo e só escreve com --aplicar-fichas, nunca junto do resto.
FICHAS = {
    "dados/candidatos.csv": "candidato",
    "dados/tse-presidenciaveis.csv": "nome_urna",
}


def forma(caminho):
    """BOM e fim de linha do arquivo como ele está no repositório."""
    b = io.open(caminho, "rb").read(4000)
    return b.startswith(b"\xef\xbb\xbf"), (b"\r\n" in b)


def ler(caminho):
    with io.open(caminho, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, [dict(x) for x in r]


def escrever(caminho, cols, linhas, bom, crlf):
    with io.open(caminho, "w", encoding="utf-8-sig" if bom else "utf-8",
                 newline="\r\n" if crlf else "\n") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n" if crlf else "\n")
        w.writeheader()
        for l in linhas:
            w.writerow({c: l.get(c, "") for c in cols})


def chave(l, campos):
    return tuple((l.get(c) or "").strip() for c in campos)


def relatar(nome, msgs):
    print("\n=== %s" % nome)
    for m in msgs:
        print("   " + m)


def superconjunto(rel, ext, campos):
    """Copia de fora, depois de provar que nenhuma linha do repositório se perde ou muda."""
    cols, aqui = ler(rel)
    _, la = ler(ext)
    ia = {chave(l, campos): l for l in aqui}
    ie = {chave(l, campos): l for l in la}
    sumiriam = [k for k in ia if k not in ie]
    mudariam = [k for k in ia if k in ie and ia[k] != ie[k]]
    msgs = ["repositório %d linhas | pasta externa %d linhas" % (len(aqui), len(la)),
            "novas: %d" % len([k for k in ie if k not in ia])]
    if sumiriam:
        msgs.append("RECUSADO: %d linha(s) do repositório não existem na pasta externa, ex.: %s"
                    % (len(sumiriam), sumiriam[:3]))
    if mudariam:
        msgs.append("ATENÇÃO: %d linha(s) existentes mudariam de conteúdo, ex.: %s"
                    % (len(mudariam), mudariam[:3]))
        for k in mudariam[:3]:
            dif = [c for c in cols if (ia[k].get(c) or "") != (ie[k].get(c) or "")]
            msgs.append("   %s difere em: %s" % (str(k), ", ".join(dif)))
    return msgs, (None if sumiriam else la), cols


def uniao(rel, ext, campos):
    """Junta os dois lados pela chave. Em empate de chave, o repositório manda e o script avisa."""
    cols, aqui = ler(rel)
    _, la = ler(ext)
    ia = {chave(l, campos): l for l in aqui}
    saida = list(aqui)
    novas, divergentes = 0, []
    for l in la:
        k = chave(l, campos)
        if k not in ia:
            saida.append(l); novas += 1
        elif ia[k] != l:
            divergentes.append(k)
    msgs = ["repositório %d | pasta externa %d | união %d (%d vindas de fora)"
            % (len(aqui), len(la), len(saida), novas)]
    if divergentes:
        msgs.append("%d chave(s) iguais com conteúdo diferente; fica a do repositório: %s"
                    % (len(divergentes), divergentes[:3]))
    return msgs, saida, cols


def duplicata_de_grafia(linhas):
    """Mesma rodada publicada sob grafias diferentes de instituto vira pesquisa contada duas vezes.

    A chave da guarda inclui o instituto, então "Nexus/BTG" e "BTG/Nexus" passariam como duas
    rodadas e a média contaria a mesma pesquisa em dobro. Dois sinais, os dois fortes:

    1. mesmo número de registro no TSE sob institutos de nome diferente. O registro identifica a
       pesquisa; é quase certeza de duplicata.
    2. o conjunto inteiro de candidatos e percentuais idêntico, no mesmo cenário e com o mesmo
       período de campo, sob institutos diferentes. Dois institutos coincidirem num candidato é
       rotina; coincidirem na tabela inteira, não.

    Comparar um candidato e um percentual sozinhos não serve: em 21/9/2026 essa regra acusou 53
    rodadas, quase todas legítimas (Datafolha e Gerp dando 1% ao mesmo nome no mesmo dia).
    O script nunca apaga: só lista para conferência.
    """
    achados = []
    porReg = {}
    for l in linhas:
        reg = (l.get("registro_tse") or "").strip()
        if reg:
            porReg.setdefault(reg, set()).add((l.get("instituto") or "").strip())
    for reg, insts in sorted(porReg.items()):
        if len(insts) > 1:
            achados.append(("registro %s" % reg, sorted(insts)))

    porRodada = {}
    for l in linhas:
        k = ((l.get("instituto") or "").strip(), (l.get("data_divulgacao") or "").strip(),
             (l.get("cenario") or "").strip())
        porRodada.setdefault(k, {"campo": ((l.get("data_campo_inicio") or "").strip(),
                                           (l.get("data_campo_fim") or "").strip()), "pts": set()})
        porRodada[k]["pts"].add(((l.get("candidato") or "").strip(), (l.get("percentual") or "").strip()))
    porTabela = {}
    for (inst, div, cen), v in porRodada.items():
        if len(v["pts"]) < 3:
            continue   # tabela curta demais para a coincidência significar algo
        assin = (div, cen, v["campo"], tuple(sorted(v["pts"])))
        porTabela.setdefault(assin, set()).add(inst)
    for assin, insts in porTabela.items():
        if len(insts) > 1:
            achados.append(("%s · %s · campo %s a %s · %d nomes iguais"
                            % (assin[0], assin[1], assin[2][0], assin[2][1], len(assin[3])), sorted(insts)))
    return achados


def fichas(rel, ext, idc):
    """Diferença campo a campo entre as duas fichas, para o olho humano decidir."""
    cols, aqui = ler(rel)
    ce, la = ler(ext)
    ia = {(l.get(idc) or "").strip(): l for l in aqui}
    ie = {(l.get(idc) or "").strip(): l for l in la}
    msgs = ["repositório %d candidatura(s) | pasta externa %d" % (len(aqui), len(la))]
    for n in sorted(set(ie) - set(ia)):
        msgs.append("SÓ NA PASTA EXTERNA: %s" % n)
    for n in sorted(set(ia) - set(ie)):
        msgs.append("SÓ NO REPOSITÓRIO: %s" % n)
    for n in sorted(set(ia) & set(ie)):
        dif = [c for c in cols if c in ce and (ia[n].get(c) or "") != (ie[n].get(c) or "")]
        for c in dif:
            msgs.append("%s · %s: repo %r -> externa %r" % (n, c, ia[n].get(c), ie[n].get(c)))
    if ce != cols:
        msgs.append("ATENÇÃO: as colunas diferem; só as do repositório seriam gravadas")
    return msgs, la, cols


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    aplicar_fichas = "--aplicar-fichas" in sys.argv
    if not args:
        print(__doc__); return 2
    base = os.path.expanduser(args[0])
    if not os.path.isdir(base):
        print("pasta não encontrada: %s" % base); return 2
    print("repositório:    %s" % AQUI)
    print("pasta externa:  %s" % base)
    print("modo:           %s" % ("APLICANDO" if aplicar or aplicar_fichas else "só conferindo (use --aplicar)"))

    faltando, recusados = [], []
    for grupo, alvo, fn in (("superconjunto", SUPERCONJUNTO, superconjunto),
                            ("união", UNIAO, uniao)):
        for caminho, campos in alvo.items():
            rel, ext = os.path.join(AQUI, caminho), os.path.join(base, caminho)
            if not os.path.exists(ext):
                faltando.append(caminho); continue
            msgs, saida, cols = fn(rel, ext, campos)
            if caminho == "dados/pesquisas-registradas.csv" and saida:
                dup = duplicata_de_grafia(saida)
                msgs.append("rodadas suspeitas de grafia dupla de instituto: %d" % len(dup))
                for descr, insts in dup[:10]:
                    msgs.append("   %s sob: %s" % (descr, " / ".join(insts)))
                if dup:
                    msgs.append("   nada foi apagado; confira e resolva à mão antes de publicar")
            relatar("%s · %s" % (caminho, grupo), msgs)
            if saida is None:
                recusados.append(caminho); continue
            if aplicar:
                bom, crlf = forma(rel)
                escrever(rel, cols, saida, bom, crlf)
                print("   gravado")

    for caminho, idc in FICHAS.items():
        rel, ext = os.path.join(AQUI, caminho), os.path.join(base, caminho)
        if not os.path.exists(ext):
            faltando.append(caminho); continue
        msgs, saida, cols = fichas(rel, ext, idc)
        relatar("%s · conferência humana" % caminho, msgs)
        if aplicar_fichas:
            bom, crlf = forma(rel)
            escrever(rel, cols, saida, bom, crlf)
            print("   gravado")
        else:
            print("   não gravado: leia a lista acima e rode com --aplicar-fichas se concordar")

    if faltando:
        print("\nnão existem na pasta externa (ignorados): %s" % ", ".join(faltando))
    if recusados:
        print("\nRECUSADOS por perda de linha: %s" % ", ".join(recusados))
        return 1
    print("\nPróximo passo: python3 testes/guarda_dados.py && ./testes/verificar.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
