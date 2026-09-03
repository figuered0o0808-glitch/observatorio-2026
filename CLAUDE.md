# Observatório do capital político digital, Eleições 2026

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
de rodar `_gerar_mural.py` de novo. O mesmo vale para
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

## Publicação

O mural é publicado como página no Claude (Artifact "Mural dos Candidatos").
Publicar e sincronizar acontece a partir da conversa no Claude (claude.ai ou
Cowork), não daqui - uma sessão de Claude Code comum, rodando só nesta pasta,
não tem essa ferramenta. Depois de regenerar e verificar aqui, avise para
publicar de lá.

## Cuidados

Este repositório git é local; não tem remoto configurado. Não adicione um
`remote` nem publique em GitHub ou qualquer outro serviço sem o Francisco
pedir explicitamente. Não edite `mural/mural.html` à mão (é gerado). Ao mudar
`_template.html`, rode `testes/verificar.sh` antes de considerar a mudança
pronta.
