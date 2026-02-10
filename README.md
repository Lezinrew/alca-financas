# Alca Finanças - Aplicação de Controle Financeiro Inteligente

Aplicação web full-stack de controle financeiro pessoal com funcionalidades modernas e interface intuitiva. Desenvolvida com foco em usabilidade, design moderno e gestão financeira completa com recursos de IA.

## 🚀 Características Principais

### 🤖 **Novidades - Login com IA**
- **Login Inteligente** - Acesso demo instantâneo com credenciais simuladas
- **Interface Moderna** - UI redesenhada com Tailwind CSS e componentes shadcn/ui
- **Dashboard Modernizado** - KPIs visuais e gráficos interativos
- **Experiência Aprimorada** - Animações, loading states e feedback visual

### Backend (Flask API)
- **Flask 3.0** com **Supabase (PostgreSQL)** para armazenamento de dados
- **Autenticação JWT** com tokens seguros HS256
- **OAuth 2.0** para login social (Google, Microsoft, Apple)
- **API RESTful** completa com endpoints para todas as funcionalidades
- **Importação CSV** para transações em massa
- **Categorização** inteligente de receitas e despesas
- **Criptografia bcrypt** para senhas
- **CORS configurável** para segurança
- **Row Level Security (RLS)** via Supabase para isolamento de dados

### Frontend (React SPA)
- **React 18** com Vite e TypeScript para desenvolvimento moderno
- **Tailwind CSS** + **shadcn/ui** para design system consistente
- **Recharts** para gráficos interativos profissionais
- **React Router DOM** para navegação SPA
- **Context API** para gerenciamento de estado global
- **Lucide React** para ícones modernos
- **Responsividade** completa para desktop, tablet e mobile
- **PWA Ready** para instalação em dispositivos

### 📊 Dashboard Moderno
- **4 KPIs Principais**: Saldo Atual, Receitas, Despesas, Tickets Abertos
- **Gráfico de Área**: Receitas vs. Despesas (últimos 12 meses)
- **Gráfico Pizza**: Distribuição de gastos por categoria
- **Transações Recentes**: Lista das últimas movimentações
- **Dados Mock**: Sistema de dados simulados para demonstração

### 🔐 Autenticação Avançada
- **Login Tradicional**: E-mail e senha com validação
- **Login com IA**: Acesso demo instantâneo (credenciais: demo@alca.fin)
- **Persistência Local**: Sessão mantida com localStorage
- **Proteção de Rotas**: Guards para páginas autenticadas
- **Token Expiration**: Tratamento inteligente de tokens expirados

## 🛠️ Tecnologias Utilizadas

### Frontend
- **React 18** - Biblioteca principal
- **TypeScript** - Tipagem estática
- **Vite** - Build tool moderna
- **Tailwind CSS** - Framework CSS utility-first
- **shadcn/ui** - Componentes UI modernos
- **Recharts** - Gráficos interativos
- **React Router DOM** - Roteamento
- **Lucide React** - Ícones
- **Axios** - Cliente HTTP
- **date-fns** - Manipulação de datas
- **Chart.js** - Gráficos complementares

### Ferramentas de Desenvolvimento
- **Vitest** - Framework de testes
- **Testing Library** - Testes de componentes
- **ESLint** - Linter JavaScript/TypeScript
- **PostCSS** - Processamento CSS
- **Autoprefixer** - Compatibilidade CSS

### Backend
- **Python 3.9+** com Flask 3.0
- **Supabase** (PostgreSQL) para banco de dados
- **JWT** para autenticação
- **bcrypt** para criptografia
- **Flask-CORS** para CORS
- **Pydantic** para validação de dados

## 🎯 Funcionalidades

### ✨ Principais
- [x] **Login Moderno** com UI redesenhada
- [x] **Login com IA** para acesso demo
- [x] **Dashboard Interativo** com KPIs e gráficos
- [x] **Gestão de Transações** (CRUD completo)
- [x] **Categorização** de receitas e despesas
- [x] **Gestão de Contas** bancárias
- [x] **Relatórios Visuais** com gráficos
- [x] **Importação CSV** de transações
- [x] **Configurações** personalizáveis
- [x] **Multi-idioma** (PT-BR, EN)

### 🔒 Segurança
- [x] Autenticação JWT segura
- [x] Proteção de rotas frontend
- [x] Validação de formulários
- [x] Sanitização de dados
- [x] Headers de segurança

### 📱 UX/UI
- [x] Design responsivo (mobile-first)
- [x] Modo claro profissional
- [x] Animações e transições suaves
- [x] Loading states e feedback visual
- [x] Acessibilidade (ARIA, navegação por teclado)

## 🚦 Como Executar

### Pré-requisitos
- **Node.js** 18+ e npm
- **Python** 3.9+ e pip
- **Supabase Account** (https://supabase.com) - Database as a Service

### 🎮 Início Rápido - Desenvolvimento

```bash
# Clone o repositório
git clone [repositório]
cd alca-financas

# 1. Configure o ambiente
cp .env.example .env
# Edite .env com suas credenciais do Supabase
# (Obtenha em: https://app.supabase.com/project/_/settings/api)

# 2. Execute o setup (instala dependências)
./scripts/dev/setup.sh

# 3. Inicie a aplicação
./scripts/dev/up.sh

# 4. Verifique a saúde do ambiente
./scripts/dev/doctor.sh

# 5. Acesse
# Frontend: http://localhost:3000
# Backend:  http://localhost:8001
# Use "Login com IA" para acesso demo instantâneo!

# 6. Para parar os serviços
./scripts/dev/down.sh
```

### ⚙️ Scripts de Desenvolvimento

```bash
# Setup e Gerenciamento
./scripts/dev/setup.sh     # Instala dependências (backend + frontend)
./scripts/dev/up.sh         # Inicia backend + frontend
./scripts/dev/up.sh --backend-only   # Apenas backend
./scripts/dev/up.sh --frontend-only  # Apenas frontend
./scripts/dev/down.sh       # Para todos os serviços
./scripts/dev/doctor.sh     # Valida saúde do ambiente

# Scripts Legados (ainda funcionam)
./alca_start_mac.sh        # Inicia aplicação (método antigo)
./alca_stop_mac.sh         # Para aplicação (método antigo)
```

### 🏭 Produção

```bash
# 1. Configure ambiente de produção
cp .env.example .env.production
# Edite .env.production com valores de produção
# IMPORTANTE: Use secrets fortes!

# 2. Build para produção
./scripts/prod/build.sh

# 3. Execute em produção
./scripts/prod/run.sh

# 4. Migre o banco de dados (se necessário)
./scripts/prod/migrate.sh
```

### ⚙️ Scripts do Frontend

```bash
cd frontend/

# Desenvolvimento
npm run dev          # Inicia servidor de desenvolvimento
npm run build        # Build para produção
npm run preview      # Preview da build

# Testes
npm run test         # Executa testes em modo watch
npm run test:run     # Executa testes uma vez
npm run test:ui      # Interface visual dos testes

# Qualidade
npm run lint         # Executa ESLint
```

### 🗄️ Backend Manual

```bash
cd backend/

# Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou: .venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar .env (na raiz do projeto)
# SUPABASE_URL=...
# SUPABASE_SERVICE_ROLE_KEY=...

# Executar
python app.py
# API disponível em http://localhost:8001
```

### 📦 Docker

```bash
# Desenvolvimento
docker-compose up -d

# Produção (com nginx)
docker-compose -f docker-compose.prod.yml up -d

# Apenas serviços específicos
docker-compose up backend    # Apenas backend
docker-compose up frontend   # Apenas frontend
```

## ⚙️ Configuração de Ambiente

### Variáveis de Ambiente Obrigatórias

```bash
# Supabase (obtenha em: https://app.supabase.com/project/_/settings/api)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...         # Para frontend (seguro)
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...  # Para backend (NUNCA exponha)

# Backend
SECRET_KEY=your-secret-key-here       # Use openssl rand -hex 32
JWT_SECRET=your-jwt-secret-here       # Use openssl rand -hex 32
BACKEND_PORT=8001

# Frontend
FRONTEND_PORT=3000
VITE_API_URL=http://localhost:8001

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Guias de Configuração

- **Índice de Documentação**: `docs/INDEX.md`
- **Guia Completo de Ambiente**: `docs/ENVIRONMENTS.md`
- **Guia de Migrações**: `scripts/db/README.md`
- **Supabase Setup**: `docs/SUPABASE-CHAVES.md`
- **Template de Variáveis**: `.env.example`

### Gerando Secrets Fortes

```bash
# Gerar secret aleatória (32 bytes)
openssl rand -hex 32

# Ou com Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 🎨 Demonstração

### 🔐 Acesso Demo
1. Acesse a aplicação
2. Clique em **"Login com IA"**
3. Explore o dashboard moderno com dados simulados

### 📊 Funcionalidades Demo
- **Dashboard**: 4 KPIs + 2 gráficos interativos
- **Transações**: Lista das movimentações recentes
- **Dados Realistas**: Valores simulados consistentes
- **Responsive**: Teste em diferentes tamanhos de tela

## 🧪 Testes

O projeto inclui testes unitários para funcionalidades críticas:

```bash
# Executar todos os testes
npm run test:run

# Testes em modo watch
npm run test

# Coverage dos testes
npm run test -- --coverage
```

### Cobertura Atual
- ✅ AuthContext (login, logout, persistência)
- ✅ Token expiration handling
- ✅ LocalStorage integration
- ✅ Loading states

## 📁 Estrutura do Projeto

```
alca-financas/
├── frontend/                 # Aplicação React
│   ├── src/
│   │   ├── components/      # Componentes React
│   │   │   ├── ui/         # Componentes UI base (shadcn/ui)
│   │   │   ├── auth/       # Componentes de autenticação
│   │   │   └── dashboard/  # Componentes do dashboard
│   │   ├── contexts/       # Context API (Auth, Theme)
│   │   ├── lib/            # Utilitários
│   │   ├── mocks/          # Dados simulados
│   │   ├── utils/          # Funções auxiliares
│   │   └── __tests__/      # Testes unitários
│   ├── package.json
│   └── tailwind.config.js
├── backend/                 # API Flask + Supabase
│   ├── routes/             # Endpoints da API
│   ├── repositories/       # Repositórios Supabase
│   ├── services/           # Lógica de negócio
│   ├── utils/              # Utilitários Python
│   ├── app.py              # Aplicação principal
│   └── requirements.txt    # Dependências Python
├── mobile/                  # App React Native (Expo)
│   └── package.json
├── scripts/                 # Scripts de automação
│   ├── dev/                # Scripts de desenvolvimento
│   │   ├── setup.sh        # Instala dependências
│   │   ├── up.sh           # Inicia serviços
│   │   ├── down.sh         # Para serviços
│   │   └── doctor.sh       # Valida ambiente
│   ├── prod/               # Scripts de produção
│   │   ├── build.sh        # Build para produção
│   │   ├── run.sh          # Executa em produção
│   │   └── migrate.sh      # Migra banco de dados
│   └── db/                 # Migrações SQL
│       └── README.md       # Guia de migrações
├── docs/                    # Documentação
│   └── ENVIRONMENTS.md     # Guia de env vars
├── .env.example            # Template de variáveis de ambiente
├── docker-compose.yml      # Docker para desenvolvimento
├── docker-compose.prod.yml # Docker para produção
├── nginx.conf              # Configuração nginx (prod)
└── README.md              # Este arquivo
```

## 🔧 Troubleshooting

### Backend não inicia

```bash
# Verifique logs
tail -f logs/backend-*.log

# Valide ambiente
./scripts/dev/doctor.sh

# Verifique Supabase
curl -H "apikey: YOUR_ANON_KEY" \
     https://your-project.supabase.co/rest/v1/
```

### Frontend não conecta ao Backend

```bash
# Verifique se backend está rodando
curl http://localhost:8001/api/health

# Verifique VITE_API_URL no frontend/.env
cat frontend/.env

# Verifique CORS no backend
# Deve incluir http://localhost:3000
```

### Erros CORS

Adicione a origem ao `.env`:
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000
```

Reinicie o backend após alterar CORS.

### "Port already in use"

```bash
# Libere as portas
./scripts/dev/down.sh

# Ou manualmente
lsof -ti:8001 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
```

### Dependências desatualizadas

```bash
# Re-executar setup
./scripts/dev/setup.sh

# Ou manualmente
cd backend && pip install -r requirements.txt
cd frontend && npm ci
```

## 🤝 Contribuição

1. **Fork** o projeto
2. **Clone** sua fork
3. **Crie** uma branch para sua feature
4. **Commit** suas mudanças
5. **Push** para sua branch
6. **Abra** um Pull Request

### 📋 Guidelines
- Use TypeScript para novo código
- Mantenha cobertura de testes
- Siga o padrão de código existente
- Documente mudanças no README
- Execute `./scripts/dev/doctor.sh` antes de commit

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para detalhes.

## 🎯 Roadmap

### 📈 Próximas Funcionalidades
- [ ] **Modo Escuro** completo
- [ ] **PWA** com install prompt
- [ ] **Notificações** push
- [ ] **Backup** automático
- [ ] **Relatórios** PDF
- [ ] **Multi-contas** bancárias
- [ ] **Metas** financeiras
- [ ] **Lembretes** de pagamento

### 🔧 Melhorias Técnicas
- [ ] **Storybook** para componentes
- [ ] **E2E Tests** com Playwright
- [ ] **CI/CD** com GitHub Actions
- [ ] **Performance** otimizations
- [ ] **Bundle** analysis
- [ ] **SEO** improvements

---

### 🚀 **Dica de Uso**
Para uma experiência completa, use o **"Login com IA"** que te dá acesso instantâneo ao dashboard com dados realistas. Perfeito para demonstrações e testes!

**Desenvolvido com ❤️ para simplificar seu controle financeiro**