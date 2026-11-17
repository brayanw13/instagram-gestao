# LinkedIn: configuração (uma vez só)

O workflow **Publicar post do dia no LinkedIn** publica 1 post por dia no seu perfil pessoal, a partir de `agenda-linkedin.json`. O disparo está marcado para 06:07 de Brasília, com reserva às 09:37. Como o GitHub atrasa o horário, o post costuma sair entre 8h e 10h.

Enquanto o token não estiver configurado, o workflow só registra "LinkedIn ainda não configurado" e termina sem erro.

## 1. Criar o app no LinkedIn (uns 10 min)

1. Acesse https://www.linkedin.com/developers/apps e clique em **Create app**.
2. Preencha nome (ex.: `publicador-gestao`), logo e a **Página do LinkedIn** a que o app fica ligado. O LinkedIn exige uma Página de empresa. Se você ainda não tem a da Bcruz, crie uma antes (é grátis). Os posts continuam saindo no seu perfil pessoal.
3. Na aba **Settings** do app, clique em **Verify** ao lado da Página e aprove com o seu usuário (você é admin da Página).
4. Na aba **Products**, adicione os dois produtos (aprovação automática):
   - **Share on LinkedIn**
   - **Sign In with LinkedIn using OpenID Connect**
5. Na aba **Auth**, em **Authorized redirect URLs**, adicione:
   `https://www.linkedin.com/developers/tools/oauth/redirect`

## 2. Gerar o token (5 min, repetir a cada ~55 dias)

1. Abra https://www.linkedin.com/developers/tools/oauth/token-generator
2. Escolha o app, marque os escopos **openid**, **profile** e **w_member_social** e clique em **Request access token**.
3. Entre com a sua conta e autorize.
4. Copie o token. Ele vale **60 dias** e o LinkedIn não oferece renovação automática para apps como este.
5. Anote a data de vencimento: hoje + 59 dias, no formato AAAA-MM-DD.

## 3. Guardar no GitHub

No repositório: **Settings → Secrets and variables → Actions**

Aba **Secrets → New repository secret**:

| Nome | Valor |
|---|---|
| `LI_TOKEN` | o token do passo 2 |

Aba **Variables → New repository variable**:

| Nome | Valor |
|---|---|
| `LI_TOKEN_VENCE` | data de vencimento, ex.: `2027-01-15` |

Não cole o token em nenhum arquivo, issue ou chat.

## 4. Testar sem publicar

**Actions → Publicar post do dia no LinkedIn → Run workflow**, com modo `teste`. O log deve mostrar o seu nome, "Permissão de publicação OK" e "arquivo e texto OK". Nada é publicado.

## Rotina

- **Renovação do token:** a partir de 7 dias antes do vencimento, o workflow publica normalmente e depois termina com erro de propósito. O GitHub te manda e-mail. Repita o passo 2 e atualize `LI_TOKEN` e `LI_TOKEN_VENCE`.
- **Primeira hora:** o post sai entre 8h e 10h. Responda os comentários logo depois de ele sair. No LinkedIn é isso que mais pesa no alcance.
- **Falhou um dia:** **Run workflow** com modo `publicar` e a data.
- **Novo ciclo:** rode o `render_linkedin.py` e depois `scripts/montar_agenda_linkedin.py` (veja o README).
- **Mudar horário:** edite o `cron` em `.github/workflows/publicar-linkedin.yml` (horário em UTC = Brasília + 3h).
- **Pausar:** **Actions → Publicar post do dia no LinkedIn → ⋯ → Disable workflow**.
