# Marca do Mural dos Candidatos

Marca tipográfica "Apuração", lapidada em 1/9/2026 e renomeada em 2/9/2026 (o subtítulo passou de "dos Presidenciáveis" para "dos Candidatos"). A palavra MURAL em Archivo (largura 72, peso 900) convertida em contorno vetorial; o filete vermelho que corre sob a palavra continua depois do L e sobe como uma curva de intenção de voto até o ponto da última rodada. Todos os arquivos saem das mesmas medidas, em unidades da fonte (1000 por eme, caixa alta 686): filete e curva de 110, a 66 da linha de base; curva de quatro segmentos (150 plano, sobe 290, recua 75, dispara até o topo); ponto de 230 tangente à caixa alta com overshoot de 12; subtítulo em Archivo largura 80, peso 700, caixa alta a 15,5% da palavra, 150 abaixo do filete, entreletras 0,30 em; área de proteção de meia caixa alta em volta.

Cores: tinta #14161A e vermelho de editoria #C8102E sobre papel #F5F5F2; sobre fundo escuro (#14161A ou #0F1013) a palavra vai para #F1F1EF e o vermelho para #FF5163. O vermelho é estrutura, nunca cor de série em gráfico.

## Arquivos

mural-assinatura.svg e mural-assinatura-escuro.svg: assinatura completa (palavra, curva e subtítulo "dos Candidatos"), versão para fundo claro e para fundo escuro. É a marca principal, para capas, cabeçalhos de relatório e cards.

mural-marca.svg e mural-marca-escuro.svg: só a palavra com a curva, sem subtítulo. É o que está no masthead do mural (lá o SVG usa as variáveis de cor da página e troca de tema sozinho; o subtítulo vai em texto ao lado).

mural-marca-preta.svg e mural-marca-branca.svg: uma cor só, para impressão em preto, carimbo, marca d'água ou sobre fotografia.

mural-monograma.svg (fundo escuro), mural-monograma-claro.svg (sem fundo) e mural-avatar.svg (círculo): o M com o filete e a curva encurtada, para avatar e marca d'água.

mural-icone.svg: M com subida única, para ícones de 32 a 64 px. mural-favicon.svg: M com o filete, para 16 px.

PNG prontos: mural-marca-2400.png e mural-assinatura-2400.png (fundo transparente), as versões escuras com fundo #14161A, mural-avatar-1000.png e mural-avatar-400.png (círculo escuro), mural-icone-512.png, mural-icone-192.png, mural-favicon-32.png e mural-favicon-16.png.

## Regras de uso

Não redesenhar a curva nem trocar sua proporção: é a mesma em toda aplicação. Não separar a curva da palavra (a exceção é o monograma, que a leva junto com o M). Largura mínima da marca sem subtítulo: 72 px; abaixo disso, monograma. Abaixo de 32 px, ícone ou favicon. Não aplicar sombra, contorno ou gradiente. Não usar o vermelho da marca como cor de candidato nos gráficos.

Os arquivos foram gerados pelos scripts em _scripts/ (marca.py, marca_final.py e gerar_assets.py; precisam de Python com fonttools, uharfbuzz e playwright) a partir da fonte Archivo do Google Fonts, licença OFL, baixada automaticamente na primeira execução. Para regenerar tudo: python3 _scripts/gerar_assets.py.

## Marca da INDICA (não é a marca do mural)

indica-marca.svg é a marca da agência, usada nas duas assinaturas de autoria
do mural ("Desenvolvido pela INDICA", no rodapé e no fim da editoria de
método). Não confundir com a marca "Apuração" acima, que é do produto.

Procedência: vetorizada do canal alpha de assets/img/logo-master-dark.png do
repositório indica-site (3228x968, fundo transparente), com o potrace. O PDF
INDICA_Strategic_Analysis.pdf não serve como fonte: a única imagem embutida
nele tem 375x112 e 450 bytes, e é o retângulo de fundo, não a marca.

O caminho é um só, sem cor fixa: no mural o SVG entra como <symbol> e as duas
assinaturas o referenciam com <use>, herdando `currentColor`. Por isso a marca
troca de tinta junto com o tema claro e escuro sem precisar de segunda versão,
e o arquivo pesa uma vez só na página.
