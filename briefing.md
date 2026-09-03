# Briefing: Observatório do capital político digital (Eleições 2026)

**Versão 4, 2/9/2026. Substitui a versão 3 do mesmo dia.** Preparado no chat do Claude para continuidade no Cowork. A mudança da versão 4: o escopo dos estados ganhou mapa geográfico, série completa de pesquisas de 2026 e busca e redes por candidato (seção 10), com os dados e os coletores descritos em `dados/estados/LEIA-ME.md` e `coleta/navegador_estados.md`.

---

## 1. O que é o projeto

Acompanhamento analítico do fenômeno Augusto Cury e, por comparação, de todos os presidenciáveis de 2026, como caso de estudo sobre a capacidade da internet de construir capital político. Nasceu da onda pós-debate da Band (23/8/2026).

A tese central, desenvolvida por Francisco e registrada no artigo `fenomeno-cury-artigo-v3.md`, é a do **escape categorial**: Cury não venceu a disputa pelo eleitor despolitizado, ele escapou da categoria que define a disputa. Ele não é lido como político, então apoiá-lo não é lido como ato político. Não é centro (ainda uma coordenada no eixo); ele está fora do plano onde o eixo existe.

O interesse do projeto não é a estratégia de crescimento do candidato (o fenômeno é orgânico), mas os efeitos: a relação com influenciadores, o perfil e o tamanho do eleitorado despolitizado, o que isso mostra sobre a internet construir capital político, e as implicações para as eleições proporcionais.

## 2. Arquivos que acompanham este briefing

- `fenomeno-cury-artigo-v3.md`: edição consolidada e vigente do artigo. Substitui v1 e v2. A última seção ("Nota de cenário") é de uso interno e deve ser removida em qualquer publicação.
- `fenomeno-cury-artigo-v1.md` e `fenomeno-cury-artigo-v2.md`: edições anteriores, guardar em subpasta de arquivo apenas como histórico.
- `notas-audios-2026-08-31.md`: transcrição dos seis áudios de 31/8 com as hipóteses de Francisco. Material bruto.

## 3. Produtos

1. **Dossiê vivo**: o artigo em edições numeradas e datadas. Uso interno em relatórios dos projetos eleitorais da INDICA e possível publicação no site (sem a seção interna).
2. **Dataset comparativo**: série diária de métricas de todos os presidenciáveis.
3. **Acervo de evidências**: prints e links datados de peças virais, declarações e eventos, antes que sumam.
4. **Fase futura**: plataforma aberta de acompanhamento (seção 9).

## 4. Escopo: candidatos

Todos os presidenciáveis com candidatura ativa. Documentados na cobertura até aqui: Lula (PT), Flávio Bolsonaro (PL), Augusto Cury (Avante, vice Júlio Delgado), Ronaldo Caiado (PSD), Romeu Zema (Novo), Renan Santos (Missão), Pablo Marçal (PRTB), Samara Martins.

**Primeira tarefa**: confirmar no DivulgaCandContas (TSE) a lista oficial, com partido, número e situação, e registrar os handles de cada um em Instagram, TikTok, YouTube, Kwai e X. Adicionar também as chapas do Avante para deputado federal e estadual nos principais estados (ver seção 8).

## 5. Estrutura de pastas

```
observatorio-2026/
  briefing.md (este arquivo)
  artigo/
    fenomeno-cury-artigo-v3.md
    arquivo/ (v1, v2)
  notas/
    notas-audios-2026-08-31.md
    varredura-2026-09-01.md
    perfil-disputa-2026-09-01.md
    briefing-site-eleicoes-2026.md
    briefing-site-decisoes-2026-09-02.md
    estados-metodo-2026-09-02.md
  dados/
    serie-diaria.csv
    pesquisas-registradas.csv
    trends-2026.csv
    wikipedia-pageviews.csv
    seguidores-historico-fontes.csv
    redes-fontes.csv
    eventos.csv
    candidatos.csv
    tse-presidenciaveis.csv
    partidos.csv
    avante-chapas.csv
    estados/
      LEIA-ME.md       (o que é cada arquivo, de onde veio, onde mora cada cópia)
      candidatos-estados.csv
      candidatos-detalhe.csv
      pesquisas-estados.csv
      pesquisas-estados-wiki.csv
      pesquisas-estados-consolidado.csv
      trends-estados.csv
      wikipedia-verbetes-estados.csv
      wikipedia-estados.csv
      instagram-estados.csv
      _parse_wiki.py, _consolidar_pesquisas.py, _integrar_busca.py
    geo/
      br-uf-paths.json (mapa do Brasil simplificado, gerado por _mapa_br.py)
  coleta/
    navegador_estados.md (roteiro dos coletores de navegador)
    tse_presidenciaveis.py, wikipedia_pageviews.py
  mural/
    _template.html   (fonte única da página: tokens, CSS, HTML e JS)
    _gerar_mural.py  (lê os CSVs, injeta o JSON no template)
    mural.html       (gerado; nunca editar à mão)
    logo/            (marca, assinatura, monograma, favicon, PNGs)
  evidencias/
    2026-08-23-debate-band/
    2026-08-27-videos-virais/
    2026-08-29-sabatina-globo/
  fontes.md
```

**`serie-diaria.csv`** (uma linha por candidato, plataforma e dia):
`data, candidato, plataforma, seguidores, variacao_dia, trends_indice, mencoes, fonte, url_fonte, observacao`

**`pesquisas-registradas.csv`**:
`instituto, data_campo_inicio, data_campo_fim, data_divulgacao, metodologia, cenario, candidato, percentual, rejeicao, margem_erro, registro_tse, url`

**`eventos.csv`** (linha do tempo qualitativa):
`data, evento, categoria (debate / entrevista / ataque / endosso / rito de reclassificacao / proposta), descricao, url`

**`avante-chapas.csv`**:
`uf, cargo, candidato, numero, situacao, seguidores_instagram, observacao`

## 6. Rotina

Snapshot diário no mesmo horário, acionado por uma frase ("atualiza o observatório"). O Claude deve: coletar os números do dia, comparar com o anterior, registrar nos CSVs, salvar evidências novas, anotar eventos. Semanalmente, um resumo comparativo curto. A cada pesquisa nova, atualizar `pesquisas-registradas.csv` com destaque para a **rejeição** de cada candidato, que é a variável central do acompanhamento (ver seção 8).

Áudios de Francisco com insights podem ser transcritos localmente com a skill /watch (faster-whisper já instalado), salvos em `notas/` e cruzados com o artigo.

## 7. Fontes gratuitas (usar primeiro)

- **Wikipédia**: API de pageviews pública, interface em pageviews.wmcloud.org. Acessos diários aos verbetes de todos os candidatos (proxy de descoberta). Monitorar o histórico de edições e a página de discussão do verbete do Cury: disputas de edição são marcador datado de tentativa de reclassificação.
- **Google Trends**: exportação manual de CSV comparando candidatos. Registrar as "pesquisas relacionadas" de cada um. Séries específicas a manter: "Augusto Cury é de esquerda ou direita", "propostas Augusto Cury", "como votar", "eleições 2026" (teste de transbordamento).
- **YouTube Data API**: gratuita, chave via Google Cloud, nó nativo no n8n. Views, likes e comentários dos grandes cortes e dos canais oficiais.
- **Social Blade**: histórico diário de seguidores por perfil, páginas públicas.
- **Biblioteca de Anúncios da Meta**: gasto em anúncio político por página, API gratuita. Comparar o gasto da campanha Cury com os demais durante a onda (teste documental da tese orgânica).
- **TSE / DivulgaCandContas**: candidaturas, bens, fundo recebido, prestação parcial de contas (setembro), gastos com impulsionamento.
- **Agregadores de pesquisas**: Poder360 e BBC News Brasil.
- **Retratos da Leitura no Brasil (Instituto Pró-Livro)**: fonte para testar a hipótese de que autoajuda está entre os gêneros mais lidos pelos jovens (seção 8).
- **PublishNews**: ranking de livros mais vendidos; se os livros do Cury voltarem às listas, a onda transborda para o domínio editorial.
- **Kwai**: sem API. Registro manual semanal dos vídeos mais vistos por candidato.

## 8. Hipóteses e variáveis em acompanhamento

Estas são as questões abertas do artigo, traduzidas em tarefas.

**Duração e reclassificação (variável central).** A rejeição de Cury na AtlasIntel de 31/8 é 18,5% (Flávio 52,7%, Lula 52%, Renan 43,1%, Zema 33,9%, Caiado 28,5%), com imagem 34% positiva e 30% negativa. Rejeitar exige classificar; a curva de rejeição, rodada a rodada, é o que dirá se e quando o sistema consegue localizá-lo no eixo. Registrar em toda pesquisa. Cruzar com eventos: sabatinas, ataques, horário eleitoral, debates.

**Transbordamento.** Se o interesse for além do nome, buscas adjacentes (propostas, como votar, outros candidatos, eleições 2026) sobem junto com a curva dele. Se não subirem, o voto segue acontecendo fora da política. Série semanal no Trends.

**Familiaridade prévia sem classificação política.** Duas hipóteses de Francisco (notas de 31/8) para explicar o voto jovem sem base leitora tradicional (0,3% acima de 60 anos): (a) familiaridade doméstica, sobretudo em famílias evangélicas e de menor renda; (b) o ecossistema jovem de autoajuda e empreendedorismo no TikTok, em que Cury é o principal nome brasileiro. Testar com: recorte religioso e de renda das próximas pesquisas; dado de leitura por gênero e faixa etária (Pró-Livro); levantamento de conteúdo sobre Cury nesse circuito no TikTok anterior a 23/8.

**A premissa do cotidiano.** O campo progressista consolidou a leitura de que alcançar esse eleitorado exige conectar a comunicação aos problemas cotidianos. O caso sugere que talvez não seja verdade, ou não seja a via mais eficaz. Registrar como hipótese aberta; não converter em sentença. Renan Santos serve de grupo de controle (mesmo palco, mesmo crescimento de rede, 43,1% de rejeição, atua de dentro da política).

**O retorno do outsider.** Após 2022 consolidou-se a leitura de que o eleitorado preferia o perfil gestor. Hipótese: leitura precipitada; o que mudou foi o tipo de outsider aceito (registro paternal, não beligerante). Acompanhar como os demais candidatos reagem e se algum tenta ocupar registro parecido.

**Avante.** Com 8 a 11% na presidencial, a puxada nas chapas estaduais deixou de ser hipótese. Mapear as chapas (`avante-chapas.csv`) e acompanhar pesquisas para a Câmara onde existirem.

**Nota de cenário (interno).** Monitorar qualquer sinal de aproximação da candidatura com estruturas profissionais de campanha, quadros econômicos ou financiadores relevantes. Isso mudaria a natureza do fenômeno. Registrar em `eventos.csv` com categoria própria.

## 9. APIs e serviços pagos a avaliar

Verificar preços antes de contratar. Prioridade:
- **Apify**: coletores prontos de Instagram, TikTok, YouTube e X, pagos por uso, integráveis ao n8n via webhook. Melhor ponto de partida.
- **Vox Radar ou Sólon**: escuta social nacional; são as duas plataformas que a imprensa está usando nos números do caso, o que alinha o projeto à régua do mercado.
- **Palver**: monitoramento de grupos públicos de WhatsApp e Telegram. Para o eleitorado despolitizado, possivelmente a fonte mais valiosa e menos observada.
- **SerpApi ou Glimpse**: Google Trends programático.
- **HypeAuditor ou Modash**: qualificar os influenciadores que endossam cada candidato (audiência real, autenticidade, demografia) e checar acusações de inflação artificial.
- **Data365 / Bright Data / Social Blade API**: robustez para a fase plataforma.
- **Meta Content Library e TikTok Research API**: gratuitas mediante credenciamento de pesquisa; avaliar via INDICA.OSC.
- Ressalva: coleta de Instagram por terceiros opera em zona cinzenta dos termos da Meta. Para a plataforma aberta, priorizar fontes oficiais.

## 10. A plataforma: Mural dos Candidatos

Deixou de ser fase futura. O painel público existe, chama-se **Mural dos Candidatos** e é publicado como artefato no claude.ai, privado até Francisco decidir compartilhar. Assinatura editorial: "Observatório do capital político digital, Eleições 2026", desenvolvido pela INDICA.

**Como se constrói.** Os CSVs de `dados/` e `dados/estados/` são lidos por `mural/_gerar_mural.py`, que injeta um único blob JSON no marcador `/*__DATA__*/` de `mural/_template.html` e escreve `mural/mural.html`. O `mural.html` é artefato de saída e nunca deve ser editado à mão: toda mudança de conteúdo entra pelos CSVs, toda mudança de página entra pelo template.

**Dois escopos.** Um botão no cabeçalho troca entre Presidência e Estados.

No escopo Presidência, oito editorias: visão geral (com contagem regressiva para 4 de outubro, alertas do dia e placar), pesquisas do ano separadas por instituto e por modo de coleta, busca e redes (Google Trends, Wikipédia, seguidores), candidatos com dossiê individual, lado a lado, partidos, linha do tempo com calendário, e método.

No escopo Estados, as oito mesmas editorias para cada uma das 27 unidades da federação, escolhidas por um seletor ou por um mapa geográfico do Brasil colorido pelo partido do candidato à frente na disputa escolhida (governo ou Senado, com hachura para empate técnico). Base: 510 candidaturas a governo e Senado do TSE DivulgaCandContas, com ficha de detalhe (bens, vice ou suplentes, coligação oficial, redes informadas, eleições anteriores); a série completa de pesquisas de 2026 compilada pela Wikipédia e casada com as 52 fichas registradas no TSE da Gazeta do Povo (1.099 rodadas de primeiro turno, 397 confrontos de segundo turno); Google Trends dentro de cada estado, verbete e acessos na Wikipédia e seguidores no Instagram para todas as candidaturas. O método, as decisões de leitura do Senado (duas vagas, empate na linha de corte, empate técnico pela margem declarada) e a lista do que ainda falta estão em `notas/estados-metodo-2026-09-02.md`; os coletores, em `coleta/navegador_estados.md`.

**Personalização.** Tema claro, escuro ou do sistema; densidade; candidatos em foco; janela temporal; marcos ligados ou desligados. Tudo guardado em `localStorage` sob a chave `mural.prefs`, por leitor, no navegador dele.

**Rotas.** `#pesquisas` e demais abas nacionais; `#uf-CE` abre um estado; `#uf-CE-pesquisas` abre o estado numa aba; `#dossie-<slug>` abre a ficha de um presidenciável.

**O que falta na plataforma.** Logo da INDICA em arquivo (o crédito hoje é tipográfico); fotos dos candidatos, que o TSE serve por URL conhecida mas a página publicada não pode carregar; série diária de seguidores e de Trends para os estados na rotina das 8h e das 20h (precisa do Mac online); TikTok e YouTube por candidato estadual; eventos de campanha por estado. Decisões ainda abertas: marca definitiva (INDICA ou OSC), hospedagem própria e licenciamento das fontes para exibição pública.

## 11. Linha de base de dados (até 31/8)

Migrar para os CSVs no primeiro dia.

**Debate Band (23/8)**: média 1,9 ponto, pico 2,9, o mais esvaziado desde 1989; entrevista do Lula na Record no mesmo horário, 5,4. Ausentes: Lula, Flávio, Zema. Cury chegou anunciando que não participaria, em protesto, e voltou atrás.

**Instagram, Cury**: ~8,3M pré-debate, crescendo ~5 mil/dia; 8,4M em 25/8; +600 mil em 26/8; +1M em 24h, 10M em 27/8; 10,3M em 28/8; ~10,7M em 30/8 e 31/8. Vox Radar: +1,55M entre 22 e 27/8 (+19,4%); 526 mil declarações espontâneas de voto em comentários no período. Campanha: 854 mil comentários entre 24 e 27/8, nega influenciadores pagos e inflação, 96% dos seguidores no Brasil.

**Ranking Instagram (27/8)**: Lula 14,9M; Marçal 13,9M; Flávio 11,3M; Cury 10,1M; Zema 3,5M; Renan Santos 2,4M; Caiado 2,2M.

**Crescimento pós-debate (Vox Radar)**: Cury +19,4%; Renan +18,8%; Flávio +0,5%; Zema +0,3%; Lula -0,04%.

**Google Trends, Cury**: 2,9 (média pré) → 49 (24/8) → 100 (noite de 26/8); +900% na semana. "Augusto Cury é de esquerda ou direita": >10 mil buscas, +~900% (27/8).

**Menções**: 13.869 (23/8) → 20.193 (26/8).

**Vídeos de referência**: Yuri Meirelles, 12M+ views, 1M+ likes; Raphael Soares, 1M+ likes (27 a 28/8). Salvar com urgência.

**Pesquisas pré-onda**: agregador BBC até 21/8: Cury 1%, Lula 39%, Flávio 35%, Caiado 5%. Datafolha 21/8: Cury 2%. BTG/Nexus (rodada anterior): Cury 2%.

**Pesquisas pós-onda (31/8)**:
- AtlasIntel/Bloomberg (BR-07972/2026, campo 25 a 30/8, n=5.014, digital): Lula 43,4 / Flávio 33,7 / Cury 7,8 / Renan 7,6 / Zema 1,0 / Samara 0,9. Variações vs. julho: Cury +6,2; Flávio -2,1; Lula -1,5; Zema -1,8; Samara -1,2. Cury por faixa etária: 16 a 24, 12,1%; 25 a 34, 19,8%; 35 a 44, 9,1%; 45 a 59, 2,6%; 60+, 0,3%. Lula entre 16 e 24 anos: de 36,8% para 17,2%. Rejeição: ver seção 8. Segundo turno Lula 47,1 x Flávio 42,6; brancos/nulos de 7,9% para 10,3%.
- BTG/Nexus (BR-08900/2026, 12ª rodada, campo 28 a 30/8, n=2.005, telefone): Lula 39 / Flávio 33 / Cury 11 / Caiado 5 / Renan 3 / Zema 1; brancos, nulos e nenhum de 5% para 3%. Cury era 2% na rodada anterior.

**Eventos**: horário eleitoral começou em 28/8; sabatina do Cury na Globo em 29/8 (avaliação preliminar: momento mais difícil dele até aqui, sobretudo a análise dos comentaristas na sequência; Nexus com campo até 30/8 não capturou queda); adversários levantam suspeita de crescimento artificial (27 a 28/8).

**Candidato**: 67 anos, psiquiatra e escritor, 40M+ livros vendidos, patrimônio declarado de R$ 242 milhões, primeira eleição, sem estrutura profissional de campanha visível.

## 12. Estilo

Nunca usar travessões nem marcações típicas de texto de IA. Registro analítico, hipóteses marcadas como hipóteses, sem julgamento das propostas dos candidatos, sem nomes de organizações financiadoras, sem menção a clientes da INDICA. Nenhum número entra no dataset sem data e fonte.
