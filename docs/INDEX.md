## Documentation Index — Alça Finanças

**Purpose:** Central index of all documentation files, grouped for fast navigation and AI-friendly discovery.

This file is IDE-agnostic and all paths are relative to the repository root.

---

## 1. Navigation by Area

### 1.1 Overview
- `README.md` — Visão geral do produto, stack e estrutura principal.
- `QUICKSTART.md` — Guia rápido de setup em poucos minutos.
- `README-QUICKSTART.md` — Variante de quickstart legado.
- `QUICK_START.md` — Guia alternativo de inicialização rápida.
- `GUIA-RAPIDO.md` — Guia rápido em português.
- `docs/00-overview/RAIO-X-ARQUITETURA-COMPLETO.md` — Raio-X completo da arquitetura.
- `docs/00-overview/ANALISE-ALCA-FINANCAS.md` — Análise geral do projeto.
- `docs/00-overview/TODO-MELHORIAS-ESTRUTURA.md` — Lista de melhorias estruturais pendentes.

### 1.2 Architecture
- `skills/ARCHITECTURE_OVERVIEW.md` — Visão geral da arquitetura por Skills.
- `skills/ADRs/0001-skills-architecture.md` — Decisão de arquitetura do sistema de Skills.
- `docs/01-architecture/backend_api_qa_checklist.md` — Checklist de QA para a API do backend.
- `docs/01-architecture/OPENCLAW-DEPLOY-SEGURO.md` — Guia de deploy seguro do OpenClaw.
- `docs/01-architecture/MCP-HOSTINGER.md` — Integração MCP com Hostinger.

### 1.3 Backend
- `backend/README_SUPABASE.md` — Notas específicas de backend com Supabase.
- `backend/SUPABASE_AUTH_SETUP.md` — Setup da autenticação Supabase.
- `backend/MIGRATION_SUPABASE.md` — Detalhes da migração para Supabase.
- `docs/03-api/backend_refactor_prompt.md` — Prompt de refatoração da API backend.
- `docs/03-api/backend_api_qa_checklist.md` — Checklist de qualidade da API.

### 1.4 Frontend
- `FEATURE-CURRENCY-INPUT.md` — Detalhes da feature de input de moeda.
- `FEATURE-CREDIT-CARDS.md` — Implementação do sistema de cartões de crédito.
- `FEATURE-CREDIT-CARD-EXPENSE-FORM.md` — Formulário de despesas com cartão.
- `FIX-ACCESSIBILITY-WARNINGS.md` — Correções de acessibilidade no frontend.
- `docs/TESTING.md` — Guia de testes, incluindo frontend.

### 1.5 Database
- `GUIDE-DATABASE-MANAGEMENT.md` — Guia geral de gestão de banco de dados.
- `scripts/db/README.md` — Guia de migrações SQL.
- `docs/04-database/SUPABASE-CHAVES.md` — Como obter as chaves do Supabase.
- `docs/04-database/RECUPERACAO-SENHA-SUPABASE.md` — Fluxo de recuperação de senha.
- `docs/SUPABASE-RLS-SECURITY.md` — Detalhes de RLS e segurança no Supabase.
- `docs/legacy/mongo/` — Documentação legado MongoDB (não mais usada em produção).

### 1.6 Security
- `SECURITY_FIX_FASE1_GUIA.md` — Guia de correções de segurança fase 1.
- `SECURITY_FIXES_TODO.md` — Itens de segurança pendentes.
- `docs/05-security/SEGURANCA-SERVIDOR.md` — Segurança do servidor em produção.
- `docs/05-security/CONFIGURAR-OAUTH.md` — Configuração geral de OAuth.
- `docs/05-security/CONFIGURAR-GOOGLE-OAUTH.md` — Configuração de OAuth Google.
- `docs/05-security/PROMPT-BROWSER-AGENT-GOOGLE-OAUTH.md` — Prompt auxiliar de configuração OAuth.

### 1.7 DevOps & Operations
- `DEPLOY_QUICK_START.md` — Guia rápido de deploy.
- `DEPLOY_PRODUCTION_GUIDE.md` — Guia de produção detalhado.
- `RENDER_DEPLOY_STEPS.md` — Deployment na Render.
- `VPS_QUICKSTART.md` — Quickstart para deploy em VPS.
- `docs/06-ops/DADOS-DEPLOY.md` — Dados e configurações de deploy.
- `docs/06-ops/COMANDOS-FIX-TRAEFIK-ALCAHUB.md` — Comandos de ajuste Traefik.
- `docs/06-ops/FIX-TRAEFIK-ALCAHUB-CLOUD.md` — Correções de Traefik na nuvem.
- `docs/CAREER-POSITIONING-DEVOPS.md` — Notas de posicionamento DevOps (contextual).

### 1.8 Contributing
- `CONTRIBUTING.md` — Guia de contribuição e fluxo de PR (ver raiz).
- `CHECKLIST_FASE1.md` — Checklist de entregas da fase 1.
- `PATCHES_DIFF.md` — Resumo de patches aplicados.
- `REFACTORING_COMPLETE.md` — Indicador de conclusão de refatoração específica.
- `skills/ADD_A_SKILL_PLAYBOOK.md` — Playbook para adicionar novas Skills.

---

## 2. Full Inventory (Docs & Markdown)

> **Scope:** All `*.md` files in the repository, grouped by directory.  
> **Rule:** Files listed here must physically exist; if você mover um arquivo, atualize o caminho neste índice.

### 2.1 Root (`./`)
- `README.md` — Visão geral do projeto e stack.
- `README-QUICKSTART.md` — Quickstart legado.
- `QUICKSTART.md` — Guia de início rápido.
- `QUICK_START.md` — Variante adicional de quickstart.
- `GUIA-RAPIDO.md` — Guia rápido em português.
- `SUPABASE_MIGRATION_COMPLETE.md` — Relatório da migração MongoDB → Supabase.
- `DEPLOY_QUICK_START.md` — Guia rápido de deploy.
- `DEPLOY_PRODUCTION_GUIDE.md` — Guia de produção.
- `VPS_QUICKSTART.md` — Deploy em VPS.
- `RENDER_DEPLOY_STEPS.md` — Passos para deploy na Render.
- `FEATURE-CREDIT-CARDS.md` — Especificação da feature de cartões.
- `FEATURE-CREDIT-CARD-EXPENSE-FORM.md` — Especificação do formulário de despesas de cartão.
- `FEATURE-CURRENCY-INPUT.md` — Especificação do input de moeda.
- `FEATURE-DELETE-PLANNING.md` — Especificação de exclusão de planejamento.
- `FIX-ACCESSIBILITY-WARNINGS.md` — Correções de acessibilidade.
- `FIX-ACCOUNTS-ERROR.md` — Correção de erro em contas.
- `FIX-AUTH-CONTEXT-ERROR.md` — Correção no contexto de autenticação.
- `FIX-CORS.md` — Correção de CORS.
- `FIX-DROPDOWN-MENU.md` — Correção em dropdown.
- `FIX-PORT-CONFLICT.md` — Correção de conflito de porta.
- `FIX-VITE-API-URL.md` — Correção de URL de API no Vite.
- `MELHORIAS-ALCA-START.md` — Melhorias no script de start.
- `SECURITY_FIX_FASE1_GUIA.md` — Guia de correções de segurança (fase 1).
- `SECURITY_FIXES_TODO.md` — To-do de segurança.
- `CHECKLIST_FASE1.md` — Checklist geral.
- `CHANGELOG-TESTES.md` — Histórico de testes.
- `PATCH_SUMMARY.md` — Resumo de patches.
- `PATCHES_DIFF.md` — Diferenças principais aplicadas.
- `START_HERE.md` — Documento de entrada para o projeto.
- `INDICE.md` — Índice legado de docs.
- `PROXIMO-PASSO.md` — Próximos passos recomendados.
- `MIGRACAO_VALIDACAO.md` — Notas de validação de migração.
- `SUPABASE_MIGRATION_COMPLETE.md` — Relatório completo da migração.
- `PROMPT_DBEXPERT.md` — Prompt para especialista em banco de dados.
- `PROMPT_DBEXPERT_CONCISO.txt` — Versão concisa do prompt de DB.
- `PROMPT_MIGRACAO_FIREBASE.md` — Prompt de migração Firebase.
- `PROMPT_LOGO_GEMINI.md` — Prompt de geração de logo.
- `ADDITIONAL_SCRIPTS_UPDATED.md` — Notas sobre scripts adicionais.
- `TEST_USER.md` — Anotações relacionadas a usuário de teste.
- `README_CORREÇÕES.md` — Sumário de correções realizadas.
- `GUIDE-DATABASE-MANAGEMENT.md` — Guia de gerenciamento de DB.

### 2.2 `docs/`
- `docs/INDEX.md` — Este índice de documentação.
- `docs/ENVIRONMENTS.md` — Guia completo de variáveis de ambiente.
- `docs/ANALISE-ALCA-FINANCAS.md` — Análise detalhada do projeto.
- `docs/RAIO-X-ARQUITETURA-COMPLETO.md` — Raio-X de arquitetura (movido para `00-overview`).
- `docs/TODO-MELHORIAS-ESTRUTURA.md` — Itens de melhoria estrutural.
- `docs/OPENCLAW-DEPLOY-SEGURO.md` — Guia de deploy seguro OpenClaw.
- `docs/MCP-HOSTINGER.md` — Integração MCP com Hostinger.
- `docs/FIX-TRAEFIK-ALCAHUB-CLOUD.md` — Correções de Traefik.
- `docs/COMANDOS-FIX-TRAEFIK-ALCAHUB.md` — Comandos de ajuste Traefik.
- `docs/ADMIN_FEATURES_PROPOSAL.md` — Proposta de features de administração.
- `docs/LOGIN-UPGRADE-ENTREGA.md` — Entrega de melhorias de login.
- `docs/PROMPT-BROWSER-AGENT-GOOGLE-OAUTH.md` — Prompt de configuração OAuth.
- `docs/CONFIGURAR-OAUTH.md` — Guia de configuração OAuth.
- `docs/CONFIGURAR-GOOGLE-OAUTH.md` — Guia de configuração Google OAuth.
- `docs/RECUPERACAO-SENHA-SUPABASE.md` — Recuperação de senha Supabase.
- `docs/SUPABASE-CHAVES.md` — Como obter chaves do Supabase.
- `docs/SUPABASE-RLS-SECURITY.md` — RLS e segurança Supabase.
- `docs/DADOS-DEPLOY.md` — Dados de deploy.
- `docs/SEGURANCA-SERVIDOR.md` — Segurança de servidor.
- `docs/TESTING.md` — Guia de testes.
- `docs/backend_api_qa_checklist.md` — Checklist QA backend API.

### 2.3 `docs/legacy/mongo/`
- `docs/legacy/mongo/ADICIONAR-IP-MONGODB-ATLAS.md` — Como liberar IP no Atlas.
- `docs/legacy/mongo/DEPLOY-HOSTINGER.md` — Deploy em Hostinger com MongoDB.
- `docs/legacy/mongo/OBTER-CONNECTION-STRING-MONGODB.md` — Obter connection string MongoDB.
- `docs/legacy/mongo/SETUP-PRODUCAO.md` — Setup de produção MongoDB.

### 2.4 `backend/`
- `backend/README_SUPABASE.md` — Documentação backend orientada a Supabase.
- `backend/SUPABASE_AUTH_SETUP.md` — Setup da autenticação Supabase.
- `backend/MIGRATION_SUPABASE.md` — Detalhes da migração para Supabase.

### 2.5 `scripts/`
- `scripts/db/README.md` — Guia de migrações e scripts de banco.

### 2.6 `services/openclaw/`
- `services/openclaw/README.md` — Notas e setup do serviço OpenClaw.

### 2.7 `skills/`
- `skills/README.md` — Visão geral do sistema de Skills.
- `skills/CONVENTIONS.md` — Convenções de documentação e contratos.
- `skills/ARCHITECTURE_OVERVIEW.md` — Visão geral da arquitetura por Skills.
- `skills/ADD_A_SKILL_PLAYBOOK.md` — Playbook para adicionar Skills.
- `skills/SKILLS_REGISTRY.md` — Registro completo de Skills.
- `skills/SKILLS_DEPENDENCY_GRAPH.mmd` — Grafo de dependências entre Skills.
- `skills/ADRs/0001-skills-architecture.md` — ADR da arquitetura de Skills.
- `skills/authentication/skill.md` — Documento principal do skill `authentication`.
- `skills/users-profile/skill.md` — Documento principal do skill `users-profile`.
- `skills/accounts/skill.md` — Documento principal do skill `accounts`.
- `skills/categories/skill.md` — Documento principal do skill `categories` (se existir, caso contrário TODO).
- `skills/transactions/skill.md` — Documento principal do skill `transactions`.
- `skills/dashboard/skill.md` — Documento principal do skill `dashboard`.
- `skills/reports/skill.md` — Documento principal do skill `reports`.
- `skills/imports-integrations/skill.md` — Documento principal do skill `imports-integrations`.
- `skills/notifications/skill.md` — Documento principal do skill `notifications`.
- `skills/admin-governance/skill.md` — Documento principal do skill `admin-governance`.
- `skills/ai-insights/skill.md` — Documento principal do skill `ai-insights`.
- `skills/infrastructure-platform/skill.md` — Documento principal do skill `infrastructure-platform`.
- `skills/**/contracts/*.md` — Contratos por skill (API, DB, events).
- `skills/**/design/*.md` — Modelos de domínio, invariantes e ameaças.
- `skills/**/runbooks/*.md` — Runbooks de troubleshooting/observability.
- `skills/**/tests/*.md` — Estratégia de testes.

> Para detalhes por skill, consulte `skills/SKILLS_REGISTRY.md` e o diretório específico em `skills/<nome-do-skill>/`.

---

## 3. Docs Directory Layout (Target)

Toda nova documentação deve ser criada dentro desta estrutura:

```text
docs/
  00-overview/
  01-architecture/
  02-domain/
  03-api/
  04-database/
  05-security/
  06-ops/
  07-contributing/
  legacy/
```

Diretrizes de colocação:
- **00-overview** — visão geral, raio-x, análises de alto nível.
- **01-architecture** — diagramas, decisões de arquitetura, checklists de qualidade.
- **02-domain** — documentação de domínio de negócio (ligar com Skills).
- **03-api** — contratos e QA de APIs.
- **04-database** — migrações, RLS, gestão de banco.
- **05-security** — hardening, OAuth, RLS, checklists de segurança.
- **06-ops** — deploy, infra, DevOps, scripts operacionais.
- **07-contributing** — guias de contribuição, governance e checklists.

---

## 4. How to Use This Index

- **Começar rápido**: leia `README.md`, depois `docs/ENVIRONMENTS.md` e siga os scripts em `scripts/dev/`.
- **Investigar arquitetura**: use `docs/00-overview/RAIO-X-ARQUITETURA-COMPLETO.md` e `skills/ARCHITECTURE_OVERVIEW.md`.
- **Trabalhar em um módulo**: comece por `skills/README.md` e o `skill.md` específico.
- **Fazer deploy**: use `docs/06-ops/DADOS-DEPLOY.md`, `DEPLOY_QUICK_START.md` e os scripts em `scripts/prod/`.
- **Ver segurança**: concentre-se em `docs/05-security/*` e `docs/SUPABASE-RLS-SECURITY.md`.

---

## 5. Maintenance

- Sempre que adicionar um novo `.md`, atualize este índice na seção adequada.
- Ao mover um documento para dentro de `docs/0x-*`, deixe um stub no caminho antigo apontando para o novo local.
- Mantenha títulos e descrições curtas para uso eficiente por agentes de IA.

**Última atualização do índice:** 2026-02-27

