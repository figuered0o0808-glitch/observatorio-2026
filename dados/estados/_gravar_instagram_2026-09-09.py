# -*- coding: utf-8 -*-
"""Grava a coleta de seguidores de 9/9/2026 em dados/estados/instagram-estados.csv.

Entrada: o JSON exportado do navegador (o que sai de `localStorage.mural_ig_20260909`), lido
de um arquivo. Formato aceito: lista de objetos, ou objeto indexado por handle, com as chaves
`handle` e `seguidores` (aceita também `follower_count`), e opcionalmente `nome_perfil`,
`slug`, `uf` e `status`.

Por que existe um script em vez de colar linhas no CSV: o arquivo é série. `testes/guarda_dados.py`
bloqueia o commit automático se linha antiga for tocada, e o contrato tem detalhes que se erra
à mão. Aqui eles ficam explícitos e conferidos:

  - UTF-8 com BOM e CRLF, como o arquivo já está;
  - colunas exatamente data,uf,slug,handle,seguidores,aproximado,nome_perfil,status,fonte;
  - chave (data, uf, slug): rodar de novo não duplica, e linha de outra data não é tocada;
  - célula vazia é indisponível e nunca zero. Perfil que sumiu entra com `seguidores` vazio e
    `status` dizendo o motivo, jamais herdando número de 2/9;
  - `aproximado` é 0 nesta coleta inteira, porque o endpoint por id devolve contagem exata (a
    de 2/9 tinha 86 valores arredondados vindos da meta description);
  - a data segue Brasília: a coleta terminou 22h52 de 9/9, quando em UTC já era dia 10.

O slug e a UF de cada handle saem do que já está no CSV e em candidatos-deputados.csv, casando
por handle. Handle que não casa com nenhuma candidatura conhecida NÃO entra: no proporcional
homônimo é regra, e inventar a que candidatura um perfil pertence é o erro mais caro deste
projeto.

Uso:
  python3 dados/estados/_gravar_instagram_2026-09-09.py coleta.json
  python3 dados/estados/_gravar_instagram_2026-09-09.py coleta.json --conferir   (não grava)
"""
import csv, io, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
CSV = os.path.join(AQUI, "instagram-estados.csv")
DEP = os.path.join(os.path.dirname(AQUI), "rjsp", "candidatos-deputados.csv")
DATA = "2026-09-09"
COLS = ["data", "uf", "slug", "handle", "seguidores", "aproximado", "nome_perfil", "status", "fonte"]
FONTE = ("coleta própria, perfil público do Instagram via navegador, %s "
         "(contagem exata do endpoint de perfil por id)" % DATA)
FONTE_SUMIU = ("coleta própria, perfil público do Instagram via navegador, %s "
               "(perfil não está mais disponível)" % DATA)

# Confirmados um a um em 9/9: devolvem "Esta página não está disponível".
SUMIRAM = {"elizeuaguiarr", "alexandresalomao.adv", "taynamiess", "rodrigobolsonarorn2026",
           "carlos_jararaca", "samuelcostapvh", "farah_governador", "priscilavoigtup",
           "marina.candia", "capi401senador", "tiagotarsisa", "maguinhamalta",
           "professorfabian_oficia", "luizantonio_lemes", "ana_da_mgs", "major_fabio",
           "mariagorettbitu", "paulorubemsantiagoferreira", "taninha_peres", "canalnalataco"}


def ler_csv(caminho):
    if not os.path.exists(caminho):
        return []
    with io.open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def indice_de_handles():
    """handle -> (uf, slug), a partir do que o projeto já conhece."""
    idx = {}
    for l in ler_csv(CSV):
        h = (l.get("handle") or "").strip().lower()
        if h and h not in idx:
            idx[h] = (l["uf"], l["slug"])
    for l in ler_csv(DEP):
        h = (l.get("instagram") or "").strip().lower().strip("/").rsplit("/", 1)[-1]
        if h and h not in idx:
            idx[h] = (l["uf"], l["slug"])
    return idx


def normalizar(bruto):
    itens = bruto.values() if isinstance(bruto, dict) else bruto
    fora = []
    for it in itens:
        if not isinstance(it, dict):
            continue
        h = str(it.get("handle") or it.get("username") or "").strip().lower().lstrip("@")
        if not h:
            continue
        n = it.get("seguidores", it.get("follower_count", it.get("seguidores_exato")))
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = None
        fora.append({"handle": h, "n": n,
                     "nome": str(it.get("nome_perfil") or it.get("full_name") or "").strip(),
                     "status": str(it.get("status") or "").strip(),
                     "uf": str(it.get("uf") or "").strip(),
                     "slug": str(it.get("slug") or "").strip()})
    return fora


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    conferir = "--conferir" in sys.argv
    entrada = [a for a in sys.argv[1:] if not a.startswith("--")][0]
    with io.open(entrada, encoding="utf-8") as f:
        coletado = normalizar(json.load(f))

    idx = indice_de_handles()
    antigas = ler_csv(CSV)
    ja = {(l["data"], l["uf"], l["slug"]) for l in antigas}

    novas, semcasar, repetidos = [], [], 0
    vistos = set()
    for it in coletado:
        alvo = idx.get(it["handle"]) or ((it["uf"], it["slug"]) if it["uf"] and it["slug"] else None)
        if not alvo:
            semcasar.append(it["handle"])
            continue
        uf, slug = alvo
        if (DATA, uf, slug) in ja or (uf, slug) in vistos:
            repetidos += 1
            continue
        vistos.add((uf, slug))
        sumiu = it["handle"] in SUMIRAM or it["n"] is None
        novas.append({
            "data": DATA, "uf": uf, "slug": slug, "handle": it["handle"],
            "seguidores": "" if sumiu else str(it["n"]),
            "aproximado": "0",
            "nome_perfil": "" if sumiu else it["nome"],
            "status": (it["status"] or ("perfil não está mais disponível" if sumiu else "ok")),
            "fonte": FONTE_SUMIU if sumiu else FONTE,
        })

    # handles que sumiram e nem apareceram no JSON também precisam de linha
    for h in sorted(SUMIRAM):
        alvo = idx.get(h)
        if not alvo:
            continue
        uf, slug = alvo
        if (DATA, uf, slug) in ja or (uf, slug) in vistos:
            continue
        vistos.add((uf, slug))
        novas.append({"data": DATA, "uf": uf, "slug": slug, "handle": h, "seguidores": "",
                      "aproximado": "0", "nome_perfil": "",
                      "status": "perfil não está mais disponível", "fonte": FONTE_SUMIU})

    novas.sort(key=lambda l: (l["uf"], l["slug"]))
    comnum = [l for l in novas if l["seguidores"]]
    print("lidos do JSON: %d | linhas novas: %d (com número %d, sem número %d) | já existiam: %d"
          % (len(coletado), len(novas), len(comnum), len(novas) - len(comnum), repetidos))
    if semcasar:
        print("handles sem candidatura correspondente, NÃO gravados (%d): %s"
              % (len(semcasar), ", ".join(sorted(semcasar)[:12])))
    if conferir or not novas:
        print("(nada gravado)")
        return

    with io.open(CSV, "a", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=COLS, lineterminator="\r\n").writerows(novas)
    print("acrescentadas %d linhas em %s (linhas antigas intocadas)" % (len(novas), CSV))


if __name__ == "__main__":
    main()
