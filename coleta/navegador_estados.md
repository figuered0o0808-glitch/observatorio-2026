# Coletores de navegador para as disputas estaduais

Roteiro usado em 2 de setembro de 2026 para montar a edição 11 do Mural dos Candidatos. Desde 6/9 as duas seções de Wikipédia (1 e 4) e, desde 7/9, a do Google Trends (3) rodam sozinhas às 8h e às 20h de Brasília no GitHub Actions (`.github/workflows/atualizar.yml`, scripts `wikipedia_pesquisas_estados.py` e `wikipedia_pageviews.py`, que produzem os mesmos arquivos que o navegador produzia); o roteiro delas fica aqui como referência do formato. As seções 2 e 5 (TSE e Instagram) continuam manuais e rodam no navegador do Mac (o embutido do app do Claude para o que baixa arquivo, o Chrome para o que precisa de login), porque nem o sandbox nem o runner do GitHub alcançam essas fontes (TSE 403 para IP de fora do Brasil, Instagram 429 na API e sem o número no HTML público).

## Regras que aprendemos no caminho

O navegador embutido do app salva downloads direto em `~/Downloads`, sem janela, mas só quando a página de origem é a Wikipédia; nas origens do TSE e do Google Trends o download não sai. Para essas, o caminho é escrever o resultado no corpo da página (`document.body.innerHTML = '<pre>...'`) e ler com `get_page_text`: resultados grandes vão para um arquivo em disco do sandbox sem passar pelo chat. No Chrome, `window.open` e downloads abrem janela de salvar e travam a aba; no navegador embutido, `window.open` navega a própria aba e apaga o estado. Nunca chamar `window.open` numa aba com dados coletados.

O resultado de `javascript_tool` é cortado em cerca de mil caracteres; os coletores guardam tudo em `window.__algo` e devolvem só contadores.

## 1. Pesquisas estaduais (Wikipédia)

Aba na Wikipédia. Lista as 27 páginas por `list=prefixsearch` com o prefixo "Pesquisas eleitorais para a eleição estadual de 2026" mais a página distrital do DF. Para cada página, `action=parse&prop=text|revid`, e o extrator (`_parse_wiki.py` documenta o formato) percorre os cabeçalhos h2 a h5 e cada `table.wikitable`, expandindo colspan e rowspan, marcando célula de cabeçalho com `H:`. Sai um texto compacto por página, com `@@PAGE título revid=N` na primeira linha e `## caminho > dos > títulos` antes de cada tabela. O JSON com as 27 páginas baixa como `wiki-pesquisas-estados.json`.

No sandbox: `_parse_wiki.py` lê o dump e gera `pesquisas-estados-wiki.csv`; `_consolidar_pesquisas.py` casa com as fichas técnicas da Gazeta do Povo em `pesquisas-estados.csv` e escolhe o cenário principal de cada rodada; sai `pesquisas-estados-consolidado.csv`, que o gerador lê.

## 2. Detalhe das candidaturas (TSE)

Aba em `divulgacandcontas.tse.jus.br/divulga/`. Para cada uma das 510 candidaturas, `GET /divulga/rest/v1/candidatura/buscar/2026/{UF}/20322002026/candidato/{id}` com 300 ms entre chamadas. Guardar só campos públicos de perfil: nome, número, partido, situação, coligação e composição, nascimento, instrução, ocupação, naturalidade, total e quantidade de bens, vice ou suplentes, sites informados, foto publicável e eleições anteriores. Nunca guardar CPF nem título de eleitor, que a API devolve. Exportar em linhas `slug|instagram|tiktok|facebook|youtube|x|site|bens|nbens|instrucao|ocupacao|nascimento|sexo|ufnasc|munnasc|vice|composicao|fotopub|anteriores` e ler pelo `get_page_text`. A foto de cada candidato fica em `https://divulgacandcontas.tse.jus.br/divulga/rest/arquivo/img/20322002026/{id}/{UF}`.

## 3. Google Trends dentro de cada estado

Desde 7/9/2026 esta seção também roda sozinha, na rodada da noite: `coleta/google_trends_estados.py` refaz os mesmos 133 lotes deste roteiro e `_integrar_busca.py --so-trends` regrava o CSV. O roteiro abaixo fica como referência do plano de lotes e da reescala.


Aba em `trends.google.com`. Plano de lotes em `dados/estados/_trends-estados.json`: por disputa (uf e cargo), o líder da última pesquisa é a âncora e entra em todos os lotes daquela disputa, com até quatro outros nomes por lote, geo `BR-UF`, período 2026-01-01 até hoje. Cada lote são duas chamadas da API interna: `/trends/api/explore` (token do widget TIMESERIES) e `/trends/api/widgetdata/multiline`. Nove segundos entre lotes; em 429, espera um minuto vezes a tentativa. Os 133 lotes levam cerca de meia hora. `_integrar_busca.py` reescala os lotes de cada disputa pela soma da âncora do lote zero (fator limitado entre 0,1 e 10) e marca nomes comuns como termo ambíguo.

## 4. Verbetes e acessos na Wikipédia

Aba na Wikipédia. Para cada candidatura, busca pelo nome completo entre aspas, depois sem aspas, depois `nome de urna + estado + político`; a pontuação soma coincidência de tokens do título com o nome, presença de palavra de papel político no trecho e menção ao estado, e desconta títulos de clube, banda, município e afins. Aceita pontuação 6 ou mais. Para os aceitos, pageviews diários pela API REST da Wikimedia (`all-access`, agente `user`, desde 2026-01-01). Baixa como `wikipedia-estados.json`. No sandbox, `_integrar_busca.py` ainda rejeita títulos sem token distintivo do nome e páginas de desambiguação, e registra tudo em `wikipedia-verbetes-estados.csv` para conferência.

## 5. Seguidores no Instagram

Reescrita depois da coleta de 9/9/2026, que não conseguiu usar o método anterior. O que está
abaixo é o que funcionou de fato, com os erros que custaram tempo.

**O endpoint antigo morreu para nós.** `GET /api/v1/users/web_profile_info/?username=X`, que
era o caminho principal, responde 429 de forma persistente. Não é falta de login: o cookie
`ds_user_id` estava presente, o corpo do próprio 429 vinha com `class="logged-in"`, e mandar os
cabeçalhos completos da página (`x-csrftoken`, `x-ig-www-claim`, `x-asbd-id`) não mudou nada.
Quatro tentativas com as esperas de dois minutos, quatro 429. A explicação provável é que o
Instagram restringe esse endpoint em particular, por ser o mais usado por scraper: em mais de
500 pedidos aos outros endpoints na mesma sessão e no mesmo IP não veio nenhum 429.

**O caminho que funciona é por id**, dois pedidos por perfil e sem renderizar página:

1. `GET /web/search/topsearch/?query=<handle>` devolve o `pk`, casando pelo `username` exato.
   (Alternativa: o HTML da página do perfil traz o padrão `profilePage_<pk>`.)
2. `GET /api/v1/users/<pk>/info/` devolve `follower_count` exato.

Nenhum dos dois estava bloqueado. Ritmo de 1,5 segundo entre perfis dá cerca de 11 perfis por
minuto, e 443 perfis saem em meia hora.

**Se for pela página renderizada, ler o `title`, nunca a meta description.** O contador de
seguidores traz o número exato no atributo `title`; a meta traz o arredondado. A diferença não
é cosmética: para Renan Santos a meta daria "3M" contra 2.554.755 reais, 18% de erro. A meta só
serve quando não existe `title`, que é o caso de perfil pequeno, em que o número já aparece
inteiro. Os dois caminhos conferem entre si: Alan Rick deu 83.713 no endpoint por id e 83.713
no `title`. Por isso a coleta de 9/9 é exata e `aproximado` fica 0 na linha toda, ao contrário
da de 2/9, que tinha 86 valores arredondados.

**Armadilha dos temporizadores, pior do que estava escrito aqui.** Em aba de segundo plano o
`setTimeout` degrada até cerca de um disparo por minuto: uma pausa pedida de 1,7 segundo levou
quarenta, o que estourava o teto de 45 segundos por chamada e processava um perfil por chamada.
A saída não é dormir com `setTimeout`. É ceder a thread com `MessageChannel` num laço que só
olha o relógio: `while (Date.now() < alvo) await tick()`. Isso não sofre estrangulamento, não
bloqueia a aba, e permite disparar o laço em segundo plano e consultar o progresso de fora.

**Armadilha nova, que custou 51 minutos e a coleta inteira de 463 perfis: navegar a aba que
guarda os resultados apaga tudo.** O aviso que existia aqui falava só de `window.open`, e o
risco é qualquer navegação, inclusive um `navigate` do próprio agente para conferir outro
perfil. A regra passa a ser: **a aba que coleta não se navega nunca, e quem precisa navegar
abre outra aba.** E a gravação em `localStorage` a cada perfil, que este roteiro já mandava
fazer e não estava implementada, agora está: chave `mural_ig_<data>`, retomada automática
pulando o que já tem. Numa das quedas o laço estava em 188 e voltou vivo no mesmo ponto.

**Perfil que não existe mais** vira linha com `seguidores` vazio e `status` explicando, nunca
zero e nunca herdando número de outra data. Na próxima passada vale conferir se algum apenas
trocou de nome de usuário: aí a correção é no handle, não no dado.

**Fuso.** A data da linha segue Brasília, não UTC. A coleta de 9/9 terminou às 22h52 de
Brasília, quando em UTC já era dia 10, e as linhas são de 2026-09-09.

**Exportação:** escrever o JSON no corpo da página e ler com `get_page_text`, depois rodar
`dados/estados/_gravar_instagram_<data>.py`, que valida e grava no contrato do CSV.

**Isso cabe em rotina?** Cabe, mas não como estava escrito. Meia hora para 443 perfis é
rotinizável e a ausência de 429 mostra folga no ritmo. O que não cabe em rotina é depender de
sessão de navegador recém-logada e de máquina que pode hibernar no meio; a retomada por
`localStorage` resolve a segunda parte, e a primeira pede uma sessão do Chrome já estabelecida.
