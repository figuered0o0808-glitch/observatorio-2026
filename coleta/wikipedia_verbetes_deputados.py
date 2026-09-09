# -*- coding: utf-8 -*-
"""Procura o verbete da Wikipédia de cada deputado curado de RJ e SP.

Proporcional é onde homônimo mais aparece: são milhares de candidatos por disputa e nomes
de urna curtos ("Freixo", "Conrado", "Barba"). O bug mais sério já corrigido neste projeto
foi exatamente casamento de identidade por nome fraco, então aqui o aceite não olha só o
título do resultado: ele lê a introdução do verbete e exige prova.

Como pontua, do mais forte para o mais fraco:

  +7  a introdução traz o nome completo do TSE inteiro. É a prova forte: o verbete de
      Eduardo Bolsonaro não diz "Marcelo Bolsonaro", e o de Thiago Auricchio não diz
      "Thiago dos Reis Pereira dos Santos".
  +5  traz o primeiro e o último nome e ao menos 60% dos tokens (verbete que abrevia o
      nome do meio, que é o caso comum).
  +4  o título é exatamente o nome de urna. Sozinho não basta: nome artístico curto
      ("Benny Briolly", "MC Smith", "Índia Armelau") quase nunca traz o nome de cartório
      no verbete, e é para esses que essa linha existe.
  +3  a introdução tem papel político e cita o estado ou o partido da candidatura.
  +2  todo token do título cabe no nome completo ou no nome de urna. Segura
      "Luiz Fernando Machado" e "Luiz Paulo Conde", que acrescentam sobrenome.
  -8  o título acrescenta nome que o candidato não tem.
 -20  página de desambiguação, ou título que é clube, banda, município, filme.

Aceita 8 ou mais, o que sempre exige duas evidências independentes. Token conta como
presente com uma letra de diferença ("Brito" do TSE e "Britto" do verbete).

O "não é pessoa" olha só o título: biografia de pastor fala de igreja, a de jogador fala
de futebol e a de ator fala de novela, e nenhuma das três deixa de ser biografia.

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


def perto(t, alvos):
    """Token presente, aceitando uma letra de diferença: o TSE grafa Brito e o verbete Britto."""
    if t in alvos: return True
    if len(t) < 5: return False
    for u in alvos:
        if abs(len(u) - len(t)) > 1 or u[0] != t[0]: continue
        i = j = dif = 0
        while i < len(t) and j < len(u):
            if t[i] == u[j]: i += 1; j += 1; continue
            dif += 1
            if dif > 1: break
            if len(t) == len(u): i += 1; j += 1
            elif len(t) > len(u): i += 1
            else: j += 1
        if dif + (len(t) - i) + (len(u) - j) <= 1: return True
    return False


def pontuar(titulo, intro, c):
    sem_par = re.sub(r"\([^)]*\)", " ", titulo)          # "(política)" não é sobrenome
    t_norm, i_norm = norm(titulo), norm(intro)
    i_toks = set(toks(intro, 2))
    completo = toks(c["nome_completo"])
    urna = [t for t in toks(c["nome_urna"]) if t not in TRATAMENTO]
    t_toks = [t for t in toks(sem_par) if t not in TRATAMENTO]
    if not t_toks: return -20
    if "pode referir-se a" in i_norm or "desambiguacao" in t_norm: return -20
    if any(w in t_norm for w in RUIM): return -20
    p = 0
    achados = [t for t in completo if perto(t, i_toks)]
    if completo and len(achados) == len(completo): p += 7
    elif completo and len(achados) >= max(2, int(0.6 * len(completo))) \
            and perto(completo[0], i_toks) and perto(completo[-1], i_toks): p += 5
    if urna and [t for t in toks(sem_par) if t not in TRATAMENTO] == urna: p += 4
    partido = norm(c["partido"])
    if any(w in i_norm for w in PAPEL) and (norm(UF_NOME[c["uf"]]) in i_norm
                                            or partido in i_toks or partido in i_norm):
        p += 3
    if all(perto(t, set(completo) | set(urna)) for t in t_toks): p += 2
    else: p -= 8
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
                       titulo if p >= 8 else "", p, re.sub(r"\s+", " ", intro)[:200], status,
                       titulo])
        print(f"{i:3d}/{len(cands)} {c['uf']} {c['nome_urna'][:28]:28s} {p:4d} {status:22s} {titulo[:42]}", flush=True)
        time.sleep(0.3)
    saida = os.path.join(DEP, "_verbetes-deputados.csv")
    with io.open(saida, "w", newline="\r\n", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["uf", "slug", "nome_urna", "nome_completo", "verbete", "pontuacao", "trecho",
                    "status", "melhor_titulo"])
        w.writerows(linhas)
    ok = sum(1 for l in linhas if l[7] == "aceito")
    print(f"\n{saida}: {len(linhas)} linhas, {ok} verbetes aceitos, {len(linhas)-ok} sem verbete")


if __name__ == "__main__":
    main()
