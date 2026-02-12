# 🔐 Como Ativar o Painel de Administrador

## 📋 Problema

O painel de administrador foi implementado e deployado, mas não está visível porque seu usuário ainda não está marcado como administrador no banco de dados.

## ✅ Solução Rápida

Execute este comando no servidor para se promover a administrador:

```bash
cd /root/alca-financas/backend
source venv/bin/activate
python3 ../scripts/set_admin.py lezinrew@gmail.com
```

## 📝 Passo a Passo Detalhado

### 1. Conectar ao Servidor

```bash
ssh root@alcahub.cloud
```

### 2. Navegar até o Projeto

```bash
cd /root/alca-financas
```

### 3. Atualizar o Código (caso ainda não tenha feito)

```bash
git pull origin main
```

### 4. Ativar o Ambiente Virtual

```bash
cd backend
source venv/bin/activate
```

### 5. Executar o Script de Promoção

```bash
python3 ../scripts/set_admin.py lezinrew@gmail.com
```

**Saída esperada:**
```
============================================================
🔐 SCRIPT DE PROMOÇÃO A ADMINISTRADOR
============================================================
✅ Arquivo .env carregado de /root/alca-financas/backend/.env
🔌 Conectando ao banco de dados...
✅ Conectado ao supabase

🔍 Buscando usuário: lezinrew@gmail.com
✅ Usuário encontrado: Leandro Zin Rew
   ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   Email: lezinrew@gmail.com
   Admin atual: False
   Bloqueado: False

🔧 Promovendo lezinrew@gmail.com a administrador...
✅ Usuário promovido a administrador com sucesso!

📋 Próximos passos:
   1. Faça logout do sistema
   2. Faça login novamente
   3. O link 'Painel Admin' aparecerá no menu do seu perfil
   4. Ou acesse diretamente: https://alcahub.cloud/admin/dashboard

============================================================
✅ OPERAÇÃO CONCLUÍDA COM SUCESSO
============================================================
```

### 6. Fazer Logout e Login Novamente

1. Acesse https://alcahub.cloud
2. Clique no seu perfil (canto superior direito)
3. Clique em "Sair"
4. Faça login novamente com seu email e senha

### 7. Acessar o Painel Admin

Após fazer login, você verá o link do **Painel Admin** em dois lugares:

1. **No menu lateral** (sidebar) - ícone de escudo 🛡️
2. **No dropdown do perfil** (canto superior direito) - opção "Painel Admin"

Ou acesse diretamente: https://alcahub.cloud/admin/dashboard

## 🔍 Verificação Manual (Alternativa)

Se preferir verificar manualmente no banco de dados Supabase:

### Via Dashboard do Supabase

1. Acesse https://app.supabase.com
2. Selecione seu projeto AlcaHub
3. Vá em **Table Editor** > **users**
4. Encontre o usuário `lezinrew@gmail.com`
5. Edite a coluna `is_admin` para `true`
6. Salve a alteração

### Via SQL no Supabase

1. Acesse https://app.supabase.com
2. Selecione seu projeto AlcaHub
3. Vá em **SQL Editor**
4. Execute:

```sql
-- Verificar status atual
SELECT id, name, email, is_admin, is_blocked
FROM users
WHERE email = 'lezinrew@gmail.com';

-- Promover a admin
UPDATE users
SET is_admin = true
WHERE email = 'lezinrew@gmail.com';

-- Confirmar alteração
SELECT id, name, email, is_admin, is_blocked
FROM users
WHERE email = 'lezinrew@gmail.com';
```

## ❓ Problemas Comuns

### Erro: "Usuário não encontrado"

**Causa:** Email incorreto ou usuário não existe no sistema

**Solução:**
- Verifique se o email está correto
- Confirme que você criou a conta no sistema
- Liste todos os usuários: `python3 ../scripts/set_admin.py --list` (se implementado)

### Erro: "Conexão com banco falhou"

**Causa:** Variáveis de ambiente do Supabase não configuradas

**Solução:**
```bash
cd /root/alca-financas/backend
cat .env | grep SUPABASE
```

Deve mostrar:
```
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

Se estiver faltando, configure o arquivo `.env`:
```bash
nano /root/alca-financas/backend/.env
```

### Painel Admin ainda não aparece

**Causa:** Cache do navegador ou sessão antiga

**Solução:**
1. Faça logout completo
2. Limpe o cache do navegador (Ctrl + Shift + Del)
3. Feche e abra o navegador novamente
4. Faça login novamente
5. Se ainda não funcionar, tente em modo anônimo

### Erro 403 ao acessar /admin

**Causa:** Token JWT antigo ainda em cache

**Solução:**
1. Abra o DevTools (F12)
2. Vá em Application > Local Storage
3. Limpe tudo relacionado a alcahub.cloud
4. Faça login novamente

## 🎯 Recursos do Painel Admin

Após ativar, você terá acesso a:

### 📊 Dashboard Admin
- Estatísticas gerais do sistema
- Usuários ativos (últimas 24h)
- Volume financeiro total
- Crescimento mensal
- Top 10 categorias mais usadas

### 👥 Gerenciamento de Usuários
- Listar todos os usuários
- Ver detalhes completos de cada usuário
- Promover/rebaixar administradores
- Bloquear/desbloquear usuários
- Exportar dados do usuário (CSV)
- Deletar usuários (cuidado!)

### 📝 Logs de Auditoria
- Histórico de todas as ações administrativas
- Quem fez o quê e quando
- IP de origem das ações
- Filtros por data/ação/usuário

### 📥 Exportação de Dados
- Exportar todos os dados de um usuário em CSV
- Inclui: transações, contas, categorias, configurações

## 🚀 Próximos Passos

1. ✅ Executar o script `set_admin.py`
2. ✅ Fazer logout e login
3. ✅ Acessar o painel admin
4. ✅ Testar as funcionalidades
5. 📋 Criar outros usuários admin se necessário

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs do backend:
   ```bash
   tail -f /var/log/supervisor/alca-backend-*.log
   ```

2. Verifique se o backend está rodando:
   ```bash
   supervisorctl status alca-backend
   ```

3. Reinicie o backend se necessário:
   ```bash
   supervisorctl restart alca-backend
   ```

---

**Autor:** Claude Code
**Data:** 2026-02-11
**Projeto:** AlcaHub - Sistema de Controle Financeiro
