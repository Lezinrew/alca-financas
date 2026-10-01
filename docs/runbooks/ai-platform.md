# Runbook: plataforma de IA

**Estado em 01/10/2026:** implementação local **parcial**, com a fatia vertical
de leitura integrada. Nada commitado, nada ativado, nenhuma migration aplicada em banco
existente. Regras e garantias: [contrato](../contracts/ai-platform-v1.md).
Detalhamento: [spec de implementação](../specs/ai-platform-implementation-v1.md).
Motivos das decisões: [RFC 0003](../rfcs/0003-ai-platform-implementation-decisions.md).

## 1. O que existe e o que falta

| Parte | Estado |
| --- | --- |
| Migration `0002_ai_platform.sql` e reversão | Pronta; aplicada só em banco de teste descartável |
| Espinha (`errors`, `settings`, `types`, `db`, `scope`, `policy`, `registry`) | Pronta e testada |
| Gateway (`backend/services/ai/gateway/`) | Pronto; testado contra servidores HTTP locais |
| Finanças (`backend/services/ai/finance/`) | Pronto; testado em PostgreSQL real descartável |
| E-mail, quarentena e prévia (`email/`, `artifacts.py`, `imports/`) | Pronto; testado com caixa postal sintética e servidor MCP local |
| Execuções, orquestrador, worker e RAG | Pronto; testado com modelo roteirizado |
| Tela do operador (`frontend/src/components/ai/`) | Pronta; atrás de `VITE_ENABLE_AI_OPERATOR` (desligada) |
| **Rotas HTTP `/api/ai/v1` (`backend/routes/ai.py`)** | Implementados `GET /status`, `POST /runs`, `GET /runs`, `GET /runs/{id}` e `POST /runs/{id}/cancel`; propostas, operações e grants continuam sem rotas |
| **Montagem das dependências (`services/ai/platform.py`)** | Implementada: todas as ferramentas reais, prévia ligada às finanças, gateway, orquestrador e worker; nada abre no import |
| **Ligação em `backend/app.py`** | Inserções locais mínimas; import, montagem e registro opcionais protegidos; falha da IA deixa a plataforma desativada |
| **Testes ponta a ponta (HTTP → worker → banco)** | Implementados em `test_ai_api_vertical.py`, com login V2 real, adaptador Ollama real e servidor HTTP sintético local; inclui worker CLI em processo separado |
| **Benchmark geral de modelos (30 casos)** | **Não implementado**; teste opt-in de oito perguntas financeiras com Ollama real executado, Qwen reprovado; [evidência](../validation/ai-ollama-read-2026-10-01.md) |

Existe agora o caminho autenticado HTTP → fila → worker → gateway → `finance.read`
→ fatos com fontes → auditoria nos testes roteirizados. A validação adicional com
Qwen real não passou: respondeu sem chamada nativa de ferramenta, fatos ou fontes.
Nenhum modelo está homologado. Esta entrega não ativa escrita
financeira, e-mail, frontend V2 nem produção.

## 2. Testes

```bash
cd backend
python -m pytest -c tests/ai/pytest.ini tests/ai
```

```bash
cd frontend
npx vitest run src/components/ai
```

- Os testes de backend usam um PostgreSQL real e descartável. Sem Docker, o
  harness usa o pacote `pgserver` (instalado só nesta máquina, fora do
  `requirements.txt`); com um Postgres local, defina `AI_TEST_PG_ADMIN_URL`
  (só loopback é aceito).
- Não rode `pytest` sem o `-c`: o conftest legado importa `app` e usaria as
  credenciais reais do `.env`.
- Novos testes HTTP/integração (01/10/2026, Python 3.11.9, Windows):
  `python -m pytest -c tests/ai/pytest.ini tests/ai/test_ai_api_vertical.py`:
  **60 passaram**, 38 avisos de depreciação herdados de gotrue/pydantic, em 61,09 s.
- Última execução completa com o código final (01/10/2026, Python 3.11.9,
  Windows): `python -m pytest -c tests/ai/pytest.ini tests/ai`:
  **982 passaram, 1 pulado** (permissões POSIX não se aplicam no Windows),
  38 avisos de depreciação herdados de gotrue/pydantic, em **679,68 s**.
- Validação de sintaxe Python 3.9 nos seis arquivos Python desta entrega:
  passou; não equivale à execução nessa versão.
- Frontend não alterado nem reexecutado nesta entrega. Histórico da etapa
  anterior: 162 testes frontend passaram, `tsc` e `eslint` da pasta `ai` sem
  erros; Fase 1 de comprovantes 34 passaram. Esses números não foram revalidados.

Não validado: Python 3.9 (versão do CI; só análise de sintaxe), `postgres:17`
com `pgcrypto`/`citext` reais (o `pgserver` não traz as extensões; o harness usa
um substituto), outros modelos e benchmark geral de 30 casos, nenhum servidor de e-mail real.

## 3. Critérios de aceite

| AC | Situação | Onde |
| --- | --- | --- |
| AC-01 isolamento | Coberto no serviço, no RLS e via HTTP para execuções: tenant, espaço e ator | `test_ai_foundation`, `test_ai_finance_*`, `test_ai_runs_*`, `test_ai_rag_*`, `test_ai_api_vertical` |
| AC-02 prévia igual ao importador | Coberto | `test_ai_imports_*` |
| AC-03 efeito único | Coberto no serviço | `test_ai_finance_*` |
| AC-04 timeout após commit | Coberto no serviço | `test_ai_finance_*` |
| AC-05 revogação | Parcial: grant coberto; OAuth só modelado | `test_ai_finance_*`, `test_ai_orchestrator_*`, `test_ai_email_*` |
| AC-06 injeção | Coberto com modelo roteirizado que obedece à injeção | `test_ai_orchestrator_*`, `test_ai_email_*` |
| AC-07 `local_only` | Coberto contra servidores locais | `test_ai_gateway_*` |
| AC-08 fatos com fonte | Coberto no serviço e na leitura vertical via HTTP; valores comparados com agregação NUMERIC independente | `test_ai_finance_*`, `test_ai_api_vertical` |
| AC-09 failover e orçamento | Coberto no gateway; parcial no orquestrador | `test_ai_gateway_*` |
| AC-10 capacidades da rota | Coberto | `test_ai_gateway_models` |
| AC-11 app sem IA | Aplicativo Flask próprio testado com plataforma ausente/desativada, sem banco; falha do modelo encerra somente a execução. Inicialização completa de `backend/app.py` não executada | `test_ai_api_vertical` |
| AC-12 mobile | Parcial: só 360 px, tema escuro, dois cenários vistos no navegador | bancada de prévia |
| AC-13 orçamento concorrente e segredos | Coberto | `test_ai_gateway_budget`, `test_ai_gateway_external` |
| AC-14 baixa parcial, mensal/global, PF/negócio | Coberto no serviço | `test_ai_finance_*` |
| AC-15 reinício do worker | Coberto com modelo roteirizado | `test_ai_orchestrator_*`, `test_ai_worker_*` |

AC-01 e AC-08 têm cobertura vertical local para esta fatia de leitura. Nenhum
critério está validado em produção; rotas de escrita seguem fora desta entrega.

## 4. Configuração (somente nomes)

Seção 16 de `.env.example`: `AI_ENABLED`, `AI_CLOUD_ENABLED`, `AI_EMAIL_ENABLED`,
`AI_WRITE_ENABLED`, `AI_WHATSAPP_ENABLED`, `AI_INLINE_WORKER`,
`AI_OLLAMA_BASE_URL`, `AI_MODEL_REGISTRY_PATH`, `AI_ALLOW_CANDIDATE_MODELS`,
`AI_EMAIL_CONNECTOR`, `AI_EMAIL_FIXTURE_DIR`, `AI_EMAIL_MCP_CONFIG_PATH`,
`AI_QUARANTINE_DIR`, `AI_BUDGET_CURRENCY`, `AI_BUDGET_TIMEZONE`,
`VITE_ENABLE_AI_OPERATOR`. Todas desligadas por padrão. Dependem de
`DATABASE_V2_URL` e da sessão V2.

No aplicativo, a montagem requer `AI_ENABLED=true` e o pool `POSTGRES_V2_POOL`
já inicializado pela prévia V2 (`ENABLE_POSTGRES_V2_AUTH_PREVIEW=true`). Pool
ausente ou configuração inválida mantém a IA desativada, com aviso seguro.
O worker CLI monta seu próprio pool V2 quando habilitado; não carrega `.env`.
`build_platform(pool, settings, ...)` não inicia threads nem processa fila;
esta entrega usa o worker separado, sem ativação de `AI_INLINE_WORKER`.

## 5. Antes de qualquer ativação

1. Revisar a fatia vertical local de leitura. Rotas de proposta/operação/grants
   e o login V2 no frontend permanecem pendentes, em entrega própria.
2. Validar a migration em `postgres:17` com as extensões reais; backup e teste
   de restauração antes de aplicar em banco existente.
3. Criar um papel de aplicação sem `SUPERUSER`/`BYPASSRLS`. O usuário do compose
   de `infra/postgres-v2` é superusuário e ignora o RLS.
4. Vincular contas e contas a pagar aos espaços financeiros.
5. Inventariar a VPS (CPU, RAM, GPU, disco, concorrência) e rodar o benchmark.
   Nenhum modelo está homologado: `config/models.json` só tem rotas `candidate`.
6. Decidir a via de download de anexo de e-mail (o servidor Gmail MCP oficial
   não a documenta) e implementar o fluxo OAuth.
7. Levar o login da sessão V2 ao frontend.
8. Rodar o Ollama com `OLLAMA_NO_CLOUD=1` em loopback ou rede interna.

## 6. Rollback

Com as flags padrão desligadas, `GET /status` informa `enabled: false` e as
demais rotas devolvem `503 ai_disabled` sem consultar banco. Para desativar a
montagem, desligar `AI_ENABLED` na configuração administrada e reiniciar os
processos; não houve ativação nesta entrega.

Para reverter somente esta integração local, remover `routes/ai.py`,
`services/ai/platform.py` e `tests/ai/test_ai_api_vertical.py`; desfazer apenas
as inserções de IA e a adição de `Idempotency-Key` em `app.py`, a injeção opcional
de adaptadores em `build_gateway` e a adequação da chamada de montagem no worker
e seu teste. Preservar as alterações anteriores de auth V2, UI e comprovantes.

Remoção da implementação anterior inteira, se solicitada em tarefa própria:

- apagar `backend/services/ai/`, `backend/tests/ai/`,
  `frontend/src/components/ai/`, `backend/database/migrations_v2/0002_*`;
- desfazer as inserções em `frontend/src/App.tsx` e
  `frontend/src/components/layout/AppShell.tsx` (rota e item "Operador");
- remover a seção 16 de `.env.example` e a linha `backend/var/` de `.gitignore`.

Depois de ativada, o rollback do contrato (seção 14) vale: desligar as flags,
drenar ou cancelar a fila, reconciliar operações em andamento e só então reverter
a imagem. `0002_ai_platform.down.sql` remove o estado da IA, mas não desfaz
efeitos financeiros já gravados; esses usam compensação. Ledger, auditoria e
outbox não devem ser apagados sem exportação.

## 7. Pendências conhecidas do código

- Baixa "registrado pago" (sem transação de extrato) nunca é aplicada por grant
  delegado; fica sempre aguardando aprovação. É uma escolha conservadora que
  cabe ao titular rever.
- Lançamento de valor zero em OFX faz a importação inteira ser recusada.
- Ninguém marca o artefato como consumido ao aplicar uma importação, e a limpeza
  da quarentena e a expiração de propostas não estão agendadas.
- `needs_reconciliation` não tem resolvedor automático.
- Circuito, suspensão de credencial e de rota ficam na memória de cada processo.
- `pypdf` não está em `requirements.txt`: sem ele todo PDF é recusado.
- O prazo total de leitura HTTP depende de `urllib3 >= 2.2`, não fixado.
- Herdado do importador do produto: nomes próprios fixos em
  `services/ofx_import/nature.py` valem para todos os tenants, e a chave de
  deduplicação do OFX depende do nome da conta.
