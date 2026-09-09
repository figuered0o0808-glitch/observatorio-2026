# Deputado federal e estadual: Rio de Janeiro e São Paulo

Pasta aberta em 7 de setembro de 2026, aplicando às proporcionais de RJ e SP o método já usado nas
disputas majoritárias (`dados/estados/`). Esta primeira carga cobre a ficha completa do TSE das
4.538 candidaturas. As coletas de rede, busca e verbete ainda não rodaram; ver "O que falta".

## Arquivo

| arquivo | linhas | conteúdo | origem |
|---|---|---|---|
| `candidatos-rjsp.csv` | 4.538 | ficha de cada candidatura a deputado federal e estadual em RJ e SP | DivulgaCandContas (TSE), listagem por disputa mais chamada de detalhe por candidatura, lidas no navegador do app em 7/9/2026 |

Contagem por disputa: RJ federal 791, RJ estadual 1.187, SP federal 1.130, SP estadual 1.430.

## Como foi obtido

Duas chamadas por disputa e uma por candidatura, todas na API pública do DivulgaCandContas, a partir
de uma aba aberta no próprio domínio do TSE, porque o contêiner do Claude não alcança o host (a
tentativa de `curl` volta com recusa do proxy de saída). O identificador da eleição de 2026 é
`20322002026`, o mesmo da presidencial; muda só a UF e o código do cargo (6 federal, 7 estadual).

O laço rodou com dez trabalhadores e 400 ms entre pedidos, cerca de treze chamadas por segundo,
4.538 detalhes em pouco menos de oito minutos, com zero erro. Os resultados ficaram em `window.__R`
e saíram em cinco fatias de até 900 linhas escritas no corpo da página e lidas com `get_page_text`,
que grava em arquivo no contêiner quando o resultado é grande. Fatia maior que isso é cortada em
torno de 260 mil caracteres sem aviso: a primeira tentativa, de uma vez só, perdeu 3.351 das 4.538
linhas em silêncio. Fatiar e conferir a marca `@@FIM` em cada pedaço é obrigatório.

## Duas armadilhas encontradas

**`sites` é vetor de strings, não de objetos.** A primeira passada leu `s.url` em cada item e
descartou todos os perfis, devolvendo 4.538 linhas com as colunas de rede vazias. O sintoma que
denunciou foi a combinação improvável de nenhuma rede com todas as fichas preenchidas. Refeita a
coleta, 3.539 candidaturas informaram Instagram.

**`gastoCampanha1T` não é gasto do candidato.** O campo tem apenas dois valores distintos nas 4.538
linhas: 3.176.572,53 para toda candidatura a federal e 1.270.629,01 para toda candidatura a
estadual. É o limite legal de gasto do primeiro turno por cargo, igual para todo mundo. A coluna
entrou como `limite_gasto_1t` e não deve ser lida como despesa. Gasto efetivo por candidatura sai na
prestação de contas, que é outra fonte.

## Colunas

`uf, cargo, id_tse, nome_urna, nome_completo, numero, partido, coligacao, composicao_coligacao,
situacao_tse, situacao_urna, totalizacao, eleicoes_anteriores, anos_anteriores, sexo, cor_raca,
nascimento, escolaridade, ocupacao, uf_nascimento, municipio_nascimento, bens_total, bens_qtd,
limite_gasto_1t, instagram, tiktok, youtube, x, facebook, site, atualizado_tse`

`situacao_tse` vem do detalhe, não da listagem: a listagem responde de um cache mais velho e
divergiu em dezenas de casos. `atualizado_tse` guarda o carimbo do próprio TSE para cada ficha.
`instagram`, `tiktok`, `x` e `facebook` guardam o identificador extraído da URL informada;
`youtube` e `site` guardam a URL inteira, porque o formato varia demais.

## O que não foi guardado

CPF e título de eleitor, que a API devolve. Também ficaram fora orientação sexual e identidade de
gênero, que vêm em `infoComplementar` e que o próprio TSE marca com um booleano de publicabilidade
por candidatura. `cor_raca` entrou por ser dado eleitoral oficial e público, de uso corrente na
análise de composição das chapas.

## Preenchimento

Instagram 3.539, Facebook 2.621, TikTok 1.558, YouTube 1.008, X 667. Já disputaram alguma eleição
anterior 3.146. Declararam bens 2.697. Situação: 3.540 deferidas, 859 aguardando julgamento, 74
renúncias, 49 indeferidas em prazo recursal ou com recurso, 11 indeferidas, 5 deferidas com recurso.

Célula vazia é indisponível, nunca zero: zeros de `totalDeBens`, de quantidade de bens e de
eleições anteriores foram convertidos em vazio, e a composição de coligação `**`, que o TSE usa
para partido isolado, também.

## O que falta

Seguidores no Instagram dos 3.508 identificadores distintos, que pelo ritmo do coletor de
`coleta/navegador_estados.md` (três a cinco segundos por perfil) são de três a quatro horas de
navegador. Google Trends e verbete na Wikipédia, que para proporcional rendem principalmente
homônimo e precisam de um grupo monitorado em vez da lista inteira. Eventos de campanha e pesquisas
por candidato, que praticamente não existem para proporcional. Prestação de contas, que é onde mora
o gasto efetivo. Nada disso entra no mural antes de existir.
