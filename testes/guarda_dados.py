#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guarda dos dados antes do commit automático.

O workflow de coleta roda este script depois dos coletores e antes de commitar. Ele compara cada
CSV de dados/ e dados/estados/, mais o dump dados/estados/_wiki-pesquisas-estados.json, com a
versão que está em HEAD (ou em outra referência, com --ref) e recusa o commit, saindo com código
1 e um relatório por arquivo, se qualquer regra falhar. As regras vêm do CLAUDE.md, do fontes.md
§7 e do mapa de testes da automação.

Forma: todo CSV alterado começa com o BOM (EF BB BF) e só tem quebra de linha CRLF, sem LF nem
CR soltos, terminando em CRLF. Os arquivos que já estão sem BOM em HEAD ficam dispensados do BOM;
hoje são os três que a automação não altera (redes-fontes, seguidores-historico-fontes,
tse-presidenciaveis).

Arquivos de acréscimo (pesquisas-registradas, wikipedia-pageviews, wikipedia-estados,
serie-diaria, eventos, instagram-estados): nenhuma chave de HEAD desaparece, nenhuma linha
existente muda de conteúdo, a contagem só cresce e não há chave duplicada.

Arquivos regravados (pesquisas-estados-wiki.csv, pesquisas-estados-consolidado.csv e o dump
JSON das páginas da Wikipédia): a contagem de linhas não cai mais de 2% e nenhuma UF presente em
HEAD some. Nesses arquivos, linha nova é a que traz uma rodada (UF, cargo, turno, instituto,
campo, cenário e candidato) que HEAD não tinha; a posição da tabela na página e a ordem da coluna
não entram nessa conta, porque a Wikipédia insere tabelas e colunas no meio das existentes e isso
desloca a numeração de centenas de linhas antigas sem mudar dado nenhum.

Em qualquer arquivo com chave, célula vazia em HEAD não vira 0 nem 0.0 na versão nova: vazio é
indisponível e zero é valor observado. O zero que já vem da fonte (a Wikimedia devolve 0 em dia
sem acesso) entra como veio e não é barrado.

Toda linha nova tem data válida em AAAA-MM-DD (na coluna data, data_ref, data_divulgacao ou
campo_fim, a que o arquivo tiver), não posterior a hoje em Brasília com um dia de tolerância, e
fonte preenchida (coluna fonte, url_fonte, url ou pagina, a que o arquivo tiver).

Os arquivos que a automação não deve tocar (candidatos, partidos, fichas do TSE, Trends, fichas
da Gazeta, verbetes) não podem ter diferença nenhuma, salvo os passados em --permitir, que ficam
sujeitos só às regras de forma: com --permitir nenhuma regra de conteúdo é aplicada ao arquivo,
nem a do vazio que vira zero, porque esses arquivos não têm chave definida aqui e a alteração é
por decisão humana. CSV novo que o guarda não conhece e CSV removido também são recusados. Outros arquivos alterados em dados/ (dumps, scripts) só geram aviso.

Uso:
    python3 testes/guarda_dados.py                          árvore de trabalho contra HEAD
    python3 testes/guarda_dados.py --ref origin/main
    python3 testes/guarda_dados.py --permitir dados/candidatos.csv
    python3 testes/guarda_dados.py --raiz /outra/copia/do/projeto

Sai com 0 quando tudo passa, 1 quando alguma regra falha e 2 quando não consegue verificar
(pasta sem git, referência inexistente). Só biblioteca padrão, Python 3.9 ou mais novo.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys

BOM = b"\xef\xbb\xbf"
PASTAS = ("dados", "dados/estados", "dados/rjsp")
# CSV que começa com "_" é arquivo de trabalho de coletor (proposta para conferência, dump
# intermediário) e não entra no mural: fica fora da classificação, como os .json e .txt da pasta
def de_trabalho(nome):
    return os.path.basename(nome).startswith("_")
QUEDA_MAXIMA = 0.02
TOLERANCIA_DIAS = 1
EXEMPLOS = 5

# arquivos de acréscimo e a chave que identifica cada linha
CSV_ACRESCIMO = {
    "dados/pesquisas-registradas.csv": ("instituto", "data_divulgacao", "cenario", "candidato"),
    "dados/wikipedia-pageviews.csv": ("data", "candidato"),
    "dados/estados/wikipedia-estados.csv": ("data", "uf", "slug"),
    "dados/serie-diaria.csv": ("data", "candidato", "plataforma"),
    "dados/eventos.csv": ("data", "candidato", "evento"),
    "dados/estados/instagram-estados.csv": ("data", "uf", "slug"),
}

# arquivos regravados inteiros a cada execução. Cada um tem duas chaves: a de casamento, que
# identifica a linha na tabela (com número de ocorrência, porque a Wikipédia repete nomes dentro
# de uma mesma tabela) e serve para a regra do vazio que vira zero; e a de rodada, sem os campos
# posicionais (secao, tabela, ordem_col), que decide o que é linha nova para a regra da data e da
# fonte. No consolidado a chave já não tem campo posicional e as duas coincidem.
CSV_REGRAVADO = {
    "dados/estados/pesquisas-estados-wiki.csv": {
        "casamento": ("pagina", "secao", "tabela", "instituto_bruto", "campo_inicio", "campo_fim", "cenario", "candidato", "ordem_col"),
        "rodada": ("uf", "cargo", "turno", "instituto_bruto", "campo_inicio", "campo_fim", "cenario", "candidato"),
    },
    "dados/estados/pesquisas-estados-consolidado.csv": {
        "casamento": ("uf", "cargo", "turno", "instituto", "data_ref", "campo_inicio", "cenario", "candidato"),
        "rodada": ("uf", "cargo", "turno", "instituto", "data_ref", "campo_inicio", "cenario", "candidato"),
    },
    # O índice do Trends é relativo à janela pedida, e a janela cresce um dia a cada coleta: a
    # série inteira é refeita, não acrescentada. "grupos" guarda o que não pode sumir de uma
    # coleta para a outra (nenhum termo de nenhum lote).
    "dados/trends-2026.csv": {
        "casamento": ("data", "lote", "termo"),
        "rodada": ("data", "lote", "termo"),
        "grupos": ("lote", "termo"),
    },
    "dados/estados/trends-estados.csv": {
        "casamento": ("data", "uf", "cargo", "termo"),
        "rodada": ("data", "uf", "cargo", "termo"),
        "grupos": ("uf", "cargo", "termo"),
    },
}
JSON_REGRAVADO = "dados/estados/_wiki-pesquisas-estados.json"

# arquivos que só mudam por decisão humana
INTOCAVEIS = (
    "dados/candidatos.csv",
    "dados/estados/candidatos-estados.csv",
    "dados/estados/candidatos-detalhe.csv",
    "dados/estados/bens-estados.csv",
    "dados/partidos.csv",
    "dados/avante-chapas.csv",
    "dados/estados/pesquisas-estados.csv",
    "dados/redes-fontes.csv",
    "dados/seguidores-historico-fontes.csv",
    "dados/tse-presidenciaveis.csv",
    "dados/estados/wikipedia-verbetes-estados.csv",
    # RJ e SP, deputado federal e estadual: coleta manual pelo navegador, curadoria de imprensa;
    # nenhuma rotina automática reescreve esses dois
    "dados/rjsp/candidatos-rjsp.csv",
    "dados/rjsp/candidatos-deputados.csv",
)

COLUNAS_DATA = ("data", "data_ref", "data_divulgacao", "campo_fim")
COLUNAS_FONTE = ("fonte", "url_fonte", "url", "pagina")
RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_ZERO = re.compile(r"^0+(\.0+)?$")

# nome do estado no fim do título da página da Wikipédia; a mesma tabela de _parse_wiki.py
UF_DE_TITULO = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE",
    "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
    "Mato Grosso do Sul": "MS", "Mato Grosso": "MT", "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB",
    "Paraná": "PR", "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC", "São Paulo": "SP",
    "Sergipe": "SE", "Tocantins": "TO",
}


def uf_do_titulo(titulo):
    for nome in sorted(UF_DE_TITULO, key=len, reverse=True):
        if titulo.endswith(nome):
            return UF_DE_TITULO[nome]
    return None


def hoje_brasilia():
    """Data de hoje em America/Sao_Paulo; sem tzdata, cai no deslocamento fixo de -3h."""
    try:
        from zoneinfo import ZoneInfo
        fuso = ZoneInfo("America/Sao_Paulo")
    except Exception:
        fuso = dt.timezone(dt.timedelta(hours=-3))
    return dt.datetime.now(fuso).date()


def raiz_padrao():
    return os.environ.get("OBSERVATORIO_RAIZ") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def exemplos(itens):
    """Formata até EXEMPLOS itens de uma lista para a mensagem, com a contagem do resto."""
    itens = list(itens)
    texto = "; ".join(str(i) for i in itens[:EXEMPLOS])
    if len(itens) > EXEMPLOS:
        texto += "; e mais %d" % (len(itens) - EXEMPLOS)
    return texto


class Relatorio:
    """Acumula as verificações por arquivo, na ordem em que foram feitas."""

    def __init__(self):
        self.itens = []

    def ok(self, arquivo, texto):
        self.itens.append(("OK", arquivo, texto))

    def falha(self, arquivo, texto):
        self.itens.append(("FALHA", arquivo, texto))

    def aviso(self, arquivo, texto):
        self.itens.append(("AVISO", arquivo, texto))

    @property
    def falhas(self):
        return [i for i in self.itens if i[0] == "FALHA"]

    def imprimir(self, saida=sys.stdout):
        for tipo, arquivo, texto in self.itens:
            print("%-5s %s: %s" % (tipo, arquivo, texto), file=saida)
        oks = sum(1 for i in self.itens if i[0] == "OK")
        avisos = sum(1 for i in self.itens if i[0] == "AVISO")
        falhas = self.falhas
        print("", file=saida)
        print("%d verificações OK, %d falhas, %d avisos" % (oks, len(falhas), avisos), file=saida)
        if falhas:
            print("FALHAS:", file=saida)
            for _, arquivo, texto in falhas:
                print("  %s: %s" % (arquivo, texto), file=saida)


# git

def git(raiz, *args):
    p = subprocess.run(["git", "-C", raiz] + list(args), capture_output=True)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace").strip()


def conferir_repositorio(raiz, ref):
    """Erro em texto se a pasta não é um repositório git ou a referência não resolve; None se está tudo bem."""
    if not os.path.isdir(raiz):
        return "a raiz %s não existe" % raiz
    rc, out, err = git(raiz, "rev-parse", "--is-inside-work-tree")
    if rc != 0 or out.strip() != b"true":
        return "%s não está dentro de um repositório git (%s)" % (raiz, err or "sem detalhe")
    rc, out, err = git(raiz, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if rc != 0:
        return "a referência %s não existe no repositório (%s)" % (ref, err or "sem commit com esse nome")
    return None


def conteudo_ref(raiz, ref, caminho):
    """Bytes do arquivo na referência, ou None se ele não existe lá."""
    rc, out, err = git(raiz, "show", "%s:./%s" % (ref, caminho))
    if rc != 0:
        return None
    return out


def arquivos_na_ref(raiz, ref):
    rc, out, err = git(raiz, "ls-tree", "-r", "--name-only", "-z", ref, "--", "dados")
    if rc != 0:
        return set()
    return set(c for c in out.decode("utf-8", "replace").split("\0") if c)


def arquivos_alterados(raiz, ref):
    """{caminho relativo à raiz: estado} para tudo que difere da referência em dados/.

    Estado é a letra do git diff (M, D, A, T) ou '?' para arquivo não rastreado."""
    estado = {}
    rc, out, err = git(raiz, "diff", "--no-renames", "--name-status", "--relative", "-z", ref, "--", "dados")
    if rc != 0:
        raise RuntimeError("git diff falhou: %s" % err)
    partes = out.decode("utf-8", "replace").split("\0")
    for i in range(0, len(partes) - 1, 2):
        if partes[i]:
            estado[partes[i + 1]] = partes[i][0]
    rc, out, err = git(raiz, "ls-files", "--others", "--exclude-standard", "-z", "--", "dados")
    if rc != 0:
        raise RuntimeError("git ls-files falhou: %s" % err)
    for caminho in out.decode("utf-8", "replace").split("\0"):
        if caminho:
            estado[caminho] = "?"
    return estado


def escopo(raiz, ref):
    """CSVs diretamente em dados/ e dados/estados/ (no disco ou na referência) mais o dump JSON."""
    arquivos = set()
    for pasta in PASTAS:
        caminho = os.path.join(raiz, pasta)
        if os.path.isdir(caminho):
            for nome in os.listdir(caminho):
                if nome.lower().endswith(".csv") and os.path.isfile(os.path.join(caminho, nome)):
                    arquivos.add(pasta + "/" + nome)
    for caminho in arquivos_na_ref(raiz, ref):
        if caminho.lower().endswith(".csv") and os.path.dirname(caminho) in PASTAS:
            arquivos.add(caminho)
    if os.path.isfile(os.path.join(raiz, JSON_REGRAVADO)) or JSON_REGRAVADO in arquivos_na_ref(raiz, ref):
        arquivos.add(JSON_REGRAVADO)
    return sorted(arquivos)


# leitura e forma

def ler_csv(dados):
    """(cabeçalho, linhas) a partir dos bytes; o BOM, se houver, é descartado."""
    texto = dados.decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(texto, newline="")))
    if not linhas:
        return [], []
    return linhas[0], linhas[1:]


def verificar_forma(caminho, dados, exige_bom, rel):
    """BOM, só CRLF (sem LF nem CR soltos, terminando em CRLF) e UTF-8. Devolve False se o arquivo nem pode ser lido como texto."""
    if dados.startswith(BOM):
        rel.ok(caminho, "começa com o BOM (EF BB BF)")
    elif exige_bom:
        rel.falha(caminho, "não começa com o BOM (EF BB BF); gravar com encoding='utf-8-sig'")
    else:
        rel.aviso(caminho, "sem BOM, como já estava em HEAD")
    crlf = dados.count(b"\r\n")
    lf_solto = dados.count(b"\n") - crlf
    cr_solto = dados.count(b"\r") - crlf
    if lf_solto:
        rel.falha(caminho, "%d quebra(s) de linha LF sem CR; a convenção é CRLF (open(..., newline='') e csv.writer)" % lf_solto)
    elif cr_solto:
        rel.falha(caminho, "%d quebra(s) de linha CR sem LF; a convenção é CRLF (open(..., newline='') e csv.writer)" % cr_solto)
    elif dados and not dados.endswith(b"\r\n"):
        rel.falha(caminho, "não termina em CRLF (última linha sem quebra de linha ou arquivo truncado)")
    else:
        rel.ok(caminho, "quebras de linha CRLF")
    try:
        dados.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        rel.falha(caminho, "não é UTF-8 válido (%s)" % e)
        return False
    return True


def conferir_largura(caminho, cabecalho, linhas, rel):
    ruins = [n for n, linha in enumerate(linhas, 2) if len(linha) != len(cabecalho)]
    if ruins:
        rel.falha(caminho, "%d linha(s) com número de campos diferente do cabeçalho (%d): linhas %s"
                  % (len(ruins), len(cabecalho), exemplos(ruins)))
        return False
    return True


def indices_da_chave(caminho, cabecalho, chave, rel):
    faltam = [c for c in chave if c not in cabecalho]
    if faltam:
        rel.falha(caminho, "coluna(s) da chave ausente(s) no cabeçalho: %s" % ", ".join(faltam))
        return None
    return [cabecalho.index(c) for c in chave]


def indexar(linhas, idx):
    """{chave: linha} e a lista de chaves repetidas."""
    mapa = {}
    repetidas = []
    for linha in linhas:
        k = tuple(linha[i] if i < len(linha) else "" for i in idx)
        if k in mapa:
            repetidas.append(k)
        mapa[k] = linha
    return mapa, repetidas


def indexar_com_ocorrencia(linhas, idx):
    """{chave + (n,): linha}, em que n distingue repetições legítimas da mesma chave, na ordem do arquivo."""
    mapa = {}
    vistos = {}
    for linha in linhas:
        k = tuple(linha[i] if i < len(linha) else "" for i in idx)
        n = vistos.get(k, 0)
        vistos[k] = n + 1
        mapa[k + (n,)] = linha
    return mapa


def descrever_chave(chave):
    return "(" + ", ".join(str(c) for c in chave) + ")"


# regras de conteúdo

def verificar_zeros(caminho, cabecalho, mapa_antigo, mapa_novo, rel):
    """Célula vazia em HEAD não pode virar 0 nem 0.0 na mesma chave."""
    viraram = []
    for k, antiga in mapa_antigo.items():
        nova = mapa_novo.get(k)
        if nova is None:
            continue
        for j, (a, b) in enumerate(zip(antiga, nova)):
            if a == "" and RE_ZERO.match(b):
                viraram.append("%s coluna %s" % (descrever_chave(k), cabecalho[j] if j < len(cabecalho) else j))
    if viraram:
        rel.falha(caminho, "%d célula(s) vazia(s) em HEAD viraram zero (vazio é indisponível, nunca 0): %s"
                  % (len(viraram), exemplos(viraram)))
    else:
        rel.ok(caminho, "nenhuma célula vazia de HEAD virou zero")


def verificar_linhas_novas(caminho, cabecalho, novas, hoje, rel):
    """Data válida e não futura, fonte preenchida, em cada linha nova."""
    if not novas:
        rel.ok(caminho, "nenhuma linha nova")
        return
    col_data = next((c for c in COLUNAS_DATA if c in cabecalho), None)
    col_fonte = next((c for c in COLUNAS_FONTE if c in cabecalho), None)
    limite = hoje + dt.timedelta(days=TOLERANCIA_DIAS)
    invalidas, futuras, sem_fonte = [], [], []
    for linha in novas:
        if col_data is not None:
            valor = linha[cabecalho.index(col_data)]
            data = None
            if RE_DATA.match(valor):
                try:
                    data = dt.date.fromisoformat(valor)
                except ValueError:
                    data = None
            if data is None:
                invalidas.append(repr(valor))
            elif data > limite:
                futuras.append(valor)
        if col_fonte is not None and not linha[cabecalho.index(col_fonte)].strip():
            sem_fonte.append(linha[cabecalho.index(col_data)] if col_data else "?")
    if col_data is None:
        rel.aviso(caminho, "sem coluna de data conhecida (%s); data das linhas novas não verificada" % ", ".join(COLUNAS_DATA))
    elif invalidas:
        rel.falha(caminho, "%d linha(s) nova(s) com %s fora de AAAA-MM-DD ou inválida: %s"
                  % (len(invalidas), col_data, exemplos(invalidas)))
    elif futuras:
        rel.falha(caminho, "%d linha(s) nova(s) com %s posterior a %s (hoje em Brasília é %s, tolerância de %d dia): %s"
                  % (len(futuras), col_data, limite, hoje, TOLERANCIA_DIAS, exemplos(sorted(set(futuras)))))
    else:
        rel.ok(caminho, "%d linha(s) nova(s) com %s válida até %s" % (len(novas), col_data, limite))
    if col_fonte is None:
        rel.aviso(caminho, "sem coluna de fonte conhecida (%s); fonte das linhas novas não verificada" % ", ".join(COLUNAS_FONTE))
    elif sem_fonte:
        rel.falha(caminho, "%d linha(s) nova(s) com %s vazia (nenhum número entra sem fonte): datas %s"
                  % (len(sem_fonte), col_fonte, exemplos(sem_fonte)))
    else:
        rel.ok(caminho, "%d linha(s) nova(s) com %s preenchida" % (len(novas), col_fonte))


def preparar_par(caminho, chave, antigo, novo, rel):
    """Lê as duas versões e confere cabeçalho, largura e chave. Devolve (cabeçalho, antigas, novas, idx) ou None."""
    try:
        cab_n, lin_n = ler_csv(novo)
    except (UnicodeDecodeError, csv.Error) as e:
        rel.falha(caminho, "não deu para ler como CSV: %s" % e)
        return None
    if antigo is None:
        cab_a, lin_a = cab_n, []
        rel.aviso(caminho, "não existe na referência; toda linha conta como nova")
    else:
        try:
            cab_a, lin_a = ler_csv(antigo)
        except (UnicodeDecodeError, csv.Error) as e:
            rel.falha(caminho, "a versão em HEAD não pôde ser lida como CSV: %s" % e)
            return None
    if cab_n != cab_a:
        rel.falha(caminho, "cabeçalho mudou: HEAD %s, agora %s" % (cab_a, cab_n))
        return None
    rel.ok(caminho, "cabeçalho igual ao de HEAD (%d colunas)" % len(cab_n))
    if not conferir_largura(caminho, cab_n, lin_n, rel):
        return None
    idx = indices_da_chave(caminho, cab_n, chave, rel)
    if idx is None:
        return None
    return cab_n, lin_a, lin_n, idx


def verificar_acrescimo(caminho, chave, antigo, novo, hoje, rel):
    par = preparar_par(caminho, chave, antigo, novo, rel)
    if par is None:
        return
    cabecalho, lin_a, lin_n, idx = par
    mapa_a, rep_a = indexar(lin_a, idx)
    mapa_n, rep_n = indexar(lin_n, idx)
    if rep_n:
        rel.falha(caminho, "%d chave(s) duplicada(s) %s: %s" % (len(rep_n), descrever_chave(chave), exemplos(map(descrever_chave, rep_n))))
    else:
        rel.ok(caminho, "sem chave duplicada em %s" % descrever_chave(chave))
    if rep_a:
        rel.aviso(caminho, "HEAD já tinha %d chave(s) duplicada(s)" % len(rep_a))
    sumiram = [k for k in mapa_a if k not in mapa_n]
    if sumiram:
        rel.falha(caminho, "%d chave(s) de HEAD desapareceram (histórico não pode ser apagado): %s"
                  % (len(sumiram), exemplos(map(descrever_chave, sumiram))))
    else:
        rel.ok(caminho, "todas as %d chaves de HEAD continuam presentes" % len(mapa_a))
    mudaram = [k for k, linha in mapa_a.items() if k in mapa_n and mapa_n[k] != linha]
    if mudaram:
        rel.falha(caminho, "%d linha(s) existente(s) mudaram de conteúdo (arquivo é só de acréscimo): %s"
                  % (len(mudaram), exemplos(map(descrever_chave, mudaram))))
    else:
        rel.ok(caminho, "nenhuma linha existente mudou")
    verificar_zeros(caminho, cabecalho, mapa_a, mapa_n, rel)
    if len(lin_n) < len(lin_a):
        rel.falha(caminho, "contagem caiu de %d para %d linhas" % (len(lin_a), len(lin_n)))
    else:
        rel.ok(caminho, "contagem %d -> %d (%+d)" % (len(lin_a), len(lin_n), len(lin_n) - len(lin_a)))
    novas = [linha for k, linha in mapa_n.items() if k not in mapa_a]
    verificar_linhas_novas(caminho, cabecalho, novas, hoje, rel)


def chaves(linhas, idx):
    """Conjunto das chaves das linhas, sem número de ocorrência."""
    return set(tuple(linha[i] if i < len(linha) else "" for i in idx) for linha in linhas)


def verificar_regravado(caminho, chave, antigo, novo, hoje, rel):
    par = preparar_par(caminho, chave["casamento"], antigo, novo, rel)
    if par is None:
        return
    cabecalho, lin_a, lin_n, idx = par
    idx_rodada = indices_da_chave(caminho, cabecalho, chave["rodada"], rel)
    if idx_rodada is None:
        return
    minimo = len(lin_a) * (1 - QUEDA_MAXIMA)
    if len(lin_n) < minimo:
        rel.falha(caminho, "contagem caiu %.1f%% (%d -> %d linhas); o limite é %d%%"
                  % (100.0 * (len(lin_a) - len(lin_n)) / len(lin_a), len(lin_a), len(lin_n), round(QUEDA_MAXIMA * 100)))
    else:
        variacao = (100.0 * (len(lin_n) - len(lin_a)) / len(lin_a)) if lin_a else 0.0
        rel.ok(caminho, "contagem %d -> %d (%+.1f%%)" % (len(lin_a), len(lin_n), variacao))
    if "uf" in cabecalho:
        col = cabecalho.index("uf")
        ufs_a = set(l[col] for l in lin_a)
        ufs_n = set(l[col] for l in lin_n)
        sumiram = sorted(ufs_a - ufs_n)
        if sumiram:
            rel.falha(caminho, "UF(s) presentes em HEAD sumiram: %s" % ", ".join(sumiram))
        else:
            rel.ok(caminho, "as %d UFs de HEAD continuam presentes" % len(ufs_a))
    if chave.get("grupos"):
        idx_g = indices_da_chave(caminho, cabecalho, chave["grupos"], rel)
        if idx_g is not None:
            g_a, g_n = chaves(lin_a, idx_g), chaves(lin_n, idx_g)
            sumiram = sorted(g_a - g_n)
            if sumiram:
                rel.falha(caminho, "%d grupo(s) de HEAD sumiram: %s"
                          % (len(sumiram), "; ".join(" ".join(x) for x in sumiram[:EXEMPLOS])))
            else:
                rel.ok(caminho, "os %d grupos de HEAD continuam presentes" % len(g_a))
    mapa_a = indexar_com_ocorrencia(lin_a, idx)
    mapa_n = indexar_com_ocorrencia(lin_n, idx)
    verificar_zeros(caminho, cabecalho, mapa_a, mapa_n, rel)
    # linha nova é a de rodada que HEAD não tinha; tabela e coluna deslocadas não contam
    rodadas_a = chaves(lin_a, idx_rodada)
    novas = [linha for linha in lin_n if tuple(linha[i] for i in idx_rodada) not in rodadas_a]
    verificar_linhas_novas(caminho, cabecalho, novas, hoje, rel)


def resumo_dump(paginas):
    """(UFs com texto útil, total de linhas de texto, títulos com ERRO, títulos sem UF reconhecida)."""
    ufs, linhas, erros, sem_uf = set(), 0, [], []
    for titulo, texto in paginas.items():
        if not isinstance(texto, str) or texto.startswith("ERRO"):
            erros.append(titulo)
            continue
        uf = uf_do_titulo(titulo)
        if uf is None:
            sem_uf.append(titulo)
        else:
            ufs.add(uf)
        linhas += texto.count("\n") + 1
    return ufs, linhas, erros, sem_uf


def verificar_dump_wiki(caminho, antigo, novo, rel):
    try:
        j_n = json.loads(novo.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as e:
        rel.falha(caminho, "JSON inválido: %s" % e)
        return
    if not isinstance(j_n, dict) or not isinstance(j_n.get("paginas"), dict):
        rel.falha(caminho, "sem a chave 'paginas' (título -> texto compacto)")
        return
    rel.ok(caminho, "JSON válido com %d páginas" % len(j_n["paginas"]))
    paginas_a = {}
    if antigo is not None:
        try:
            j_a = json.loads(antigo.decode("utf-8-sig"))
            paginas_a = j_a.get("paginas", {}) if isinstance(j_a, dict) else {}
        except (UnicodeDecodeError, ValueError):
            rel.aviso(caminho, "a versão em HEAD não é JSON válido; comparação feita contra vazio")
    else:
        rel.aviso(caminho, "não existe na referência")
    ufs_a, linhas_a, erros_a, _ = resumo_dump(paginas_a)
    ufs_n, linhas_n, erros_n, sem_uf = resumo_dump(j_n["paginas"])
    if linhas_n < linhas_a * (1 - QUEDA_MAXIMA):
        rel.falha(caminho, "texto compacto caiu %.1f%% (%d -> %d linhas); o limite é %d%%"
                  % (100.0 * (linhas_a - linhas_n) / linhas_a, linhas_a, linhas_n, round(QUEDA_MAXIMA * 100)))
    else:
        variacao = (100.0 * (linhas_n - linhas_a) / linhas_a) if linhas_a else 0.0
        rel.ok(caminho, "texto compacto %d -> %d linhas (%+.1f%%)" % (linhas_a, linhas_n, variacao))
    sumiram = sorted(ufs_a - ufs_n)
    if sumiram:
        rel.falha(caminho, "UF(s) presentes em HEAD sumiram ou vieram com ERRO: %s" % ", ".join(sumiram))
    else:
        rel.ok(caminho, "as %d UFs de HEAD continuam com texto" % len(ufs_a))
    if erros_n:
        rel.aviso(caminho, "%d página(s) com ERRO no dump novo: %s" % (len(erros_n), exemplos(erros_n)))
    if sem_uf:
        rel.aviso(caminho, "%d título(s) sem UF reconhecida: %s" % (len(sem_uf), exemplos(sem_uf)))


# um arquivo

def verificar_arquivo(caminho, raiz, ref, estado, permitidos, hoje, rel):
    if caminho not in estado:
        rel.ok(caminho, "sem alteração em relação a %s" % ref)
        return
    permitido = caminho in permitidos
    completo = os.path.join(raiz, caminho)
    if estado[caminho] == "D" or not os.path.isfile(completo):
        if permitido:
            rel.aviso(caminho, "removido; aceito por --permitir")
        else:
            rel.falha(caminho, "arquivo removido da árvore de trabalho")
        return
    with open(completo, "rb") as f:
        novo = f.read()
    antigo = conteudo_ref(raiz, ref, caminho)
    if caminho.lower().endswith(".csv"):
        exige_bom = antigo is None or antigo.startswith(BOM)
        if not verificar_forma(caminho, novo, exige_bom, rel):
            return
    if permitido:
        rel.aviso(caminho, "conteúdo alterado; aceito por --permitir, só a forma foi verificada")
        return
    if caminho in INTOCAVEIS:
        rel.falha(caminho, "%s pela automação; esse arquivo só muda por decisão humana (--permitir %s se for intencional)"
                  % ("criado" if antigo is None else "alterado", caminho))
        return
    if caminho in CSV_ACRESCIMO:
        verificar_acrescimo(caminho, CSV_ACRESCIMO[caminho], antigo, novo, hoje, rel)
    elif caminho in CSV_REGRAVADO:
        verificar_regravado(caminho, CSV_REGRAVADO[caminho], antigo, novo, hoje, rel)
    elif caminho == JSON_REGRAVADO:
        verificar_dump_wiki(caminho, antigo, novo, rel)
    else:
        rel.falha(caminho, "arquivo sem regra no guarda; classifique-o em testes/guarda_dados.py ou passe --permitir %s" % caminho)


def normalizar_caminho(caminho, raiz):
    """Caminho relativo à raiz com barras normais, aceitando absoluto, './' e barras invertidas."""
    c = caminho.replace("\\", "/")
    if os.path.isabs(c):
        c = os.path.relpath(c, raiz).replace("\\", "/")
    while c.startswith("./"):
        c = c[2:]
    return c


def executar(raiz, ref, permitidos, hoje, saida=sys.stdout):
    """Roda todas as verificações e devolve (código de saída, relatório)."""
    raiz = os.path.abspath(raiz)
    erro = conferir_repositorio(raiz, ref)
    if erro:
        print("guarda de dados: %s" % erro, file=saida)
        return 2, None
    permitidos = set(normalizar_caminho(p, raiz) for p in permitidos)
    rel = Relatorio()
    print("guarda de dados: árvore de trabalho de %s contra %s; hoje em Brasília: %s%s"
          % (raiz, ref, hoje, ("; permitidos: " + ", ".join(sorted(permitidos))) if permitidos else ""), file=saida)
    try:
        estado = arquivos_alterados(raiz, ref)
    except RuntimeError as e:
        print("guarda de dados: %s" % e, file=saida)
        return 2, None
    arquivos = escopo(raiz, ref)
    for caminho in arquivos:
        verificar_arquivo(caminho, raiz, ref, estado, permitidos, hoje, rel)
    for caminho in sorted(estado):
        if caminho not in arquivos:
            rel.aviso(caminho, "alterado, fora do escopo do guarda (%s)" % {"?": "não rastreado", "D": "removido"}.get(estado[caminho], "modificado"))
    rel.imprimir(saida)
    return (1 if rel.falhas else 0), rel


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compara os CSVs de dados/ com a versão em git e recusa o commit se alguma regra do dataset falhar.")
    ap.add_argument("--raiz", default=raiz_padrao(), help="pasta do projeto (padrão: a pasta acima de testes/, ou OBSERVATORIO_RAIZ)")
    ap.add_argument("--ref", default="HEAD", help="referência git para comparar (padrão: HEAD)")
    ap.add_argument("--permitir", action="append", default=[], metavar="ARQUIVO",
                    help="aceita qualquer alteração de conteúdo nesse arquivo (relativo à raiz); pode repetir")
    ap.add_argument("--hoje", default=None, metavar="AAAA-MM-DD", help="data de referência em vez de hoje em Brasília (para testes)")
    a = ap.parse_args(argv)
    if a.hoje:
        try:
            hoje = dt.date.fromisoformat(a.hoje)
        except ValueError:
            ap.error("--hoje precisa estar em AAAA-MM-DD")
    else:
        hoje = hoje_brasilia()
    codigo, _ = executar(a.raiz, a.ref, a.permitir, hoje)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
