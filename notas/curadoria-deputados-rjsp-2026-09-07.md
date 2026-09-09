# Curadoria de deputados estaduais e federais, RJ e SP: cruzamento com o TSE (7/9/2026)

Este documento cruza as duas varreduras de imprensa já feitas para o recorte
curado de deputado estadual e federal em RJ e SP
(`notas/varredura-deputados-rj-2026-09-07.md` e
`notas/varredura-deputados-sp-2026-09-07.md`) contra a ficha completa do TSE
em `dados/rjsp/candidatos-rjsp.csv` (4.538 candidaturas, coletada no mesmo
dia). Cruzamento feito por nome, com correspondência manual conferida onde o
casamento automático deu mais de um resultado plausível; script usado em
`dados/rjsp/_cruzar_curados_2026-09-07.py`. Serve de base para
`candidatos-deputados.csv`, gerado em 9/9/2026 por
`dados/rjsp/_gerar_candidatos_deputados.py` (75 candidaturas: RJ estadual
24, RJ federal 18, SP estadual 13, SP federal 20).

**Atualização de 9/9/2026:** as três pendências abaixo foram resolvidas sem
resposta do Francisco, por decisão minha, e já refletidas em
`candidatos-deputados.csv`: Val Marchiori entrou na lista de São Paulo como
categoria B; Gracyanne Barbosa e José de Abreu ficaram de fora por não
aparecerem em nenhuma das 4.538 candidaturas do arquivo do TSE. Se o
Francisco tiver fonte melhor sobre os dois, é só avisar que eu ajusto.

## Correções que o cruzamento com o TSE trouxe

O cruzamento contra o registro oficial encontrou quatro problemas nas duas
varreduras de imprensa, que valem a pena olhar antes de qualquer coisa:

**Martha Rocha não concorre à reeleição na Alerj.** A varredura do RJ
classificou-a em "deputados estaduais atuais buscando reeleição", mas a
ficha do TSE mostra o oposto: ela é candidata a **deputada federal** em
2026 (PDT, número 1240, nome de urna "Delegada Martha Rocha", deferida),
não à reeleição no cargo atual. Movida para a tabela de deputado federal
abaixo.

**Val Marchiori não concorre no Rio de Janeiro.** A varredura do RJ a
incluiu como candidata a deputada federal pelo estado, citando uma matéria
de março de 2026 sobre pré-candidatura. A ficha do TSE mostra que ela é
candidata a deputada federal por **São Paulo** (Republicanos, número 1077,
deferida), não pelo Rio. Removida da lista do RJ; incluída na tabela de São
Paulo abaixo (ver nota de 9/9/2026 no topo deste documento).

**Gracyanne Barbosa e José de Abreu não aparecem em nenhuma das 4.538
candidaturas do arquivo**, nem em RJ nem em SP, em nenhum cargo. As duas
entradas na varredura do RJ vieram da mesma matéria de listicle de
celebridades (Band, sem data de publicação clara). É possível que a
candidatura não tenha se confirmado no registro final, ou que o nome de
urna registrado seja muito diferente do nome público a ponto de escapar da
busca por sobrenome; não encontrei uma explicação melhor com o tempo
disponível. Meu recomendado é excluir os dois da lista rastreada até
aparecer confirmação direta do registro de candidatura de cada um.

Além disso, três nomes da varredura de SP têm partido diferente do TSE em
relação ao que a notícia usada como fonte registrava: Ana Carolina Serra
(a notícia de janeiro cita Cidadania; o TSE mostra PSDB), Carla Morando
(notícia cita PSDB; TSE mostra PSD) e Oseias de Madureira (notícia cita
PSD; TSE mostra PL). Como as notícias são de janeiro e o registro de
candidatura fechou em agosto, a explicação mais provável é troca de
partido na janela partidária; o TSE é a fonte mais recente e é o que uso
nas tabelas abaixo. Não voltei a checar cada um individualmente com uma
segunda fonte jornalística sobre a troca em si.

Uma ressalva herdada da varredura do RJ, agora reforçada: os 18 nomes do
PL na Alerj (tabela abaixo) tiveram a candidatura a deputado estadual
confirmada individualmente contra o TSE nesta consolidação (todos com
ficha deferida ou aguardando julgamento sob esse cargo específico); o que
não foi verificado nome a nome numa segunda fonte jornalística é a frase
"busca reeleição" em si, que na varredura original veio por eliminação das
exceções nomeadas (ver o documento original para o raciocínio completo).

## Rio de Janeiro, deputado estadual (Alerj)

### Categoria A, reeleição (21)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Alan Lopes | PL | 22377 | Deferido | 225.000 | alanlopesrio |
| Alexandre Knoploch | PL | 22722 | Deferido | 2.026.761,79 | aknoploch |
| Anderson Moraes | PL | 22120 | Deferido | 1.953.122,93 | deputadoandersonmoraes |
| Chico Machado | PL | 22611 | Deferido | 48.026.625 | - |
| Delegado Carlos Augusto | PL | 22045 | Deferido | 1.167.566,08 | delegadocarlosaugusto |
| Dr. Deodalto | PL | 22456 | Deferido | 2.767.074,04 | dr.deodalto |
| Dr. Pedro Ricardo | PL | 22000 | Deferido | 1.180.904,77 | pedroricardorj |
| Fred Pacheco | PL | 22010 | Deferido | 2.521.362,31 | fredpachecorj |
| Giselle Monteiro | PL | 22500 | Deferido | 149.246,72 | gisellemonteiro.br |
| Guilherme Delaroli | PL | 22222 | Deferido | 1.581.060 | guilherme.delaroli |
| Índia Armelau | PL | 22322 | Deferido | 989.302,63 | india_armelau |
| Jair Bittencourt | PL | 22300 | Aguardando julgamento | 2.601.092,79 | jairbittencourtoficial |
| Jorge Felippe Neto | PL | 22800 | Aguardando julgamento | 690.484 | depjorgefelippeneto |
| Marcelo Dino | PL | 22190 | Deferido | 726.000 | marcelodinorj |
| Márcio Gualberto | PL | 22070 | Deferido | 17.904,57 | depmgualberto |
| Renan Jordy | PL | 22111 | Deferido | 1.700.000 | renanjordybr |
| Renato Miranda | PL | 22345 | Deferido | 887.875,01 | renato.mirandarj |
| Valdecy da Saúde | PL | 22615 | Deferido | 3.505.671 | valdecydasaude |
| Carlos Minc | PSB | 40000 | Deferido | 424.590,50 | carlos.minc |
| Rafael Picciani | União | 44333 | Deferido | 20.885.976,57 | - |
| Luiz Paulo | PSD | 55678 | Deferido | 2.663.675,89 | luizpaulo_dep |

### Categoria B, candidatos novos de repercussão (3)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Inês Brasil | PSB | 40169 | Deferido | vazio | inesbrasil__tv |
| MC Smith | REDE | 18123 | Deferido | 390.600 | mcsmithoriginal |
| Conrado | DC | 27200 | Aguardando julgamento | vazio | conradooficial |

## Rio de Janeiro, deputado federal

### Categoria A, reeleição (9, incluindo Martha Rocha)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Chico Alencar | PSOL | 5050 | Deferido | 961.600 | chico.alencar |
| Talíria Petrone | PSOL | 5077 | Deferido | 25.000 | taliriapetrone |
| Tarcísio Motta | PSOL | 5000 | Deferido | 99.100 | tarcisiomottapsol |
| Jandira Feghali | PCdoB | 6565 | Aguardando julgamento | 406.383,70 | jandira_feghali |
| General Pazuello | PL | 2212 | Deferido | 1.135.737 | generalpazuello.oficial |
| Sóstenes Cavalcante | PL | 2277 | Deferido | 600.000 | sostenescavalcante |
| Altineu Cortes | PL | 2269 | Deferido | 2.319.487,82 | altineucortesrj |
| Soraya Santos | PL | 2222 | Deferido | 34.587,61 | dep.sorayasantos |
| Martha Rocha (nome de urna: Delegada Martha Rocha) | PDT | 1240 | Deferido | 3.173.307,78 | delmartharocha |

### Categoria B, candidatos novos de repercussão (9, confirmados)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Marcelo Freixo | PT | 1331 | Aguardando julgamento | 719.857,67 | marcelofreixo |
| Thiago Gagliasso | PL | 2227 | Deferido | 54.000 | thigagliasso |
| Benny Briolly | PT | 1350 | Aguardando julgamento | 10.000 | bennybriolly |
| Antonia Fontenelle | PSDB | 4540 | Aguardando julgamento | 25.000 | canalnalataco |
| Edmundo Souza | PSDB | 4510 | Aguardando julgamento | 16.059.865,50 | edmundosouza10 |
| Humberto Martins | DC | 2707 | Aguardando julgamento | 3.609.173,69 | humbertomartins.oficial |
| Andréa Sorvetão | DC | 2720 | Aguardando julgamento | 144.932 | andreasorvetaooficial |
| Cristina Mel | PSDB | 4553 | Deferido | 2.352.360 | cristinamelreal |
| MC Darlan (nome de urna: Darlan Praxedes) | PSB | 4087 | Deferido | vazio | mcdarlanoficial |

Não confirmados no TSE, fora da lista: Gracyanne Barbosa, José de Abreu. Val
Marchiori saiu desta lista porque concorre por SP, não pelo RJ; ver a tabela
de São Paulo abaixo.

## São Paulo, deputado estadual (Alesp)

### Categoria A, reeleição (11)

| Nome | Partido (TSE) | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Ana Carolina Serra | PSDB | 45045 | Deferido | 2.394.020,49 | anacarolinaserra |
| Carla Morando | PSD | 55155 | Deferido | 7.545.793,96 | deputadacarlamorando |
| Thiago Auricchio | PL | 22343 | Deferido | 5.684.784,72 | thiagoauricchio_ |
| Oseias de Madureira | PL | 22223 | Deferido | 1.297.819,27 | pr_oseiasdemadureira |
| Luiz Fernando Teixeira | PT | 13134 | Deferido | 7.223.757,80 | luizfernandopt13 |
| Teonilio Barba (nome de urna: Barba) | PT | 13110 | Deferido | 718.178,87 | teonilio_barba |
| Rômulo Fernandes | PT | 13789 | Deferido | 499.788 | 13romulofernandes |
| Ediane Maria | PSOL | 50110 | Deferido | 20.393,73 | edianemariamtst |
| Itamar Borges | MDB | 15300 | Deferido | 6.588.140,76 | itamar.borges |
| Capitão Telhada | PP | 11190 | Deferido | 1.904.059,35 | capitaotelhada |
| Valéria Bolsonaro | PL | 22922 | Deferido | 157.826,27 | bolsonarovaleria |

### Categoria B, candidatos novos de repercussão (2)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Paulo Kogos | PL | 22038 | Deferido | 254.347,81 | opropriokogos |
| Marcelo Bolsonaro | PL | 22202 | Deferido | 356.231,53 | dr.marcelobolsonaro |

## São Paulo, deputado federal

### Categoria A, reeleição (7)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Marco Feliciano | PL | 2270 | Deferido | 5.402.023 | marcofeliciano |
| Erika Hilton | PSOL | 5070 | Deferido | 15.975,73 | hilton_erika |
| Sâmia Bomfim | PSOL | 5000 | Deferido | 498.640,73 | timesamia5000 |
| Rosana Valle | PL | 2227 | Deferido | 2.295.059 | rosanavalleoficial |
| Kim Kataguiri | MISSÃO | 1414 | Deferido | 1.109.702,79 | kimkataguiri |
| Baleia Rossi | MDB | 1515 | Deferido | 1.506.200,57 | baleia.rossi |
| Renata Abreu | Podemos | 2020 | Deferido | 4.758.519,62 | renataabreu.2020 |

### Categoria B, candidatos novos de repercussão (12)

| Nome | Partido | Número | Situação TSE | Bens declarados | Instagram |
|---|---|---|---|---|---|
| Jean Wyllys | PT | 1350 | Deferido | 250.000 | jeanwyllys_real |
| Lucas Penteado | PT | 1303 | Deferido | 1.200 | lucaskokapenteado |
| Adrilles Jorge | União | 4401 | Deferido | 542.495,69 | adrillesjorge |
| Renato Bolsonaro | PL | 2222 | Deferido | 3.327.848,02 | renatobolsonaro |
| Lucas Pavanato | PL | 2211 | Deferido | 43.661,77 | lucaspavanato |
| Rachel Sheherazade | PSD | 5560 | Deferido | 140.293,01 | rachelsherazade |
| Silvia Abravanel | PSD | 5590 | Deferido | 47.546.965,91 | silviaabravanel |
| Geraldo Luís | Avante | 7077 | Deferido | 7.212.252,79 | geraldoluistv |
| Manoel Gomes | Avante | 7030 | Deferido | vazio | manoelgomesbr |
| Thiago dos Reis | PT | 1399 | Deferido | 1.600.000 | thiagoresiste |
| MC Gui | PSD | 5544 | Deferido | 1.190.301,10 | mcgui |
| Luís Fabiano | MDB | 1509 | Deferido | 20.103.841,12 | luisfabianooficial |
| Val Marchiori (movida da varredura do RJ, ver correção acima) | Republicanos | 1077 | Deferido | 1.317.778,60 | valmarchiori |

## Pendências (resolvidas em 9/9/2026)

`candidatos-deputados.csv` já existe, gerado por
`dados/rjsp/_gerar_candidatos_deputados.py` a partir da lista confirmada
acima: 75 candidaturas (RJ estadual 24, RJ federal 18, SP estadual 13, SP
federal 20). Sem resposta do Francisco sobre as duas pendências abertas,
segui por decisão própria: Val Marchiori entrou na lista de São Paulo como
categoria B (já refletida na tabela acima); Gracyanne Barbosa e José de
Abreu ficaram de fora por não aparecerem em nenhuma das 4.538 candidaturas
do TSE. Se o Francisco quiser reverter algum dos dois, é só falar.

Próximos passos represados: coletar Instagram/seguidores só para esse
grupo de 75 (o resto do TSE já está em `candidatos-rjsp.csv` sem
enriquecimento, por decisão do Francisco), e estender
`_template.html`/`_gerar_mural.py` para os dois cargos novos, restritos a
RJ e SP.
