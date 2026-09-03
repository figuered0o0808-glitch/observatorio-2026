# Coletores de navegador para as disputas estaduais

Roteiro usado em 2 de setembro de 2026 para montar a edição 11 do Mural dos Candidatos e que a rotina das 8h e das 20h passa a repetir. Tudo roda no navegador do Mac (o embutido do app do Claude para o que baixa arquivo, o Chrome para o que precisa de login), porque o sandbox não alcança TSE, Wikipédia, Google Trends nem Instagram.

## Regras que aprendemos no caminho

O navegador embutido do app salva downloads direto em `~/Downloads`, sem janela, mas só quando a página de origem é a Wikipédia; nas origens do TSE e do Google Trends o download não sai. Para essas, o caminho é escrever o resultado no corpo da página (`document.body.innerHTML = '<pre>...'`) e ler com `get_page_text`: resultados grandes vão para um arquivo em disco do sandbox sem passar pelo chat. No Chrome, `window.open` e downloads abrem janela de salvar e travam a aba; no navegador embutido, `window.open` navega a própria aba e apaga o estado. Nunca chamar `window.open` numa aba com dados coletados.

O resultado de `javascript_tool` é cortado em cerca de mil caracteres; os coletores guardam tudo em `window.__algo` e devolvem só contadores.

## 1. Pesquisas estaduais (Wikipédia)

Aba na Wikipédia. Lista as 27 páginas por `list=prefixsearch` com o prefixo "Pesquisas eleitorais para a eleição estadual de 2026" mais a página distrital do DF. Para cada página, `action=parse&prop=text|revid`, e o extrator (`_parse_wiki.py` documenta o formato) percorre os cabeçalhos h2 a h5 e cada `table.wikitable`, expandindo colspan e rowspan, marcando célula de cabeçalho com `H:`. Sai um texto compacto por página, com `@@PAGE título revid=N` na primeira linha e `## caminho > dos > títulos` antes de cada tabela. O JSON com as 27 páginas baixa como `wiki-pesquisas-estados.json`.

No sandbox: `_parse_wiki.py` lê o dump e gera `pesquisas-estados-wiki.csv`; `_consolidar_pesquisas.py` casa com as fichas técnicas da Gazeta do Povo em `pesquisas-estados.csv` e escolhe o cenário principal de cada rodada; sai `pesquisas-estados-consolidado.csv`, que o gerador lê.

## 2. Detalhe das candidaturas (TSE)

Aba em `divulgacandcontas.tse.jus.br/divulga/`. Para cada uma das 510 candidaturas, `GET /divulga/rest/v1/candidatura/buscar/2026/{UF}/20322002026/candidato/{id}` com 300 ms entre chamadas. Guardar só campos públicos de perfil: nome, número, partido, situação, coligação e composição, nascimento, instrução, ocupação, naturalidade, total e quantidade de bens, vice ou suplentes, sites informados, foto publicável e eleições anteriores. Nunca guardar CPF nem título de eleitor, que a API devolve. Exportar em linhas `slug|instagram|tiktok|facebook|youtube|x|site|bens|nbens|instrucao|ocupacao|nascimento|sexo|ufnasc|munnasc|vice|composicao|fotopub|anteriores` e ler pelo `get_page_text`. A foto de cada candidato fica em `https://divulgacandcontas.tse.jus.br/divulga/rest/arquivo/img/20322002026/{id}/{UF}`.

## 3. Google Trends dentro de cada estado

Aba em `trends.google.com`. Plano de lotes em `dados/estados/_trends-estados.json`: por disputa (uf e cargo), o líder da última pesquisa é a âncora e entra em todos os lotes daquela disputa, com até quatro outros nomes por lote, geo `BR-UF`, período 2026-01-01 até hoje. Cada lote são duas chamadas da API interna: `/trends/api/explore` (token do widget TIMESERIES) e `/trends/api/widgetdata/multiline`. Nove segundos entre lotes; em 429, espera um minuto vezes a tentativa. Os 133 lotes levam cerca de meia hora. `_integrar_busca.py` reescala os lotes de cada disputa pela soma da âncora do lote zero (fator limitado entre 0,1 e 10) e marca nomes comuns como termo ambíguo.

## 4. Verbetes e acessos na Wikipédia

Aba na Wikipédia. Para cada candidatura, busca pelo nome completo entre aspas, depois sem aspas, depois `nome de urna + estado + político`; a pontuação soma coincidência de tokens do título com o nome, presença de palavra de papel político no trecho e menção ao estado, e desconta títulos de clube, banda, município e afins. Aceita pontuação 6 ou mais. Para os aceitos, pageviews diários pela API REST da Wikimedia (`all-access`, agente `user`, desde 2026-01-01). Baixa como `wikipedia-estados.json`. No sandbox, `_integrar_busca.py` ainda rejeita títulos sem token distintivo do nome e páginas de desambiguação, e registra tudo em `wikipedia-verbetes-estados.csv` para conferência.

## 5. Seguidores no Instagram

Aba do Chrome logada no Instagram, em qualquer perfil. Para cada handle informado ao TSE, `GET /api/v1/users/web_profile_info/?username=X` com cabeçalho `x-ig-app-id: 936619743392459`; devolve o número exato em `edge_followed_by.count`. Quando o endpoint responde 400 com erro de esquema (perfis comerciais), o fallback é a página do perfil e o número aproximado da meta description ("338K seguidores"), guardado com a marca de aproximado. Três a cinco segundos entre pedidos; em 401, 403 ou 429, dois minutos de espera e desistência depois de seis falhas seguidas. Resultados ficam em `localStorage.mural_ig` para retomar. Armadilha do Chrome: numa aba em segundo plano os temporizadores (`setTimeout`) passam a disparar uma vez por segundo e, depois de cinco minutos, uma vez por minuto, e o laço fica lento sem dar erro. O que funcionou: o laço dorme com um `sleep` que só usa `setTimeout` enquanto uma chamada do app está em curso na aba (uma variável `__attachedUntil` marcada por chamadas de 20 a 28 segundos, repetidas até o fim) e, fora dessas janelas, espera a próxima chamada. Dois laços em paralelo sobre uma fila compartilhada, com cinco a sete segundos de intervalo cada, dão um intervalo agregado de três a cinco segundos entre pedidos; no fim, uma passada refaz só os handles sem resposta. O mural marca com "≈" os números arredondados da meta (a partir de mil) e a coluna `aproximado` do CSV guarda a marca; abaixo de mil a meta traz o número inteiro. Exportação: escrever o JSON no corpo da página e ler com `get_page_text`.
