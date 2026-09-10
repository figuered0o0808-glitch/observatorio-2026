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
   (`https://figuered0o0808-glitch.github.io/observatorio-2026/`) e a mesma URL em
   *Redirect URLs*. Sem isso o link de recuperação de senha e o retorno do Google não voltam.

4. Em **Authentication > Email Templates**, traduza os dois emails que o usuário recebe
   (confirmação e recuperação). O padrão vem em inglês.

5. Em **Storage**, crie um bucket **privado** chamado `mural`. É onde a carga protegida vai
   morar. Enquanto ele não existir, a carga fica em `mural-completo.json` na raiz do site, que
   é público: funciona igual, mas sem a parte de "não está na página".

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

A conta é apagável pelo próprio usuário. Como isso é dado pessoal de brasileiro, a LGPD se
aplica: uma página de política de privacidade precisa existir antes da divulgação, dizendo o
que é guardado, para quê, por quanto tempo e como pedir exclusão. **Isso ainda não está
escrito**, e é o que falta para o cadastro poder ir ao ar.
