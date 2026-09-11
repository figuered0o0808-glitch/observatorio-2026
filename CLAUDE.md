# Observatório do desempenho dos candidatos, Eleições 2026

Acompanhamento de dados públicos (TSE, pesquisas registradas, Wikipédia, Google
Trends, redes sociais oficiais) da disputa presidencial e das disputas estaduais
a governador e senador em 2026. O produto principal é o **Mural dos
Candidatos**, uma página HTML autocontida gerada a partir dos CSVs desta pasta.
De quem é: Francisco (INDICA, Rio de Janeiro).

Leia também `briefing.md` (o que entra e o que fica de fora do mural),
`fontes.md` (convenções do dataset, pendências, decisões de cada edição) e
`dados/estados/LEIA-ME.md` (origem de cada arquivo estadual).

## Como regenerar o mural

Pipeline, nessa ordem. Cada script lê e escreve só dentro desta pasta, com
caminhos relativos ao próprio arquivo (funciona em qualquer máquina):

```
coletar (roteiro em coleta/navegador_estados.md, quando há coleta nova)
  -> dados/estados/_parse_wiki.py
  -> dados/estados/_consolidar_pesquisas.py
  -> dados/estados/_integrar_busca.py
  -> mural/_gerar_mural.py
```

Na prática, para gerar uma edição nova a partir dos dados já coletados (sem
recoletar nada):

```bash
python3 dados/estados/_consolidar_pesquisas.py
python3 mural/_gerar_mural.py
```

`mural/mural.html` é **gerado**; nunca edite esse arquivo à mão. Toda mudança
visual ou de comportamento vai em `mural/_template.html`, e o mural final sai
de rodar `_gerar_mural.py` de novo. `index.html`, na raiz, é uma cópia
idêntica que o mesmo script grava para o GitHub Pages servir o site na raiz
do endereço; também é gerado e também não se edita à mão. O mesmo vale para
`dados/estados/pesquisas-estados-consolidado.csv`: é saída de
`_consolidar_pesquisas.py`, não edite direto.

## Como verificar

```bash
pip install -r requirements.txt --break-system-packages   # uma vez
playwright install chromium                                # uma vez
./testes/verificar.sh                                       # regenera e verifica
./testes/verificar.sh --pular-geracao                        # só verifica o que já existe
```

`testes/regressao_bugs_conhecidos.py` reproduz cada bug já corrigido e falha se
algum voltar. `testes/varredura_geral.py` é uma rede de segurança mais ampla:
percorre os 27 estados x 2 cargos, mobile, tema escuro, alguns dossiês, e falha
em qualquer erro de console novo. Ao corrigir um bug novo, **adicione um bloco
em `regressao_bugs_conhecidos.py`** em vez de só corrigir e seguir; é isso que
impede o mesmo bug de voltar numa edição futura sem ninguém notar. Rode os
testes antes de publicar qualquer edição nova.

## Mapa da pasta

- `briefing.md`, `fontes.md` - regras editoriais e convenções do dataset.
- `notas/` - varreduras de notícias e decisões, uma por data.
- `artigo/` - o acompanhamento analítico em texto corrido (não é o mural).
- `coleta/` - roteiros e scripts de coleta (TSE, Wikipédia pageviews).
- `dados/*.csv` - dados nacionais (13 presidenciáveis): candidatos, pesquisas,
  série diária de seguidores/buscas, eventos, partidos.
- `dados/estados/` - os mesmos dados para as disputas estaduais (governador e
  senador, 27 estados, 510 candidaturas). Ver `dados/estados/LEIA-ME.md`.
- `dados/geo/` - GeoJSON simplificado do mapa do Brasil (`_mapa_br.py` gera
  `br-uf-paths.json`; raramente precisa rodar de novo, precisa de `shapely`).
- `mural/_template.html` - fonte do mural (HTML+CSS+JS num arquivo só).
- `mural/_gerar_mural.py` - lê `dados/` e `dados/estados/`, escreve
  `mural/mural.html` a partir de `_template.html`.
- `mural/mural.html` - o mural gerado, o que é publicado.
- `index.html` - cópia idêntica do mural na raiz, gerada junto, é o que o
  GitHub Pages serve em https://muraldoscandidatos.com/.
- `mural/logo/` - marca "Apuração" (SVG/PNG prontos) e `_scripts/` que os
  geraram (precisa de `fonttools`, `uharfbuzz`, `playwright`; ver
  `mural/logo/LEIA-ME.md`).
- `testes/` - verificação automatizada do mural (ver seção acima).
- `evidencias/` - capturas de tela e vídeo por data/evento, referenciadas do
  `fontes.md` ou do artigo.

Scripts com nome de data no meio (`dados/_coleta_busca_2026-09-01.py`,
`dados/_merge_historico_2026-09-01.py`) são coletas pontuais já executadas,
não fazem parte do pipeline repetível acima; alguns têm caminho absoluto de
uma máquina específica e não devem ser rodados de novo como estão.

## Regras de conteúdo e dados

Estas regras valem para qualquer edição, script novo ou texto escrito neste
projeto:

- **Nenhum número entra sem data e fonte.** Cada linha de CSV carrega sua data
  e sua fonte por extenso; todo dado no mural mostra de onde veio e quando.
- **Célula vazia é indisponível, nunca zero.** Não preencher com 0 um dado que
  simplesmente não foi encontrado.
- **Fontes nunca se misturam numa mesma célula.** Quando duas fontes cobrem a
  mesma linha (por exemplo, uma rodada de pesquisa que aparece tanto na
  Wikipédia quanto na ficha técnica da Gazeta do Povo), os números vêm de uma
  fonte e os metadados de registro vêm da outra, e a coluna `fonte` (ou
  equivalente) sempre diz qual é qual.
- **Datas em `AAAA-MM-DD`.** CSVs em UTF-8 com BOM, separador vírgula, decimal
  com ponto.
- **Seguidores, buscas e engajamento não são pesquisa eleitoral.** Ficam em
  colunas e arquivos separados dos números de intenção de voto
  (`serie-diaria.csv` usa plataformas como `google_trends`,
  `instagram_comentarios_voto` etc.; nunca tratar esses números como
  equivalentes ou conversíveis em intenção de voto.
- **Privacidade:** CPF e título de eleitor não são armazenados em nenhum CSV,
  mesmo quando a fonte original os disponibiliza.
- **Cuidado com nomes homônimos.** O verbete de Renan Santos (MISSÃO,
  presidenciável) na Wikipédia fica sob o título "Renan Santos"; a grafia
  "Renan dos Santos" é de um futebolista, pessoa diferente, e não deve ser
  usada para casar dados. Nomes comuns como Fábio, Renan e Marina em geral
  captam homônimos nas buscas do Google Trends e entram marcados como termo
  ambíguo.
- **Convenções do TSE:** `uf_nascimento` pode vir `"ZZ"` (candidato nascido no
  exterior); o mural mostra isso como "exterior", não como a sigla crua.
  `municipio_nascimento` vem em maiúsculas no dado bruto; capitalize por
  palavra ao exibir, não só a primeira letra da string inteira.

## Convenções técnicas do mural (`_template.html`)

- `DATA` é o objeto global com os dados **nacionais** (13 presidenciáveis:
  `DATA.candidatos`, `DATA.polls`, `DATA.partidos` etc.). `UF` é o objeto
  global com os dados **estaduais**, indexado por sigla (`UF.SP.gov`,
  `UF.SP.sen`, `UF.SP.polls`, `UF.SP.polls2` para segundo turno). Não confundir
  os dois.
- `ufAtual` (estado sendo visto) só muda através de `trocarUF(sigla)`; setar
  `prefs.uf` direto não move `ufAtual`. O mesmo vale para `ufCargo`, que só
  muda por `trocarCargoUF(cargo)`.
- Datas usam sempre `Intl.DateTimeFormat` com `timeZone: "America/Sao_Paulo"`
  para calcular "hoje" (`HOJE`). Nunca `new Date().toISOString().slice(0,10)`
  sozinho: isso dá a data em UTC, e à noite no Brasil (21h-23h59 em horário de
  Brasília) já é o dia seguinte em UTC.
- Ao copiar um objeto de preferências (`{...DEF}`), lembre que isso é cópia
  rasa: arrays aninhados continuam sendo a mesma referência. Sempre reatribua
  um array novo (`prefs.x = [...(prefs.x||[])]`) em vez de mutar em lugar
  (`.push`/`.splice` direto no array compartilhado).
- Toasts e tooltips que vivem fora de um `<dialog>` ficam escondidos atrás dele
  quando o dialog está aberto (comportamento do "top layer" do navegador,
  `position:fixed` não resolve isso). A solução usada é reparentar o elemento
  flutuante para dentro do dialog aberto no momento de mostrá-lo.
- `esc()` escapa HTML para uso em `innerHTML`; nunca aplicar `esc()` a um valor
  que vai para `.textContent` (que já escapa sozinho) - isso produz
  `&#39;`/`&amp;` literais na tela.
- A página é uma casca de site: `header.band.band-top` (masthead), `div.band`
  com a navegação fixa (escopo Presidência/Estados mais oito editorias),
  `div.band.subnav` do estado, o `main` dentro de `.wrap` e o
  `footer.band`. As faixas ocupam a largura toda e o conteúdo para em 1280px
  pelo `.wrap`. Quem navega por hash passa por `irPara()`, que mede o masthead
  (não a barra fixa) para rolar até o topo da editoria.
- A linha das pesquisas não é média simples. `agregarEm(rodadas,nomes,sigma,t)` pondera cada
  rodada pelo tempo (a régua) e depois desconta discrepância; `linhaAgregada` desenha a série e
  `incertezaEm`/`empatam` dizem quando a diferença entre dois nomes cabe dentro da incerteza da
  própria média (aí o mural diz empate técnico em vez de anunciar um líder). As quatro defesas
  estão comentadas no código, junto de `AG`: uma rodada por instituto, janela que alarga até
  cinco institutos, desconto de quem aponta disputa diferente do conjunto (medido depois de
  tirar o nível da rodada) e teto de 15% por rodada. Todo gráfico de intenção de voto passa a
  `chartTempo` a chave `linha` com esse resultado, nunca `sigma` sozinho: o rótulo do gráfico
  sai do último ponto da linha, e um gráfico que fique na média antiga mostra número diferente
  do placar.
- A janela da média móvel não é fixa: `REGUA` e `sigmaRegua(dia)` calculam
  `SIG` pela data de Brasília (4 dias, perdendo um a cada dez até 1 em 4/10).
  Todo texto que cite a janela usa `${SIG}` ou a classe `.sig-dias`; nunca
  escrever "7 dias" à mão.
- A manchete da home (`#manchete`) e a dos estados (`#e-tag`) são numéricas e
  factuais, montadas por `ORDEM()` (média móvel do dia) e por `liderDe()`
  (última rodada do estado). Não escrever leitura editorial ali: o observatório
  publica número com data e fonte, e quem lidera muda com o dado.
- Gráficos: `chartTempo` desenha na largura do contêiner sempre que ela for
  menor que o viewBox pedido, e `drawRegua`/`drawBens` aceitam largura (versão
  vertical no celular). Ao mostrar uma editoria que estava oculta,
  `reajustarGraficos()` redesenha na largura real; `DRAW` guarda quem redesenha
  cada contêiner.
- Ausência de dado não vira texto repetido: quando a rodada não traz modo de
  coleta, o texto omite o trecho em vez de anunciar a falta em cada linha. A
  falta de registro no TSE continua dita uma vez, porque muda o valor da ficha.

## Estilo de escrita

Textos deste projeto (mural, artigo, relatórios, respostas ao Francisco) não
usam travessão nem as marcações "clássicas de IA" (títulos decorativos, listas
onde prosa serviria melhor, negrito em excesso). Prosa direta, em português.

## Bugs já corrigidos (edição 12, setembro de 2026)

Contexto para não redescobrir nem reintroduzir o que já foi corrigido; cada um
tem um teste correspondente em `testes/regressao_bugs_conhecidos.py`:

fuso horário de `HOJE` (virava o dia 3h cedo demais); reset de preferências
não limpava `focoUF` por causa de cópia rasa; foco de candidato estadual
vazava de um estado para outro; eixo Y de governador cortava a linha de
estados com corrida concentrada acima de 52%; situação "Indeferido" aparecia
com selo verde de "bom" (regex de "Deferido" casava dentro de "Indeferido");
legenda de tendências mostrava `&#39;` literal em nomes com apóstrofo; partido
AGIR não entrava na barra do comparador de partidos por causa de comparação
case-sensitive com a sigla; toast ficava escondido atrás de um dossiê aberto;
`fPct` mostrava "-0"; `fM` mostrava "1.000 mil" em vez de trocar de escala
perto de 1 milhão; botão de tema no canto superior direito ciclava entre 3
estados (sistema/claro/escuro) em vez de alternar só entre claro e escuro;
rodadas de pesquisa estaduais coincidiam entre estados diferentes por uma
chave de deduplicação sem a UF, derrubando ~17% das rodadas e trocando o líder
mais recente em 9 estados; `casar()` (que liga nomes pesquisados a
candidaturas registradas) aceitava correspondências fracas demais e misturou
identidades de 26 candidaturas em casos como Geraldo Alckmin/Antônio
Denarium/Marcos Rocha.

Da repaginação de setembro: `.cover{white-space:nowrap}` genérico empurrava o
dossiê e a sparkline para fora da caixa; os ids `lado` e `e-lado` faziam o
navegador rolar até o comparador ao abrir um hash; o carimbo de Pesquisas do
estado contava governo e Senado juntos enquanto o painel contava só a disputa
escolhida; navegar por hash com a página rolada parava no meio da editoria de
destino; entre 761 e 960px o masthead transbordava e a página inteira rolava
de lado; a média das pesquisas era simples e uma rodada isolada (a Veritá de 6/9, única a dar
Flávio à frente no segundo turno) respondia por 27% do peso e invertia a corrida; o gráfico da
home ficou na média antiga por uma passada e mostrava número diferente do placar.

## Publicação

O mural é publicado no GitHub Pages, em
https://muraldoscandidatos.com/, a partir do
repositório https://github.com/figuered0o0808-glitch/observatorio-2026 (branch
`main`). O Pages está no modo "GitHub Actions": quem publica é o workflow
`.github/workflows/publicar.yml`, a cada push na `main` que mude o
`index.html`, e o `atualizar.yml` no fim de cada rodada automática. Um push
sozinho não publica nada. O site serve só o `index.html` e o cartão de prévia
de link; os CSVs ficam versionados aqui, fora do site.

A publicação antiga como página no Claude (Artifact) não é mais o canal
principal; se for feita, usa o mesmo `mural/mural.html`.

## Atualização automática

Duas vezes por dia, às 8h e às 20h de Brasília (`0 11,23 * * *` em UTC), o
workflow `.github/workflows/atualizar.yml` roda num runner do GitHub, que
alcança a Wikipédia (o ambiente do Claude e o Mac atrás do proxy não
alcançam). Ele coleta o que é público e sem login, regenera, confere e
publica:

- `coleta/wikipedia_pesquisas_nacional.py` acrescenta a
  `dados/pesquisas-registradas.csv` as rodadas presidenciais que a compilação
  da Wikipédia tem e o arquivo ainda não tem (nunca altera linha existente;
  `registro_tse` fica vazio porque a página não traz).
- `coleta/wikipedia_pesquisas_estados.py` regrava
  `dados/estados/_wiki-pesquisas-estados.json` no mesmo formato compacto que o
  navegador produzia, só para as páginas cuja revisão mudou; depois rodam
  `_parse_wiki.py` e `_consolidar_pesquisas.py` como sempre.
- `coleta/wikipedia_pageviews.py` acrescenta os acessos diários aos verbetes,
  nacionais (`dados/wikipedia-pageviews.csv`) e estaduais
  (`dados/estados/wikipedia-estados.csv`), com a lista de verbetes congelada
  em `wikipedia-verbetes-estados.csv` e em `candidatos.csv`.
- `testes/guarda_dados.py` compara cada CSV com o HEAD e bloqueia o commit se
  alguma regra de dado for violada (BOM, CRLF, linha antiga tocada, vazio que
  vira zero, data inválida ou futura, arquivo manual alterado).
- Os dois testes Playwright rodam; só com tudo verde o workflow commita
  dados e mural (como `github-actions[bot]`) e publica.
- Testes de coletor nunca usam o dado de produção como oráculo: a coleta roda
  duas vezes por dia e o que hoje é "linha nova" amanhã já está no arquivo. Os
  oráculos ficam congelados em `testes/fixtures/wikipedia/` (dump do navegador de
  2/9, CSV de pesquisas de 6/9, as duas séries de acessos de 6/9).

- `coleta/google_trends_estados.py` refaz os 133 lotes do Trends por estado no mesmo
  plano que o navegador montou (`dados/estados/_trends-estados.json`, âncora por
  disputa) e `dados/estados/_integrar_busca.py --so-trends` transforma em
  `trends-estados.csv` com a reescala pela âncora. São quinze minutos, então roda
  só na rodada da noite. O `--so-trends` existe porque sem ele o script regravaria
  também `wikipedia-estados.csv` e `candidatos-detalhe.csv`, que têm dono próprio.
- `coleta/google_trends.py` refaz a série de busca nacional (`dados/trends-2026.csv`)
  nos três lotes da coleta de navegador. O índice do Trends é relativo à janela
  pedida, então a série inteira é regravada a cada coleta, não acrescentada; é o
  único CSV nessa condição fora dos estaduais de pesquisa. Se o Google bloquear
  num dia, o coletor não grava nada e a rodada segue com o resto.

TSE e Instagram não entram nessa rotina: o TSE responde 403 (Akamai) a qualquer
IP de fora do Brasil, inclusive no portal, e o Instagram devolve 429 na API e não
traz o número de seguidores no HTML público. Medido no runner em 6 e 7/9/2026, com
o resultado por fonte em `coleta/RESULTADO.md`. Os dois continuam pelo roteiro de
navegador em `coleta/navegador_estados.md`, com a data de cada número no mural.
O Google Trends estava nessa lista até 7/9: ele responde ao runner desde que a
sessão visite `trends.google.com` antes de chamar a API, para receber os cookies.

O HTML real das páginas da Wikipédia usado nos testes está em
`testes/fixtures/wikipedia/` (workflow `fixtures-wikipedia.yml`, à mão).

## Cuidados

O remoto é o GitHub (decisão do Francisco em 3/9/2026) e a publicação é pelo
Pages; não publique em outro serviço sem ele pedir. O que a automação grava
em `dados/` passa pelo guarda; o que é digitado à mão (fichas da Gazeta,
eventos, seguidores, TSE) continua sendo fonte primária e a automação nunca
o regrava. Não edite `mural/mural.html` à mão (é gerado). Ao mudar
`_template.html`, rode `testes/verificar.sh` antes de considerar a mudança
pronta.
