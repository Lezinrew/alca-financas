# TODO – Melhorias de estrutura (alca-financas)

Documento gerado a partir da avaliação da estrutura do projeto. Itens priorizados: [P0] crítico, [P1] importante, [P2] desejável.

---

## Limpeza / Dívida técnica

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P1] | Arquivos `.bak` e temporários no backend | `backend/app.py.bak`, `backend/app.py.bak.*`, `app.py.tmp` | Remover todos os `*.bak`, `*.bak.*` e `*.tmp`; manter só `app.py` versionado. |
| [P1] | Variáveis MongoDB no `.env` ativo | `backend/.env` (MONGO_URI, MONGO_DB) | Remover MONGO_URI e MONGO_DB do `backend/.env`; o app usa apenas Supabase. |
| [P2] | Script `reset_password.py` usa pymongo | `scripts/reset_password.py` | Atualizar para usar Supabase (ou marcar como legado e apontar para `backend/scripts/set_user_password.py` que já suporta Supabase). |
| [P2] | `.env` na raiz com MONGO_* | `.env` (raiz) | Remover ou atualizar para Supabase; evitar confusão com `backend/.env`. |
| [P1] | Alinhar nome da chave no .env.example | `backend/.env.example` usa `SUPABASE_SERVICE_ROLE_KEY` | Padronizar: usar `SUPABASE_KEY` (e opcional `SUPABASE_LEGACY_JWT`) como em `connection.py`; atualizar comentários. |

---

## Código morto / Consistência pós-Supabase

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P2] | Repositórios MongoDB ainda presentes | `backend/repositories/*_repository.py`, `base_repository.py` | Manter por enquanto se houver plano de fallback; senão mover para `backend/repositories/legacy/` ou remover e deixar só Supabase. |
| [P2] | Referências a MongoDB em comentários/docstrings | `backend/routes/auth.py`, `auth_utils.py`, `user_service.py` | Atualizar comentários para “Supabase (id) / legado (_id)” em vez de “MongoDB”. |
| [P2] | `alca_start_mac.sh` verifica pymongo | Linha ~113: `python -c "import flask, pymongo, pydantic"` | Trocar para `flask, supabase, pydantic` (backend não usa mais pymongo em runtime). |
| [P1] | Scripts de deploy/update que assumem MongoDB | `scripts/update-mongo-uri-*.sh`, `scripts/quick-start.sh` (start MongoDB) | Marcar como legado (mover para `scripts/legacy/mongo/`) ou remover; documentar que o fluxo oficial é Supabase + `alca_start_mac.sh`. |

---

## Segurança

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P0] | Secrets em .env não devem ir para o repositório | `backend/.env`, `.env` raiz | Garantir que `.env` está em `.gitignore`; nunca commitar chaves reais. |
| [P1] | CORS e JWT em produção | `backend/.env` (CORS_ORIGINS, JWT_SECRET, SECRET_KEY) | Documentar em `docs/` uso de valores fortes em produção e lista restrita de origens. |
| [P2] | CI usa variável diferente do app | CI: `SUPABASE_SERVICE_ROLE_KEY`; app: `SUPABASE_KEY` / `SUPABASE_LEGACY_JWT` | Alinhar nome no CI com o que o backend lê (`SUPABASE_KEY` ou manter compatibilidade em `connection.py`). |

---

## Testes

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P1] | Cobertura e testes de integração com Supabase | `backend/tests/` | CI já usa mocks; considerar testes de integração contra projeto Supabase de teste (secrets no GitHub). |
| [P2] | Frontend: testes além de AuthContext e api | `frontend/src/__tests__/` | Aumentar cobertura em componentes críticos (Login, Dashboard, Transactions). |
| [P2] | E2E desabilitado no CI | `.github/workflows/ci.yml` (`if: false` em e2e-tests) | Habilitar quando houver Supabase de teste e fluxo estável; documentar pré-requisitos. |

---

## Documentação

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P1] | README principal atualizado | `README.md` | Garantir que descreve stack atual (Flask + Supabase), sem MongoDB; link para `docs/SUPABASE-CHAVES.md` e `alca_start_mac.sh`. |
| [P2] | Índice de documentação | Vários `.md` na raiz (FEATURE-*, FIX-*) | Criar `docs/INDEX.md` listando todos os guias e referenciando os da raiz. |
| [P2] | .env.example completo | `backend/.env.example` | Incluir FRONTEND_URL, JWT_EXPIRES_HOURS e comentário sobre SUPABASE_LEGACY_JWT; remover referências a MongoDB. |

---

## DevOps / Deploy

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P1] | Health check do backend no CI | `backend-health` job usa `timeout 30 python app.py` | Backend pode falhar por “Invalid API key” em CI; garantir que `SKIP_DB_INIT` ou chave de teste evita falha na inicialização. |
| [P2] | Docker: contexto Supabase | `docker-compose.yml`, `backend/Dockerfile` | Revisar se imagens e compose assumem apenas Supabase (sem serviços MongoDB). |
| [P2] | Scripts de deploy Hostinger/VPS | `scripts/deploy-*.sh` | Verificar se atualizam apenas `backend/.env` com SUPABASE_* e não MONGO_*. |

---

## Performance e boas práticas

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P2] | Lazy loading de rotas | `frontend/src/App.tsx` | Já usa `lazy()`; manter e revisar se todas as rotas pesadas estão lazy. |
| [P2] | Bundle do frontend | `frontend/` (Vite) | Rodar `npm run build` e analisar tamanho de chunks; considerar code-split por rota se necessário. |
| [P2] | Queries N+1 ou listagens pesadas | `backend/repositories/`, `backend/routes/` | Revisar listagens (transações, contas) para uso de limit/offset e índices no Supabase. |

---

## Acessibilidade e i18n

| Prioridade | Descrição | Onde | Ação sugerida |
|------------|-----------|------|----------------|
| [P2] | Uso consistente de i18n | `frontend/src/i18n/`, componentes | Garantir que telas principais usam chaves de `locales/pt.json` (e en/es) em vez de texto fixo. |
| [P2] | Acessibilidade (labels, contraste) | Formulários e botões | Revisar `Login`, `Register`, `TransactionForm` para labels associados e contraste (já há docs em FIX-ACCESSIBILITY-WARNINGS.md). |

---

## Resumo – Ações de maior impacto (ordem sugerida)

1. **Remover arquivos .bak e .tmp** do backend para reduzir ruído e risco de uso acidental.
2. **Limpar variáveis MongoDB** de `backend/.env` e da raiz; padronizar apenas Supabase.
3. **Alinhar `backend/.env.example`** com `SUPABASE_KEY` / `SUPABASE_LEGACY_JWT` e remover MONGO_*; incluir FRONTEND_URL.
4. **Atualizar `alca_start_mac.sh`** para checar `supabase` em vez de `pymongo` nas dependências.
5. **Revisar CI** (backend-health): garantir que o backend sobe em modo mock/test sem falha de API key.
6. **README.md**: descrever stack atual (Supabase only) e passos de início rápido com `./alca_start_mac.sh`.
7. **Scripts legados**: mover ou marcar `update-mongo-uri-*`, `quick-start.sh` (MongoDB) como legado; documentar fluxo Supabase.
8. **`scripts/reset_password.py`**: adaptar para Supabase ou redirecionar para `backend/scripts/set_user_password.py`.
9. **Documentação**: criar `docs/INDEX.md` com índice de todos os guias.
10. **Testes E2E**: habilitar no CI quando houver projeto Supabase de teste e credenciais em secrets.

---

*Documento gerado com base na estrutura do repositório e no prompt em `PROMPT-AVALIACAO-ESTRUTURA.md`.*
