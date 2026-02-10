# Guia de Migração para Supabase

Este guia explica como migrar o projeto de MongoDB para Supabase (PostgreSQL).

## 📋 Pré-requisitos

1. Conta no Supabase: https://app.supabase.com
2. Projeto criado no Supabase
3. Credenciais do projeto (URL e Service Role Key)

## 🔧 Configuração

### 1. Obter Credenciais do Supabase

1. Acesse o dashboard do Supabase: https://app.supabase.com
2. Selecione seu projeto
3. Vá em **Settings** > **API**
4. Copie:
   - **Project URL** → `SUPABASE_URL`
   - **service_role key** → `SUPABASE_KEY` (NÃO use a anon key para backend)

### 2. Configurar Variáveis de Ambiente

Crie ou atualize o arquivo `backend/.env`:

```env
# Supabase Configuration
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-service-role-key-aqui

# Opcional: URL PostgreSQL direta (para queries SQL complexas)
# Encontre em Settings > Database > Connection string
SUPABASE_DB_URL=postgresql://postgres:[password]@db.[projeto].supabase.co:5432/postgres

# Outras configurações
SECRET_KEY=seu-secret-key-aqui
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 3. Executar Schema SQL

1. Acesse o **SQL Editor** no dashboard do Supabase
2. Abra o arquivo `backend/database/schema.sql`
3. Execute o script completo
4. Verifique se as tabelas foram criadas em **Table Editor**

## 🔄 Migração de Dados (Opcional)

Se você tem dados no MongoDB que precisa migrar:

1. Execute o script de migração (será criado em breve)
2. Ou exporte manualmente do MongoDB e importe no Supabase

## 🚀 Atualização do Código

### Mudanças Principais

1. **Repositórios**: Agora usam `base_repository_supabase.py` ao invés de `base_repository.py`
2. **Conexão**: Usa `database.connection` ao invés de `pymongo.MongoClient`
3. **IDs**: UUIDs ao invés de ObjectId
4. **Queries**: SQL ao invés de queries MongoDB

### Arquivos Atualizados

- ✅ `requirements.txt` - Dependências do Supabase
- ✅ `database/` - Módulo de conexão
- ✅ `repositories/*_supabase.py` - Novos repositórios
- ✅ `app.py` - Configuração do Supabase

### Arquivos que Precisam de Atualização

- ⚠️ `services/user_service.py` - Ainda usa MongoDB diretamente
- ⚠️ `services/category_service.py` - Precisa usar repositórios
- ⚠️ `services/transaction_service.py` - Precisa usar repositórios
- ⚠️ `services/account_service.py` - Precisa usar repositórios
- ⚠️ `routes/*.py` - Verificar se usam MongoDB diretamente

## 📝 Notas Importantes

1. **Row Level Security (RLS)**: O schema inclui RLS básico. Você pode querer ajustar as políticas conforme necessário.

2. **Senhas**: As senhas são armazenadas como `BYTEA` (bytes) para compatibilidade com bcrypt.

3. **JSONB**: Campos como `settings` e `auth_providers` usam JSONB para flexibilidade.

4. **Timestamps**: Triggers automáticos atualizam `updated_at` quando registros são modificados.

5. **Índices**: Todos os índices necessários estão no schema SQL.

## 🧪 Testes

Após a migração, teste:

1. ✅ Criação de usuário
2. ✅ Login
3. ✅ Criação de categorias
4. ✅ Criação de transações
5. ✅ Dashboard e relatórios

## 🐛 Troubleshooting

### Erro: "SUPABASE_URL e SUPABASE_KEY devem estar configurados"

- Verifique se as variáveis estão no `.env`
- Certifique-se de usar a **service_role key**, não a anon key

### Erro: "relation does not exist"

- Execute o schema SQL no Supabase
- Verifique se as tabelas foram criadas no Table Editor

### Erro: "permission denied"

- Verifique as políticas RLS no Supabase
- Certifique-se de usar a service_role key para operações server-side

## 📚 Recursos

- [Documentação Supabase](https://supabase.com/docs)
- [Supabase Python Client](https://github.com/supabase/supabase-py)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

