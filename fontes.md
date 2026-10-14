# Fontes e pendências de dados

**Atualizado em 1/9/2026, 20h20 de Brasília (snapshot agendado da noite).** Consolida as seções 7 e 9 do briefing e registra o que ainda falta confirmar na linha de base.

---

## 1. Fontes gratuitas (usar primeiro)

| Fonte | O que dá | Como acessar | Situação |
|---|---|---|---|
| Wikipédia | Acessos diários aos verbetes, proxy de descoberta | API pública de pageviews | coletado 1/1 a 31/8 em 1/9 via navegador (`dados/wikipedia-pageviews.csv`); rotina diária a automatizar |
| Wikipédia, histórico e discussão | Disputas de edição no verbete do Cury, marcador datado de tentativa de reclassificação | página de histórico e de discussão | a implementar |
| Google Trends | Índice de busca comparado e pesquisas relacionadas | API interna da página do explore, via navegador | coletado 1/1 a 1/9 em 1/9, diário, candidatos e termos (`dados/trends-2026.csv`); rotina a automatizar |
| YouTube Data API | Views, likes e comentários dos cortes e canais oficiais | chave gratuita via Google Cloud, nó nativo no n8n | chave a criar |
| Social Blade | Histórico diário de seguidores por perfil | páginas públicas | linha de base de 27/8 carregada |
| Biblioteca de Anúncios da Meta | Gasto em anúncio político por página | API gratuita | a implementar, teste documental da tese orgânica |
| TSE / DivulgaCandContas | Candidaturas, número, situação, bens, fundo, prestação parcial de contas (setembro), gasto com impulsionamento | portal e API | primeira tarefa pendente |
| Poder360 e BBC News Brasil | Agregação de pesquisas | páginas públicas | agregador BBC de 21/8 carregado |
| Retratos da Leitura no Brasil (Instituto Pró-Livro) | Leitura por gênero e faixa etária, teste da hipótese da autoajuda | relatório público | a levantar |
| PublishNews | Ranking de livros mais vendidos, teste de transbordamento editorial | páginas públicas | a monitorar |
| Kwai | Sem API, registro manual semanal dos vídeos mais vistos | manual | a implementar |

### Séries de busca a manter no Trends

Augusto Cury é de esquerda ou direita; propostas Augusto Cury; como votar; eleições 2026. As três últimas são o teste de transbordamento.

## 2. Serviços pagos a avaliar

Verificar preços antes de contratar, em ordem de prioridade.

1. **Apify.** Coletores prontos de Instagram, TikTok, YouTube e X, pagos por uso, integráveis ao n8n via webhook. Melhor ponto de partida.
2. **Vox Radar ou Sólon.** Escuta social nacional. São as duas plataformas que a imprensa está usando nos números do caso, o que alinha o projeto à régua do mercado.
3. **Palver.** Grupos públicos de WhatsApp e Telegram. Para o eleitorado despolitizado, possivelmente a fonte mais valiosa e menos observada.
4. **SerpApi ou Glimpse.** Google Trends programático.
5. **HypeAuditor ou Modash.** Qualificação dos influenciadores que endossam cada candidato, audiência real, autenticidade, demografia, e checagem das acusações de inflação artificial.
6. **Data365, Bright Data, Social Blade API.** Robustez para a fase plataforma.
7. **Meta Content Library e TikTok Research API.** Gratuitas mediante credenciamento de pesquisa, avaliar via INDICA.OSC.

Ressalva: coleta de Instagram por terceiros opera em zona cinzenta dos termos da Meta. Para a plataforma aberta, priorizar fontes oficiais.

## 3. Fontes já citadas na linha de base

- AtlasIntel/Bloomberg, registro TSE BR-07972/2026, campo de 25 a 30/8, divulgação em 31/8.
- BTG/Nexus, 12ª rodada, registro TSE BR-08900/2026, campo de 28 a 30/8, divulgação em 31/8.
- Repercussão das duas pesquisas via InfoMoney, Money Times, Metrópoles, CNN Brasil e Diário do Grande ABC.
- Audiência do debate, imprensa, 24/8.
- Seguidores e menções: Vox Radar via CNN Brasil, 27/8; Social Blade via Estado de Minas, 27/8.
- Google Trends: Diário Tocantinense e Revista Oeste, 27/8.
- Posição da campanha: Gazeta do Povo, 28/8, e CNN Brasil, 28/8.

## 4. Coleta automatizada: o que foi testado em 1/9 e onde ela deve rodar

Teste feito em 1/9 a partir do ambiente do Claude. Resultado por fonte:

| Fonte | Resultado | Chave | Uso na rotina |
|---|---|---|---|
| TSE DivulgaCandContas | Funciona. API pública JSON, sem chave. ID da eleição 2026: `20322002026`. Listagem dos 13 presidenciáveis e detalhe por candidato (vice, coligação, bens, situação, redes). | não | Diária: listagem + 13 detalhes, guardar JSON bruto para diff de situação e bens. Já coletado: `dados/tse-presidenciaveis.csv`. |
| Wikipédia pageviews e edições | API pública, sem chave, mas o ambiente do Claude bloqueia o host. Script pronto em `coleta/wikipedia_pageviews.py`. | não | Diária, fonte principal de "descoberta". Precisa rodar fora do ambiente do Claude (ver abaixo). |
| YouTube | Página do canal acessível, mas sem extrair inscritos. | sim, gratuita | YouTube Data API v3, `channels.list` com `part=statistics`; 10.000 unidades/dia, 1 por consulta. Criar chave no Google Cloud. |
| Google Trends | pytrends instala; consulta bloqueada pelo ambiente. Google costuma responder 429 a consultas seguidas. | não | 1 consulta/dia com os 5 principais nomes no mesmo payload, fora do ambiente do Claude. Tendência relativa, não volume. |
| Instagram | Bloqueado por robots.txt e pelo ambiente. | Graph API exige app aprovado | Não automatizar por scraping. Alternativas: Apify (pago), registro manual semanal, ou Vox Radar/Bites via imprensa. |
| Social Blade | 403 do próprio site. | API paga | Descartar como fonte automatizada. Usar só via imprensa. |

**Onde rodar.** O ambiente do Claude e o shell do Mac conectado passam por uma lista de saída restrita que bloqueia Wikipédia, TSE (por requests), YouTube, Trends e Instagram. As páginas de imprensa e o TSE por WebFetch passam. A infraestrutura certa para os coletores é o **n8n da INDICA**, que já está conectado a esta sessão, roda com internet aberta e tem nó nativo de YouTube e de HTTP Request. Arquitetura proposta: um workflow agendado por dia que consulta TSE, Wikipédia, YouTube e Trends e grava numa Data Table do n8n; o Claude lê a tabela pelo MCP no snapshot diário e transcreve para os CSVs. Credenciais hoje no n8n: Evolution API e Gmail (indica.osc). Falta: chave da YouTube Data API.

## 5. Snapshot de 1/9/2026, 20h20 de Brasília

Rodada agendada da noite, cerca de quinze minutos depois da rodada anterior. O que foi coletado e o que ficou de fora:

- **Google Trends.** Três consultas refeitas na mesma janela (1/1 a 1/9, diário, geo BR). `trends-2026.csv` regravado inteiro: 3.172 linhas, 65 células diferentes da versão da tarde. As diferenças são de amostragem do próprio Google, quase todas de um ponto; a maior é o pico de Cury em 27/8, que caiu de 90 para 85. O índice é relativo ao máximo da janela e ao lote da consulta, então a série precisa ser regravada por inteiro a cada coleta, nunca acrescentada. O lote B precisou de uma segunda consulta por erro de transcrição, e a primeira tentativa voltou com bloqueio do Google; funcionou depois de 25 segundos de pausa.
- **Wikipédia.** Consultados os oito principais para 29 a 31/8. Nenhum dia novo: a API só publica até a véspera e 31/8 já havia entrado na rodada da manhã. Os oito valores conferiram com os do arquivo, o que serve de verificação da coleta anterior. Confirmado que o verbete de Renan responde por "Renan Santos".
- **Instagram.** Os oito perfis lidos de novo pelo navegador, com o `follower_count` exato do HTML. As linhas de 1/9 foram atualizadas no lugar em vez de duplicadas, para manter uma linha por candidato, plataforma e dia; o valor das 19h ficou registrado na observação junto com a variação intradiária. A API interna `web_profile_info` responde 401 sem sessão; o caminho que funciona é navegar até o perfil e ler o HTML renderizado.
- **TSE.** Listagem consultada por WebFetch. Os treze registros seguem iguais aos da rodada anterior: Caiado e Rui Costa Pimenta deferidos, os outros onze aguardando julgamento, todos concorrendo. Nada a alterar em `candidatos.csv`.
- **Imprensa.** Quatro eventos novos em `eventos.csv` e duas linhas em `serie-diaria.csv`. Nenhuma pesquisa nova: a Real Time Big Data de 1/9 já estava registrada com as 51 linhas e o registro BR-03490/2026.

Coisas que esta rodada não alcançou: nenhuma. As três coletas próprias dependeram do Mac online e ele estava.

## 6. Pendências de dados

**Resolvidas em 1/9:** margem de erro da AtlasIntel (1 p.p., Gazeta do Povo 31/8); série precisa do Instagram do Cury de 23 a 28/8 (Social Blade via Canal MyNews) e 16/8 e 31/8 (Vox Radar via CNN), substituindo os valores aproximados; número, situação, vice e coligação de Cury no TSE; URLs de todas as linhas novas.

**Ficaram fora dos CSVs por falta de data:**

- Rodada AtlasIntel de julho, base das variações de 31/8. Os valores são dedutíveis (Cury 1,6%; Flávio 35,8%; Lula 44,9%; Lula 36,8% entre 16 e 24 anos), mas faltam datas de campo, registro TSE e link. Confirmar e inserir: é o ponto de partida da série de rejeição.
- BTG/Nexus, 11ª rodada, com Cury em 2%. Faltam datas de campo e registro.
- PoderData de 27/8 com Cury em 4%, citada pela Oeste; original não localizada.
- Publicação original da Quaest sobre o Índice de Popularidade Digital (Cury de 37,8 para 54,5); registrado via Brasil em Folhas com essa ressalva.

**Entraram com lacuna ou conflito:**

- `url_fonte` vazia nas 14 linhas herdadas da linha de base (ranking de 27/8, Trends, menções de 23 e 26/8). Recuperar os links das matérias de 27/8 (Estado de Minas, CNN, Diário Tocantinense, Revista Oeste).
- Janela do Vox Radar: o briefing registrava "22 a 27/8"; a CNN de 27/8 descreve a janela como 23/7 até o pós-debate. As observações do ranking de 27/8 foram corrigidas para a versão da CNN. Confirmar no relatório original do Vox Radar.
- Comentários declarando voto: 526 mil (citado em 27/8) contra 168 mil (Vox Radar via CNN, 31/8, janela 16 a 31/8). Critérios ou janelas diferentes; reconciliar antes de usar no artigo.
- Seguidores de Cury em 27/8: três valores no mesmo dia (Social Blade via MyNews 10.427.863; Estado de Minas 10,1 milhões; Vox Radar 9,9 milhões), snapshots em horas diferentes num dia de +1,2 milhão. A série usa o Social Blade; os outros ficam na observação.
- `variacao_dia` só onde a fonte reportou. A partir do primeiro snapshot próprio, calcular sempre sobre a mesma fonte.
- Rejeição de Ronaldo Caiado (28,5%) consta sem intenção de voto correspondente na AtlasIntel.
- Metodologia do Datafolha de 21/8 não registrada.
- Situação da candidatura de Teté (RS, 7070) a confirmar no TSE; chapas do Avante nos demais estados ainda não mapeadas.
- Real Time Big Data: Money Times atribui a pesquisa ao GAEP; Poder360 diz recursos próprios (R$ 30 mil). Registrada a divergência.

**Evidências a salvar com urgência (pastas já criadas, vazias):**

- Vídeo de Yuri Meirelles, mais de 12 milhões de visualizações e mais de 1 milhão de curtidas.
- Vídeo de Raphael Soares, mais de 1 milhão de curtidas, 27 e 28/8.
- Prints do pico do Google Trends e da busca "Augusto Cury é de esquerda ou direita".
- Trechos da sabatina da Globo de 29/8 e da análise dos comentaristas na sequência.

## 7. Convenções do dataset

- Codificação UTF-8 com BOM, separador vírgula, decimal com ponto. Abre direto no Google Sheets e no Numbers. No Excel em português, importar em vez de abrir com duplo clique.
- Datas sempre em `AAAA-MM-DD`.
- Célula vazia significa dado não disponível, nunca zero. Exceção que confirma a regra: quando a API da Wikimedia devolve 0 acessos para um dia, esse 0 é valor observado e fica gravado; dia que a API omite não vira linha.
- `candidatos.csv` é o perfil dos 13 registrados (ficha TSE, vice, bens, handles por rede, verbete da Wikipédia); `redes-fontes.csv` guarda a origem e a confiança de cada handle e cada número de seguidores. `tse-presidenciaveis.csv` é a ficha bruta da API do TSE.
- `eventos.csv` ganhou a coluna `candidato` em 1/9 (segunda posição); eventos que afetam a disputa inteira levam "todos"; mais de um candidato, separados por "; ". Categoria nova: `justiça eleitoral`.
- `mural/mural.html` é gerado por `mural/_gerar_mural.py` a partir dos CSVs; nunca editar o HTML à mão. Publicado como página no Claude (artifact "Mural dos Presidenciáveis"); republicar após cada snapshot.
- Edição 2 do mural (1/9, noite): histórico completo de pesquisas de 2026 (83 rodadas, 15 institutos, cada ponto com ficha e registro TSE), evolução de seguidores no Instagram com todos os pontos publicados pela imprensa no ano, índices Datrix e Quaest, seção de partidos (bancadas, FEFC, filiados, TV, cláusula) e 174 eventos na linha do tempo. Arquivos novos em `dados/`: `partidos.csv`, `seguidores-historico-fontes.csv` (fonte por ponto). `pesquisas-registradas.csv` agora tem 13 colunas (ganhou `observacao`) e cobre o ano inteiro.
- Pendências novas: rodadas Datafolha e PoderData de janeiro a abril não localizadas; AtlasIntel de 19/5 parcial (divulgação suspensa por liminar); fundo partidário 2026 por partido (planilha XLSM do TSE inacessível); série diária própria de seguidores iniciada em 1/9 pelos perfis públicos do Instagram via navegador do Mac (número exato de cada um; Renan acessível deste Mac apesar da retirada do ar reportada); Trends e Wikipédia coletados em 1/9 pelo mesmo caminho. A rotina diária dessas três coletas precisa do Mac online no horário do snapshot, ou dos coletores no n8n. Verbete de Renan na Wikipédia fica sob o título "Renan Santos"; a grafia "Renan dos Santos", registrada por engano na rodada anterior, é de um futebolista e não deve ser usada. O Trends devolveu 16/8 zerado (lacuna conhecida, confirmada na recoleta de 1/9 à noite).
- Uma linha por candidato, plataforma e dia em `serie-diaria.csv`. Métricas que não são de perfil usam plataformas próprias: `google_trends`, `google_buscas_termo`, `mencoes_web`, `instagram_comentarios_voto`, `instagram_comentarios_total`, `ap_exata_share_mencoes`, `quaest_ipd`, `tiktok_topico`, `instagram_ganho_periodo`.
- Categorias em uso em `eventos.csv`: debate, entrevista, ataque, endosso, rito de reclassificação, proposta, mais três acrescentadas: `declaração` (falas do candidato ou da campanha), `pesquisa` (divulgações) e `contexto` (fatos de terceiros que afetam a disputa, como decisões do TSE ou ações das plataformas). A categoria `cenário` fica reservada para os sinais da nota interna do briefing: estrutura física de campanha, aproximação com estruturas profissionais, quadros econômicos ou financiadores.
- Nenhum número entra sem data e fonte.

## 8. Segundo turno de 2026 (registro de 13/10/2026)

- `dados/resultados/candidatos.csv` e `totais.csv` são o resultado oficial do TSE, regravados a cada coleta. O mural lê os dois por `mural/_resultados.py`: só entra apuração com seção totalizada (o 2º turno existe zerado antes da votação), a situação vem da coluna `situacao` e nunca da coluna `eleito` (o TSE marca `s` também para quem foi ao 2º turno), o exterior (`zz`) fica à parte das 27 UFs e linha que não converte é pulada com aviso. Em apuração final, a soma dos percentuais tem de fechar entre 99,5 e 100,5.
- As UFs com 2º turno de governador saem de `totais.csv` (linhas de turno 2), nunca da situação do 1º turno. Tocantins saiu marcado "2º turno" no 1º turno, mas a configuração do 2º turno publicada pelo TSE, conferida em 13/10/2026, não inclui o estado; o mural o trata como pendente no TSE, com os dois nomes e os percentuais, e nunca escreve "eleito" nem "25/10" para ele.
- `dados/medias-publicadas.csv` guarda a média de votos válidos que o mural publicou na véspera do 1º turno (edição de 3/10/2026, 23h12, commit `fa89b7d`): Lula 45,2484, Flávio Bolsonaro 43,9142, incerteza 0,5730, janela de 2 dias. É arquivo manual, protegido pelo guarda. Refeita hoje com o mesmo corte, a conta daria Lula 45,23 e Flávio 44,08, porque três rodadas datadas de 3/10 só entraram na base em 4/10; a comparação com a urna usa o número publicado, com a conta refeita ao lado.
- A editoria Pesquisas abre pelo 2º turno em votos válidos (o mesmo `media2T` da capa, com filtros de instituto e de modo que escolhem os pontos e a média, mas não a base do efeito casa) e guarda o 1º turno como histórico, com a linha refeita pela régua de cada dia. O painel "O 1º turno: pesquisas x urna" (`erro1T` no template) mede o erro como pesquisa menos urna e a margem como o primeiro de `DATA.finalistas` menos o segundo. Para cada instituto vale a última rodada com campo terminado na semana antes da votação (27/9 a 3/10) que fecha em votos válidos; quando ela não fecha (Gerp e Veritá de 3/10), vale a anterior do mesmo instituto, com campo terminado desde 20/9, e a tabela diz isso. As três rodadas que entraram na base depois da edição da véspera (AtlasIntel/Bloomberg, Futura Inteligência e Instituto Veritá, todas datadas de 3/10, chegadas no commit `76d2812`, de 4/10 às 12h33) ficam listadas no template, porque a base não guarda quando cada linha entrou. O erro é medida e não corrige a média do 2º turno. "Desvio" (cada instituto contra os outros na mesma semana) e "erro" (pesquisa contra urna) aparecem separados em Pesquisas e no Método.
- Rodadas nacionais de 2º turno: cada uma vira votos válidos (a parte de cada nome na soma dos dois) e leva a base, `v` quando a rodada saiu só em votos válidos (Lula + Flávio a partir de 99,5) e `t` quando saiu em intenção total. Rodada "depois do 1º turno" é a de campo terminado depois de 4/10, o mesmo corte do coletor.
- A média do 2º turno (`media2T` no template) é feita sempre em votos válidos, com as rodadas de campo terminado depois de 4/10 e a régua do 2º turno, `REGUA2T = {inicio: 2026-10-05, sigma0: 1, passo: 10, minimo: 1}`: janela de 1 dia, a mesma em que a régua do 1º turno chegou na votação, alargando sozinha até juntar cinco institutos, como no 1º turno. É decisão padrão de 13/10/2026, a confirmar com o Francisco; se ele escolher outra régua, muda só a constante, e a janela escrita no mural acompanha. O efeito casa de cada instituto é medido em todas as rodadas do confronto em válidos, de antes e de depois de 4/10, e descontado só das rodadas da campanha. A média da campanha só aparece com 3 rodadas de 2 institutos feitas depois de 4/10 (`MIN_POS1T`); sem isso o mural mostra as simulações feitas até 3/10 e diz que são elas. Os dois percentuais exibidos são renormalizados para somar 100, porque o efeito casa corrige cada nome separadamente e a soma das médias sai 100,04. A conta em intenção total ficou só para a tabela do efeito casa, sem as rodadas publicadas só em válidos.
- "Vox" e "Vox Brasil" são o mesmo instituto; o nome se acerta na leitura (`INST_ALIAS` no gerador), porque a base só aceita acréscimo.
- Pesquisa de 1º turno vai até 3/10 e de 2º turno até 24/10. O guarda recusa linha nova de pesquisa de 1º turno com data depois de 4/10 e de 2º turno depois de 25/10, e o parser estadual recua um ano a data sem ano que passe desses limites.
- `eventos.csv` ganhou a categoria `resultado`, com o resultado de 4/10 para presidente, governador e Senado, números tirados de `dados/resultados`. A linha de 25/10 ("2º turno: Presidência e governo em AC, AM, DF, ES e RN", votação das 8h às 17h de Brasília) não entrou: o guarda recusa linha nova com data futura, e ela fica para um commit com decisão humana. Quando entrar, a linha "2º turno (eventual)" de agosto, na mesma data, sai da linha do tempo sozinha.
- A capa (Visão geral) passou a ser do 2º turno em 13/10/2026: o placar e a manchete trazem a média do 2º turno em válidos (ou, sem média da campanha, o resultado do 1º turno), os tiles trazem o resultado oficial do 1º turno com a média publicada na véspera ao lado, e o painel "Pesquisas x urna" compara as duas; o gráfico da média do 1º turno saiu da capa. O cartão de compartilhamento (og:image) mostra os dois do 2º turno, e o resumo da rodada automática avisa quando ele não é refeito.
- Estados, desde 13/10/2026: cada estado fala pelo resultado oficial do TSE. Governo decidido mostra o eleito com o percentual do TSE (duas casas), Senado mostra os dois eleitos, e o mapa pinta o governo pelo partido do eleito, com listras nas cores dos partidos dos dois finalistas nas UFs com 2º turno e cor neutra no Tocantins. O 2º turno estadual usa só o confronto que vai à urna, casado pelo slug (`real` em `rodadas2`), em votos válidos (a parte de cada um na soma dos dois); a média segue a mesma regra do país, 3 rodadas de 2 institutos com campo terminado depois de 4/10, com a janela do estado (14 dias). Com menos que isso, a abertura do estado mostra o 1º turno do TSE e cada rodada como rodada, com o aviso de que não é média. As simulações de outros pares ficam numa dobra fechada, e as anteriores a 4/10 do mesmo par aparecem apagadas. "Eleita" e "eleito" seguem o sexo declarado ao TSE em `candidatos-detalhe.csv`. Sem os CSVs de resultado, os estados voltam à média das pesquisas.
- Decisões tomadas por padrão em 13/10/2026, a confirmar com o Francisco: a régua do 2º turno começa em 5/10 com janela de 1 dia; a véspera de referência é o número publicado, com a conta refeita ao lado; o texto do Tocantins é o desta seção; o resultado do TSE e as chaves do 2º turno ficam na parte aberta do site, e os estados continuam atrás do cadastro; a incerteza do 2º turno não ganha termo de erro comum medido no 1º turno.
