# A conta do mural: o que fazer no Supabase

A Visão geral da Presidência é aberta a todo mundo. O resto do mural pede cadastro. Este
documento é o passo a passo para ligar isso, e o registro do que a trava é e do que ela não é.

## O que a trava é, e o que não é

É real na página: a carga protegida (os 27 estados, deputados, busca, redes, rejeição e segundo
turno, uns 1,6 MB) **não está** no HTML público. Ela é baixada depois do login e guardada na
sessão do navegador. Quem abrir o código-fonte da página pública não acha esse dado.

Não é proteção do dado em si: **este repositório é público**. Os CSVs e o gerador estão nele, e
quem quiser refaz a carga inteira sozinho. Se a intenção passar a ser proteger o dado, o
repositório tem de virar privado, e aí o GitHub Pages para site público exige plano pago.

Enquanto as chaves não estiverem configuradas, o mural abre inteiro para todo mundo. Isso é de
propósito: variável de ambiente em branco não pode trancar o público do lado de fora.

## Passo a passo (uns dez minutos)

1. Em supabase.com, crie um projeto novo, separado de qualquer outro sistema. Região São Paulo.

2. Em **Authentication > Providers**, deixe ligado *Email* e ligue *Google*. Para o Google você
   precisa de um OAuth Client ID no Google Cloud, com esta URL de retorno:
   `https://<projeto>.supabase.co/auth/v1/callback`

3. Em **Authentication > URL Configuration**, ponha em *Site URL* o endereço do mural
   (`https://muraldoscandidatos.com/`) e a mesma URL em
   *Redirect URLs*. Sem isso o link de recuperação de senha e o retorno do Google não voltam.

4. Em **Authentication > Email Templates**, traduza os dois emails que o usuário recebe
   (confirmação e recuperação). O padrão vem em inglês.

5. Em **Storage**, crie um bucket **privado** chamado `mural`. É onde a carga protegida vai
   morar. Enquanto ele não existir, a carga fica em `mural-completo.json` na raiz do site, que
   é público: funciona igual, mas sem a parte de "não está na página".

   **Atenção:** hoje nenhum workflow envia a carga para o bucket. O mural regenera
   `mural-completo.json` a cada rodada, e quem serve esse arquivo é o próprio site. Se você
   apontar `MURAL_CARGA_URL` para `storage:` sem antes automatizar o envio, o bucket fica vazio
   ou com dado velho, e quem se cadastrar não recebe carga nenhuma. Comece com
   `MURAL_CARGA_URL` em branco; o envio automático é um passo a construir depois, e ele exige
   guardar a chave *service_role* nos segredos do GitHub, decisão que ainda não foi tomada.

6. Em **SQL Editor**, rode o conteúdo de `notas/conta-supabase.sql`.

7. Em **Project Settings > API**, copie *Project URL* e a chave *anon public*. No GitHub, em
   Settings > Secrets and variables > Actions, crie:
   - `MURAL_SUPABASE_URL`
   - `MURAL_SUPABASE_ANON`
   - `MURAL_CARGA_URL` com o valor `storage:mural/mural-completo.json` (ou deixe em branco para
     usar o arquivo público da raiz enquanto você testa)

   A chave *anon* é pública por definição: ela só serve para falar com o Supabase respeitando as
   regras de acesso por linha. A chave *service_role* **nunca** entra aqui nem no repositório.

8. Rode o workflow "Publicar o mural". A partir daí a página sai com a trava ligada.

## O que fica guardado de quem se cadastra

Email, e o nome e a área de trabalho se a pessoa preencher. Nada de CPF, título de eleitor ou
qualquer dado de voto, o que segue a mesma regra que já vale para os candidatos.

A conta é apagável pelo próprio usuário, de dentro do mural, pela função `apagar_minha_conta()`
(LGPD art. 18, VI).

Como isso é dado pessoal de brasileiro, a LGPD se aplica: a política de privacidade precisa
existir antes da divulgação, dizendo o que é guardado, para quê, por quanto tempo e como pedir
exclusão. **Isso já está pronto**: `privacidade.html` é gerada a cada publicação a partir de
`mural/_privacidade.html` e de `notas/organizacao.json`, que identifica o Instituto Democracia
e Sustentabilidade como controlador, com CNPJ, endereço, email e encarregado. Os dois workflows
se recusam a publicar se as chaves estiverem configuradas e a política ainda tiver campos por
preencher, então não há como o cadastro ir ao ar sem ela.
