# Briefing: estender o mural para deputado estadual e federal (RJ e SP)

Para uma sessão de Claude Code rodando nesta pasta. Leia primeiro o
`CLAUDE.md` na raiz, que traz as regras e convenções gerais do projeto; este
documento é específico da fase de deputados e assume esse contexto. Não é
um roteiro para copiar literalmente: descreve o que já existe, o que falta
e os pontos de atenção, mas a implementação em si (nomes de função exatos,
onde encaixar cada trecho) é trabalho de quem for codar, depois de ler
`_template.html` e `_gerar_mural.py` inteiros.

## Onde isso se encaixa

O observatório cobria até aqui presidenciáveis (nacional) e governador e
senador (27 estados). O Francisco pediu a mesma cobertura para deputado
estadual e deputado federal, mas só no Rio de Janeiro e em São Paulo, e só
para um grupo curado de "principais" (parlamentares atuais buscando
reeleição e candidatos novos de forte repercussão), não a lista completa de
candidatos registrados. Essa decisão e o porquê estão em
`notas/curadoria-deputados-rjsp-2026-09-07.md`.

## O que já está pronto

`dados/rjsp/candidatos-rjsp.csv`: ficha completa do TSE para as 4.538
candidaturas a deputado estadual e federal em RJ e SP (todo mundo
registrado, sem curadoria). Serve de fonte, não de roteiro do mural.

`dados/rjsp/candidatos-deputados.csv`: o grupo curado, 75 candidaturas (RJ
estadual 24, RJ federal 18, SP estadual 13, SP federal 20), no formato de
`dados/estados/candidatos-estados.csv` (`uf,cargo,id_tse,nome_urna,
nome_completo,numero,partido,coligacao,situacao_tse,totalizacao,slug,
url_tse,fonte`), com duas colunas a mais: `categoria` (A = busca reeleição,
B = candidato novo de repercussão, informação que não existe no arquivo de
governador/senador porque lá entra todo mundo registrado) e, já embutidos
porque o arquivo de origem já tinha, `bens_total` e `instagram`.

`dados/rjsp/_gerar_candidatos_deputados.py`: gera o arquivo acima a partir
da lista curada (hardcoded no script, por nome de urna exato) cruzada
contra `candidatos-rjsp.csv`. Se a curadoria mudar (Francisco pedir para
tirar ou incluir alguém), o ajuste é nessa lista, não no CSV direto.

`notas/varredura-deputados-rj-2026-09-07.md`,
`notas/varredura-deputados-sp-2026-09-07.md`,
`notas/curadoria-deputados-rjsp-2026-09-07.md`: a pesquisa de imprensa por
trás de cada nome curado, com fonte e data, e as correções que o
cruzamento com o TSE trouxe (alguns nomes que a imprensa dava como
concorrendo a um cargo na verdade concorrem a outro, ou em outro estado).
Vale ler antes de mexer na lista curada, para não reintroduzir por engano
um nome já descartado.

Nada disso ainda aparece no mural. `_template.html` e `_gerar_mural.py`
não sabem que essas disputas existem.

## Tarefa 1: estender o mural (a parte principal)

### Como o mural lida com estado e cargo hoje

`_gerar_mural.py` lê `candidatos-estados.csv` e monta, por sigla de
estado, um objeto com duas listas fixas: `gov` (governador) e `sen`
(senador), escolhidas pela coluna `cargo` do CSV. Esse objeto vira o `UF`
global no JS gerado.

No template, `ufCargo` é uma variável só binária: `"senador"` ou
`"governador"` (qualquer outra coisa cai em `"governador"` por padrão, em
`trocarCargoUF`). Várias funções pequenas despacham nesse binário:
`candsDe(uf,cargo)` escolhe `UF[uf].gov` ou `UF[uf].sen`; `VAGAS(cargo)`
devolve 1 ou 2 (usado para desenhar a linha de corte de quem está eleito
numa rodada, já que o Senado tem duas vagas por estado); `cargoLabel(cargo)`
devolve "governo" ou "Senado" para os textos da interface. A troca de cargo
tem sua própria barra de botões (`#ufbar .seg button[data-cargo]`), e a aba
"Candidatos" tem uma segunda barra independente para filtrar só a lista de
cards (`#v-e-candidatos .seg button[data-ecargo]`, variável `ufCargoCards`).
A URL guarda o cargo no hash (`#uf-sp-senado`, `#uf-sp-governo`).

### O que precisa virar N-vias (mas só onde há dado)

Isso tudo foi desenhado para exatamente dois cargos, sempre presentes em
todo estado. Deputado estadual e federal quebram as duas premissas: são
dois cargos a mais, e só existem (por enquanto) no Rio e em São Paulo. A
mudança não é generalizar para todo o Brasil, é fazer o seletor de cargo
mostrar 2 botões nos outros 25 estados e até 4 no RJ e em SP, e fazer os
pontos que hoje despacham `senador`/`governador` num binário passarem a
despachar por uma lista de cargos que cada UF realmente tem.

Um jeito razoável de organizar isso: um objeto de configuração por cargo
(chave interna, rótulo, nome da lista dentro de `UF[uf]`, se usa vagas
múltiplas) em vez de `if/else` espalhado, e cada `UF[uf]` carregando só as
listas de cargo que aquele estado realmente tem (`UF.RJ.depest`,
`UF.RJ.depfed`, mas `UF.AC` sem essas duas chaves). O seletor de cargo
(`#ufbar .seg`) e a barra da aba Candidatos passam a se montar
dinamicamente a partir dos cargos presentes no `ufAtual`, em vez de HTML
fixo com dois botões. Vale conferir se `_template.html` já tem algum
padrão parecido de UI que se adapta por estado (a régua de senado com duas
vagas é o mais próximo) antes de inventar um mecanismo novo.

### O que não precisa entrar nesta fase

Deputado estadual e federal não têm pesquisa nominal registrada (ver
`notas/curadoria-deputados-rjsp-2026-09-07.md` e o próprio
`dados/rjsp/LEIA-ME.md`: proporcional não tem pesquisa por nome, é prática
do mercado). Isso significa que toda a maquinaria de `rodadas`, `polls`,
`cenarios`, a aba "Pesquisas" e o corte de `VAGAS` para saber quem está
eleito numa rodada não têm o que mostrar para esses dois cargos, pelo
menos por enquanto. Não vale a pena construir essa parte agora: o cargo
novo entra só com a aba "Candidatos" (ficha do TSE de cada um, filtrável
por categoria A/B) funcionando, e o resto do UI (pesquisas, lado a lado,
linha do tempo) trata esses dois cargos como "sem dado" do mesmo jeito que
já trata um estado sem rodada de pesquisa hoje, com a mensagem de vazio já
existente, sem cortar nada por vaga.

### Dados de entrada para essa tarefa

Já dá para montar a lista de candidatos com o que existe:
`dados/rjsp/candidatos-deputados.csv` tem número, partido, situação, bens e
Instagram para as 75 candidaturas curadas. Se a ficha do dossiê individual
quiser mais campos (ocupação, escolaridade, coligação completa, vice não
existe para deputado, eleições anteriores), esses campos estão em
`dados/rjsp/candidatos-rjsp.csv`, e dá para juntar por `id_tse` no
`_gerar_mural.py`, do mesmo jeito que hoje `candidatos-detalhe.csv`
enriquece `candidatos-estados.csv` por `slug`.

### Risco específico de deputados: homônimo

O bug mais sério já corrigido neste projeto foi `casar()` misturando
identidades por correspondência de nome fraca demais (documentado em
"Bugs já corrigidos" no `CLAUDE.md`). Deputado estadual e federal têm
centenas de candidatos por disputa, contra dezenas em governador/senador:
o risco de homônimo em qualquer casamento por nome (não por `id_tse`) é
maior aqui, não menor. Se alguma parte da implementação precisar casar
nome de pesquisa ou notícia com candidatura registrada (não deveria ser
necessário nesta fase, já que não há pesquisa nominal, mas vale o alerta
caso apareça mais adiante), usar `id_tse`, nunca nome, como chave.

## Tarefa 2: coleta de Instagram para o grupo curado

Falta o número de seguidores dos 75 curados (o `instagram` que já está em
`candidatos-deputados.csv` é só o identificador do perfil, extraído da URL
que o próprio candidato informou ao TSE, não o número de seguidores). O
método já usado para governador/senador está em
`coleta/navegador_estados.md`: navegar até o perfil público e ler o HTML
carregado, porque a API interna do Instagram devolve 401 sem sessão. Isso
depende de um navegador de verdade controlado pela sessão, não só de
`requests`/`curl`.

Se esta sessão de Claude Code tiver alguma ferramenta de navegador
disponível, o roteiro de `coleta/navegador_estados.md` deveria funcionar
igual, adaptado para os 75 perfis de `candidatos-deputados.csv` em vez dos
perfis estaduais. Se não tiver, essa etapa específica provavelmente precisa
voltar para uma conversa no Claude (claude.ai ou Cowork) com navegador
conectado, do mesmo jeito que a publicação do mural também só acontece de
lá (ver "Publicação" no `CLAUDE.md`). Não vale a pena forçar um caminho
alternativo (scraping sem navegador, API não documentada) só para evitar
essa dependência.

## Regras que já valem e continuam valendo

Tudo que está em "Regras de conteúdo e dados" e "Convenções técnicas do
mural" no `CLAUDE.md` vale igual para deputados: nenhum número sem data e
fonte, célula vazia nunca zero, fontes não se misturam numa mesma célula,
`ufAtual`/`ufCargo` só mudam pelas funções próprias, `HOJE` sempre por
fuso horário de Brasília. A regra de privacidade (sem CPF, sem título de
eleitor) também vale para `candidatos-rjsp.csv` e já foi seguida na coleta
original, documentada em `dados/rjsp/LEIA-ME.md`.

## Critério de pronto

Rodar `./testes/verificar.sh` antes de considerar qualquer mudança pronta.
`testes/varredura_geral.py` hoje percorre 27 estados x 2 cargos; ao
adicionar deputado estadual e federal, vale estender essa varredura para
cobrir RJ e SP nos 4 cargos (e confirmar que os outros 25 estados continuam
só com 2, sem erro de console por causa de uma lista de cargo ausente).
Qualquer bug novo encontrado no caminho ganha um bloco em
`testes/regressao_bugs_conhecidos.py`, como já é hábito neste projeto.
Nunca editar `mural/mural.html` à mão; ele sai de `_gerar_mural.py`. Depois
de gerar e verificar, avisar para publicar numa conversa do Claude, porque
uma sessão de Claude Code comum não tem a ferramenta de publicar artefato.
