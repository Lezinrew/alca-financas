# 🚀 Migração para Supabase - Resumo

## ✅ O que foi feito

1. ✅ **Dependências atualizadas** - `requirements.txt` agora inclui `supabase` e `psycopg2-binary`
2. ✅ **Schema SQL criado** - `database/schema.sql` com todas as tabelas necessárias
3. ✅ **Módulo de conexão** - `database/connection.py` para gerenciar conexões Supabase
4. ✅ **Repositórios atualizados** - Novos repositórios para Supabase:
   - `base_repository_supabase.py`
   - `user_repository_supabase.py`
   - `category_repository_supabase.py`
   - `transaction_repository_supabase.py`
   - `account_repository_supabase.py`
5. ✅ **app.py atualizado** - Configuração para usar Supabase
6. ✅ **Script de inicialização** - `archives/scripts-raiz/alca_start_mac.sh` (arquivado) suportava Supabase

## 📋 Próximos Passos

### 1. Configurar Supabase

1. Crie uma conta em https://app.supabase.com
2. Crie um novo projeto
3. Copie as credenciais (URL e Service Role Key)

### 2. Executar Schema SQL

1. No dashboard do Supabase, vá em **SQL Editor**
2. Abra `backend/database/schema.sql`
3. Execute o script completo
4. Verifique as tabelas em **Table Editor**

### 3. Configurar Variáveis de Ambiente

Adicione ao `backend/.env`:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-service-role-key-aqui
```

### 4. Instalar Dependências

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Testar

```bash
./archives/scripts-raiz/alca_start_mac.sh  # arquivado
```

O script detectará automaticamente se você está usando Supabase ou MongoDB.

## ⚠️ Avisos

- **Service Role Key**: Use a **service_role key**, não a anon key, para operações server-side
- **RLS**: As políticas RLS estão configuradas, mas podem precisar de ajustes
- **Migração de Dados**: Se você tem dados no MongoDB, precisará migrá-los manualmente ou criar um script de migração

## 📚 Documentação

- Guia completo: `MIGRATION_SUPABASE.md`
- Schema SQL: `database/schema.sql`
- Exemplo de uso: `database/connection.py`

