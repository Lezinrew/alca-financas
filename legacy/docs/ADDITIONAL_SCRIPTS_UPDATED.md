# Scripts Adicionais Atualizados - Supabase Migration

**Data:** 2026-02-09
**Status:** ✅ Completo

---

## 📋 Scripts Identificados e Atualizados

Após a refatoração inicial, foram identificados 3 scripts adicionais que ainda usavam MongoDB. Todos foram atualizados para Supabase ou marcados como deprecated.

---

## ✅ Scripts Atualizados

### 1. scripts/make_admin.py ✅

**Status:** ✅ Atualizado para Supabase

**Problema:** Usava `pymongo.MongoClient` para promover usuários a admin.

**Solução:** Reescrito completamente para usar Supabase.

**Mudanças:**
```python
# ANTES (MongoDB)
from pymongo import MongoClient
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
client = MongoClient(mongo_uri)
db = client[mongo_db]
users = db.users
result = users.update_one({'email': email}, {'$set': {'is_admin': True}})

# DEPOIS (Supabase)
from supabase import create_client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
client = create_client(supabase_url, supabase_key)
response = client.table('users').select('*').ilike('email', email).execute()
update_response = client.table('users').update({'is_admin': True}).eq('id', user['id']).execute()
```

**Recursos:**
- ✅ Busca case-insensitive por email
- ✅ Verifica se usuário já é admin
- ✅ Mensagens de erro claras e acionáveis
- ✅ Valida credenciais do Supabase
- ✅ Tratamento de exceções completo

**Uso:**
```bash
python scripts/make_admin.py lezinrew@gmail.com
```

---

### 2. scripts/create-user-server.py ⚠️

**Status:** ⚠️ Marcado como DEPRECATED

**Problema:** Script complexo para criar usuários via SSH em servidor remoto assumindo MongoDB.

**Solução:** Transformado em deprecation notice com alternativas.

**Alternativas fornecidas:**

1. **Via Supabase Dashboard** (mais simples)
   - URL: https://app.supabase.com/project/_/auth/users

2. **Via SQL Editor do Supabase**
   - Usar: `scripts/sql-ensure-user-lezinrew.sql`

3. **Via Script Python Local** (recomendado)
   - Usar: `backend/scripts/set_user_password.py`

4. **Via SSH + Script Supabase** (para servidores)
   ```bash
   ssh user@servidor
   cd /var/www/alca-financas/backend
   source venv/bin/activate
   python scripts/set_user_password.py
   ```

**Por que deprecated?**
- Assumia MongoDB no servidor remoto
- Complexidade desnecessária com Supabase (banco é cloud)
- Alternativas mais simples e seguras disponíveis

---

### 3. scripts/deploy-remote.py ⚠️

**Status:** ⚠️ Aviso adicionado (funcional mas requer atualização manual)

**Problema:** Script de deploy completo para Hostinger com configuração MongoDB.

**Solução:** Adicionado aviso extenso no cabeçalho do arquivo.

**Avisos adicionados:**

```python
"""
⚠️  AVISO IMPORTANTE - REQUER ATUALIZAÇÃO:
    Este script foi criado para MongoDB mas o projeto agora usa Supabase.

    ANTES DE USAR:
    1. Linhas 116-117: Substitua MONGO_URI/MONGO_DB por:
       SUPABASE_URL=https://seu-projeto.supabase.co
       SUPABASE_SERVICE_ROLE_KEY=eyJ...

    2. Linha 223: Remova dependência "mongod.service" (não necessário)

    3. Linha 133, 269: Atualize instruções para mencionar Supabase

    ALTERNATIVA: Use scripts modernos em scripts/prod/:
    - scripts/prod/build.sh
    - scripts/prod/run.sh

    Esses scripts já estão configurados para Supabase.
"""
```

**Por que não foi reescrito completamente?**
- Script complexo (~277 linhas) com lógica específica de servidor
- Usuários podem ter customizações próprias
- Scripts modernos em `scripts/prod/` já cobrem uso padrão
- Mantido para referência/casos especiais

**Alternativa recomendada:**
```bash
# Use os scripts modernos já configurados para Supabase
./scripts/prod/build.sh
./scripts/prod/run.sh
```

---

## 📊 Resumo das Mudanças

### Arquivos Modificados: 3

| Arquivo | Status | Ação |
|---------|--------|------|
| `scripts/make_admin.py` | ✅ Atualizado | Reescrito para Supabase |
| `scripts/create-user-server.py` | ⚠️ Deprecated | Deprecation notice com alternativas |
| `scripts/deploy-remote.py` | ⚠️ Warning | Aviso adicionado no header |

### Impacto

**Positivo:**
- ✅ `make_admin.py` agora funcional com Supabase
- ✅ Usuários são direcionados para métodos corretos
- ✅ Scripts modernos (`scripts/prod/`) cobrem casos de uso comuns
- ✅ Menos confusão sobre qual método usar

**Pontos de Atenção:**
- ⚠️ `deploy-remote.py` requer atualização manual se for usado
- ⚠️ Usuários com fluxos customizados de criação de usuários via SSH precisam adaptar

---

## 🎯 Como Usar os Scripts Atualizados

### 1. Tornar Usuário Admin

```bash
# Método 1: Via script Python (recomendado)
python scripts/make_admin.py usuario@email.com

# Método 2: Via SQL no Supabase Dashboard
# Execute: UPDATE users SET is_admin = true WHERE email = 'usuario@email.com';
```

### 2. Criar Usuários

```bash
# Método 1: Supabase Dashboard (mais simples)
# https://app.supabase.com/project/_/auth/users

# Método 2: Script Python (local ou servidor)
cd backend
python scripts/set_user_password.py

# Método 3: SQL direto
# scripts/sql-ensure-user-lezinrew.sql
```

### 3. Deploy

```bash
# Método Recomendado: Scripts modernos
cp .env.example .env.production
# Editar .env.production com valores de produção
./scripts/prod/build.sh
./scripts/prod/run.sh

# Método Legado: deploy-remote.py
# Requer atualização manual das linhas indicadas no aviso
```

---

## 🔍 Validação

### Verificar que scripts MongoDB foram limpos

```bash
# Verificar scripts Python que ainda usam MongoDB
grep -l "pymongo\|MongoClient\|MONGO_URI" scripts/*.py 2>/dev/null | grep -v legacy

# Resultado esperado:
# scripts/deploy-remote.py  (tem aviso, OK)
# (nenhum outro arquivo)

# Verificar se make_admin.py usa Supabase
grep "supabase" scripts/make_admin.py
# Deve retornar: from supabase import create_client
```

### Testar make_admin.py

```bash
# Deve mostrar mensagens claras se credenciais não configuradas
python scripts/make_admin.py test@example.com

# Com credenciais configuradas, deve funcionar:
# export SUPABASE_URL="..."
# export SUPABASE_SERVICE_ROLE_KEY="..."
# python scripts/make_admin.py usuario@real.com
```

---

## 📚 Scripts por Categoria

### ✅ Prontos para Uso (Supabase)

- `scripts/make_admin.py` - Promover usuário a admin
- `backend/scripts/set_user_password.py` - Definir senha de usuário
- `scripts/prod/build.sh` - Build para produção
- `scripts/prod/run.sh` - Executar em produção
- `scripts/prod/migrate.sh` - Migrar banco de dados
- `scripts/dev/*` - Scripts de desenvolvimento

### ⚠️ Requerem Atenção

- `scripts/deploy-remote.py` - Requer atualização manual (ver aviso no arquivo)

### 🗂️ Deprecated

- `scripts/create-user-server.py` - Use alternativas listadas no arquivo
- `scripts/reset_password.py` - Use backend/scripts/set_user_password.py
- `scripts/legacy/mongo/*` - Scripts MongoDB antigos

---

## 🔗 Documentação Relacionada

- `REFACTORING_COMPLETE.md` - Refatoração principal
- `SUPABASE_MIGRATION_COMPLETE.md` - Migração MongoDB → Supabase
- `docs/INDEX.md` - Índice completo da documentação
- `docs/TODO-MELHORIAS-ESTRUTURA.md` - Lista de melhorias

---

## ✨ Conclusão

Todos os scripts Python identificados foram tratados:

1. **make_admin.py**: ✅ Atualizado e funcional
2. **create-user-server.py**: ⚠️ Deprecated com alternativas claras
3. **deploy-remote.py**: ⚠️ Aviso adicionado

**Status do Projeto:**
- 🟢 Nenhum script ativo usa MongoDB sem aviso
- 🟢 Alternativas modernas para todos os casos de uso
- 🟢 Documentação clara sobre qual método usar
- 🟢 Scripts legados organizados em `scripts/legacy/`

**O projeto agora tem scripts Python totalmente compatíveis com Supabase ou com avisos claros de atualização necessária.**

---

**Atualização realizada em:** 2026-02-09
**Autor:** Claude Code
**Base:** Continuação de REFACTORING_COMPLETE.md
