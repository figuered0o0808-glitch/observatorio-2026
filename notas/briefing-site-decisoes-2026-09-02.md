# Briefing do "Painel Eleitoral 2026": o que entrou no mural e o que ficou de fora

Nota de decisão, 2 de setembro de 2026. O briefing (briefingsiteeleicoes2026.md) descreve um site completo de cobertura eleitoral, presidencial e estadual, com contas de usuário e apuração ao vivo. O mural é outra coisa: um painel analítico dos presidenciáveis, gerado a partir dos CSVs do observatório e publicado como página única. Cada item do briefing foi lido com essa régua.

## O que entrou (edição 7 do mural)

Termômetro da corrida. Virou "A régua da corrida", no topo da editoria de pesquisas: posição atual de cada candidato (média móvel de 7 dias, todos os institutos), posição de 30 dias atrás em círculo vazio, traço de movimento e seta quando a diferença passa de 1 ponto. Escala linear, sem reordenação por cor.

Perfil de candidato como dossiê. Cada ficha ganhou o botão "Abrir dossiê", que abre um diálogo com ficha do TSE (nome completo, nascimento, naturalidade, escolaridade, ocupação, bens, urna, chapa, situação, data da última atualização no TSE, links para a ficha, a foto oficial e o verbete), leitura da situação, últimas rodadas com rejeição, pesquisas por modo de coleta, redes com série de seguidores, buscas no Google, acessos à Wikipédia, cronologia do candidato e a lista de fontes. Cada dossiê tem link próprio (#dossie-nome) e botão "Copiar link".

Comparador. Seção "Lado a lado": dois ou três candidatos nos mesmos quinze critérios (pesquisas, busca e redes, ficha do TSE, cobertura), com fonte e data debaixo de cada número, barra proporcional entre os comparados e o melhor valor da linha em vermelho (o menor, no caso da rejeição).

Raio-x do patrimônio. Os treze candidatos numa régua logarítmica de bens declarados ao TSE, com os dois que declararam zero em faixa própria. Sem tabela.

Completude do dossiê. "Cobertura do dossiê: n de 10 fontes" em cada ficha e no dossiê, contando registro, bens, chapa, perfis, seguidores no ano, pesquisas nominais, rejeição, Trends, Wikipédia e eventos datados. Mede dado disponível, não mérito, exatamente como o briefing pede.

Página do usuário, sem conta. "Acompanhar" em cada ficha marca o candidato como "sob vigilância" só no navegador de quem marcou (localStorage): a lista aparece abaixo do lede, alimenta o comparador ("Usar os vigiados") e filtra a linha do tempo. Não há login, alertas nem notas privadas: a página não tem servidor.

Linha do tempo. Já era filtrável por candidato e categoria; ganhou o filtro "sob vigilância" e a cronologia por candidato dentro do dossiê.

Microcopy de redação. "Abrir dossiê", "Lado a lado", "Sob vigilância", "Nada apurado" nos estados vazios, carimbo de registro (deferido, aguardando julgamento, campanha restrita) no cabeçalho do dossiê. Usado com parcimônia, como o briefing recomenda.

Método visível. A seção "Fontes e ressalvas" virou "Método e fontes" e abriu com a cadência de atualização (8h e 20h de Brasília) e o que a cobertura do dossiê significa.

Acessibilidade e celular. Diálogo nativo com foco devolvido ao botão de origem e fechamento por Esc; nenhuma informação só por cor (setas e rótulos acompanham as cores); gráficos largos rolam dentro do próprio painel no celular em vez de encolher; corrigido um vazamento horizontal antigo na editoria de metodologia.

## O que ficou de fora, e por quê

Governos estaduais, mapa do Brasil como hub, seletor de estado. O observatório é dos presidenciáveis; não há dados estaduais coletados e a promessa do projeto é profundidade no nível nacional. Fica como possível fase 2, com pipeline próprio.

Identidade "dossiê investigativo" (serifada de jornal, paleta escura de base, texturas de papel, fotos em duotone). A identidade do mural foi decidida e lapidada nesta mesma semana: Archivo condensada e Source Sans 3, vermelho de editoria, temas claro e escuro. Trocar agora desfaria isso. Entraram só os elementos compatíveis: carimbos, voz de repórter e o tema escuro que já existia. Fotos oficiais do TSE ficaram pendentes porque o ambiente não consegue baixá-las (bloqueio de rede); os dossiês trazem o link para a foto.

Contas de usuário, alertas, notas privadas, histórico de leitura, notificações da noite da eleição. Exigem servidor e cadastro; o mural é uma página estática. O que dava para fazer sem conta (acompanhados por navegador e link por dossiê) foi feito.

Painel de apuração ao vivo e modo "big number" da noite. A página publicada não pode chamar o feed JSON do TSE (política de rede do artefato) e o pico de acesso da noite pede outra arquitetura. Se for construído, é um produto separado, com backend, como o próprio briefing recomenda.

Rastro do dinheiro (sankey de doações e gastos). O observatório ainda não coleta receitas e despesas de campanha; só o FEFC por partido. Entra quando a prestação de contas estiver no dataset.

Backend, API intermediária, três camadas. Não se aplica ao artefato; o equivalente aqui é o pipeline de CSVs, o gerador e a rodada agendada.

Neutralidade das cores de destaque. O briefing pede que a cor de destaque não coincida com a de partidos grandes. O vermelho de editoria vem da convenção de jornalismo (G1, CNN) pedida pelo Francisco e nunca é cor de série: Lula é azul nos gráficos, Flávio é laranja. Mantido, com a regra explícita na identidade.

## Pendências abertas por esta nota

Fotos oficiais do TSE em preto e branco nos dossiês, quando houver um caminho de download (navegador do Mac ou n8n). Receitas e despesas de campanha por candidato para o rastro do dinheiro. Decidir se a fase estadual existe e, se sim, quais estados entram primeiro.
