# 🔐 Guia de Configuração OAuth - Alça Finanças

Este guia explica como configurar login social (OAuth) com Google, Microsoft e Apple.

## 📋 Status Atual

- ✅ **Google OAuth**: Implementado (requer configuração)
- ⚠️ **Microsoft OAuth**: Não implementado (retorna erro 501)
- ⚠️ **Apple OAuth**: Não implementado (retorna erro 501)

---

## 🔵 Configurar Google OAuth

### 1. Criar Projeto no Google Cloud Console

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto ou selecione um existente
3. Vá para **APIs & Services** > **Credentials**
4. Clique em **Create Credentials** > **OAuth client ID**
5. Configure:
   - **Application type**: Web application
   - **Name**: Alça Finanças
   - **Authorized JavaScript origins**: 
     - `http://localhost:3000` (desenvolvimento)
     - `https://alcahub.cloud` (produção)
   - **Authorized redirect URIs**:
     - `http://localhost:3000/api/auth/google/callback` (desenvolvimento)
     - `https://alcahub.cloud/api/auth/google/callback` (produção)

### 2. Obter Credenciais

Após criar, você receberá:
- **Client ID**: `xxxxx.apps.googleusercontent.com`
- **Client Secret**: `xxxxx`

### 3. Configurar no Backend

No arquivo `.env` do backend:

```env
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu-client-secret
```

### 4. Reiniciar Serviço

```bash
# No servidor
ssh root@alcahub.cloud
systemctl restart alca-financas
```

---

## 🔴 Microsoft OAuth (Não Implementado)

O login com Microsoft ainda não está implementado no backend. Para implementar:

1. Criar app no [Azure Portal](https://portal.azure.com/)
2. Configurar redirect URIs
3. Implementar rotas no `backend/routes/auth.py`
4. Adicionar variáveis no `.env`:
   ```env
   MICROSOFT_CLIENT_ID=seu-client-id
   MICROSOFT_CLIENT_SECRET=seu-client-secret
   ```

---

## 🍎 Apple OAuth (Não Implementado)

O login com Apple ainda não está implementado no backend. Para implementar:

1. Criar app no [Apple Developer Portal](https://developer.apple.com/)
2. Configurar Services ID
3. Implementar rotas no `backend/routes/auth.py`
4. Adicionar variáveis no `.env`:
   ```env
   APPLE_CLIENT_ID=seu-client-id
   APPLE_CLIENT_SECRET=seu-client-secret
   ```

---

## 🚀 Configurar no Servidor de Produção

### Atualizar .env no Servidor

```bash
ssh root@alcahub.cloud
nano /var/www/alca-financas/backend/.env
```

Adicione as credenciais:

```env
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu-client-secret
```

### Reiniciar Serviço

```bash
systemctl restart alca-financas
```

### Verificar Logs

```bash
journalctl -u alca-financas -f
```

---

## ✅ Testar OAuth

1. Acesse: `https://alcahub.cloud/register`
2. Clique em "Continuar com Google"
3. Você será redirecionado para o Google
4. Após autorizar, será redirecionado de volta e logado automaticamente

---

## 🔍 Troubleshooting

### Erro: "Configuração OAuth do Google não definida"

- Verifique se `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` estão no `.env`
- Reinicie o serviço: `systemctl restart alca-financas`

### Erro: "redirect_uri_mismatch"

- Verifique se o redirect URI no Google Cloud Console corresponde exatamente ao usado
- Deve ser: `https://alcahub.cloud/api/auth/google/callback`

### Microsoft/Apple retornam erro 501

- Isso é esperado, pois ainda não estão implementados
- Os botões aparecem, mas retornarão erro ao clicar
- Para ocultar os botões, edite `frontend/src/components/auth/Register.tsx`

---

## 📝 Notas

- O Google OAuth está totalmente funcional após configuração
- Microsoft e Apple precisam de implementação no backend
- Para produção, sempre use HTTPS nas URLs de callback

