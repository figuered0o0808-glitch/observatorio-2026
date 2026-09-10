# Teste de fontes gratuitas para o observatório 2026

Data do teste: 1 de setembro de 2026.
Pasta: /home/claude/api-tests/

## Atualização de 10 de setembro de 2026: a Wikipédia não compila cronologia de campanha

A linha do tempo do mural (`dados/eventos.csv`) é curada de imprensa e parou em 1/9. Antes de
propor coleta automática, `coleta/_sonda_cronologia.py` perguntou à Wikipédia o que existe:

- "Eleição presidencial no Brasil em 2026": seções de sistema eleitoral, candidaturas (uma
  por candidato), pesquisas de opinião, debates e entrevistas, e calendário eleitoral, que é
  só uma predefinição de datas legais. Não há seção de cronologia nem linha do tempo.
- "Eleições gerais no Brasil em 2026": remete à página presidencial e às estaduais.
- "Campanha presidencial de 2026 no Brasil": não existe.

Ou seja, acontecimento de campanha não tem fonte compilada como as pesquisas têm. Continua
sendo trabalho de leitura de imprensa, uma fonte por evento.

A exceção útil é a seção "Debates e entrevistas" da página presidencial: ela traz prosa
datada com referência (foi de lá que saiu o cancelamento do debate de 14/9, noticiado pela
CNN em 8/9, que o mural ainda anunciava como agendado) e uma tabela de debates com data,
organização, mediadores e presença de cada candidato. Serve para conferir o calendário de
debates de tempos em tempos; não substitui a curadoria do resto.

## Atualização de 10 de setembro de 2026: Instagram reconferido, e piorou

Sonda repetida antes de começar a divulgação do mural, com `coleta/_sonda_instagram.py` no
runner do GitHub, em três perfis (@lula, @jandirafeghali, @erikahilton) e quatro caminhos:

| Caminho | Em 7/9 | Em 10/9 |
|---|---|---|
| `www.instagram.com/<perfil>/` (HTML público) | 200, sem o número no corpo | **429 Too Many Requests** |
| `www.instagram.com/api/v1/users/web_profile_info` | 429 | 429 |
| `i.instagram.com/api/v1/users/web_profile_info` | não testado | 429 |
| `?__a=1&__d=dis` | não testado | 201 com corpo vazio |

Nenhum dos quatro devolveu número, em nenhum dos três perfis. O bloqueio é por faixa de IP
de datacenter: o 429 vem antes de qualquer autenticação, então cookie de sessão no runner
não resolveria, além de ser coisa que não se guarda em segredo de repositório.

Do contêiner do Claude Code é pior ainda: o proxy de saída recusa o CONNECT para
instagram.com, para o TSE, para a Wikipédia e para o próprio github.io, então de lá só o
GitHub responde.

Conclusão prática, a mesma de 7/9 e agora com mais evidência: seguidores de Instagram só
saem de um navegador em IP residencial, que é como a coleta de 2/9 foi feita. O roteiro
está em `coleta/navegador_estados.md`, seção 5.

## Atualização de 7 de setembro de 2026: o que o runner alcança

Sonda rodada de dentro do runner do GitHub, com sessão que guarda cookies e cabeçalhos de
navegador. Resultado por fonte:

| Fonte | Resposta | Decisão |
|---|---|---|
| Wikimedia pageviews | 200 | automatizada desde 6/9 |
| Google Trends (`/trends/api/explore` e `widgetdata/multiline`) | 200 | **automatizada em 7/9**; o 429 medido em 6/9 era chamada sem cookie, e basta visitar `trends.google.com` antes para a sessão passar |
| TSE (divulgacandcontas, dados abertos e o próprio portal) | 403 Akamai, com e sem Referer | bloqueio por IP de fora do Brasil; continua manual |
| Instagram `web_profile_info` | 429 | continua manual |
| Instagram página pública | 200, mas sem o número de seguidores no HTML (nem em `og:description`, nem em `edge_followed_by`) | não serve; continua manual |
| YouTube Data API | 403 sem chave | precisaria de chave no Google Cloud |
| Gazeta do Povo (agregador) | 403 | sem uso |
| Poder360 | 200 | alternativa possível de pesquisas, hoje coberta pela Wikipédia |

## Atualização de 6 de setembro de 2026

A Wikipédia passou a ser coletada duas vezes por dia num runner do GitHub Actions (`.github/workflows/atualizar.yml`), que alcança `pt.wikipedia.org` e `wikimedia.org` sem proxy: pesquisas presidenciais compiladas (`wikipedia_pesquisas_nacional.py`), páginas estaduais de pesquisas (`wikipedia_pesquisas_estados.py`) e acessos aos verbetes (`wikipedia_pageviews.py`). Testado no mesmo runner em 6/9: TSE responde 403 (Akamai, IP de fora do Brasil), Google Trends devolve 429 e Instagram exige login. Essas três continuam pelo roteiro de navegador em `navegador_estados.md`. O restante deste arquivo é o registro do teste de 1/9 e vale como histórico.

## Aviso importante sobre o ambiente

Nesta sessão todo o tráfego HTTPS passa por um proxy de saída com lista de permissão da organização. O proxy recusou o CONNECT (HTTP 403, antes de qualquer pacote chegar ao destino) para os seguintes hosts: pt.wikipedia.org, en.wikipedia.org, wikimedia.org, api.wikimedia.org, divulgacandcontas.tse.jus.br, www.instagram.com, socialblade.com, www.youtube.com e trends.google.com. Só o PyPI passou. O computador conectado (Mac) usa a mesma lista e também recebeu 403. Isso significa que, para essas fontes, a falha registrada abaixo com "requests" é do ambiente, não da fonte. A ferramenta WebFetch tem outro caminho de rede e por isso conseguiu alcançar o TSE e o YouTube, mas trata a Wikimedia como "domínio somente cache" e não busca.

Seguindo a regra combinada, não tentei contornar nada. Onde a fonte não pôde ser testada de verdade, deixei o script pronto para rodar em uma máquina com internet aberta.

## 1. Wikipédia Pageviews e histórico de edições (prioridade máxima)

Funcionou: NÃO nesta sessão. Motivo: proxy da organização bloqueia pt.wikipedia.org e wikimedia.org (403 no CONNECT). WebFetch também recusa ("This domain is cache-only and cannot be fetched"). Nenhum dado foi coletado, portanto wikipedia-pageviews.csv e wikipedia-edicoes-cury.csv NÃO foram gerados. Preferi não entregar arquivos vazios ou inventados.

O que ficou pronto: /home/claude/api-tests/wikipedia_pageviews.py, script completo e com sintaxe validada que:
1. Resolve o título exato de cada verbete pela API de busca (com fallback fixo por candidato e resolução de redirecionamentos).
2. Baixa os acessos diários (all-access, agente user) de 15/8 até ontem para os 8 candidatos e grava wikipedia-pageviews.csv com as colunas data, candidato, artigo, pageviews, fonte, url_fonte.
3. Baixa as revisões do verbete do Augusto Cury desde 20/8 (prop=revisions, rvdir=newer, paginado) e grava wikipedia-edicoes-cury.csv (edições e usuários distintos por dia) mais um arquivo bruto com uma linha por revisão.
4. Usa o User-Agent "observatorio-2026/0.1 (contato: figuered0o0808@gmail.com)".

Como rodar em outra máquina: `python3 wikipedia_pageviews.py 20260815 20260831`.

Limitações conhecidas da fonte (da documentação, não observadas aqui): a API de pageviews só tem dados até o dia anterior (fecha por volta das 6h UTC); o limite é generoso (100 req/s); artigos renomeados precisam do título novo; o agente "user" já exclui bots e spiders.

Recomendação para a rotina diária: rodar o script uma vez por dia, de manhã, pedindo só o dia anterior (ou os 3 últimos dias para absorver correções) e fazer append em uma base histórica. É a fonte mais confiável e barata do conjunto: sem chave, sem limite prático e com dados oficiais. Vale acrescentar os candidatos menores do TSE (lista abaixo) para ter uma linha de base.

## 2. TSE DivulgaCandContas

Funcionou: SIM, via WebFetch (o proxy bloqueia o host para requests, mas a API em si é pública, JSON, sem chave e sem autenticação).

Endpoints confirmados e formato atual:
- Eleições: https://divulgacandcontas.tse.jus.br/divulga/rest/v1/eleicao/ordinarias. Retorna lista; a Eleição Geral Federal 2026 tem id 20322002026, data 2026-10-04.
- Lista de presidenciáveis: https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/listar/2026/BR/20322002026/1/candidatos. Retorna 13 candidatos com id, nomeUrna, nomeCompleto, numero, partido.sigla, nomeColigacao, descricaoSituacao, descricaoTotalizacao, candidatoApto. Na listagem, vices, bens, ocupação, foto e composição da coligação vêm nulos.
- Detalhe do candidato: https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/buscar/2026/BR/20322002026/candidato/{id}. Traz vice (nome, nome de urna, partido, situação), composição da coligação, ocupação, data de nascimento, escolaridade, totalDeBens, dataUltimaAtualizacao, número do processo e links de redes sociais.

Arquivo gerado: /home/claude/api-tests/tse-presidenciaveis.csv (13 linhas) com nome, nome de urna, número, partido, situação da candidatura, totalização, coligação e composição, ocupação, total de bens, última atualização no TSE, dados do vice, fonte e URL de origem. O script tse_presidenciaveis.py regenera o CSV.

Dados que chamaram atenção (situação em 1/9/2026):
- Os 13 registrados: Lula (PT, 13), Flávio Bolsonaro (PL, 22), Augusto Cury (Avante, 70, nome de urna "ESCRITOR AUGUSTO CURY"), Ronaldo Caiado (PSD, 55), Zema (Novo, 30), Renan Santos (Missão, 14), Pablo Marçal (PRTB, 28), Samara (UP, 80), Clariana Barão (DC, 27), Edmilson Costa (PCB, 21), Hertz Dias (PSTU, 16), Rui Costa Pimenta (PCO, 29) e Wilson Grassi (Democrata, 35).
- Só Caiado e Rui Costa Pimenta estão "Deferido"; os outros 11, incluindo Cury, estão "Aguardando julgamento".
- Vice do Cury: Júlio Delgado (Avante). Coligação "Brasil dos Nossos Sonhos" (Agir / Avante). Bens declarados: R$ 242,3 milhões, o maior patrimônio entre todos os presidenciáveis (Zema R$ 178,7 mi, Marçal R$ 150,0 mi, Caiado R$ 52,6 mi, Lula R$ 4,8 mi).
- O registro do Cury foi o mais recentemente atualizado (29/8 20:25).

Limitação observada: nenhuma de rate limit. O JSON é grande (muitos campos nulos). O host não é acessível por requests neste ambiente; em máquina aberta deve funcionar com requests normalmente (é uma API REST comum).

Recomendação: consultar a listagem uma vez por dia e o detalhe de cada um dos 13 (14 chamadas) para acompanhar mudanças de situação (deferido, indeferido, impugnado), substituições e atualização de bens. Guardar o JSON bruto com data para ter diff histórico. Não precisa de chave.

## 3. Instagram (contagem pública de seguidores)

Funcionou: NÃO. WebFetch recusou com "URL is disallowed by robots.txt rules" para https://www.instagram.com/augustocury/. Requests: bloqueado pelo proxy (403). Não foi possível verificar a meta tag og:description. Testei um perfil só, como combinado.

Recomendação: não depender de scraping do Instagram. Alternativas legítimas: a Graph API do Instagram (precisa de app aprovado e conta profissional), ou registro manual semanal a partir do app. O TSE lista as URLs oficiais das redes de cada candidato (campo sites no detalhe), útil para saber qual perfil acompanhar.

## 4. Google Trends (pytrends)

Funcionou: PARCIAL. `pip install pytrends --break-system-packages` instalou e importou sem erro. A consulta única (interesse ao longo do tempo, "Augusto Cury", geo BR, últimos 30 dias) falhou com ProxyError 403 no CONNECT para trends.google.com, ou seja, bloqueio do ambiente antes de chegar ao Google. Não foi possível observar se o Google devolve 429.

Limitação conhecida da fonte: pytrends é biblioteca não oficial e o Google costuma responder 429 a poucas consultas seguidas; os valores são relativos (0 a 100), não absolutos.

Recomendação: em máquina aberta, uma consulta por dia com os 5 principais nomes no mesmo payload (para os índices ficarem comparáveis), com espera de alguns minutos entre tentativas e cache local. Tratar como indicador de tendência, não de volume.

## 5. Social Blade

Funcionou: NÃO. WebFetch recebeu HTTP 403 em https://socialblade.com/instagram/user/augustocury (bloqueio anti-bot do próprio site). Requests: bloqueado pelo proxy. Uma tentativa só.

Recomendação: descartar como fonte automatizada. O Social Blade tem API paga; para uso gratuito só consulta manual.

## 6. YouTube (sem chave)

Funcionou: PARCIAL. WebFetch alcançou https://www.youtube.com/@augustocury e identificou o canal "Augusto Cury" (handle @AugustoCury), mas o conteúdo convertido para texto não expôs o número de inscritos. O número existe no HTML bruto (dentro do JSON ytInitialData) mas a ferramenta não o extraiu, e com requests o host está bloqueado aqui.

Recomendação: usar a YouTube Data API v3 com chave gratuita do Google Cloud (channels.list com part=statistics devolve subscriberCount, viewCount e videoCount; cota diária de 10.000 unidades, cada consulta custa 1). É gratuita, oficial e estável; melhor do que raspar o HTML.

## Resumo em uma linha por fonte

| Fonte | Resultado | Chave | Uso diário recomendado |
|---|---|---|---|
| Wikipédia pageviews e edições | bloqueado pelo ambiente; script pronto | não | sim, 1 vez por dia, base do observatório |
| TSE DivulgaCandContas | funcionou, 13 presidenciáveis salvos | não | sim, listagem + detalhe diários |
| Instagram | robots.txt / bloqueio | Graph API precisa app | não automatizar |
| Google Trends (pytrends) | instala; consulta bloqueada pelo ambiente | não | 1 consulta/dia, com cautela |
| Social Blade | 403 | API paga | não |
| YouTube | página abre, inscritos não extraídos | Data API v3 gratuita | sim, via API oficial |

Arquivos na pasta: RESULTADO.md, tse-presidenciaveis.csv, tse_presidenciaveis.py, wikipedia_pageviews.py (pronto para rodar fora deste ambiente), trends_test.py.
