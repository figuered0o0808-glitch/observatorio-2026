# -*- coding: utf-8 -*-
"""Procura o verbete da Wikipédia de cada deputado curado de RJ e SP.

Mesmo método já usado nas disputas majoritárias (coleta/navegador_estados.md, seção 4),
escrito aqui para rodar sem navegador: busca pelo nome completo entre aspas, depois sem
aspas, depois nome de urna mais estado mais "político"; pontua coincidência de tokens do
título com o nome, papel político no trecho e menção ao estado, e desconta títulos que
são clube, banda, município, filme e afins. Aceita pontuação 6 ou mais.

Proporcional é onde homônimo mais aparece: são milhares de candidatos por disputa e nomes
de urna curtos. Por isso o aceite exige token distintivo do nome no título e o resultado
sai para conferência antes de virar dado.

Saída: dados/rjsp/_verbetes-deputados.csv (proposta, para conferência) (uf,slug,nome_urna,nome_completo,verbete,
pontuacao,trecho,status), no mesmo formato de dados/estados/wikipedia-verbetes-estados.csv
mais as colunas de nome para a conferência.

Roda no GitHub Actions: do contêiner do Claude a Wikipédia responde 403 no proxy de saída.
Uso: python3 coleta/wikipedia_verbetes_deputados.py [--limite N]
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DEP = os.path.join(RAIZ, "dados", "rjsp")
API = "https://pt.wikipedia.org/w/api.php"
UA = "MuralDosCandidatos/1.0 (observatorio de candidatos 2026; contato pelo repositorio)"
UF_NOME = {"RJ": "Rio de Janeiro", "SP": "São Paulo"}
PAPEL = ("polít", "deputad", "vereador", "senador", "prefeit", "governador", "advogad",
         "delegad", "pastor", "jornalist", "empresár", "sindicalist", "ativist")
RUIM = ("futebol", "clube", "banda", "álbum", "canção", "filme", "novela", "município",
        "bairro", "rio ", "avenida", "escola de samba", "personagem", "desambiguação",
        "igreja", "distrito", "estação", "rodovia", "espécie", "gênero de")

def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()

def tokens(nome):
    corte = {"de", "da", "do", "dos", "das", "e", "junior", "filho", "neto", "sobrinho"}
    return [t for t in re.split(r"[^a-z0-9]+", norm(nome)) if len(t) > 2 and t not in corte]

def pedir(params, tentativas=5):
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    espera = 5
    for t in range(tentativas):
        try:
            req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if t == tentativas - 1:
                print("  falhou:", type(e).__name__, str(e)[:80], file=sys.stderr)
                return None
            time.sleep(espera); espera = min(espera * 2, 60)

def buscar(termo, n=6):
    d = pedir({"action": "query", "list": "search", "srsearch": termo, "srlimit": n,
               "srprop": "snippet"})
    if not d: return []
    return [(x["title"], re.sub("<[^>]+>", "", x.get("snippet", ""))) for x in d.get("query", {}).get("search", [])]

def pontuar(titulo, trecho, nome_urna, nome_completo, uf):
    t_norm, tr_norm = norm(titulo), norm(trecho)
    toks_c, toks_u = tokens(nome_completo), tokens(nome_urna)
    distintivos = [t for t in toks_c if len(t) >= 4]
    achados = [t for t in toks_c if t in t_norm]
    # sem nenhum token distintivo do nome no título, não é a pessoa: é o principal freio de homônimo
    if not any(t in t_norm for t in distintivos): return 0, "sem token distintivo no título"
    p = 2 * len(achados)
    if all(t in t_norm for t in toks_u): p += 2
    if any(w in tr_norm for w in PAPEL): p += 3
    if norm(UF_NOME[uf]) in tr_norm or norm(uf) == t_norm[-2:]: p += 1
    if any(w in t_norm for w in RUIM) or any(w in tr_norm[:80] for w in RUIM): p -= 6
    if "(" in titulo and not any(w in t_norm for w in ("polit", "deputad")): p -= 1
    return p, ""

def main():
    lim = None
    if "--limite" in sys.argv: lim = int(sys.argv[sys.argv.index("--limite") + 1])
    cands = list(csv.DictReader(io.open(os.path.join(DEP, "candidatos-deputados.csv"), encoding="utf-8-sig")))
    if lim: cands = cands[:lim]
    linhas = []
    for i, c in enumerate(cands, 1):
        uf, urna, completo = c["uf"], c["nome_urna"], c["nome_completo"]
        melhor = (0, "", "", "")
        for termo in (f'"{completo}"', completo, f'{urna} {UF_NOME[uf]} político'):
            for titulo, trecho in buscar(termo):
                p, _ = pontuar(titulo, trecho, urna, completo, uf)
                if p > melhor[0]: melhor = (p, titulo, trecho, termo)
            time.sleep(0.4)
            if melhor[0] >= 10: break
        p, titulo, trecho, _ = melhor
        status = "aceito" if p >= 6 else "sem verbete localizado"
        linhas.append([uf, c["slug"], urna, completo, titulo if p >= 6 else "", p,
                       trecho[:180], status])
        print(f"{i:3d}/{len(cands)} {uf} {urna[:28]:28s} {p:3d} {status:22s} {titulo[:40]}", flush=True)
    saida = os.path.join(DEP, "_verbetes-deputados.csv")
    with io.open(saida, "w", newline="\r\n", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["uf", "slug", "nome_urna", "nome_completo", "verbete", "pontuacao", "trecho", "status"])
        w.writerows(linhas)
    ok = sum(1 for l in linhas if l[7] == "aceito")
    print(f"\n{saida}: {len(linhas)} linhas, {ok} verbetes aceitos, {len(linhas)-ok} sem verbete")

if __name__ == "__main__":
    main()
