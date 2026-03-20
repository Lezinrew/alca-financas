# 📚 Índice Geral - Alça Finanças

Documentação completa do projeto organizada por categoria.

---

## 🚀 Início Rápido

| Arquivo | Descrição | Quando Usar |
|---------|-----------|-------------|
| **[PROXIMO-PASSO.md](./PROXIMO-PASSO.md)** | **⭐ Comece aqui!** Próximo passo: deploy produção | Agora mesmo |
| **[GUIA-RAPIDO.md](./GUIA-RAPIDO.md)** | Referência rápida de comandos | Consulta rápida |
| **[README-QUICKSTART.md](./README-QUICKSTART.md)** | Como rodar localmente | Primeira vez |
| **[README.md](./README.md)** | Documentação principal do projeto | Visão geral |

---

## 🧪 Testes e Automação

| Arquivo | Descrição | Quando Usar |
|---------|-----------|-------------|
| **[docs/TESTING.md](./docs/TESTING.md)** | Guia completo de testes (60+ páginas) | Aprender sobre testes |
| **[CHANGELOG-TESTES.md](./CHANGELOG-TESTES.md)** | O que foi implementado na estrutura de testes | Entender mudanças |

---

## 🌐 Produção

| Arquivo | Descrição | Quando Usar |
|---------|-----------|-------------|
| **[docs/SETUP-PRODUCAO.md](./docs/SETUP-PRODUCAO.md)** | Guia completo de setup (alcahub.com.br) | Configurar servidor |
| **[.github/SECRETS-TEMPLATE.md](./.github/SECRETS-TEMPLATE.md)** | Como configurar secrets GitHub | Configurar CI/CD |

---

## 🔧 Scripts Disponíveis

### Desenvolvimento

| Script | Comando | Descrição |
|--------|---------|-----------|
| **quick-start.sh** | `npm start` | ⭐ Inicia tudo (sem Docker obrigatório) |
| **deploy-local.sh** | `npm run dev:docker` | Inicia com Docker Compose |
| **stop-local.sh** | `npm stop` | Para todos os serviços |
| **start-mongodb.sh** | `npm run mongo` | Apenas MongoDB |

### Testes

| Script | Comando | Descrição |
|--------|---------|-----------|
| **run-tests.sh** | `npm test` | Todos os testes |
| **run-tests.sh** | `npm run test:unit` | Apenas unitários |
| **run-tests.sh** | `npm run test:e2e` | Testes E2E local |
| **run-tests.sh** | `npm run test:e2e:prod` | Testes E2E produção |

### Produção

| Script | Comando | Descrição |
|--------|---------|-----------|
| **setup-github-secrets.sh** | `./scripts/setup-github-secrets.sh` | Configurar secrets (interativo) |
| **deploy-production.sh** | `npm run deploy:prod` | Deploy para alcahub.com.br |
| **backup.sh** | `npm run backup` | Backup BD e arquivos |

---

## 📁 Estrutura do Projeto

```
alca-financas/
├── 📚 Documentação Principal
│   ├── README.md                    # Documentação geral
│   ├── INDICE.md                    # Este arquivo
│   ├── PROXIMO-PASSO.md            # ⭐ Próximo passo
│   ├── GUIA-RAPIDO.md              # Referência rápida
│   ├── README-QUICKSTART.md        # Início rápido
│   └── CHANGELOG-TESTES.md         # Mudanças recentes
│
├── 📖 docs/
│   ├── TESTING.md                   # Guia completo de testes
│   ├── SETUP-PRODUCAO.md           # Setup servidor produção
│   ├── backend_api_qa_checklist.md # Checklist QA API
│   └── backend_refactor_prompt.md  # Histórico refatoração
│
├── 🤖 .github/
│   ├── workflows/
│   │   ├── ci.yml                  # Pipeline de testes
│   │   └── deploy-production.yml  # Deploy automático
│   └── SECRETS-TEMPLATE.md        # Template secrets
│
├── 🎬 scripts/
│   ├── quick-start.sh              # ⭐ Início rápido
│   ├── start-mongodb.sh            # MongoDB
│   ├── deploy-local.sh             # Deploy local completo
│   ├── stop-local.sh               # Parar serviços
│   ├── run-tests.sh                # Executar testes
│   ├── deploy-production.sh        # Deploy produção
│   ├── backup.sh                   # Backup
│   └── setup-github-secrets.sh    # Setup secrets
│
├── 🔧 backend/
│   ├── app.py                      # API Flask
│   ├── routes/                     # Endpoints
│   ├── services/                   # Lógica de negócio
│   ├── utils/                      # Utilitários
│   └── tests/                      # Testes
│       ├── unit/                   # Unitários
│       └── integration/            # Integração
│
├── 🎨 frontend/
│   ├── src/
│   │   ├── components/             # Componentes React
│   │   ├── contexts/               # Context API
│   │   ├── utils/                  # Utilitários
│   │   └── __tests__/              # Testes unitários
│   └── e2e/                        # Testes E2E
│
├── 📱 mobile/
│   ├── src/                        # React Native
│   └── ...
│
├── 📊 logs/
│   ├── backend.log                 # Logs backend
│   └── frontend.log                # Logs frontend
│
└── ⚙️ Configuração
    ├── .env.example                # Template variáveis
    ├── package.json                # Scripts root
    ├── docker-compose.yml          # Orquestração
    └── ...
```

---

## 🎯 Fluxos Comuns

### 1. Primeira Vez no Projeto

```
1. README.md → Entender o projeto
2. README-QUICKSTART.md → Instalar dependências
3. npm start → Rodar localmente
4. http://localhost:3000 → Testar
```

### 2. Desenvolvedor Novo

```
1. README-QUICKSTART.md → Setup local
2. docs/TESTING.md → Aprender sobre testes
3. npm start → Desenvolver
4. npm test → Testar mudanças
```

### 3. Deploy para Produção

```
1. PROXIMO-PASSO.md → Entender o que fazer
2. docs/SETUP-PRODUCAO.md → Configurar servidor
3. ./scripts/setup-github-secrets.sh → Configurar secrets
4. git push origin main → Deploy automático
```

### 4. Resolver Problemas

```
1. GUIA-RAPIDO.md → Problemas comuns
2. tail -f logs/*.log → Ver logs
3. docs/TESTING.md → Troubleshooting
4. GitHub Issues → Reportar bug
```

---

## 📖 Por Categoria

### Para Desenvolvedores

- **Início:** [README-QUICKSTART.md](./README-QUICKSTART.md)
- **Comandos:** [GUIA-RAPIDO.md](./GUIA-RAPIDO.md)
- **API:** [docs/backend_api_qa_checklist.md](./docs/backend_api_qa_checklist.md)
- **Testes:** [docs/TESTING.md](./docs/TESTING.md)

### Para DevOps

- **Setup:** [docs/SETUP-PRODUCAO.md](./docs/SETUP-PRODUCAO.md)
- **Secrets:** [.github/SECRETS-TEMPLATE.md](./.github/SECRETS-TEMPLATE.md)
- **CI/CD:** [.github/workflows/](./github/workflows/)
- **Scripts:** [scripts/](./scripts/)

### Para QA

- **Testes:** [docs/TESTING.md](./docs/TESTING.md)
- **Checklist:** [docs/backend_api_qa_checklist.md](./docs/backend_api_qa_checklist.md)
- **E2E:** [frontend/e2e/](./frontend/e2e/)

### Para Gestores

- **Visão Geral:** [README.md](./README.md)
- **Roadmap:** [README.md](./README.md) (Seção Roadmap)
- **Changelog:** [CHANGELOG-TESTES.md](./CHANGELOG-TESTES.md)

---

## 🔍 Busca Rápida

### Como fazer...

| Tarefa | Arquivo |
|--------|---------|
| Rodar localmente | [README-QUICKSTART.md](./README-QUICKSTART.md) |
| Rodar testes | [docs/TESTING.md](./docs/TESTING.md) |
| Fazer deploy | [PROXIMO-PASSO.md](./PROXIMO-PASSO.md) |
| Configurar servidor | [docs/SETUP-PRODUCAO.md](./docs/SETUP-PRODUCAO.md) |
| Ver comandos | [GUIA-RAPIDO.md](./GUIA-RAPIDO.md) |
| Resolver problemas | [GUIA-RAPIDO.md](./GUIA-RAPIDO.md) (Problemas Comuns) |
| Configurar GitHub | [.github/SECRETS-TEMPLATE.md](./.github/SECRETS-TEMPLATE.md) |
| Backup do BD | [scripts/backup.sh](./scripts/backup.sh) |

---

## 📊 Estatísticas do Projeto

- **Documentação:** 12+ arquivos
- **Scripts:** 8 scripts automatizados
- **Testes:** 3 tipos (unit, integration, e2e)
- **Browsers:** 5 testados
- **Ambientes:** 2 (local, production)
- **Pipeline:** CI/CD completo
- **Cobertura:** 70%+ (meta)

---

## 🆘 Precisa de Ajuda?

1. **Início Rápido:** [GUIA-RAPIDO.md](./GUIA-RAPIDO.md)
2. **FAQ:** [README.md](./README.md) (Seção Contribuição)
3. **Issues:** https://github.com/seu-usuario/alca-financas/issues
4. **Discussions:** https://github.com/seu-usuario/alca-financas/discussions

---

## ✅ Checklist de Onboarding

Para novos desenvolvedores:

- [ ] Leu [README.md](./README.md)
- [ ] Configurou ambiente com [README-QUICKSTART.md](./README-QUICKSTART.md)
- [ ] Rodou `npm start` com sucesso
- [ ] Testou login no app
- [ ] Executou `npm test`
- [ ] Leu [docs/TESTING.md](./docs/TESTING.md)
- [ ] Salvou [GUIA-RAPIDO.md](./GUIA-RAPIDO.md) nos favoritos

---

**Navegação:**
- 🏠 [Início](./README.md)
- 🚀 [Próximo Passo](./PROXIMO-PASSO.md)
- ⚡ [Guia Rápido](./GUIA-RAPIDO.md)
- 📖 [Testes](./docs/TESTING.md)
