# Mobills Pro - Aplicação de Controle Financeiro Pessoal

Aplicação web full-stack de controle financeiro pessoal, inspirada no Mobills Pro, com API em Python/Flask e front-end em React. Desenvolvida com foco em usabilidade, design moderno e funcionalidades completas de gestão financeira.

## 🚀 Características Principais

### Backend (Flask API)
- **Flask 3.0** com MongoDB para armazenamento de dados
- **Autenticação JWT** com tokens seguros HS256
- **OAuth 2.0** para login social (Google, Microsoft, Apple)
- **API RESTful** completa com endpoints para todas as funcionalidades
- **Importação CSV** para transações em massa
- **Categorização** inteligente de receitas e despesas
- **Criptografia bcrypt** para senhas
- **CORS configurável** para segurança

### Frontend (React SPA)
- **React 18** com Vite para desenvolvimento rápido
- **Bootstrap 5** para design responsivo e moderno
- **React Router DOM** para navegação
- **Multi-idioma** (Português, Inglês, Espanhol) com react-i18next
- **Dashboard interativo** com gráficos e resumos
- **Interface mobile-friendly** totalmente responsiva
- **Componentes reutilizáveis** bem estruturados

## 📁 Estrutura do Projeto

```
/app/
├── backend/                 # API Flask
│   ├── app.py              # Aplicação principal
│   ├── requirements.txt    # Dependências Python
│   ├── .env               # Variáveis de ambiente
│   └── .env.example       # Exemplo de configuração
├── frontend/               # SPA React
│   ├── src/
│   │   ├── components/    # Componentes React
│   │   ├── contexts/      # Context API
│   │   ├── i18n/          # Internacionalização
│   │   └── utils/         # Utilitários
│   ├── package.json       # Dependências Node.js
│   └── .env              # Configuração frontend
├── supervisord.conf        # Configuração Supervisor
└── README.md              # Esta documentação
```

## 🛠️ Instalação e Execução

### Pré-requisitos
- Python 3.11+
- Node.js 18+
- MongoDB
- Yarn

### 1. Instalação das Dependências

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
yarn install
```

### 2. Configuração do Ambiente

```bash
# Backend - copie e configure
cp backend/.env.example backend/.env

# Frontend - já configurado
# REACT_APP_BACKEND_URL=http://localhost:8001
```

### 3. Iniciar MongoDB

```bash
# Certifique-se de que o MongoDB está rodando na porta 27017
mongod --dbpath /tmp/mongodb --bind_ip 127.0.0.1 --port 27017 &
```

### 4. Executar a Aplicação

```bash
# Usando Supervisor (recomendado)
supervisord -c supervisord.conf

# Ou manualmente:
# Backend
cd backend && python app.py &

# Frontend
cd frontend && yarn dev --host 0.0.0.0 &
```

### 5. Acessar a Aplicação

- **Frontend**: http://localhost:3000
- **API Backend**: http://localhost:8001

## 📚 API Endpoints

### Autenticação
- `POST /api/register` - Registro de usuário
- `POST /api/login` - Login de usuário
- `POST /api/forgot-password` - Reset de senha
- `GET /api/me` - Dados do usuário autenticado

### OAuth Social Login
- `GET /api/auth/google/login` - Iniciar login Google
- `GET /api/auth/google/callback` - Callback Google
- `GET /api/auth/microsoft/login` - Login Microsoft (placeholder)
- `GET /api/auth/apple/login` - Login Apple (placeholder)

### Categorias
- `GET /api/categories` - Listar categorias do usuário
- `POST /api/categories` - Criar nova categoria
- `PUT /api/categories/:id` - Atualizar categoria
- `DELETE /api/categories/:id` - Deletar categoria

### Transações
- `GET /api/transactions` - Listar transações (com filtros)
- `POST /api/transactions` - Criar transação/parcelamento
- `PUT /api/transactions/:id` - Atualizar transação
- `DELETE /api/transactions/:id` - Deletar transação
- `POST /api/transactions/import` - Importar via CSV

### Dashboard
- `GET /api/dashboard` - Dados consolidados do dashboard

### Configurações
- `GET /api/settings` - Configurações do usuário
- `PUT /api/settings` - Atualizar configurações

## 🔐 Configuração OAuth

Para habilitar login social, configure as credenciais no arquivo `.env`:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Microsoft OAuth
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Apple OAuth  
APPLE_CLIENT_ID=your-apple-client-id
APPLE_TEAM_ID=your-apple-team-id
APPLE_KEY_ID=your-apple-key-id
APPLE_PRIVATE_KEY=your-apple-private-key
```

## 📊 Funcionalidades Implementadas

### ✅ Autenticação e Autorização
- [x] Registro e login tradicional
- [x] Login social (Google configurado, Microsoft/Apple preparados)
- [x] JWT tokens com expiração
- [x] Middleware de autenticação
- [x] Logout seguro

### ✅ Dashboard Inteligente
- [x] Resumo mensal (receitas, despesas, saldo)
- [x] Transações recentes
- [x] Gráficos por categoria
- [x] Filtros por período
- [x] Indicadores visuais

### ✅ Gestão de Transações
- [x] CRUD completo de transações
- [x] Suporte a parcelamento
- [x] Transações recorrentes
- [x] Categorização
- [x] Filtros avançados
- [x] Ordenação por data

### ✅ Categorias Personalizáveis
- [x] Categorias de receita e despesa
- [x] Cores e ícones customizáveis
- [x] Categorias padrão criadas automaticamente
- [x] Validação de uso antes da exclusão

### ✅ Importação de Dados
- [x] Upload de arquivos CSV
- [x] Validação de formato
- [x] Relatório de erros detalhado
- [x] Exemplo de arquivo para download
- [x] Mapeamento automático de categorias

### ✅ Multi-idioma
- [x] Português (padrão)
- [x] Inglês
- [x] Espanhol
- [x] Mudança dinâmica de idioma
- [x] Detecção automática do navegador

### ✅ Interface Responsiva
- [x] Design mobile-first
- [x] Bootstrap 5 integrado
- [x] Componentes acessíveis
- [x] Navegação por sidebar
- [x] Tema moderno

## 🧪 Exemplos de Uso

### 1. Criar Usuário via API
```bash
curl -X POST http://localhost:8001/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "João Silva",
    "email": "joao@exemplo.com",
    "password": "senha123"
  }'
```

### 2. Fazer Login
```bash
curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@exemplo.com",
    "password": "senha123"
  }'
```

### 3. Criar Transação Parcelada
```bash
curl -X POST http://localhost:8001/api/transactions \
  -H "Authorization: Bearer SEU_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Compra Parcelada",
    "amount": 1200.00,
    "type": "expense",
    "category_id": "category-id",
    "date": "2025-08-20T00:00:00Z",
    "installments": 12
  }'
```

### 4. Formato CSV para Importação
```csv
description,amount,type,category_name,date
Salário,3000.00,income,Salário,2025-08-01
Supermercado,250.50,expense,Alimentação,2025-08-02
Combustível,120.00,expense,Transporte,2025-08-03
```

## 🔧 Desenvolvimento

### Tecnologias Utilizadas

**Backend:**
- Flask 3.0.0
- PyMongo 4.6.0
- PyJWT 2.8.0
- Bcrypt 4.1.2
- Authlib 1.2.1
- Flask-CORS 4.0.0
- Pandas 2.1.4 (para CSV)

**Frontend:**
- React 18.2.0
- Vite 4.5.0
- React Router DOM 6.20.1
- Axios 1.6.2
- Bootstrap 5.3.2
- React-i18next 13.5.0
- Bootstrap Icons 1.11.2

### Padrões de Código
- **Backend**: Snake_case, docstrings em português, validação robusta
- **Frontend**: CamelCase, componentes funcionais, hooks customizados
- **API**: RESTful, status codes apropriados, respostas JSON padronizadas

## 🚀 Deploy e Produção

### Variáveis de Ambiente Críticas
```env
# Produção
SECRET_KEY=strong-random-secret-key-for-production
MONGO_URI=mongodb://production-host:27017
JWT_EXPIRES_HOURS=24
CORS_ORIGINS=https://yourdomain.com

# OAuth Produção
GOOGLE_CLIENT_ID=real-google-client-id
GOOGLE_CLIENT_SECRET=real-google-secret
```

### Checklist de Segurança
- [ ] Alterar SECRET_KEY para valor único e seguro
- [ ] Configurar CORS_ORIGINS apenas para domínios autorizados
- [ ] Configurar MongoDB com autenticação
- [ ] Habilitar HTTPS em produção
- [ ] Configurar rate limiting
- [ ] Validar certificados OAuth

---

**Desenvolvido com ❤️ para gestão financeira inteligente**
