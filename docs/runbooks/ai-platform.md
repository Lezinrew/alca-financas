# Runbook: plataforma de IA

**Estado em 01/10/2026:** implementação local **parcial**, interrompida a pedido do
titular. Nada commitado, nada ativado, nenhuma migration aplicada em banco
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
| **Rotas HTTP `/api/ai/v1` (`backend/routes/ai.py`)** | **Não implementadas** |
| **Montagem das dependências (`services/ai/platform.py`)** | **Não implementada** |
| **Ligação em `backend/app.py`** | **Não feita**: o app não importa nada da IA |
| **Testes ponta a ponta (HTTP → worker → banco)** | **Não escritos** |
| **Benchmark de modelos (casos e executor)** | **Não implementado**; nenhum modelo foi executado |

Consequência prática: os componentes funcionam e são testados isoladamente, mas
ainda **não há caminho de uma requisição HTTP até um efeito**. O gateway real, o
orquestrador e as ferramentas reais nunca rodaram juntos.

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
- Última execução (01/10/2026, Python 3.11, Windows): backend 922 passaram e 1
  foi pulado (permissões POSIX); frontend 162 passaram; `tsc` e `eslint` da pasta
  `ai` sem erros; Fase 1 de comprovantes 34 passaram.

Não validado: Python 3.9 (versão do CI; só análise de sintaxe), `postgres:17`
com `pgcrypto`/`citext` reais (o `pgserver` não traz as extensões; o harness usa
um substituto), nenhum provedor de modelo real, nenhum servidor de e-mail real.

## 3. Critérios de aceite

| AC | Situação | Onde |
| --- | --- | --- |
| AC-01 isolamento | Coberto no serviço e no RLS; falta via HTTP | `test_ai_foundation`, `test_ai_finance_*`, `test_ai_runs_*`, `test_ai_rag_*` |
| AC-02 prévia igual ao importador | Coberto | `test_ai_imports_*` |
| AC-03 efeito único | Coberto no serviço | `test_ai_finance_*` |
| AC-04 timeout após commit | Coberto no serviço | `test_ai_finance_*` |
| AC-05 revogação | Parcial: grant coberto; OAuth só modelado | `test_ai_finance_*`, `test_ai_orchestrator_*`, `test_ai_email_*` |
| AC-06 injeção | Coberto com modelo roteirizado que obedece à injeção | `test_ai_orchestrator_*`, `test_ai_email_*` |
| AC-07 `local_only` | Coberto contra servidores locais | `test_ai_gateway_*` |
| AC-08 fatos com fonte | Coberto no serviço | `test_ai_finance_*` |
| AC-09 failover e orçamento | Coberto no gateway; parcial no orquestrador | `test_ai_gateway_*` |
| AC-10 capacidades da rota | Coberto | `test_ai_gateway_models` |
| AC-11 app sem IA | Parcial: o app não importa a IA; falta teste com rotas | — |
| AC-12 mobile | Parcial: só 360 px, tema escuro, dois cenários vistos no navegador | bancada de prévia |
| AC-13 orçamento concorrente e segredos | Coberto | `test_ai_gateway_budget`, `test_ai_gateway_external` |
| AC-14 baixa parcial, mensal/global, PF/negócio | Coberto no serviço | `test_ai_finance_*` |
| AC-15 reinício do worker | Coberto com modelo roteirizado | `test_ai_orchestrator_*`, `test_ai_worker_*` |

Nenhum critério está validado de ponta a ponta nem em produção.

## 4. Configuração (somente nomes)

Seção 16 de `.env.example`: `AI_ENABLED`, `AI_CLOUD_ENABLED`, `AI_EMAIL_ENABLED`,
`AI_WRITE_ENABLED`, `AI_WHATSAPP_ENABLED`, `AI_INLINE_WORKER`,
`AI_OLLAMA_BASE_URL`, `AI_MODEL_REGISTRY_PATH`, `AI_ALLOW_CANDIDATE_MODELS`,
`AI_EMAIL_CONNECTOR`, `AI_EMAIL_FIXTURE_DIR`, `AI_EMAIL_MCP_CONFIG_PATH`,
`AI_QUARANTINE_DIR`, `AI_BUDGET_CURRENCY`, `AI_BUDGET_TIMEZONE`,
`VITE_ENABLE_AI_OPERATOR`. Todas desligadas por padrão. Dependem de
`DATABASE_V2_URL` e da sessão V2.

Enquanto as rotas não existirem, essas variáveis não têm efeito no aplicativo.

## 5. Antes de qualquer ativação

1. Implementar `platform.py`, `routes/ai.py`, a ligação em `app.py` e os testes
   ponta a ponta.
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

Hoje não há o que desativar: o aplicativo não importa a plataforma. Para remover
o trabalho local:

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
