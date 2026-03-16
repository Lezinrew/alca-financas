# 🔐 Configurar Google OAuth para Alça Finanças

Este guia explica como configurar a autenticação OAuth do Google para permitir que usuários façam login usando suas contas do Google.

## 📋 Pré-requisitos

- Conta Google (Gmail)
- Acesso ao Google Cloud Console
- Domínio da aplicação: `alcahub.cloud` (ou seu domínio de produção)

---

## 🚀 Passo a Passo Manual

### 1. Acessar Google Cloud Console

1. Acesse: https://console.cloud.google.com/
2. Faça login com sua conta Google
3. Se não tiver um projeto, clique em **"Selecionar projeto"** → **"NOVO PROJETO"**
4. Nome do projeto: `Alca Finanças` (ou outro nome de sua preferência)
5. Clique em **"CRIAR"**

### 2. Habilitar Google+ API / OAuth 2.0

1. No menu lateral, vá em **"APIs e Serviços"** → **"Biblioteca"**
2. Procure por **"Google+ API"** ou **"Identity Platform"**
3. Clique no resultado e depois em **"ATIVAR"**
   - **Nota**: O Google+ API foi descontinuado, mas ainda funciona. Alternativamente, use **"Identity Platform"** ou apenas configure OAuth diretamente.

### 3. Configurar Tela de Consentimento OAuth

1. No menu lateral, vá em **"APIs e Serviços"** → **"Tela de consentimento OAuth"**
2. Selecione **"Externo"** (ou "Interno" se tiver Google Workspace)
3. Clique em **"CRIAR"**
4. Preencha os campos obrigatórios:
   - **Nome do aplicativo**: `Alça Finanças`
   - **Email de suporte do usuário**: Seu email (ex: `lezinrew@gmail.com`)
   - **Email de contato do desenvolvedor**: Seu email
5. Clique em **"SALVAR E CONTINUAR"**
6. Na etapa **"Escopos"**, clique em **"SALVAR E CONTINUAR"** (sem adicionar escopos extras)
7. Na etapa **"Usuários de teste"**, adicione seu email se necessário, depois **"SALVAR E CONTINUAR"**
8. Na etapa **"Resumo"**, revise e clique em **"VOLTAR AO PAINEL"**

### 4. Criar Credenciais OAuth 2.0

1. No menu lateral, vá em **"APIs e Serviços"** → **"Credenciais"**
2. Clique em **"+ CRIAR CREDENCIAIS"** → **"ID do cliente OAuth"**
3. Selecione **"Aplicativo da Web"** como tipo de aplicativo
4. Preencha:
   - **Nome**: `Alca Finanças Web Client`
   - **URIs de redirecionamento autorizados**:
     ```
     https://alcahub.cloud/api/api/auth/google/callback
     https://alcahub.cloud/api/auth/google/callback
     http://localhost:8001/api/auth/google/callback
     ```
     - **Importante**: Adicione todas as URLs onde sua aplicação pode receber o callback do Google
5. Clique em **"CRIAR"**
6. **Copie e salve**:
   - **ID do cliente** (ex: `123456789-abcdefghijklmnop.apps.googleusercontent.com`)
   - **Segredo do cliente** (ex: `GOCSPX-abcdefghijklmnopqrstuvwxyz`)
   - ⚠️ **IMPORTANTE**: O segredo só aparece uma vez! Salve imediatamente.

### 5. Configurar no Backend

1. Acesse o servidor via SSH:
   ```bash
   ssh root@alcahub.cloud
   ```

2. Edite o arquivo `.env` do backend:
   ```bash
   nano /var/www/alca-financas/backend/.env
   ```

3. Adicione ou atualize as linhas:
   ```env
   GOOGLE_CLIENT_ID=seu-client-id-aqui.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=seu-client-secret-aqui
   ```

4. Salve o arquivo (Ctrl+O, Enter, Ctrl+X)

5. Reinicie o serviço:
   ```bash
   systemctl restart alca-financas
   ```

6. Verifique os logs para confirmar:
   ```bash
   journalctl -u alca-financas -f
   ```

### 6. Testar a Autenticação

1. Acesse: `https://alcahub.cloud/register` ou `https://alcahub.cloud/login`
2. Clique em **"Continuar com Google"**
3. Você deve ser redirecionado para a tela de login do Google
4. Após autorizar, deve retornar para a aplicação logado

---

## 🔍 Verificação e Troubleshooting

### Verificar se as credenciais estão configuradas

```bash
ssh root@alcahub.cloud
cat /var/www/alca-financas/backend/.env | grep GOOGLE
```

Deve mostrar:
```
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx
```

### Erros Comuns

#### "Missing required parameter: client_id"
- **Causa**: `GOOGLE_CLIENT_ID` não está definido ou está vazio no `.env`
- **Solução**: Verifique se as variáveis estão corretas no arquivo `.env` e reinicie o serviço

#### "redirect_uri_mismatch"
- **Causa**: A URL de callback não está autorizada no Google Cloud Console
- **Solução**: Adicione a URL exata (com `https://` e sem barra final) em **"URIs de redirecionamento autorizados"**

#### "Error 400: invalid_request"
- **Causa**: Geralmente `client_id` ou `client_secret` incorretos
- **Solução**: Verifique se copiou corretamente do Google Cloud Console

### Testar endpoint diretamente

```bash
curl -I https://alcahub.cloud/api/api/auth/google/login
```

Deve retornar `302 Found` com `Location` apontando para `accounts.google.com`.

---

## 📝 Notas Importantes

1. **Segurança**: Nunca commite o `.env` com as credenciais no Git
2. **Ambientes**: Configure credenciais diferentes para desenvolvimento e produção
3. **Limites**: O Google tem limites de requisições OAuth (geralmente muito altos para uso normal)
4. **Renovação**: O `client_secret` não expira, mas pode ser regenerado se necessário

---

## 🔄 Atualizar Credenciais

Se precisar regenerar o `client_secret`:

1. Acesse Google Cloud Console → **"Credenciais"**
2. Clique no ID do cliente OAuth
3. Clique em **"REGENERAR SEGREDO"**
4. Copie o novo segredo
5. Atualize no `.env` do servidor
6. Reinicie o serviço: `systemctl restart alca-financas`

---

## ✅ Checklist Final

- [ ] Projeto criado no Google Cloud Console
- [ ] Tela de consentimento OAuth configurada
- [ ] Credenciais OAuth 2.0 criadas
- [ ] URIs de redirecionamento adicionadas (produção + localhost)
- [ ] `GOOGLE_CLIENT_ID` configurado no `.env` do servidor
- [ ] `GOOGLE_CLIENT_SECRET` configurado no `.env` do servidor
- [ ] Serviço backend reiniciado
- [ ] Teste de login com Google funcionando

---

## 📚 Referências

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Flask OAuth with Authlib](https://docs.authlib.org/en/latest/client/flask.html)

