# Briefing: Painel Eleitoral 2026 (Presidencial + Governos Estaduais)

## 1. Resumo do projeto

Um site editorial e de dados sobre a corrida eleitoral de 2026 no Brasil, cobrindo a disputa presidencial e as disputas para governo estadual. O site acompanha a campanha do lançamento das candidaturas até a apuração final, combinando dados oficiais em tempo real com uma cobertura de perfil investigativo sobre cada candidato. A referência de identidade é o jornalismo investigativo (tipo dossiê, capa de revista de investigação, arquivo confidencial), não um painel institucional do tipo "gov.br".

O objetivo final deste documento é servir de briefing para evoluir um artefato já existente no Claude, então as seções abaixo estão organizadas para virar decisões de design e de produto diretas.

## 2. Público e objetivo

Público principal: pessoas politicamente engajadas que já acompanham eleição mas querem uma fonte central, rápida e visualmente melhor que os grandes portais de notícia. Público secundário: jornalistas, pesquisadores e curiosos que quiserem cruzar dados de candidatos (bens, doações, histórico) sem precisar garimpar o portal de dados abertos do TSE.

O site precisa responder três perguntas centrais para o usuário a qualquer momento: quem está na disputa, como cada um está indo na corrida (posição em pesquisas, tendência, dinheiro de campanha) e o que se sabe sobre cada um (biografia, patrimônio, processos, propostas).

## 3. Escopo eleitoral

Cobertura de dois níveis, com o usuário podendo alternar entre eles:

Presidencial: visão nacional única, todos os candidatos ao Palácio do Planalto.

Governos estaduais: um seletor de estado (mapa do Brasil ou dropdown) leva à disputa de governador daquele estado. Cada estado tem sua própria lista de candidatos, pesquisas e resultados.

Uma home unificada mostra um resumo dos dois níveis ao mesmo tempo (destaque presidencial + mapa do Brasil com a cor do candidato líder em cada estado), e a partir daí o usuário navega para o nível que interessa.

## 4. Identidade visual e tom

Direção escolhida: jornalismo investigativo sério. Pensar em capa de revista de investigação política, dossiê classificado, arquivo jornalístico, não em painel de governo nem em rede social. Alguns elementos concretos para guiar o design:

Paleta de base escura ou de "sala de redação à noite" (grafite, preto, off white), com uma cor de destaque forte e política (vermelho profundo, âmbar ou um azul frio) usada com moderação para dados críticos e alertas, nunca para tudo.

Tipografia com uma serifada de jornal para títulos e manchetes, e uma sans grotesca para dados e interface, criando contraste entre "reportagem" e "painel".

Texturas e motivos editoriais: linhas de corte de papel, carimbos tipo "confidencial" ou "apurado", marcas d'água sutis, números de página tipo dossiê, uso de sublinhado tipo caneta em destaques. Usar com parcimônia para não virar pastiche.

Fotografia de candidatos tratada de forma consistente (preferencialmente preto e branco ou duotone com a cor de destaque), para dar unidade visual mesmo com fotos de fontes diferentes.

Microcopy com voz de repórter investigativo: em vez de "Ver mais", algo como "Abrir dossiê"; em vez de "Comparar", "Colocar lado a lado"; em vez de "Favoritos", "Meus acompanhados" ou "Sob vigilância". Vale revisar todos os textos de interface com esse filtro.

## 5. Arquitetura do site

Home: resumo nacional, mapa do Brasil interativo, destaques do dia (fato novo, doação relevante, movimento nas pesquisas), atalho para presidencial e para escolher estado.

Página da corrida presidencial: lista de candidatos ordenada por posição nas pesquisas, com um "termômetro da corrida" no topo (ver seção 7) e feed cronológico de eventos da campanha.

Página da corrida estadual: mesma estrutura da presidencial, filtrada por estado, com contexto local (quem é o governador atual, coligações locais).

Perfil de candidato (dossiê individual): página densa por candidato com biografia, trajetória política, patrimônio declarado, doações e gastos de campanha, processos e pendências na Justiça Eleitoral, propostas de governo, presença e discurso nas redes, histórico de posição nas pesquisas ao longo do tempo, e notícias relacionadas.

Comparador: o usuário escolhe dois ou mais candidatos e vê um "frente a frente" nos mesmos critérios do dossiê (patrimônio, propostas por tema, histórico eleitoral).

Linha do tempo da campanha: feed cronológico geral, filtrável por candidato, estado ou tipo de evento (pesquisa nova, debate, escândalo, prestação de contas, resultado).

Painel de apuração (ativado no dia da eleição): visão dedicada de resultados em tempo real, com percentual de urnas apuradas, votos por candidato, atualização automática e possibilidade de acompanhar só o que o usuário marcou como favorito.

Página do usuário: descrita em detalhe na seção 8.

Sobre e metodologia: página explicando fontes de dados, frequência de atualização e como a redação (ou o processo automatizado) verifica as informações. Importante para credibilidade em um site de pegada investigativa.

## 6. Dados em tempo real e fontes

O projeto tem duas fases de dados em tempo real, que pedem tratamento diferente.

Fase de campanha (a maior parte do tempo até a eleição): dados de candidaturas registradas, prestação de contas de campanha e pesquisas eleitorais registradas. A fonte oficial de candidaturas é o Portal de Dados Abertos do TSE, que já publica o conjunto "Candidatos 2026" com arquivos de candidatos, informações complementares, bens declarados, coligações, vagas por cargo, motivo de cassação quando houver, redes sociais informadas e fotos oficiais por estado (https://dadosabertos.tse.jus.br/dataset/candidatos-2026). Esses dados vêm em CSV grande por UF e pedem um pipeline de ingestão e cache próprio, não uma chamada direta do front-end a cada carregamento de página.

Fase de apuração (noite da eleição): o TSE distribui os resultados por arquivos JSON estruturados, atualizados continuamente durante a contagem, servidos por CDN, sem necessidade de cadastro prévio, mas com limite de 100 requisições por segundo por IP e bloqueio temporário em caso de excesso. Existem arquivos específicos para eleitos, configuração da eleição e resultados por município, estado e nível federal, além de arquivos de rastreamento que indicam quando um resultado mudou, o que permite fazer polling eficiente em vez de recarregar tudo o tempo todo (ver "Informações técnicas sobre a divulgação de resultados" no site do TSE). Essa é a fonte certa para o Painel de apuração da seção 5.

Pesquisas eleitorais (para o termômetro da corrida) não vêm do TSE, e sim de institutos de pesquisa registrados (Datafolha, Quaest, Genial/Quaest, Paraná Pesquisas, entre outros), cujo registro formal também passa pelo TSE. Vale prever no design uma forma de mostrar a média de pesquisas (tipo "poll of polls") em vez de só a pesquisa mais recente isolada, com transparência sobre metodologia, instituto e data de cada pesquisa usada.

Recomendação de arquitetura: um serviço de backend (ainda que simples) que busca e normaliza esses dados periodicamente e serve uma API própria e mais leve para o front-end, em vez do front-end consumir CSV do TSE ou o feed de apuração diretamente. Isso também é o que permite cache, checagem de qualidade dos dados e resiliência caso a fonte oficial fique fora do ar em um momento de pico (muito comum na noite da eleição).

## 7. Soluções criativas de visualização

O pedido explícito foi fugir de tabela e gráfico genérico. Algumas direções concretas:

Termômetro da corrida: em vez de só um gráfico de barras com porcentagem de pesquisa, uma visualização tipo régua ou corrida de fato (metáfora de pista, barômetro, ou "linha de largada e chegada") mostrando a posição relativa dos candidatos e a tendência (subindo, caindo, estável) com uma seta ou traço de movimento, não só o número atual.

Mapa do Brasil como hub central: o mapa não é só decoração na home, é navegação. Cor de cada estado reflete o candidato à frente na disputa estadual, e o presidencial pode ter uma camada separada (tipo alternância entre "mapa estadual" e "mapa de intenção presidencial por região").

Linha do tempo horizontal tipo "investigação em andamento": em vez de lista de notícias, uma trilha horizontal ou vertical com marcos (registro de candidatura, debates, pesquisas, escândalos, prestação de contas), com iconografia de dossiê (marcado, arquivado, sob apuração), que o usuário pode arrastar ou filtrar.

Dossiê financeiro como "rastro de dinheiro": visualização tipo fluxo (sankey ou similar) mostrando de onde vem o dinheiro de campanha e para onde vai, em vez de uma tabela crua de doações. Reforça a pegada investigativa e é naturalmente mais interessante que uma tabela.

Cartão de patrimônio como "raio-x": comparação visual do patrimônio declarado ao longo dos anos ou entre candidatos, com uma metáfora de "raio-x financeiro" (camadas, silhueta), não uma tabela de bens.

Modo "big number" para a noite da apuração: números grandes, tipográficos, quase de placar esportivo, com atualização ao vivo e uma pequena animação de pulso quando um número muda, para dar sensação de "ao vivo" sem depender de gráfico.

Cards de candidato com "nível de transparência" ou "completude do dossiê": um indicador visual (não nota de caráter moral, e sim de dado disponível) mostrando quanto da prestação de contas, patrimônio e processos está público e verificado, reforçando o tom investigativo sem parecer parcial.

## 8. Página de usuário

Sistema de conta simples (e-mail ou login social) com uma área pessoal chamada algo como "Meus acompanhados" ou "Minha investigação". Funcionalidades sugeridas:

Favoritar candidatos (presidencial e estaduais) para um feed personalizado só com eventos, pesquisas e notícias deles.

Acompanhar um estado específico como padrão, para quem só quer ver a disputa da própria região sem navegar toda vez.

Alertas configuráveis: nova pesquisa envolvendo um candidato favoritado, movimento relevante de posição, prestação de contas nova, dia da eleição com um resumo antes da apuração começar.

Comparador salvo: guardar um comparativo entre dois ou mais candidatos para voltar depois sem remontar.

Anotações pessoais privadas por candidato, tipo bloco de notas do usuário dentro do dossiê, útil para quem está decidindo o voto e quer registrar prós e contras.

Histórico de leitura ou "linha do tempo pessoal", mostrando o que o usuário já visitou e leu, ajudando a retomar de onde parou.

Modo compartilhamento: gerar uma imagem ou link de um comparativo, de um trecho do dossiê ou de um resultado da apuração para postar em rede social, mantendo a identidade visual do site (isso ajuda tanto engajamento quanto tráfego).

Preferência de notificação para a noite da eleição (push ou e-mail) avisando quando os candidatos favoritados tiverem resultado definido.

## 9. Requisitos de UX e usabilidade

Performance é requisito de produto, não só técnico, principalmente no painel de apuração, que vai ter pico de acesso concentrado em poucas horas.

Design responsivo com prioridade mobile, já que boa parte do consumo de notícia eleitoral acontece no celular, inclusive na própria noite da eleição.

Estados vazios e de carregamento tratados com a mesma identidade visual (nada de spinner genérico), reforçando a sensação de produto cuidado mesmo enquanto os dados carregam.

Acessibilidade básica cuidada desde o início: contraste adequado mesmo com a paleta escura, textos alternativos em gráficos e mapas, navegação por teclado, e nunca comunicar informação só por cor (por exemplo liderança em pesquisa não pode depender só da cor do partido).

Transparência de dados sempre visível: toda peça de dado (pesquisa, resultado, patrimônio) deve indicar fonte e data de atualização perto do próprio dado, não só numa página de metodologia separada.

Neutralidade visual entre candidatos: cores de destaque do site não podem coincidir com as cores oficiais dos maiores partidos, para não parecer favorecer ninguém sem querer.

## 10. Considerações técnicas

Separar claramente três camadas: ingestão de dados (jobs periódicos consumindo TSE e pesquisas), uma API própria intermediária, e o front-end. Isso protege o site de instabilidade das fontes oficiais e permite cache agressivo fora da janela de apuração.

Para a noite da eleição, prever um modo de operação diferente do resto do site: menos elementos decorativos, mais leveza de carregamento, e um fallback claro caso o feed do TSE fique instável (mensagem de "atualizando", não erro cru).

Modelar desde já um identificador único de candidato que funcione tanto para presidencial quanto para cada disputa estadual, já que o mesmo nome pode aparecer em contextos diferentes ou mudar de partido entre eleições.

Guardar histórico versionado de pesquisas e de posição na corrida ao longo do tempo, não só o dado mais recente, porque a tendência (subindo, caindo, estável) é uma das peças centrais pedidas na seção 7.

## 11. Próximos passos sugeridos

Definir com mais precisão a lista de estados cobertos na primeira versão (todos os 26 mais o Distrito Federal, ou um recorte inicial menor para lançar mais rápido).

Levar este briefing para a conversa onde o artefato atual do Claude será evoluído, priorizando primeiro a identidade visual e a página de perfil de candidato (dossiê), depois o comparador e o mapa, e só depois o painel de apuração ao vivo, que é o componente tecnicamente mais exigente.

Validar com uma reportagem de exemplo (um candidato real, com dados reais do TSE) se a estrutura de dossiê proposta na seção 5 realmente comporta o tipo de informação disponível, antes de generalizar para todos os candidatos.
