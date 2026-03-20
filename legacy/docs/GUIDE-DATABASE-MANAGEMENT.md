# Guia: Gerenciamento do Banco de Dados

## Overview
Documentação sobre como gerenciar o banco de dados MongoDB do Alça Finanças, incluindo limpeza, backup e manutenção.

## Limpeza do Banco de Dados

### Método 1: Script Automatizado (Recomendado)

```bash
./scripts/clear-database.sh
```

**O que o script faz:**
1. ✅ Verifica se MongoDB está rodando
2. ✅ Solicita confirmação (digite "sim")
3. ✅ Mostra status antes da limpeza
4. ✅ Remove todos os documentos de todas as coleções
5. ✅ Mostra status após limpeza
6. ✅ Fornece dicas de próximos passos

**Output esperado:**
```
🗑️  Limpando banco de dados do Alça Finanças

⚠️  Tem certeza que deseja limpar TODOS os dados? (digite 'sim' para confirmar): sim

🧹 Limpando coleções...
📊 Status antes da limpeza:
  transactions: 150 documentos
  accounts: 3 documentos
  users: 1 documentos
  categories: 12 documentos

🗑️  Removendo dados...
  ✓ transactions: 150 documentos removidos
  ✓ accounts: 3 documentos removidos
  ✓ users: 1 documentos removidos
  ✓ categories: 12 documentos removidos

📊 Status após limpeza:
  transactions: 0 documentos
  accounts: 0 documentos
  users: 0 documentos
  categories: 0 documentos

✅ Banco de dados limpo com sucesso!

💡 Dicas:
   - Faça logout no frontend
   - Limpe o localStorage do navegador (F12 > Application > Storage > Clear)
   - Crie um novo usuário para começar do zero
```

### Método 2: Comando Manual

```bash
# Limpar todas as coleções
mongosh --eval "use alca_financas" --eval "db.getCollectionNames().forEach(function(col) { db[col].deleteMany({}); })"

# Verificar status
mongosh --eval "use alca_financas" --eval "db.getCollectionNames().forEach(function(col) { print(col + ': ' + db[col].countDocuments()); })"
```

### Método 3: Limpar Coleções Específicas

```bash
# Apenas usuários
mongosh --eval "use alca_financas" --eval "db.users.deleteMany({})"

# Apenas transações
mongosh --eval "use alca_financas" --eval "db.transactions.deleteMany({})"

# Apenas categorias
mongosh --eval "use alca_financas" --eval "db.categories.deleteMany({})"

# Apenas contas
mongosh --eval "use alca_financas" --eval "db.accounts.deleteMany({})"
```

## Coleções do Sistema

### 1. users
Armazena informações dos usuários:
```javascript
{
  _id: ObjectId,
  email: String,
  password: String (hashed),
  name: String,
  created_at: Date,
  updated_at: Date
}
```

### 2. categories
Categorias de receitas e despesas:
```javascript
{
  _id: ObjectId,
  user_id: String,
  name: String,
  type: String, // 'income' ou 'expense'
  color: String,
  icon: String,
  created_at: Date
}
```

### 3. transactions
Transações financeiras:
```javascript
{
  _id: ObjectId,
  user_id: String,
  description: String,
  amount: Number,
  type: String, // 'income' ou 'expense'
  category_id: String,
  date: Date,
  status: String, // 'paid', 'pending', 'overdue', 'cancelled'
  is_recurring: Boolean,
  responsible_person: String,
  installment_info: {
    total: Number,
    current: Number
  }
}
```

### 4. accounts
Contas bancárias:
```javascript
{
  _id: ObjectId,
  user_id: String,
  name: String,
  type: String, // 'checking', 'savings', etc
  balance: Number,
  color: String,
  icon: String,
  created_at: Date
}
```

## Após Limpar o Banco

### 1. Frontend - Limpar localStorage

**Chrome/Edge/Brave:**
1. Abra DevTools (F12)
2. Vá para "Application" tab
3. Sidebar > Storage > Local Storage
4. Clique em `http://localhost:3000` (ou sua URL)
5. Clique com botão direito > Clear

**Firefox:**
1. Abra DevTools (F12)
2. Vá para "Storage" tab
3. Local Storage > `http://localhost:3000`
4. Clique com botão direito > Delete All

**Safari:**
1. Abra DevTools (Cmd+Option+I)
2. Vá para "Storage" tab
3. Local Storage > `http://localhost:3000`
4. Limpe os dados

### 2. Fazer Logout

```javascript
// No console do navegador
localStorage.clear();
location.reload();
```

### 3. Criar Novo Usuário

1. Acesse a página de registro
2. Crie uma nova conta
3. Faça login
4. Sistema começará do zero

## Verificar Status do Banco

### Contar Documentos por Coleção

```bash
mongosh alca_financas --eval "
db.getCollectionNames().forEach(function(col) {
    print(col + ': ' + db[col].countDocuments() + ' documentos');
});
"
```

### Listar Últimos Usuários

```bash
mongosh alca_financas --eval "
db.users.find({}, {email: 1, name: 1, created_at: 1})
    .sort({created_at: -1})
    .limit(5)
    .forEach(printjson);
"
```

### Estatísticas Gerais

```bash
mongosh alca_financas --eval "
print('=== Estatísticas do Banco ===');
print('Usuários: ' + db.users.countDocuments());
print('Categorias: ' + db.categories.countDocuments());
print('Transações: ' + db.transactions.countDocuments());
print('Contas: ' + db.accounts.countDocuments());
print('');
print('Tamanho do banco: ' + (db.stats().dataSize / 1024 / 1024).toFixed(2) + ' MB');
"
```

## Backup do Banco de Dados

### Criar Backup

```bash
# Backup completo
mongodump --db=alca_financas --out=./backups/$(date +%Y%m%d_%H%M%S)

# Backup de coleção específica
mongodump --db=alca_financas --collection=users --out=./backups/users_$(date +%Y%m%d)
```

### Restaurar Backup

```bash
# Restaurar backup completo
mongorestore --db=alca_financas ./backups/20251116_120000/alca_financas

# Restaurar coleção específica
mongorestore --db=alca_financas --collection=users ./backups/users_20251116/alca_financas/users.bson
```

## Comandos Úteis

### Iniciar MongoDB

```bash
./scripts/start-mongodb.sh
```

### Parar MongoDB

```bash
docker stop alca-mongo
# ou
pkill -f mongod
```

### Conectar ao MongoDB

```bash
mongosh alca_financas
```

### Dentro do MongoDB Shell

```javascript
// Usar banco
use alca_financas

// Listar coleções
show collections

// Contar documentos
db.users.countDocuments()

// Listar todos
db.users.find()

// Buscar específico
db.users.findOne({email: "user@example.com"})

// Remover um documento
db.users.deleteOne({email: "user@example.com"})

// Atualizar documento
db.users.updateOne(
    {email: "user@example.com"},
    {$set: {name: "Novo Nome"}}
)

// Criar índice
db.users.createIndex({email: 1}, {unique: true})

// Ver índices
db.users.getIndexes()

// Estatísticas
db.stats()
db.users.stats()
```

## Troubleshooting

### MongoDB não inicia

```bash
# Verificar se porta 27017 está em uso
lsof -i :27017

# Matar processo na porta
kill -9 <PID>

# Reiniciar MongoDB
./scripts/start-mongodb.sh
```

### Erro: "connection refused"

```bash
# Verificar se MongoDB está rodando
ps aux | grep mongod

# Verificar logs
docker logs alca-mongo
# ou
tail -f /usr/local/var/log/mongodb/mongo.log
```

### Banco muito grande

```bash
# Ver tamanho
mongosh alca_financas --eval "db.stats().dataSize"

# Compactar banco
mongosh alca_financas --eval "db.runCommand({compact: 'transactions'})"
```

## Segurança

### Boas Práticas

1. ✅ Sempre faça backup antes de limpar
2. ✅ Use o script com confirmação
3. ✅ Não compartilhe backups com dados sensíveis
4. ✅ Use senhas fortes para usuários
5. ✅ Não execute comandos de limpeza em produção sem backup

### Comandos Perigosos

```bash
# ⚠️  NUNCA EXECUTE EM PRODUÇÃO SEM BACKUP!
db.dropDatabase()  # Remove o banco inteiro
db.collection.drop()  # Remove uma coleção
```

## Scripts Disponíveis

### `/scripts/clear-database.sh`
Limpa todas as coleções do banco de dados com confirmação

### `/scripts/start-mongodb.sh`
Inicia o MongoDB (Docker ou local)

### `/scripts/stop-local.sh`
Para todos os serviços locais

### Criar Novos Scripts

```bash
# Backup automático diário
./scripts/backup-daily.sh

# Seed de dados de teste
./scripts/seed-test-data.sh

# Migração de schema
./scripts/migrate-schema.sh
```

## Date
2025-11-16
