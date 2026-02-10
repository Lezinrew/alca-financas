# Índice de Documentação - Alça Finanças

Este documento organiza toda a documentação do projeto por categoria.

---

## 📚 Documentação Principal

### Início Rápido
- [README.md](../README.md) - Visão geral do projeto
- [QUICKSTART.md](../QUICKSTART.md) - Guia de início rápido (5 minutos)
- [GUIA-RAPIDO.md](../GUIA-RAPIDO.md) - Guia rápido alternativo

### Implementação e Arquitetura
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - Resumo completo da implementação de scripts e ambiente
- [SUPABASE_MIGRATION_COMPLETE.md](../SUPABASE_MIGRATION_COMPLETE.md) - Migração completa de MongoDB para Supabase
- [PROMPT-AVALIACAO-ESTRUTURA.md](../PROMPT-AVALIACAO-ESTRUTURA.md) - Avaliação da estrutura do projeto
- [TODO-MELHORIAS-ESTRUTURA.md](TODO-MELHORIAS-ESTRUTURA.md) - Lista de melhorias identificadas

---

## 🔧 Configuração

### Ambiente
- [ENVIRONMENTS.md](ENVIRONMENTS.md) - Guia completo de variáveis de ambiente
- [.env.example](../.env.example) - Template de configuração

### Banco de Dados
- [SUPABASE-CHAVES.md](SUPABASE-CHAVES.md) - Como obter chaves do Supabase
- [RECUPERACAO-SENHA-SUPABASE.md](RECUPERACAO-SENHA-SUPABASE.md) - Recuperação de senha com Supabase
- [GUIDE-DATABASE-MANAGEMENT.md](../GUIDE-DATABASE-MANAGEMENT.md) - Gerenciamento de banco de dados
- [scripts/db/README.md](../scripts/db/README.md) - Guia de migrações

### Autenticação
- [CONFIGURAR-OAUTH.md](CONFIGURAR-OAUTH.md) - Configuração geral de OAuth
- [CONFIGURAR-GOOGLE-OAUTH.md](CONFIGURAR-GOOGLE-OAUTH.md) - Configuração específica do Google OAuth
- [PROMPT-BROWSER-AGENT-GOOGLE-OAUTH.md](PROMPT-BROWSER-AGENT-GOOGLE-OAUTH.md) - Prompt para configuração assistida
- [CONTEXTO-TELA-LOGIN.md](CONTEXTO-TELA-LOGIN.md) - Contexto da tela de login
- [LOGIN-UPGRADE-ENTREGA.md](LOGIN-UPGRADE-ENTREGA.md) - Melhorias no sistema de login

---

## 🚀 Deploy e Produção

### Deploy
- [DADOS-DEPLOY.md](DADOS-DEPLOY.md) - Dados e configurações de deploy
- [SEGURANCA-SERVIDOR.md](SEGURANCA-SERVIDOR.md) - Segurança do servidor em produção

### Scripts
- [scripts/dev/](../scripts/dev/) - Scripts de desenvolvimento (setup.sh, up.sh, down.sh, doctor.sh)
- [scripts/prod/](../scripts/prod/) - Scripts de produção (build.sh, run.sh, migrate.sh)
- [alca_start_mac.sh](../alca_start_mac.sh) - Script de início rápido (compatível com macOS/Linux)

---

## 🧪 Testes

### Documentação de Testes
- [TESTING.md](TESTING.md) - Guia de testes
- [CHANGELOG-TESTES.md](../CHANGELOG-TESTES.md) - Histórico de alterações nos testes

### Scripts de Testes
- [scripts/run-tests.sh](../scripts/run-tests.sh) - Executar testes

---

## ✨ Features e Correções

### Features Implementadas
- [FEATURE-CREDIT-CARDS.md](../FEATURE-CREDIT-CARDS.md) - Sistema de cartões de crédito
- [FEATURE-CREDIT-CARD-EXPENSE-FORM.md](../FEATURE-CREDIT-CARD-EXPENSE-FORM.md) - Formulário de despesas com cartão
- [FEATURE-CURRENCY-INPUT.md](../FEATURE-CURRENCY-INPUT.md) - Input de moeda
- [FEATURE-DELETE-PLANNING.md](../FEATURE-DELETE-PLANNING.md) - Exclusão de planejamentos

### Correções
- [FIX-ACCESSIBILITY-WARNINGS.md](../FIX-ACCESSIBILITY-WARNINGS.md) - Correções de acessibilidade
- [FIX-ACCOUNTS-ERROR.md](../FIX-ACCOUNTS-ERROR.md) - Correção de erro em contas
- [FIX-AUTH-CONTEXT-ERROR.md](../FIX-AUTH-CONTEXT-ERROR.md) - Correção de erro no contexto de autenticação
- [FIX-CORS.md](../FIX-CORS.md) - Correção de problemas CORS
- [FIX-DROPDOWN-MENU.md](../FIX-DROPDOWN-MENU.md) - Correção de dropdown menu
- [FIX-PORT-CONFLICT.md](../FIX-PORT-CONFLICT.md) - Correção de conflitos de porta
- [FIX-VITE-API-URL.md](../FIX-VITE-API-URL.md) - Correção de URL da API no Vite

---

## 📊 Análise e Refatoração

### Análise
- [ANALISE-ALCA-FINANCAS.md](ANALISE-ALCA-FINANCAS.md) - Análise completa do projeto
- [backend_api_qa_checklist.md](backend_api_qa_checklist.md) - Checklist de QA da API do backend

### Refatoração
- [backend_refactor_prompt.md](backend_refactor_prompt.md) - Prompt para refatoração do backend
- [MELHORIAS-ALCA-START.md](../MELHORIAS-ALCA-START.md) - Melhorias no script de início

---

## 📝 Prompts e Auxiliares

### Prompts
- [PROMPT_DBEXPERT.md](../PROMPT_DBEXPERT.md) - Prompt para especialista em banco de dados
- [PROMPT_DBEXPERT_CONCISO.txt](../PROMPT_DBEXPERT_CONCISO.txt) - Versão concisa
- [PROMPT_MIGRACAO_FIREBASE.md](../PROMPT_MIGRACAO_FIREBASE.md) - Prompt para migração Firebase
- [PROMPT_LOGO_GEMINI.md](../PROMPT_LOGO_GEMINI.md) - Prompt para geração de logo

---

## 🗂️ Documentação Legada

### MongoDB (Legado)
- [docs/legacy/mongo/](legacy/mongo/) - Documentação MongoDB antiga
  - ADICIONAR-IP-MONGODB-ATLAS.md
  - DEPLOY-HOSTINGER.md
  - OBTER-CONNECTION-STRING-MONGODB.md
  - SETUP-PRODUCAO.md

### Scripts MongoDB (Legado)
- [scripts/legacy/mongo/](../scripts/legacy/mongo/) - Scripts MongoDB antigos
  - backup.sh
  - clear-all-databases.sh
  - install-mongodb-local.py
  - start-mongodb.sh
  - update-mongo-uri-*.sh

---

## 🔍 Como Usar Este Índice

### Por Necessidade

**Quero começar rapidamente:**
1. [QUICKSTART.md](../QUICKSTART.md)
2. [ENVIRONMENTS.md](ENVIRONMENTS.md)
3. `./scripts/dev/setup.sh && ./scripts/dev/up.sh`

**Preciso configurar o ambiente:**
1. [ENVIRONMENTS.md](ENVIRONMENTS.md)
2. [SUPABASE-CHAVES.md](SUPABASE-CHAVES.md)
3. [.env.example](../.env.example)

**Vou fazer deploy:**
1. [scripts/prod/README.md](../scripts/prod/) (se existir) ou [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
2. [DADOS-DEPLOY.md](DADOS-DEPLOY.md)
3. [SEGURANCA-SERVIDOR.md](SEGURANCA-SERVIDOR.md)

**Preciso configurar OAuth:**
1. [CONFIGURAR-OAUTH.md](CONFIGURAR-OAUTH.md)
2. [CONFIGURAR-GOOGLE-OAUTH.md](CONFIGURAR-GOOGLE-OAUTH.md)

**Problemas? Consulte:**
1. [FIX-*.md](../) - Documentos de correções
2. [TODO-MELHORIAS-ESTRUTURA.md](TODO-MELHORIAS-ESTRUTURA.md)
3. [TESTING.md](TESTING.md)

---

## 📋 Convenções

### Nomenclatura de Arquivos

- **FEATURE-*.md** - Documentação de funcionalidades
- **FIX-*.md** - Documentação de correções
- **PROMPT-*.md** - Prompts para IA/assistentes
- **GUIDE-*.md** - Guias específicos
- **README.md** - Documentação de diretório ou projeto
- **INDEX.md** - Este arquivo (índice geral)

### Estrutura de Diretórios

```
alca-financas/
├── docs/                    # Documentação principal
│   ├── legacy/             # Documentação legada
│   └── INDEX.md           # Este arquivo
├── scripts/                # Scripts de automação
│   ├── dev/               # Scripts de desenvolvimento
│   ├── prod/              # Scripts de produção
│   ├── db/                # Scripts de banco de dados
│   └── legacy/            # Scripts legados
├── backend/               # Código do backend
├── frontend/              # Código do frontend
└── *.md                   # Documentação na raiz
```

---

## 🆕 Última Atualização

**Data:** 2026-02-09
**Status:** Projeto migrado 100% para Supabase (PostgreSQL)
**Stack:** Flask (Backend) + React/Vite (Frontend) + Supabase (Database)

---

**Nota:** Este índice é mantido manualmente. Se você adicionar nova documentação, atualize este arquivo.
