# 🔐 Configuração do Supabase Auth

## ✅ Integração Completa

Agora você pode usar o **Supabase Auth** nativo ao invés da autenticação customizada!

## 🚀 Como Ativar

### 1. Configurar Variáveis de Ambiente

Adicione ao `backend/.env`:

```env
# Ativar Supabase Auth
USE_SUPABASE_AUTH=true

# Credenciais do Supabase (já devem estar configuradas)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-service-role-key
```

### 2. Reiniciar o Backend

```bash
./archives/scripts-raiz/alca_start_mac.sh  # arquivado
```

## 📋 O que Mudou

### ✅ Vantagens do Supabase Auth

1. **Gerenciamento Automático**: Senhas, tokens, refresh tokens gerenciados automaticamente
2. **Segurança**: Sistema de autenticação robusto e testado
3. **Email Verification**: Verificação de email integrada
4. **Password Reset**: Recuperação de senha pronta
5. **OAuth**: Suporte nativo para Google, GitHub, etc.

### 🔄 Compatibilidade

- ✅ **Tabela `users` customizada**: Mantida para dados adicionais (settings, etc.)
- ✅ **Sincronização automática**: Usuários criados no Supabase Auth são sincronizados com a tabela `users`
- ✅ **Mesma API**: Endpoints `/api/auth/*` funcionam da mesma forma
- ✅ **Tokens JWT**: Tokens do Supabase são usados diretamente

## 📝 Endpoints Disponíveis

### POST `/api/auth/register`
Registra novo usuário

```json
{
  "email": "user@example.com",
  "password": "senha123",
  "name": "Nome do Usuário"
}
```

### POST `/api/auth/login`
Faz login

```json
{
  "email": "user@example.com",
  "password": "senha123"
}
```

### POST `/api/auth/refresh`
Renova o token de acesso

```json
{
  "refresh_token": "token_aqui"
}
```

### GET `/api/auth/me`
Obtém dados do usuário autenticado

**Header**: `Authorization: Bearer <access_token>`

### POST `/api/auth/logout`
Faz logout

**Header**: `Authorization: Bearer <access_token>`

## 🔧 Estrutura de Dados

### Tabela `users` (Customizada)
Armazena dados adicionais do usuário:

```sql
- id (UUID) - Mesmo ID do Supabase Auth
- email
- name
- settings (JSONB)
- auth_providers (JSONB)
- is_admin (BOOLEAN)
- created_at
- updated_at
```

### Supabase Auth
Gerencia:
- Autenticação
- Senhas (hasheadas)
- Tokens JWT
- Sessões
- Email verification

## 🔄 Migração de Usuários Existentes

Se você tem usuários na tabela `users` antiga:

1. **Opção 1**: Criar usuários no Supabase Auth manualmente
2. **Opção 2**: Usar script de migração (será criado se necessário)

## 🐛 Troubleshooting

### Erro: "USE_SUPABASE_AUTH não configurado"
- Adicione `USE_SUPABASE_AUTH=true` no `.env`

### Erro: "Supabase Auth não inicializado"
- Verifique `SUPABASE_URL` e `SUPABASE_KEY` no `.env`
- Certifique-se de usar a **service_role key**

### Usuário não encontrado após login
- O sistema cria automaticamente na tabela `users` se não existir
- Verifique se o schema SQL foi executado

## 📚 Recursos

- [Supabase Auth Docs](https://supabase.com/docs/guides/auth)
- [Supabase Python Client](https://github.com/supabase/supabase-py)



