# Alca Finanças

Aplicação web full-stack de controle financeiro pessoal. Stack moderno com React/TypeScript no frontend e Flask/Python no backend, utilizando Supabase (PostgreSQL) como database.

## Características Principais

### Autenticação
- Supabase Auth nativo (migração completa de MongoDB)
- Sistema de recuperação de senha via email
- Token management com storage seguro e renovação automática
- Login demo para testes (credenciais: demo@alca.fin)
- Session management com localStorage

### Backend
- Flask 3.0 + Supabase (PostgreSQL)
- Supabase Auth com Row Level Security (RLS)
- Email service para notificações e password reset
- API RESTful com endpoints para transações, contas e categorias
- Importação CSV em batch
- Auto-detecção de contas em transações
- CORS configurável

### Frontend
- React 18 + Vite + TypeScript
- Tailwind CSS + shadcn/ui
- Recharts para visualizações
- React Router DOM para navegação
- Context API para state management
- Lucide React para ícones
- Responsive design (mobile-first)
- PWA ready

### Dashboard
- KPIs principais: saldo atual, receitas, despesas, tickets abertos
- Gráfico de área: receitas vs despesas (12 meses)
- Gráfico pizza: distribuição por categoria
- Lista de transações recentes
- Mock data para demo


## Stack

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

### Dev Tools
- Vitest + Testing Library
- ESLint
- PostCSS + Autoprefixer

### Backend
- Python 3.9+ + Flask 3.0
- Supabase (PostgreSQL)
- JWT + bcrypt
- Flask-CORS
- Pydantic

## Funcionalidades

### Core
- [x] Supabase Auth com password recovery
- [x] Email service integrado
- [x] Dashboard com KPIs e gráficos (Recharts)
- [x] CRUD completo de transações
- [x] Categorização de receitas/despesas
- [x] Gestão de contas bancárias
- [x] Importação CSV
- [x] Auto-detecção de contas
- [x] Relatórios visuais

### Segurança
- [x] Row Level Security (RLS)
- [x] JWT com token rotation
- [x] Route guards (frontend/backend)
- [x] Input validation e sanitization
- [x] Security headers
- [x] Data isolation per user

### UI/UX
- [x] Responsive design (mobile-first)
- [x] Loading states
- [x] Error handling
- [x] Accessibility (ARIA)

## Setup

### Pré-requisitos
- Node.js 18+
- Python 3.9+
- Supabase account (https://supabase.com)

### Quick Start

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

# 6. Para parar
./scripts/dev/down.sh
```

### Scripts de Dev

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

### Produção

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

### Frontend Scripts

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

### Backend Manual

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

### Docker

```bash
# Desenvolvimento
docker-compose up -d

# Produção (com nginx)
docker-compose -f docker-compose.prod.yml up -d

# Apenas serviços específicos
docker-compose up backend    # Apenas backend
docker-compose up frontend   # Apenas frontend
```

## Configuração

### Environment Variables

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
- **Recuperação de Senha**: `docs/RECUPERACAO-SENHA-SUPABASE.md`
- **Migração Completa**: `SUPABASE_MIGRATION_COMPLETE.md`
- **Template de Variáveis**: `.env.example`

### Gerando Secrets Fortes

```bash
# Gerar secret aleatória (32 bytes)
openssl rand -hex 32

# Ou com Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Demo

Acesse a aplicação e use o login demo (credenciais: demo@alca.fin) para testar com dados simulados.

## Testes

```bash
# Executar todos os testes
npm run test:run

# Testes em modo watch
npm run test

# Coverage dos testes
npm run test -- --coverage
```

### Coverage
- AuthContext (login, logout, persistência)
- Token expiration handling
- LocalStorage integration
- Loading states

## Estrutura

```
alca-financas/
├── frontend/                 # Aplicação React
│   ├── src/
│   │   ├── components/      # Componentes React
│   │   │   ├── ui/         # Componentes UI base (shadcn/ui)
│   │   │   │   └── gradient-button.tsx  # Botão com gradiente
│   │   │   ├── auth/       # Componentes de autenticação
│   │   │   │   ├── Login.tsx
│   │   │   │   ├── Register.tsx
│   │   │   │   ├── ForgotPassword.tsx   # NEW
│   │   │   │   └── ResetPassword.tsx    # NEW
│   │   │   └── dashboard/  # Componentes do dashboard
│   │   ├── contexts/       # Context API (Auth, Theme)
│   │   ├── lib/            # Utilitários
│   │   ├── mocks/          # Dados simulados
│   │   ├── utils/          # Funções auxiliares
│   │   │   ├── api.ts
│   │   │   └── tokenStorage.ts  # NEW - Token management
│   │   └── __tests__/      # Testes unitários
│   ├── package.json
│   └── tailwind.config.js
├── backend/                 # API Flask + Supabase
│   ├── routes/             # Endpoints da API
│   │   ├── auth.py         # Autenticação (Supabase)
│   │   ├── transactions.py
│   │   ├── accounts.py
│   │   ├── categories.py
│   │   └── dashboard.py
│   ├── repositories/       # Repositórios Supabase
│   │   └── transaction_repository_supabase.py
│   ├── services/           # Lógica de negócio
│   │   ├── supabase_auth_service.py  # NEW
│   │   ├── email_service.py          # NEW
│   │   ├── account_detector.py
│   │   ├── account_service.py
│   │   ├── category_service.py
│   │   ├── transaction_service.py
│   │   └── report_service.py
│   ├── utils/              # Utilitários Python
│   │   ├── auth_utils.py
│   │   └── auth_utils_supabase.py    # NEW
│   ├── scripts/
│   │   └── set_user_password.py      # NEW
│   ├── database/           # Conexão Supabase
│   ├── app.py              # Aplicação principal
│   └── requirements.txt    # Dependências Python
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
│   ├── db/                 # Migrações SQL e scripts DB
│   │   └── README.md       # Guia de migrações
│   └── legacy/             # Scripts antigos
│       └── mongo/          # Scripts MongoDB (deprecated)
├── docs/                    # Documentação
│   ├── INDEX.md            # Índice da documentação
│   ├── ENVIRONMENTS.md     # Guia de env vars
│   ├── SUPABASE-CHAVES.md  # Configuração Supabase
│   ├── RECUPERACAO-SENHA-SUPABASE.md  # Guia de recuperação
│   ├── CONTEXTO-TELA-LOGIN.md
│   └── legacy/             # Docs antigas
│       └── mongo/          # Documentação MongoDB (deprecated)
├── .env.example            # Template de variáveis de ambiente
├── docker-compose.yml      # Docker para desenvolvimento
├── docker-compose.prod.yml # Docker para produção (com nginx)
├── nginx.conf              # Configuração nginx (prod)
├── SUPABASE_MIGRATION_COMPLETE.md  # Relatório de migração
└── README.md              # Este arquivo
```

## Troubleshooting

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

## Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para sua branch
5. Abra um Pull Request

### Guidelines
- Use TypeScript para novo código
- Mantenha cobertura de testes
- Siga o padrão de código existente
- Execute `./scripts/dev/doctor.sh` antes de commit

## Licença

MIT License

## Roadmap

### Implementado
- [x] Migração MongoDB → Supabase
- [x] Password recovery via email
- [x] Email service
- [x] Token management com rotation
- [x] Auto-detecção de contas
- [x] Scripts organizados (dev/, prod/, db/)
- [x] Docker para produção

### Próximas Features
- [ ] Dark mode
- [ ] PWA install prompt
- [ ] Push notifications
- [ ] Backup automático
- [ ] Relatórios PDF
- [ ] Metas financeiras
- [ ] 2FA
- [ ] OAuth (Google, Microsoft, Apple)

### Melhorias Técnicas
- [x] CI/CD com GitHub Actions (parcial)
- [ ] Storybook
- [ ] E2E tests completo (Playwright)
- [ ] Performance optimization
- [ ] Bundle analysis
- [ ] Monitoring (Sentry)
- [ ] Analytics (PostHog)

---

## Documentação

### Principais Docs
- [SUPABASE_MIGRATION_COMPLETE.md](SUPABASE_MIGRATION_COMPLETE.md) - Relatório da migração
- [QUICKSTART.md](QUICKSTART.md) - Guia rápido
- [docs/INDEX.md](docs/INDEX.md) - Índice completo
- [docs/RECUPERACAO-SENHA-SUPABASE.md](docs/RECUPERACAO-SENHA-SUPABASE.md) - Setup de password recovery

### Setup Guides
1. Setup inicial: Siga "Quick Start" acima
2. Configurar Supabase: `docs/SUPABASE-CHAVES.md`
3. Password recovery: `docs/RECUPERACAO-SENHA-SUPABASE.md`
4. Deploy produção: Scripts em `scripts/prod/`