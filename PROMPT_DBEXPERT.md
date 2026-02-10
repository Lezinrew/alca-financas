# Prompt para DBExpert - Modelo de Banco de Dados Alca Finanças

## Contexto do Projeto

Sistema de controle financeiro pessoal chamado **Alca Finanças**, desenvolvido com Flask (Python) no backend e React no frontend. O banco de dados utilizado é **MongoDB** (NoSQL).

## Banco de Dados: MongoDB

**Nome do banco:** `alca_financas`

## Coleções e Estrutura de Documentos

### 1. Collection: `users`

**Descrição:** Armazena informações dos usuários do sistema.

**Estrutura do documento:**
```javascript
{
  "_id": String (UUID v4),  // Identificador único do usuário
  "name": String,            // Nome completo do usuário
  "email": String,           // Email único (usado para login)
  "password": String,        // Hash da senha (bcrypt)
  "settings": {
    "currency": String,      // Moeda padrão (ex: "BRL")
    "theme": String,         // Tema da interface (ex: "light", "dark")
    "language": String       // Idioma (ex: "pt", "en")
  },
  "auth_providers": [        // Array de provedores OAuth
    {
      "provider": String,    // Nome do provedor (ex: "google")
      "sub": String,         // ID do usuário no provedor
      "email_verified": Boolean
    }
  ],
  "profile_picture": String, // URL da foto de perfil (opcional)
  "is_admin": Boolean,       // Indica se é administrador (opcional, default: false)
  "created_at": DateTime,    // Data de criação
  "updated_at": DateTime     // Data de última atualização
}
```

**Índices:**
- `email` (único)
- `created_at`

**Relacionamentos:**
- Um usuário pode ter múltiplas categorias (`categories.user_id`)
- Um usuário pode ter múltiplas contas (`accounts.user_id`)
- Um usuário pode ter múltiplas transações (`transactions.user_id`)

---

### 2. Collection: `categories`

**Descrição:** Categorias de receitas e despesas personalizadas por usuário.

**Estrutura do documento:**
```javascript
{
  "_id": String (UUID v4),   // Identificador único da categoria
  "user_id": String,         // Referência ao _id do usuário
  "name": String,            // Nome da categoria (ex: "Alimentação", "Salário")
  "type": String,            // Tipo: "income" (receita) ou "expense" (despesa)
  "color": String,           // Cor em hexadecimal (ex: "#FF6B6B")
  "icon": String,            // Nome do ícone (ex: "basket", "house", "car-front")
  "description": String,     // Descrição opcional
  "active": Boolean,         // Se a categoria está ativa (default: true)
  "essential": Boolean,      // Se é uma categoria essencial (default: false)
  "created_at": DateTime,    // Data de criação
  "updated_at": DateTime     // Data de última atualização
}
```

**Índices:**
- `user_id`
- `type`
- `active`
- Composto: `user_id + name + type` (para busca única)

**Relacionamentos:**
- Pertence a um usuário (`user_id` → `users._id`)
- Referenciada por transações (`transactions.category_id`)

**Categorias padrão criadas automaticamente:**
- Despesas: "Alimentação", "Transporte", "Casa", "Saúde"
- Receitas: "Salário", "Freelance"

---

### 3. Collection: `accounts`

**Descrição:** Contas bancárias, cartões de crédito e outras contas financeiras.

**Estrutura do documento:**
```javascript
{
  "_id": String (UUID v4),   // Identificador único da conta
  "user_id": String,         // Referência ao _id do usuário
  "name": String,            // Nome da conta (ex: "Conta Corrente Nubank", "Cartão Visa")
  "type": String,            // Tipo: "bank", "credit_card", "savings", "investment", etc.
  "color": String,           // Cor em hexadecimal (ex: "#4ECDC4")
  "icon": String,            // Nome do ícone (ex: "wallet", "credit-card")
  "balance": Number,         // Saldo atual (Decimal, default: 0.00)
  "initial_balance": Number, // Saldo inicial ou limite do cartão (para credit_card)
  "current_balance": Number, // Saldo atual calculado (pode diferir de balance)
  "currency": String,        // Moeda (default: "BRL")
  "active": Boolean,         // Se a conta está ativa (default: true)
  "is_active": Boolean,      // Alias para active
  "created_at": DateTime,    // Data de criação
  "updated_at": DateTime     // Data de última atualização
}
```

**Índices:**
- `user_id`
- `active`
- Composto: `user_id + name` (para busca única)

**Relacionamentos:**
- Pertence a um usuário (`user_id` → `users._id`)
- Referenciada por transações (`transactions.account_id`)

**Observações:**
- Para cartões de crédito (`type: "credit_card"`), o campo `initial_balance` representa o limite do cartão
- O `current_balance` é calculado dinamicamente baseado nas transações

---

### 4. Collection: `transactions`

**Descrição:** Transações financeiras (receitas e despesas).

**Estrutura do documento:**
```javascript
{
  "_id": String (UUID v4),   // Identificador único da transação
  "user_id": String,         // Referência ao _id do usuário
  "category_id": String,     // Referência ao _id da categoria (opcional)
  "account_id": String,      // Referência ao _id da conta (opcional)
  "description": String,     // Descrição da transação (máx. 500 caracteres)
  "amount": Number,          // Valor da transação (Decimal, sempre positivo)
  "type": String,            // Tipo: "income" (receita) ou "expense" (despesa)
  "date": Date,              // Data da transação
  "status": String,          // Status: "paid", "pending", "overdue", "cancelled" (default: "pending")
  "responsible_person": String, // Pessoa responsável (opcional)
  "is_recurring": Boolean,   // Se é uma transação recorrente (default: false)
  "installment_info": {      // Informações de parcelamento (opcional)
    "current": Number,       // Parcela atual
    "total": Number,         // Total de parcelas
    "parent_id": String      // ID da transação pai (primeira parcela)
  },
  "tags": [String],          // Array de tags para organização
  "notes": String,           // Notas adicionais (opcional)
  "created_at": DateTime,    // Data de criação
  "updated_at": DateTime     // Data de última atualização
}
```

**Índices:**
- `user_id`
- `category_id`
- `account_id`
- `date`
- `type`
- `status`
- Composto: `user_id + date` (descendente, para ordenação)

**Relacionamentos:**
- Pertence a um usuário (`user_id` → `users._id`)
- Opcionalmente relacionada a uma categoria (`category_id` → `categories._id`)
- Opcionalmente relacionada a uma conta (`account_id` → `accounts._id`)

**Observações:**
- O campo `amount` sempre armazena valores positivos
- O tipo (`type`) determina se é receita ou despesa
- Transações podem ser parceladas usando `installment_info`
- Transações podem ser filtradas por mês/ano, categoria, tipo, conta e status

---

### 5. Collection: `oauth_states`

**Descrição:** Cache temporário para estados OAuth durante autenticação social.

**Estrutura do documento:**
```javascript
{
  "_id": String (UUID v4),   // Identificador único
  "state": String,           // Estado único do OAuth (único)
  "provider": String,         // Nome do provedor (ex: "google", "microsoft", "apple")
  "created_at": DateTime,    // Data de criação
  "expires_at": DateTime     // Data de expiração (deve ser limpo após uso)
}
```

**Índices:**
- `state` (único)
- `expires_at` (para limpeza automática de registros expirados)

**Observações:**
- Esta coleção é usada temporariamente durante o fluxo OAuth
- Registros devem ser limpos periodicamente após expiração
- Usado para segurança no processo de autenticação OAuth 2.0

---

## Relacionamentos entre Coleções

```
users (1) ──< (N) categories
users (1) ──< (N) accounts
users (1) ──< (N) transactions
categories (1) ──< (N) transactions
accounts (1) ──< (N) transactions
```

**Diagrama de relacionamentos:**
- **users** é a entidade central
- Cada usuário pode ter múltiplas **categories**, **accounts** e **transactions**
- **transactions** podem referenciar opcionalmente uma **category** e/ou uma **account**
- **oauth_states** é independente e usado apenas temporariamente

---

## Regras de Negócio Importantes

1. **Isolamento de dados:** Todos os dados são isolados por `user_id`. Um usuário só pode acessar seus próprios dados.

2. **Categorias padrão:** Ao criar um novo usuário, são criadas automaticamente 6 categorias padrão (4 despesas + 2 receitas).

3. **Saldo de contas:** O saldo das contas é calculado dinamicamente baseado nas transações associadas.

4. **Transações parceladas:** Transações podem ser parceladas usando o campo `installment_info`, onde cada parcela é uma transação separada vinculada à transação pai.

5. **Status de transações:** Transações podem ter status "pending" (pendente), "paid" (paga), "overdue" (vencida) ou "cancelled" (cancelada).

6. **Tipos de contas:** Suporta diferentes tipos: "bank" (conta bancária), "credit_card" (cartão de crédito), "savings" (poupança), "investment" (investimento), etc.

7. **Autenticação:** Suporta login tradicional (email/senha) e OAuth (Google, Microsoft, Apple).

---

## Índices Recomendados

### Performance
- Índice composto em `transactions`: `{user_id: 1, date: -1}` para consultas frequentes de transações por usuário ordenadas por data
- Índice em `transactions.status` para filtros por status
- Índice em `categories`: `{user_id: 1, type: 1}` para listagem de categorias por tipo

### Unicidade
- `users.email` (único)
- `oauth_states.state` (único)
- Composto em `categories`: `{user_id: 1, name: 1, type: 1}` (para evitar duplicatas)

---

## Exemplos de Consultas Comuns

1. **Buscar todas as transações de um usuário em um mês:**
   ```javascript
   db.transactions.find({
     user_id: "user-uuid",
     date: { $gte: ISODate("2025-01-01"), $lt: ISODate("2025-02-01") }
   }).sort({ date: -1 })
   ```

2. **Buscar todas as categorias de despesas de um usuário:**
   ```javascript
   db.categories.find({
     user_id: "user-uuid",
     type: "expense",
     active: true
   })
   ```

3. **Calcular saldo total de todas as contas de um usuário:**
   ```javascript
   db.accounts.aggregate([
     { $match: { user_id: "user-uuid", active: true } },
     { $group: { _id: null, total: { $sum: "$current_balance" } } }
   ])
   ```

---

## Observações Finais

- O banco utiliza **MongoDB** (NoSQL), então não há esquemas rígidos
- Os documentos podem ter campos opcionais
- IDs são strings UUID v4, não ObjectId do MongoDB
- Timestamps são armazenados como DateTime (ISO 8601)
- Valores monetários são armazenados como Number (Decimal)
- O sistema suporta multi-moeda através do campo `currency` nas contas

---

**Gerar diagrama ER/relacional adaptado para MongoDB mostrando:**
- As 5 coleções principais
- Relacionamentos entre elas
- Campos principais de cada documento
- Índices importantes
- Tipos de dados principais




