# -*- coding: utf-8 -*-
"""Procura o verbete da Wikipédia de cada deputado curado de RJ e SP.

Proporcional é onde homônimo mais aparece: são milhares de candidatos por disputa e nomes
de urna curtos ("Freixo", "Conrado", "Barba"). O bug mais sério já corrigido neste projeto
foi exatamente casamento de identidade por nome fraco, então aqui o aceite não olha só o
título do resultado: ele lê a introdução do verbete e exige prova.

Como pontua, do mais forte para o mais fraco:

  +7  a introdução traz o nome completo do TSE (todos os tokens com três letras ou mais,
      na ordem ou não). É a prova forte: o verbete de Eduardo Bolsonaro não diz "Marcelo
      Messias Bolsonaro", e o do jogador Luís Fabiano não diz "Luis Fabiano Clemente".
  +3  a introdução tem papel político (deputado, vereador, político...) e cita o estado
      ou o partido da candidatura.
  +2  todo token do título cabe dentro do nome completo. Segura "Luiz Fernando Machado" e
      "Luiz Paulo Conde", que acrescentam sobrenome que o candidato não tem.
  -8  o título tem token de nome que não existe no nome completo nem no nome de urna.
  -8  o verbete é de outra coisa (clube, banda, município, filme, desambiguação).

Aceita 8 ou mais, o que na prática significa: ou o nome completo aparece no verbete, ou o
título cabe no nome e o texto confirma cargo e estado. Empate resolve pelo maior.

A saída é uma PROPOSTA, com pontuação e o trecho que sustentou cada aceite, para
conferência humana antes de qualquer nome entrar na lista congelada de verbetes.

Roda no GitHub Actions: do contêiner do Claude a Wikipédia responde 403 no proxy de saída.
Uso: python3 coleta/wikipedia_verbetes_deputados.py [--limite N]
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DEP = os.path.join(RAIZ, "dados", "rjsp")
API = "https://pt.wikipedia.org/w/api.php"
UA = "observatorio-2026/0.3 (coleta automática; contato: figuered0o0808@gmail.com)"
UF_NOME = {"RJ": "Rio de Janeiro", "SP": "São Paulo"}
PAPEL = ("polit", "deputad", "vereador", "senador", "prefeit", "governador", "parlamentar",
         "secretario", "ministro", "candidat")
RUIM = ("futebol", "clube", "banda", "album", "cancao", "filme", "novela", "municipio",
        "bairro", "escola de samba", "personagem", "desambiguacao", "igreja", "distrito",
        "estacao", "rodovia", "especie", "genero de", "telenovela", "jogo eletronico")
CORTE = {"de", "da", "do", "dos", "das", "e", "-"}
TRATAMENTO = {"dr", "dra", "delegado", "delegada", "pastor", "pastora", "professor", "professora",
              "capitao", "coronel", "general", "sargento", "soldado", "mc", "dj", "doutor",
              "doutora", "tia", "tio", "irmao", "irma", "vereador", "vereadora", "deputado",
              "deputada", "indio", "india", "sargenta"}


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def toks(s, minimo=3):
    return [t for t in re.split(r"[^a-z0-9]+", norm(s)) if len(t) >= minimo and t not in CORTE]


def pedir(params, tentativas=3):
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2", "maxlag": "5"})
    espera = 5
    for t in range(tentativas):
        try:
            req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if t == tentativas - 1:
                print("  falhou: %s %s" % (type(e).__name__, str(e)[:70]), file=sys.stderr, flush=True)
                return None
            time.sleep(espera); espera = min(espera * 2, 20)


def buscar(termo, n=6):
    d = pedir({"action": "query", "list": "search", "srsearch": termo, "srlimit": n, "srprop": ""})
    if not d: return []
    return [x["title"] for x in d.get("query", {}).get("search", [])]


def intros(titulos):
    """Introdução em texto puro de até 20 verbetes por chamada."""
    if not titulos: return {}
    d = pedir({"action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
               "exlimit": "20", "redirects": "1", "titles": "|".join(titulos)})
    if not d: return {}
    out = {}
    q = d.get("query", {})
    volta = {}
    for r in q.get("redirects", []) or []: volta[r["to"]] = r["from"]
    for r in q.get("normalized", []) or []: volta.setdefault(r["to"], r["from"])
    for p in q.get("pages", []):
        if p.get("missing"): continue
        out[p["title"]] = p.get("extract", "")
    return out


def pontuar(titulo, intro, c):
    t_norm, i_norm = norm(titulo), norm(intro)
    completo = toks(c["nome_completo"])
    urna = [t for t in toks(c["nome_urna"]) if t not in TRATAMENTO]
    t_toks = [t for t in toks(titulo) if t not in TRATAMENTO]
    if not t_toks: return -20
    p = 0
    if completo and all(t in i_norm for t in completo): p += 7
    if any(w in i_norm for w in PAPEL) and (norm(UF_NOME[c["uf"]]) in i_norm or norm(c["partido"]) in i_norm):
        p += 3
    if all(t in completo or t in urna for t in t_toks): p += 2
    else: p -= 8
    if any(w in t_norm for w in RUIM) or any(w in i_norm[:160] for w in RUIM): p -= 8
    return p


def main():
    lim = None
    if "--limite" in sys.argv: lim = int(sys.argv[sys.argv.index("--limite") + 1])
    cands = list(csv.DictReader(io.open(os.path.join(DEP, "candidatos-deputados.csv"), encoding="utf-8-sig")))
    if lim: cands = cands[:lim]
    linhas = []
    for i, c in enumerate(cands, 1):
        vistos = []
        for termo in (c["nome_urna"], c["nome_completo"], f'{c["nome_urna"]} {UF_NOME[c["uf"]]} político'):
            for t in buscar(termo):
                if t not in vistos: vistos.append(t)
            time.sleep(0.3)
        textos = intros(vistos[:20])
        melhor = (-99, "", "")
        for t in vistos:
            intro = textos.get(t, "")
            if not intro: continue
            p = pontuar(t, intro, c)
            if p > melhor[0]: melhor = (p, t, intro)
        p, titulo, intro = melhor
        status = "aceito" if p >= 8 else "sem verbete localizado"
        linhas.append([c["uf"], c["slug"], c["nome_urna"], c["nome_completo"],
                       titulo if p >= 8 else "", p, re.sub(r"\s+", " ", intro)[:200], status])
        print(f"{i:3d}/{len(cands)} {c['uf']} {c['nome_urna'][:28]:28s} {p:4d} {status:22s} {titulo[:42]}", flush=True)
        time.sleep(0.3)
    saida = os.path.join(DEP, "_verbetes-deputados.csv")
    with io.open(saida, "w", newline="\r\n", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["uf", "slug", "nome_urna", "nome_completo", "verbete", "pontuacao", "trecho", "status"])
        w.writerows(linhas)
    ok = sum(1 for l in linhas if l[7] == "aceito")
    print(f"\n{saida}: {len(linhas)} linhas, {ok} verbetes aceitos, {len(linhas)-ok} sem verbete")


if __name__ == "__main__":
    main()
