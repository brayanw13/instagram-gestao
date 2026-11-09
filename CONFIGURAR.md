# Configuração (uma vez só)

Este repositório publica 1 post por dia no Instagram usando o GitHub Actions. O disparo está marcado para 07:17 de Brasília, com uma reserva às 11:47. O GitHub costuma atrasar algumas horas, então o post sai em horário variável, normalmente entre o fim da manhã e o começo da tarde.
Ele precisa ser **público**, porque o Instagram baixa as imagens pelo link público do GitHub.
O token fica guardado como *secret*, que não aparece no código nem nos logs.

## 1. Criar o app na Meta (uns 15 min)

1. Acesse https://developers.facebook.com, entre com o Facebook que administra a Página e vá em **Meus apps → Criar app**.
2. Caso de uso: escolha a opção de gerenciar conteúdo/mensagens do Instagram com **login do Facebook** (o nome muda de vez em quando; se não aparecer, escolha **Outro → Empresa**).
3. Dê um nome (ex.: `publicador-gestao`) e conclua. O app pode ficar em **modo de desenvolvimento**: como você é administrador dele, consegue publicar na própria conta.

## 2. Gerar o token que não expira (uns 10 min)

1. Abra o **Graph API Explorer**: https://developers.facebook.com/tools/explorer
2. À direita, selecione o seu app e clique em **Gerar token de acesso** (token de usuário), marcando as permissões:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
   Na janela do Facebook, autorize **a sua Página e a sua conta do Instagram**.
3. Copie o token, abra o **Depurador de token**: https://developers.facebook.com/tools/debug/accesstoken, cole, clique em **Depurar** e depois em **Estender token de acesso**. Copie o token longo gerado.
4. Volte ao Explorer, cole o token longo no campo de token e faça a consulta (GET):
   `me/accounts?fields=name,access_token,instagram_business_account`
5. Na resposta, na sua Página, copie:
   - `access_token` → este é o **IG_TOKEN** (token da Página)
   - `instagram_business_account.id` → este é o **IG_USER_ID**
6. Confira no Depurador que o `access_token` da Página mostra **Expira: Nunca**.

O token da Página deixa de valer se você trocar a senha do Facebook, remover o app ou se a Meta pedir uma verificação de segurança. Nesse caso, repita o passo 2.

## 3. Guardar no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**

| Nome | Valor |
|---|---|
| `IG_TOKEN` | o access_token da Página |
| `IG_USER_ID` | o id do instagram_business_account |

Não cole o token em nenhum arquivo, issue ou chat.

## 4. Testar sem publicar

**Actions → Publicar post do dia → Run workflow**, com modo `teste`. O log deve mostrar o seu @, o limite de publicação e "imagens acessíveis". Nada é publicado.

## Rotina

- Todo dia, o workflow publica o post daquela data em `agenda.json` e registra em `publicados.json`. Ele nunca publica o mesmo post duas vezes.
- Se algo falhar, o GitHub manda e-mail. Para publicar manualmente o post de um dia que falhou: **Run workflow** com modo `publicar` e a data.
- Para mudar o horário, edite o `cron` em `.github/workflows/publicar.yml`. O horário é em UTC: Brasília + 3 horas.
- Pausar: **Actions → Publicar post do dia → ⋯ → Disable workflow**.
