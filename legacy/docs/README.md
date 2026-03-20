# Documentação Legacy

Documentação arquivada de features implementadas, fixes aplicados, migrações concluídas e planejamento histórico.

## 📁 Estrutura

```
legacy/docs/
├── features/           # Features implementadas (FEATURE-*.md)
├── fixes/              # Fixes aplicados (FIX-*.md)
├── migrations/         # Migrações concluídas (Supabase, MongoDB, etc)
├── prompts/            # Prompts de desenvolvimento usados
├── planning/           # Checklists e planejamento de fases concluídas
└── *.md                # Summaries, changelogs, audits, guides antigos
```

## 📋 Conteúdo

### Features (features/)
Documentação de features implementadas:
- `FEATURE-CREDIT-CARD-EXPENSE-FORM.md`
- `FEATURE-CREDIT-CARDS.md`
- `FEATURE-CURRENCY-INPUT.md`
- `FEATURE-DELETE-PLANNING.md`

### Fixes (fixes/)
Correções aplicadas ao projeto:
- `FIX-ACCESSIBILITY-WARNINGS.md`
- `FIX-ACCOUNTS-ERROR.md`
- `FIX-AUTH-CONTEXT-ERROR.md`
- `FIX-CORS.md`
- `FIX-DROPDOWN-MENU.md`
- `FIX-LOGIN-PROBLEM.md`
- `FIX-PORT-CONFLICT.md`
- `FIX-VITE-API-URL.md`

### Migrações (migrations/)
Documentação de migrações concluídas:
- `MIGRACAO_VALIDACAO.md` - Validação de migração MongoDB → Supabase
- `MIGRATION_FIX_SUMMARY.md` - Fixes durante migração
- `SUPABASE_MIGRATION_COMPLETE.md` - Migração Supabase concluída
- `backend_migrations.txt` - Histórico de migrations

### Prompts (prompts/)
Prompts usados durante desenvolvimento:
- `PROMPT-AVALIACAO-ESTRUTURA.md`
- `PROMPT_DBEXPERT.md`
- `PROMPT_DBEXPERT_CONCISO.txt`
- `PROMPT_LOGO_GEMINI.md`
- `PROMPT_MIGRACAO_FIREBASE.md`

### Planning (planning/)
Planejamento de fases concluídas:
- `CHECKLIST_FASE1.md` - Checklist Fase 1 (concluída)
- `MELHORIAS-ALCA-START.md` - Melhorias planejadas (aplicadas)
- `PROXIMO-PASSO.md` - Próximos passos históricos

### Outros Documentos

#### Summaries & Changelogs
- `ADDITIONAL_SCRIPTS_UPDATED.md`
- `CHANGELOG-TESTES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `PATCHES_DIFF.md`
- `PATCH_SUMMARY.md`
- `README_CORREÇÕES.md`
- `REFACTORING_COMPLETE.md`
- `UPDATE-CREDIT-CARDS-NO-MOCK-DATA.md`

#### Security Audits
- `SECURITY_AUDIT_REPORT.md`
- `SECURITY_FIXES_TODO.md`
- `SECURITY_FIX_FASE1_GUIA.md`

#### Chatbot (descontinuado)
- `CHATBOT_DEPLOYMENT_GUIDE.md`
- `CHATBOT_SECURITY.md`
- `OPENCLAW_CHATBOT_SETUP.md`

#### VPS/Infra Antigas
- `COMANDOS-SSL-VPS.sh`
- `VPS_BACKEND_ENV.txt`
- `VPS_FRONTEND_ENV.txt`
- `VPS_QUICKSTART.md`

#### Quickstarts Consolidados
- `GUIA-RAPIDO.md` (consolidado em QUICKSTART.md na raiz)
- `QUICK_START.md` (consolidado)
- `README-QUICKSTART.md` (consolidado)
- `START_HERE.md` (consolidado)

#### Outros
- `GUIDE-DATABASE-MANAGEMENT.md`
- `TEST_USER.md`
- `cursor.md`

---

## 🗑️ Podem ser deletados?

**SIM**, após período de retenção. Mantidos aqui por cautela durante transição.

**Período de retenção sugerido**: 30-60 dias, depois deletar permanentemente.

---

## 📚 Documentação Ativa (raiz do projeto)

- `README.md` - Visão geral do projeto
- `CONTRIBUTING.md` - Guia de contribuição
- `QUICKSTART.md` - Início rápido
- `DEPLOY.md` - Deploy e infraestrutura
- `CICD-GUIDE.md` - CI/CD workflows
- `SUPABASE-SECRETS-SETUP.md` - Setup Supabase
- `LOCAL-DEV-TROUBLESHOOTING.md` - Troubleshooting local

Documentação técnica adicional em `docs/`.

---

**Data de arquivamento**: 2026-03-20
**Razão**: Limpeza e organização do projeto após múltiplas fases de desenvolvimento
