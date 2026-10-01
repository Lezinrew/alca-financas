# Prompt para o Codex: plataforma de IA — fatia vertical HTTP

**Criado em:** 01/10/2026.
**Objetivo:** situar o agente no estado atual da plataforma de IA e pedir a próxima
ação: `platform.py`, `routes/ai.py`, ligação mínima em `app.py` e o teste ponta a
ponta da fatia "pedido autenticado → `finance.read` → resultado com fontes →
auditoria".
**Estado de referência:** [docs/runbooks/ai-platform.md](../runbooks/ai-platform.md).

Cole o bloco abaixo no Codex, com o repositório aberto em
`C:\Users\lezin\Downloads\project\alca-financas`.

````text
Você vai continuar a implementação da plataforma de IA do Alça Finanças.
Idioma de comunicação, comentários e documentação: português brasileiro.

REPOSITÓRIO
C:\Users\lezin\Downloads\project\alca-financas
Stack: Flask/Python (backend), React + TypeScript + Vite (frontend),
PostgreSQL V2 próprio (em fundação local), Supabase em produção.

LEIA PRIMEIRO, NESTA ORDEM
1. CLAUDE.md e AGENTS.md (regras de execução do projeto).
2. docs/contracts/ai-platform-v1.md — contrato, referência principal (AC-01 a AC-15 na seção 13).
3. docs/runbooks/ai-platform.md — estado real: o que existe, o que falta, pendências.
4. docs/specs/ai-platform-implementation-v1.md — seções 2 e 4 (identidade/escopo e API HTTP com formatos exatos).
5. docs/rfcs/0003-ai-platform-implementation-decisions.md — por que cada decisão foi tomada.
6. O código que você vai integrar (leia os módulos inteiros, não confie só nos documentos):
   backend/services/ai/{errors,settings,types,db,scope,policy,registry,runs,orchestrator,worker}.py,
   backend/services/ai/gateway/gateway.py, backend/services/ai/finance/{tools,proposals,operations}.py,
   backend/services/ai/email/tools.py, backend/services/ai/imports/tools.py, backend/services/ai/misc_tools.py,
   backend/routes/auth_v2.py, backend/services/auth_v2_service.py,
   backend/tests/ai/conftest.py, backend/tests/ai/support/{pg,seed}.py,
   frontend/src/components/ai/{aiApi.ts,aiTypes.ts}.

EM QUE PÉ ESTAMOS
Pronto e testado isoladamente (922 testes de backend e 162 de frontend passando localmente):
- migration backend/database/migrations_v2/0002_ai_platform.sql (com reversão), aplicada só em banco de teste;
- espinha: erros no formato do contrato, contexto resolvido no servidor, grants e modos observe/assisted/delegated, registro de ferramentas;
- gateway de modelos (Ollama, OpenAI-compatível/OpenRouter, Anthropic), finanças (leitura, propostas, operações idempotentes, reversão), e-mail/quarentena/prévia de importação, execuções/orquestrador/worker/RAG;
- tela do operador em frontend/src/components/ai/, atrás de VITE_ENABLE_AI_OPERATOR (desligada).

NÃO existe ainda:
- backend/services/ai/platform.py (montagem das dependências);
- backend/routes/ai.py (API /api/ai/v1);
- ligação em backend/app.py (o app não importa nada da IA);
- testes ponta a ponta (HTTP -> worker -> banco);
- benchmark de modelos (nenhum modelo foi executado).
Consequência: não há caminho de uma requisição HTTP até um efeito, e o gateway real, o orquestrador e as ferramentas reais nunca rodaram juntos.

Git: a árvore de trabalho está em main com muito trabalho NÃO commitado, inclusive de outra frente (auth V2, comprovantes WhatsApp, login). Existe a branch ci/ai-platform-tests com o workflow .github/workflows/ai-platform-tests.yml e o código da IA commitado.

SUA TAREFA (próxima ação, e só ela)
Entregar a menor fatia vertical demonstrável:
pedido autenticado -> finance.read -> resultado com fontes -> auditoria.

1. backend/services/ai/platform.py
   build_platform(pool, settings=None, *, adapters=None, email_connector_factory=None, credential_store=None) -> AiPlatform
   (dataclass com settings, pool, registry, gateway, orchestrator, worker).
   Registra TODAS as ferramentas reais (build_finance_tools, build_email_tools, build_import_tools, build_misc_tools),
   liga o preview_provider de imports em finance, e monta o gateway com build_gateway.
   Nada pode ser criado no import do módulo (sem conexão, credencial ou rede fora de build_platform).
   worker.main() já espera build_platform() e usa .worker ou (.pool, .settings, .orchestrator): confira no código.

2. backend/routes/ai.py — blueprint "bp", registrado com url_prefix="/api/ai/v1". Nesta entrega, somente:
   GET /status, POST /runs, GET /runs, GET /runs/<id>, POST /runs/<id>/cancel.
   - Plataforma em current_app.config["AI_PLATFORM"]. Ausente ou settings.enabled False:
     GET /status responde 200 {"enabled": false} sem tocar em banco; as demais respondem 503 ai_disabled.
   - Sessão V2: valide o cookie com current_app.config["AUTH_V2_SERVICE"].get_session (mesmo nome de cookie de routes/auth_v2.py).
     Sem sessão -> 401 unauthorized. Todo POST exige X-CSRF-Token (AuthV2Service.require_csrf) -> 403 invalid_csrf.
   - Escopo sempre por services.ai.scope.resolve_scope com o usuário da sessão. Nenhum tenant/ator vem do corpo.
     financial_space_id só ESCOLHE entre os espaços do usuário. Recurso de outro tenant, espaço ou ator -> 404 not_found (nunca 403).
   - Corpo validado com pydantic (extra="forbid") -> 400 invalid_request; acima de 64 KiB -> 413; Idempotency-Key em POST /runs; conflito -> 409.
   - Erros sempre {"error": {"code","retryable","safe_message","trace_id"}}; AiError -> status do catálogo;
     erro inesperado -> 500 internal_error sem stacktrace. Cabeçalho X-Trace-Id e Cache-Control: no-store em tudo.
   - As formas de resposta devem bater com frontend/src/components/ai/aiTypes.ts e com a seção 4 da spec.

3. backend/app.py — edição MÍNIMA (o arquivo tem mudanças locais de outra frente: só insira linhas, não reformate):
   import do blueprint dentro de try/except; "Idempotency-Key" em allow_headers do CORS;
   se AiSettings.from_env().enabled, montar app.config["AI_PLATFORM"] dentro de try/except que loga aviso
   e deixa a IA desativada em caso de erro. Falha da IA NUNCA pode impedir o app de subir (AC-11).

4. Testes em backend/tests/ai/test_ai_api_*.py (prefixo test_ai_ é obrigatório para a coleta):
   app Flask de teste próprio (NÃO importe backend/app.py), AuthV2Service real com login de verdade,
   banco real via fixture "pool", adaptador Ollama REAL apontando para o servidor HTTP local de teste
   que já existe em backend/tests/ai/support/gateway_server.py.
   Cubra: fatia vertical completa (login -> POST /runs -> worker.run_once() -> GET /runs/<id> "completed"
   com facts cujos valores batem com uma agregação NUMERIC independente, cada fato com fonte, e linhas
   ai.run.created / ai.run.finished em audit_events sem o texto do pedido);
   401 sem sessão; 403 sem CSRF; 400 com propriedade extra; 409 e reuso por Idempotency-Key;
   404 para execução de outro tenant, outro espaço e outro ator; IA desativada -> status enabled=false e 503;
   servidor de modelo fora do ar -> execução "failed" com error.code model_unavailable.

REGRAS QUE NÃO PODEM SER QUEBRADAS
- Não faça commit, push, deploy nem aplique migrations em banco existente sem eu pedir.
- Não leia nem altere .env, segredos ou credenciais. Não chame API de modelo paga, caixa postal real nem VPS.
- Não edite: services/receipt-intake/**, infra/automation/**, n8n/workflows/**, backend/routes/auth_v2.py,
  backend/services/auth_v2_service.py, backend/requirements.txt.
- Sem dependências novas (use stdlib, Flask, flask-limiter, pydantic 2.5, psycopg2, requests).
- Python compatível com 3.9: "from __future__ import annotations"; em modelos pydantic use Optional/List/Dict, nunca "X | None".
- Banco sempre por services.ai.db.scoped_tx + filtro explícito de tenant/espaço. Dinheiro em Decimal/string, nunca float.
- Regra canônica do realizado: só source_file terminado em ".ofx" e status "paid". Fase 1 de comprovantes continua sem baixa automática.
- Logs e erros sem conteúdo de e-mail/anexo/prompt, cabeçalhos HTTP ou segredos.
- Testes com fronteiras reais; nada de teste que só procura string no código ou que troca a lógica sob teste por mock.

COMO RODAR OS TESTES
cd backend
python -m pytest -c tests/ai/pytest.ini tests/ai
NUNCA rode "pytest" sem o -c: o conftest legado importa app e usaria as credenciais reais do .env.
O banco de teste vem do pacote pgserver (já instalado nesta máquina) ou de AI_TEST_PG_ADMIN_URL (só loopback).
Ao terminar, a suíte inteira de tests/ai deve continuar passando.

FORA DO ESCOPO DESTA ENTREGA
Rotas de proposta/operação/grants, benchmark de modelos, login V2 no frontend, OAuth de e-mail, WhatsApp, VPS.
Não refatore os componentes prontos; se a integração revelar um defeito neles, faça a correção mínima com um teste e me avise.

AO TERMINAR, ENTREGUE
1. O que foi implementado e arquivos alterados (com o diff exato de app.py).
2. Resultado dos testes: comando e números da última execução, novos e da suíte completa.
3. O que não foi feito ou não foi validado contra serviço real.
4. Atualização da tabela "O que existe e o que falta" em docs/runbooks/ai-platform.md.
5. Próximo passo concreto.

Antes de alterar arquivos, me mostre um plano curto. Trabalhe em escopo pequeno e prefira mudanças mínimas.
````

## Depois desta fatia

O segundo prompt deve pedir o restante da seção 4 da spec: rotas de proposta
(`GET`, `approve`, `reject`), de operação (`GET`, `reverse`) e de grants, com os
testes ponta a ponta de extrato por e-mail, baixa parcial e revogação.
