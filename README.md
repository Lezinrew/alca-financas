# Alca Finanças - Aplicação de Controle Financeiro Inteligente

Aplicação web full-stack de controle financeiro pessoal com funcionalidades modernas e interface intuitiva. Desenvolvida com foco em usabilidade, design moderno e gestão financeira completa com recursos de IA.

## 🚀 Características Principais

### 🤖 **Novidades - Login com IA**
- **Login Inteligente** - Acesso demo instantâneo com credenciais simuladas
- **Interface Moderna** - UI redesenhada com Tailwind CSS e componentes shadcn/ui
- **Dashboard Modernizado** - KPIs visuais e gráficos interativos
- **Experiência Aprimorada** - Animações, loading states e feedback visual

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

### Backend (Original)
- **Python 3.9+** com Flask
- **MongoDB** para banco de dados
- **JWT** para autenticação
- **bcrypt** para criptografia
- **Flask-CORS** para CORS

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
- **MongoDB** (local ou Atlas)

### 🎮 Início Rápido - Frontend

```bash
# Clone o repositório
git clone [repositório]
cd alca-financas/frontend

# Instale as dependências
npm install

# Execute o servidor de desenvolvimento
npm install

# Acesse http://localhost:3000
# Use "Login com IA" para acesso demo instantâneo!
```

### ⚙️ Scripts Disponíveis

```bash
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

### 🗄️ Backend (Original)

```bash
cd backend/

# Instale dependências Python
pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações

# Execute a API
python app.py
# API disponível em http://localhost:5000
```

### 📦 Docker (Opcional)

```bash
# Execute todo o stack
docker-compose up -d

# Apenas frontend
docker-compose up frontend

# Apenas backend + MongoDB
docker-compose up backend mongo
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
│   │   │   ├── ui/         # Componentes UI base
│   │   │   ├── auth/       # Componentes de autenticação
│   │   │   └── dashboard/  # Componentes do dashboard
│   │   ├── contexts/       # Context API
│   │   ├── lib/            # Utilitários
│   │   ├── mocks/          # Dados simulados
│   │   ├── utils/          # Funções auxiliares
│   │   └── __tests__/      # Testes unitários
│   ├── package.json
│   └── tailwind.config.js
├── backend/                 # API Flask
│   ├── routes/             # Endpoints da API
│   ├── services/           # Lógica de negócio
│   └── utils/              # Utilitários Python
├── docker-compose.yml      # Orquestração Docker
└── README.md              # Este arquivo
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