# Observatório do capital político digital, Eleições 2026

Acompanhamento de dados públicos da disputa presidencial e das disputas
estaduais (governador e senador) nas eleições de 2026: candidaturas
registradas no TSE, pesquisas eleitorais com ficha técnica, seguidores e
buscas, eventos de campanha, dados partidários. O produto é o **Mural dos
Candidatos**, uma página HTML gerada a partir dos CSVs desta pasta.

Para as regras de conteúdo, as convenções do dataset e o histórico de
decisões de cada edição, ver `briefing.md`, `fontes.md` e `notas/`. Para
trabalhar neste repositório com o Claude Code, ver `CLAUDE.md`.

## Regenerar o mural

```bash
python3 dados/estados/_consolidar_pesquisas.py
python3 mural/_gerar_mural.py
```

Abra `mural/mural.html` num navegador.

## Verificar antes de publicar

```bash
pip install -r requirements.txt --break-system-packages   # uma vez
playwright install chromium                                # uma vez
./testes/verificar.sh
```

## Estrutura

```
briefing.md, fontes.md      regras editoriais e convenções do dataset
notas/                       varreduras de notícias, uma por data
artigo/                      o acompanhamento analítico em texto corrido
coleta/                      roteiros e scripts de coleta
dados/                       CSVs nacionais (13 presidenciáveis)
dados/estados/                CSVs estaduais (27 estados, 510 candidaturas)
dados/geo/                   mapa do Brasil simplificado (GeoJSON)
mural/_template.html         fonte do mural
mural/_gerar_mural.py        gera mural/mural.html a partir dos CSVs
mural/mural.html              o mural gerado, publicado como página no Claude
mural/logo/                  marca "Apuração"
testes/                      verificação automatizada do mural
evidencias/                  capturas de tela e vídeo por data/evento
```
