# Dados das disputas estaduais (governo e Senado, 27 estados)

Pasta montada em 2 de setembro de 2026 para a edição 11 do Mural dos Candidatos. O gerador `mural/_gerar_mural.py` lê daqui; nada no mural estadual vem de outro lugar.

## Arquivos e de onde vêm

| arquivo | linhas | conteúdo | origem |
|---|---|---|---|
| `candidatos-estados.csv` | 510 | candidaturas registradas a governador e senador | DivulgaCandContas (TSE), lista por estado |
| `candidatos-detalhe.csv` | 510 | bens declarados, escolaridade, ocupação, naturalidade, vice ou suplentes, composição oficial da coligação, redes informadas, foto, eleições anteriores | API de detalhe do DivulgaCandContas, lida no navegador do Mac (`coleta/navegador_estados.md`, seção 2). CPF e título de eleitor não foram guardados |
| `pesquisas-estados.csv` | 52 rodadas | fichas técnicas com número de registro no TSE, modo de coleta e contratante | Gazeta do Povo, agregador de pesquisas |
| `pesquisas-estados-wiki.csv` | 10.276 | todas as tabelas de 2026 das páginas "Pesquisas eleitorais para a eleição estadual de 2026 em ..." | Wikipédia em português, `action=parse`, com página e revid por linha; extraído por `_parse_wiki.py` de `_wiki-pesquisas-estados.json` |
| `pesquisas-estados-consolidado.csv` | 10.028 | série usada pelo mural: Wikipédia casada com as fichas da Gazeta (51 de 52 encontraram par), cenário principal por rodada, slug do candidato registrado quando o nome casa | `_consolidar_pesquisas.py` |
| `trends-estados.csv` | 124.950 | Google Trends dentro de cada estado, diário desde 1º de janeiro, para os 510 nomes, reescalado por disputa | coleta própria no navegador (`_trends-estados.json`), integrada por `_integrar_busca.py` |
| `wikipedia-verbetes-estados.csv` | 510 | verbete localizado para cada candidatura, pontuação e status (240 aceitos) | busca na Wikipédia + filtro de plausibilidade no `_integrar_busca.py` |
| `wikipedia-estados.csv` | 55.875 | acessos diários aos 240 verbetes aceitos desde 1º de janeiro | API REST da Wikimedia (all-access, agente user) |
| `instagram-estados.csv` | 1 linha por perfil informado ao TSE | seguidores lidos no perfil público em 2 de setembro; `aproximado=1` quando o número veio da meta da página (perfis comerciais), e o mural marca esses com "≈" | coleta própria no Chrome logado (`coleta/navegador_estados.md`, seção 5) |
| `bens-estados.csv` | 0 | reservado para a lista de bens item a item; o dump compacto desta edição não trouxe os itens | |

Os arquivos `_*.json` e `_*.txt` são os dumps brutos que saíram do navegador; ficam para auditoria e para reprocessar sem coletar de novo.

## Regras que valem para todas as linhas

Nenhum número entra sem data e fonte: cada linha carrega sua data e sua fonte por extenso. Célula vazia é indisponível, nunca zero. A coluna `fonte` do consolidado de pesquisas diz de onde vêm os números (W = Wikipédia) e de onde vem a ficha (G = Gazeta do Povo, registro no TSE); as duas nunca se misturam numa mesma célula. Nomes testados que não registraram candidatura continuam nas rodadas antigas, sem slug, marcados como não registrados.

## Onde cada cópia mora

O projeto no claude.ai tem limite de tamanho e guarda só os scripts, o GeoJSON simplificado do mapa, `candidatos-detalhe.csv` e `wikipedia-verbetes-estados.csv`. Os arquivos grandes (`pesquisas-estados-consolidado.csv`, `pesquisas-estados-wiki.csv`, `trends-estados.csv`, `wikipedia-estados.csv`) e os dumps brutos ficam na pasta do Mac (`documentos observatório 2026/dados/estados`) e na conversa em que foram gerados. Para refazer tudo do zero: coletar pelo roteiro de `coleta/navegador_estados.md`, rodar `_parse_wiki.py`, `_consolidar_pesquisas.py`, `_integrar_busca.py` e por fim `mural/_gerar_mural.py`.
