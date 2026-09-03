"""Gera tse-presidenciaveis.csv a partir dos dados coletados via WebFetch
na API DivulgaCandContas (eleicao 20322002026, cargo 1) em 2026-09-01.
O host divulgacandcontas.tse.jus.br esta bloqueado para requests neste
ambiente (403 no CONNECT do proxy); os dados abaixo foram transcritos das
respostas JSON obtidas com a ferramenta WebFetch."""
import csv

BASE = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/buscar/2026/BR/20322002026/candidato/"
cols = ["id_tse", "nome_completo", "nome_urna", "numero", "partido", "situacao_candidatura",
        "totalizacao", "coligacao", "composicao_coligacao", "ocupacao", "total_bens_reais",
        "ultima_atualizacao_tse", "vice_nome_completo", "vice_nome_urna", "vice_partido",
        "vice_situacao", "fonte", "url_fonte"]
rows = [
 ("280002542548","LUIZ INÁCIO LULA DA SILVA","LULA",13,"PT","Aguardando julgamento","Concorrendo","BRASIL PRONTO PRA MAIS","PSB / PDT / FEDERAÇÃO BRASIL DA ESPERANÇA - FE BRASIL(PT/PC do B/PV) / FEDERAÇÃO PSOL REDE(PSOL/REDE)","Torneiro Mecânico","4775650.64","2026-08-26 18:45","GERALDO JOSE RODRIGUES ALCKMIN FILHO","GERALDO ALCKMIN","PSB",""),
 ("280002551544","FLAVIO NANTES BOLSONARO","FLAVIO BOLSONARO",22,"PL","Aguardando julgamento","Concorrendo","PL","","Senador","8186555.83","2026-08-18 21:22","ALFREDO GASPAR DE MENDONÇA NETO","ALFREDO GASPAR","PL","Concorrendo"),
 ("280002551547","AUGUSTO JORGE CURY","ESCRITOR AUGUSTO CURY",70,"AVANTE","Aguardando julgamento","Concorrendo","BRASIL DOS NOSSOS SONHOS","AGIR / AVANTE","Escritor e Crítico","242281162.52","2026-08-29 20:25","JULIO CESAR DELGADO","JÚLIO DELGADO","AVANTE","Concorrendo"),
 ("280002551932","RONALDO RAMOS CAIADO","RONALDO CAIADO",55,"PSD","Deferido","Concorrendo","PSD","","Médico","52557930.98","2026-08-26 19:56","GILBERTO KASSAB","GILBERTO KASSAB","PSD",""),
 ("280002539826","ROMEU ZEMA NETO","ZEMA",30,"NOVO","Aguardando julgamento","Concorrendo","NOVO","","Empresário","178707610.09","2026-08-18 21:22","LUIS EDUARDO GRANGEIRO GIRÃO","EDUARDO GIRÃO","NOVO",""),
 ("280002540694","RENAN ANTONIO FERREIRA DOS SANTOS","RENAN SANTOS",14,"MISSÃO","Aguardando julgamento","Concorrendo","MISSÃO","","Empresário","795089","2026-08-27 19:48","AROLDO MEDINA","CORONEL MEDINA","MISSÃO",""),
 ("280002553884","PABLO HENRIQUE COSTA MARCAL","PABLO MARÇAL",28,"PRTB","Aguardando julgamento","Concorrendo","PRTB","","Diretor de Empresas","149986151.74","2026-08-24 14:24","LEONARDO ALVES DE ARAUJO","LEONARDO AVALANCHE","PRTB","Concorrendo"),
 ("280002538811","SAMARA MARTINS DA SILVA FEITOSA","SAMARA",80,"UP","Aguardando julgamento","Concorrendo","UP","","Odontólogo","33000","2026-08-18 21:22","RAQUEL NONATO DE BRICIO","RAQUEL BRÍCIO","UP",""),
 ("280002552484","CLARIANA ZACARKIM BARAO","CLARIANA BARAO",27,"DC","Aguardando julgamento","Concorrendo","DC","","Advogado","1820760.17","2026-08-19 13:52","FABIANA CRISTINA TAVARES TORQUATO","FABIANA TORQUATO","DC",""),
 ("280002551975","EDMILSON SILVA COSTA","EDMILSON COSTA",21,"PCB","Aguardando julgamento","Concorrendo","PCB","","Aposentado (Exceto Servidor Público)","454485.68","2026-08-18 21:22","CLEUSA DOS SANTOS","CLEUSA SANTOS","PCB","Concorrendo"),
 ("280002541457","HERTZ DA CONCEICAO DIAS","HERTZ DIAS",16,"PSTU","Aguardando julgamento","Concorrendo","PSTU","","Professor de Ensino Fundamental","0","2026-08-18 21:22","VANESSA PORTUGAL BARBOSA","VANESSA PORTUGAL","PSTU",""),
 ("280002552487","RUI COSTA PIMENTA","RUI COSTA PIMENTA",29,"PCO","Deferido","Concorrendo","PCO","","Jornalista e Redator","0","2026-08-26 19:54","ANTONIO CARLOS SILVA","ANTÔNIO CARLOS","PCO",""),
 ("280002548139","WILSON GRASSI JUNIOR","VETERINÁRIO WILSON GRASSI",35,"DEMOCRATA","Aguardando julgamento","Concorrendo","DEMOCRATA","","Veterinário","50000000","2026-08-20 16:45","SUÊD HAIDAR NOGUEIRA","SUÊD HAIDAR","DEMOCRATA",""),
]
with open("/home/claude/api-tests/tse-presidenciaveis.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for r in rows:
        w.writerow(list(r) + ["TSE DivulgaCandContas (coleta 2026-09-01)", BASE + r[0]])
print("ok", len(rows))
