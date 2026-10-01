"""Orquestrador: plano, sequência de ferramentas, checkpoints e resposta.

Contrato, seções 6, 8, 9 e 10. O orquestrador conhece só duas interfaces da
espinha: ``ToolRegistry`` (ferramentas) e ``ModelGateway`` (modelo). Ele é o
dono de quatro garantias:

1. **Checkpoint.** Toda inferência e toda ferramenta é uma etapa com
   ``step_key`` estável (posição + nome + hash dos argumentos). Ao retomar
   depois de uma queda, etapa concluída é REUTILIZADA: a ferramenta não é
   chamada de novo e a inferência concluída não é refeita. Persistimos a
   decisão estruturada do modelo (quais ferramentas, com quais argumentos) e
   o resultado estruturado da ferramenta — nunca o prompt nem a resposta bruta.
2. **Autorização viva.** Antes de CADA ação o escopo e os grants são relidos
   do banco. Grant revogado no meio da execução (ou com ela ainda na fila)
   nega a próxima ação. Vale também para o reuso: em tarefa com modelo, o
   resultado guardado de uma capacidade que foi revogada não é reenviado ao
   modelo na retomada.
3. **Conteúdo não confiável não manda.** Resultado de ferramenta volta ao
   modelo como dado. Mesmo que o modelo obedeça a uma instrução escondida em
   um e-mail, a defesa é estrutural: só o subconjunto de ferramentas da tarefa
   executa, o schema rejeita propriedade extra, o contexto vem do servidor e
   escrita exige aprovação ou grant.
4. **Escrita nunca é repetida às cegas.** Etapa de escrita encontrada sem
   conclusão consulta ``finance.operation_status`` antes de qualquer nova
   tentativa; sem como confirmar, a execução vai para ``needs_reconciliation``.

Os números da resposta vêm dos ``ToolResult`` (verdade do backend). O texto do
modelo passa pela guarda numérica de ``services.ai.summary``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg2

from . import policy, prompts, runs, scope, summary
from .db import scoped_tx
from .errors import AiError
from .gateway.base import (
    PURPOSE_READ,
    PURPOSE_WRITE,
    TASK_COMPLEX,
    AttemptBudget,
    ChatMessage,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolSpec,
)
from .registry import ToolDefinition, ToolRegistry
from .settings import AiSettings
from .types import ExecutionContext, Mode, RunStatus, canonical_json


logger = logging.getLogger("ai.orchestrator")

# Subconjunto de ferramentas por tarefa. O modelo nunca recebe (nem consegue
# executar) algo fora desta lista, tenha o ator o grant que tiver.
TASK_TOOLS: Dict[str, Tuple[str, ...]] = {
    "finance_question": ("finance.read", "rag.search_personal"),
    "statement_import": (
        "email.search_financial",
        "email.get_message",
        "email.download_attachment",
        "imports.preview",
        "finance.prepare_change",
        "finance.apply_change",
    ),
}
SYSTEM_TASK_TOOLS: Dict[str, Tuple[str, ...]] = {
    "apply_proposal": ("finance.apply_change",),
    "reverse_operation": ("finance.reverse_change", "finance.apply_change"),
}

APPLY_TOOL = "finance.apply_change"
REVERSE_TOOL = "finance.reverse_change"
STATUS_TOOL = "finance.operation_status"

# O contexto é do servidor. Estas chaves nunca podem vir como argumento de
# ferramenta, em nenhum nível, mesmo que algum schema as aceitasse por engano.
RESERVED_ARG_KEYS = frozenset({"tenant_id", "actor_id", "actor_user_id", "financial_space_id"})

MAX_TOOL_ARGS_CHARS = 8000
MAX_TOOL_MESSAGE_CHARS = 24000
_LIVE_PROPOSAL_STATUSES = ("draft", "ready", "approved")

MSG_TOOL_BUDGET = "O limite de chamadas de ferramenta desta execução foi atingido."
MSG_DEADLINE = "A execução excedeu o tempo limite e foi encerrada."
MSG_SCOPE_LOST = "O acesso a este espaço financeiro não está mais disponível."
MSG_NO_GRANT = "Não há autorização ativa para as ferramentas desta tarefa."
MSG_TOOL_OUTSIDE_TASK = "Esta ferramenta não está disponível nesta tarefa."
MSG_RESERVED_ARG = "Argumentos de ferramenta não podem definir organização, pessoa ou espaço financeiro."
MSG_ATTEMPTS = "A execução foi interrompida vezes demais e foi encerrada."
MSG_CHECKPOINT_REVOKED = (
    "A autorização usada em uma etapa anterior desta execução foi revogada; a execução foi encerrada."
)
MSG_BAD_ARG_CHARS = "Argumentos de ferramenta contêm caracteres que não são aceitos."
MSG_RECONCILE = (
    "Não foi possível confirmar se a alteração foi aplicada. Nada será repetido automaticamente; "
    "a execução aguarda conciliação."
)
WARN_FALLBACK = (
    "A rota principal de modelo estava indisponível; a resposta foi gerada por uma rota alternativa autorizada."
)
WARN_ROUTE_CHANGED = (
    "O modelo foi trocado durante a execução; as etapas já concluídas foram reaproveitadas, sem repetir ferramentas."
)
WARN_RECONCILED = (
    "A execução foi interrompida durante uma alteração; o estado foi confirmado por consulta e nada foi reaplicado."
)
WARN_CANCELLED_WITH_EFFECT = (
    "Execução cancelada a pedido do titular. As alterações já confirmadas foram mantidas e podem ser revertidas."
)
WARN_FAILED_WITH_EFFECT = (
    "A execução não foi concluída, mas as alterações já confirmadas foram mantidas e podem ser revertidas."
)

# Erros de DADO ao gravar um checkpoint (o banco recusou o conteúdo, ou o texto
# nem pôde ser codificado). Falha de conexão NÃO está aqui: essa deve subir,
# para a execução ser retomada por outro worker quando o lease vencer.
_CHECKPOINT_DATA_ERRORS = (psycopg2.DataError, UnicodeError)


class _Cancelled(Exception):
    """Cancelamento solicitado: para antes da próxima ação."""


class _NeedsReconciliation(Exception):
    """Efeito de escrita com estado desconhecido."""

    def __init__(self, tool: str, reason: str) -> None:
        self.tool = tool
        self.reason = reason
        super().__init__(reason)


@dataclass
class _ToolOutcome:
    ok: bool
    result: Optional[Dict[str, Any]] = None  # ToolResult.to_dict()
    error: Optional[Dict[str, Any]] = None   # {code, retryable, safe_message, details?}
    reused: bool = False
    reconciled: bool = False


@dataclass
class _RunState:
    """Agregado da execução. Só recebe dados vindos de ``ToolResult``."""

    facts: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    proposal_ids: List[str] = field(default_factory=list)
    operation_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tools: List[Dict[str, str]] = field(default_factory=list)
    grant_ids: List[str] = field(default_factory=list)
    route_attempts: List[Dict[str, Any]] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    model: Dict[str, Any] = field(default_factory=dict)
    tool_calls: int = 0
    tools_succeeded: int = 0
    inference_calls: int = 0
    cost_micros: int = 0
    fallback_used: bool = False
    waiting_flag: bool = False
    summary_replaced: bool = False
    model_summary: Optional[str] = None
    summary: str = ""
    # Detalhes curtos do erro final (ex.: motivo dado pelo gateway). Vão para a
    # auditoria; não fazem parte do erro mostrado ao titular.
    error_details: Dict[str, Any] = field(default_factory=dict)
    _fact_keys: set = field(default_factory=set)

    def warn(self, message: str) -> None:
        if message and message not in self.warnings:
            self.warnings.append(message)

    def add_result(self, result: Dict[str, Any]) -> None:
        for fact in result.get("facts") or []:
            key = canonical_json(fact)
            if key not in self._fact_keys:
                self._fact_keys.add(key)
                self.facts.append(fact)
        known_refs = {source.get("ref") for source in self.sources}
        for source in result.get("sources") or []:
            if source.get("ref") not in known_refs:
                known_refs.add(source.get("ref"))
                self.sources.append(source)
        for item in result.get("proposal_ids") or []:
            if str(item) not in self.proposal_ids:
                self.proposal_ids.append(str(item))
        for item in result.get("operation_ids") or []:
            if str(item) not in self.operation_ids:
                self.operation_ids.append(str(item))
        for item in result.get("warnings") or []:
            self.warn(str(item))
        data = result.get("data")
        if isinstance(data, dict) and data.get("status") == RunStatus.WAITING_REVIEW.value:
            self.waiting_flag = True

    def record_inference(self, meta: Dict[str, Any]) -> None:
        self.inference_calls += int(meta.get("inference_calls") or 0)
        self.cost_micros += int(meta.get("cost_micros") or 0)
        alias = meta.get("alias")
        if alias:
            if not self.aliases or self.aliases[-1] != alias:
                self.aliases.append(alias)
            self.model = {
                "alias": alias,
                "provider": meta.get("provider"),
                "model_id": meta.get("model_id"),
                "effective_provider": meta.get("effective_provider"),
            }
        if meta.get("fallback_used"):
            self.fallback_used = True
        self.add_route_attempts(meta.get("attempts") or [])

    def add_route_attempts(self, attempts: Sequence[Dict[str, Any]]) -> None:
        for attempt in attempts:
            if len(self.route_attempts) < 40:
                self.route_attempts.append(attempt)

    def result_dict(self) -> Dict[str, Any]:
        return {
            "summary_pt_br": self.summary,
            "facts": self.facts,
            "sources": self.sources,
            "proposal_ids": self.proposal_ids,
            "operation_ids": self.operation_ids,
            "warnings": self.warnings,
        }


def _normalize_args(value: Any) -> Any:
    """Argumentos do modelo em forma estável e sem float.

    A normalização acontece UMA vez, antes de executar e de gravar o
    checkpoint: assim a retomada executa exatamente o que a primeira tentativa
    executaria. Float vira decimal em string (o schema da ferramenta converte);
    é o mesmo motivo pelo qual resultados nunca carregam float.
    """
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return str(Decimal(repr(value))) if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(key): _normalize_args(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_args(item) for item in value]
    return str(value)


def _has_reserved_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key) in RESERVED_ARG_KEYS or _has_reserved_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_reserved_key(item) for item in value)
    return False


def _short_details(raw: Any) -> Dict[str, Any]:
    """Detalhes de erro reduzidos a chaves e valores curtos.

    Nomes de campo rejeitados vêm do modelo: corta para não gravar texto
    arbitrário, e passa por ``runs.storable`` para não gravar o que o banco
    recusaria.
    """
    details: Dict[str, Any] = {}
    if not isinstance(raw, dict):
        return details
    for key, item in list(raw.items())[:5]:
        if isinstance(item, (list, tuple)):
            details[str(key)[:40]] = [str(part)[:60] for part in list(item)[:10]]
        else:
            details[str(key)[:40]] = str(item)[:120]
    return runs.storable(details)


def _error_payload(exc: AiError) -> Dict[str, Any]:
    """Erro de ferramenta devolvido ao modelo e gravado no checkpoint."""
    payload: Dict[str, Any] = {
        "code": exc.code, "retryable": exc.retryable, "safe_message": runs.storable(exc.safe_message),
    }
    details = _short_details(exc.details)
    if details:
        payload["details"] = details
    return payload


def _run_error(exc: AiError, trace_id: str) -> Dict[str, Any]:
    """Erro final da execução, com EXATAMENTE as quatro chaves do contrato (seção 6).

    ``AiError.to_dict`` acrescenta ``details`` quando existem (o gateway manda
    ``{"reason": "all_routes_failed"}``, por exemplo). Isso é diagnóstico para
    quem opera, não para o titular: fica na auditoria (``result.error_details``)
    e no checkpoint da etapa que falhou. ``GET /runs/{id}`` devolve só
    ``code``, ``retryable``, ``safe_message`` e ``trace_id``.
    """
    return {
        "code": exc.code,
        "retryable": bool(exc.retryable),
        "safe_message": exc.safe_message,
        "trace_id": trace_id,
    }


def _attempt_dicts(attempts: Any) -> List[Dict[str, Any]]:
    """Trilha de tentativas de rota (``AttemptRecord``) em forma curta e gravável."""
    result: List[Dict[str, Any]] = []
    for item in list(attempts or [])[:20]:
        try:
            latency_ms = max(0, int(getattr(item, "latency_ms", 0) or 0))
        except (TypeError, ValueError):
            latency_ms = 0
        status = getattr(item, "status", None)
        result.append(
            {
                "alias": str(getattr(item, "alias", ""))[:80],
                "provider": str(getattr(item, "provider", ""))[:40],
                "outcome": str(getattr(item, "outcome", ""))[:60],
                "latency_ms": latency_ms,
                "status": status if isinstance(status, int) and not isinstance(status, bool) else None,
            }
        )
    return runs.storable(result)


def _final_summary(response: ModelResponse) -> Optional[str]:
    parsed: Any = response.parsed
    if not isinstance(parsed, dict):
        try:
            parsed = json.loads(response.content or "")
        except (ValueError, TypeError):
            return None
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("summary_pt_br")
    cleaned = summary.clean_summary(value)
    return cleaned or None


def _as_uuid(value: Any) -> Optional[str]:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _as_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


class Orchestrator:
    """Executa uma execução já assumida por um worker (``runs.claim_next``)."""

    def __init__(
        self,
        pool,
        settings: AiSettings,
        registry: ToolRegistry,
        gateway: Optional[ModelGateway] = None,
    ) -> None:
        self._pool = pool
        self._settings = settings
        self._registry = registry
        # ``None`` é válido: tarefas determinísticas (aplicar proposta aprovada,
        # reverter) não dependem de modelo disponível (AC-11).
        self._gateway = gateway

    # ------------------------------------------------------------------ API

    def execute(self, run_id: str, tenant_id: str, owner: str) -> Dict[str, Any]:
        """Conduz a execução até um estado persistido. Não deixa ``Exception`` escapar
        da lógica de negócio: falha vira ``failed`` com erro seguro.

        ``BaseException`` (encerramento do processo) propaga de propósito, sem
        finalizar: o lease vence e outro worker retoma dos checkpoints.
        """
        started = time.monotonic()
        run = runs.load_for_execution(self._pool, tenant_id, run_id, owner)
        if run is None:
            logger.info("run_skipped run_id=%s owner=%s reason=not_owner", run_id, owner)
            return {"run_id": str(run_id), "status": "skipped"}
        run["id"] = str(run["id"])
        run["tenant_id"] = str(run["tenant_id"])
        trace_id = str(run["trace_id"])
        state = _RunState()
        error: Optional[Dict[str, Any]] = None

        try:
            if int(run["attempts"]) > runs.MAX_RUN_ATTEMPTS:
                raise AiError("internal_error", MSG_ATTEMPTS, retryable=False)
            task = run["task"]
            if task in TASK_TOOLS:
                self._run_model_task(run, owner, state)
            elif task == "apply_proposal":
                self._run_apply_proposal(run, owner, state)
            elif task == "reverse_operation":
                self._run_reverse_operation(run, owner, state)
            else:
                raise AiError("invalid_request", "Tarefa inválida.")
            status = self._conclude(run, state)
        except runs.LeaseLost:
            logger.info("run_lease_lost run_id=%s owner=%s", run_id, owner)
            return {"run_id": run["id"], "status": "lease_lost"}
        except _Cancelled:
            status = RunStatus.CANCELLED.value
        except _NeedsReconciliation as exc:
            status = RunStatus.NEEDS_RECONCILIATION.value
            state.summary = MSG_RECONCILE
            state.warn(MSG_RECONCILE)
            logger.warning("run_needs_reconciliation run_id=%s tool=%s reason=%s", run_id, exc.tool, exc.reason)
        except AiError as exc:
            status = RunStatus.FAILED.value
            error = _run_error(exc, trace_id)
            state.error_details = _short_details(exc.details)
        except Exception as exc:  # noqa: BLE001 - nada de stacktrace para o titular
            status = RunStatus.FAILED.value
            error = _run_error(AiError("internal_error"), trace_id)
            logger.error("run_internal_error run_id=%s error_type=%s", run_id, type(exc).__name__)

        return self._finalize(run, owner, state, status, error, started)

    # ------------------------------------------------------- antes de agir

    def _context(self, run: Dict[str, Any]) -> ExecutionContext:
        """Contexto relido do banco. Vínculo perdido -> ``scope_denied``."""
        try:
            ctx = scope.context_for_run(self._pool, run)
        except AiError:
            raise AiError("scope_denied", MSG_SCOPE_LOST)
        # A execução fixa a versão de política com que foi criada (contrato, seção 15).
        return replace(ctx, policy_version=int(run["policy_version"]))

    def _before_action(self, run: Dict[str, Any], owner: str) -> Tuple[ExecutionContext, List[policy.Grant]]:
        """Roda antes de CADA inferência e CADA ferramenta.

        Ordem: posse do lease, cancelamento, prazo, escopo e grants — todos
        lidos agora, do banco. Nada aqui vem de cache nem da tentativa anterior.
        """
        with scoped_tx(self._pool, run["tenant_id"]) as cursor:
            lease = runs.touch_lease(cursor, run["id"], run["tenant_id"], owner, self._settings.lease_seconds)
        if lease["cancel_requested"]:
            raise _Cancelled()
        if lease["deadline_passed"]:
            raise AiError("budget_exceeded", MSG_DEADLINE)
        ctx = self._context(run)
        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            grants = policy.load_active_grants(cursor, ctx)
        return ctx, grants

    def _definition(self, name: str) -> Optional[ToolDefinition]:
        try:
            return self._registry.get(name)
        except AiError:
            return None

    def _allowed_tools(self, task: str, grants: Sequence[policy.Grant]) -> Tuple[str, ...]:
        if task in SYSTEM_TASK_TOOLS:
            return SYSTEM_TASK_TOOLS[task]
        names = list(TASK_TOOLS.get(task, ()))
        if APPLY_TOOL in names:
            # Conduzida pelo modelo, a aplicação só existe com grant delegado.
            # No modo assistido quem aplica é a tarefa determinística criada
            # pela aprovação do titular, nunca uma decisão do modelo.
            grant = policy.best_grant(grants, APPLY_TOOL)
            if grant is None or grant.mode != Mode.DELEGATED.value:
                names.remove(APPLY_TOOL)
        return tuple(names)

    # ------------------------------------------------------ tarefa com modelo

    def _run_model_task(self, run: Dict[str, Any], owner: str, state: _RunState) -> None:
        if self._gateway is None:
            raise AiError("model_unavailable")
        task = run["task"]
        payload = run["input"] if isinstance(run["input"], dict) else {}
        messages: List[ChatMessage] = [
            ChatMessage(role="system", content=prompts.system_prompt(task)),
            ChatMessage(
                role="user",
                content=prompts.user_message(str(payload.get("message") or ""), payload.get("input_refs") or []),
            ),
        ]
        position = 0
        chain = hashlib.sha256(("%s|%s" % (run["id"], task)).encode("utf-8")).hexdigest()

        while True:
            ctx, grants = self._before_action(run, owner)
            allowed = self._allowed_tools(task, grants)
            specs = self._registry.specs_for(grants, only=allowed)
            if not specs:
                # Nenhuma capacidade da tarefa está autorizada agora (sem grant ou
                # grant revogado, inclusive com a execução na fila): o pedido do
                # titular nem chega a ser enviado a um modelo.
                raise AiError("capability_denied", MSG_NO_GRANT)
            remaining = self._settings.max_tool_calls_per_run - state.tool_calls
            # Orçamento de ferramentas esgotado: a inferência seguinte não recebe
            # ferramentas, o que obriga o modelo a concluir com o que já tem.
            offered = specs if remaining > 0 else []

            position += 1
            step_key = "%03d:inference:%s" % (position, chain[:16])
            decision, meta = self._inference_step(run, owner, ctx, state, step_key, messages, offered, remaining)
            chain = hashlib.sha256(("%s|%s" % (chain, step_key)).encode("utf-8")).hexdigest()
            state.record_inference(meta)

            calls = decision.get("tool_calls") or []
            if not calls:
                final = decision.get("final") or {}
                state.model_summary = final.get("summary_pt_br")
                return

            messages.append(
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(id=call["id"], name=call["name"], arguments=call.get("arguments") or {})
                        for call in calls
                    ],
                )
            )
            for call in calls:
                position += 1
                outcome = self._tool_action(
                    run, owner, state,
                    position=position,
                    name=call["name"],
                    arguments=call.get("arguments") or {},
                    invalid=call.get("invalid"),
                )
                # Erro de ferramenta (argumento inválido, capacidade negada...) volta
                # ao modelo como resultado; conta no limite e não derruba a execução.
                messages.append(self._tool_message(call, outcome))
                step_key = "%03d:tool:%s" % (position, call["name"][:40])
                chain = hashlib.sha256(("%s|%s" % (chain, step_key)).encode("utf-8")).hexdigest()

    def _inference_step(
        self,
        run: Dict[str, Any],
        owner: str,
        ctx: ExecutionContext,
        state: _RunState,
        step_key: str,
        messages: List[ChatMessage],
        offered: List[Dict[str, Any]],
        remaining: int,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        lease_seconds = self._settings.lease_seconds
        step = runs.begin_step(
            self._pool, run["id"], run["tenant_id"], owner,
            step_key=step_key, kind="inference", name=runs.INFERENCE_STEP_NAME,
            version=prompts.PROMPT_VERSION, lease_seconds=lease_seconds,
        )
        if step["state"] == "succeeded":
            # Inferência concluída não é refeita: nem no reinício do worker, nem
            # quando a rota de modelo mudou entre uma tentativa e outra.
            output = step["output"] or {}
            return dict(output.get("decision") or {}), dict(output.get("meta") or {})
        if step["state"] in ("interrupted", "failed"):
            # Inferência não tem efeito externo: repetir é seguro.
            runs.restart_step(self._pool, run["id"], run["tenant_id"], owner, step["id"], lease_seconds=lease_seconds)

        definitions = [self._definition(spec["name"]) for spec in offered]
        has_write = any(item is not None and item.effect == "write" for item in definitions)
        request = ModelRequest(
            task_class=TASK_COMPLEX,
            messages=list(messages),
            # Só é "escrita" quando o modelo pode disparar um efeito direto
            # (grant delegado). O gateway usa isso para não degradar para uma
            # rota homologada apenas para leitura/resumo.
            purpose=PURPOSE_WRITE if has_write else PURPOSE_READ,
            tools=[ToolSpec(name=s["name"], description=s["description"], parameters=s["parameters"]) for s in offered],
            response_schema=prompts.FINAL_RESPONSE_SCHEMA,
        )
        # Orçamento NOVO a cada etapa de inferência: o teto é por etapa e quem o
        # consome (retentativas, troca de rota) é exclusivamente o gateway.
        budget = AttemptBudget(limit=self._settings.max_inference_calls_per_step)
        started = time.monotonic()
        try:
            response = self._gateway.complete(request, ctx, budget)
        except AiError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            # O gateway anexa ao erro a trilha das rotas tentadas, o custo já
            # gasto e o número de chamadas (lidos com getattr porque não fazem
            # parte de ``AiError``). É justamente quando TODAS as rotas caem que
            # a trilha importa: sem lê-la aqui, a auditoria de uma execução que
            # falhou por indisponibilidade sairia sem nenhuma tentativa.
            attempts = _attempt_dicts(getattr(exc, "attempts", None))
            calls = max(int(budget.used or 0), _as_count(getattr(exc, "inference_calls", 0)))
            cost_micros = _as_count(getattr(exc, "cost_micros", 0))
            failure_meta: Dict[str, Any] = {
                "inference_calls": calls, "duration_ms": duration_ms, "cost_micros": cost_micros,
                "attempts": attempts, "prompt_version": prompts.PROMPT_VERSION,
            }
            details = _short_details(exc.details)
            if details:
                failure_meta["details"] = details
            state.inference_calls += calls
            state.cost_micros += cost_micros
            state.add_route_attempts(attempts)
            runs.finish_step(
                self._pool, run["id"], run["tenant_id"], owner, step["id"],
                status="failed", error_code=exc.code, output={"meta": failure_meta},
                duration_ms=duration_ms, cost_micros=cost_micros, lease_seconds=lease_seconds,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            state.inference_calls += int(budget.used or 0)
            logger.error("inference_internal_error run_id=%s error_type=%s", run["id"], type(exc).__name__)
            runs.finish_step(
                self._pool, run["id"], run["tenant_id"], owner, step["id"],
                status="failed", error_code="internal_error",
                output={"meta": {"inference_calls": int(budget.used or 0), "duration_ms": duration_ms}},
                duration_ms=duration_ms, lease_seconds=lease_seconds,
            )
            raise AiError("internal_error")

        duration_ms = int((time.monotonic() - started) * 1000)
        decision = self._decision(response, step["seq"], keep=max(1, remaining + 1))
        meta = {
            "alias": response.alias,
            "provider": response.provider,
            "model_id": response.model_id,
            "effective_provider": response.effective_provider,
            "inference_calls": max(int(response.inference_calls or 0), int(budget.used or 0)),
            "fallback_used": bool(response.fallback_used),
            "cost_micros": max(0, int(response.cost_micros or 0)),
            "latency_ms": max(0, int(response.latency_ms or 0)),
            "duration_ms": duration_ms,
            "finish_reason": str(response.finish_reason)[:20],
            "usage": {
                "input_tokens": response.usage.input_tokens if response.usage else None,
                "output_tokens": response.usage.output_tokens if response.usage else None,
            },
            "attempts": _attempt_dicts(response.attempts),
            "prompt_version": prompts.PROMPT_VERSION,
        }
        # Nome de modelo e de fornecedor efetivo vêm do provedor: passam pela
        # mesma higiene de qualquer texto externo antes de ir para o checkpoint.
        meta = runs.storable(meta)
        # Checkpoint: decisão estruturada + metadados. Sem prompt, sem resposta bruta.
        runs.finish_step(
            self._pool, run["id"], run["tenant_id"], owner, step["id"],
            status="succeeded", output={"decision": decision, "meta": meta},
            duration_ms=duration_ms, cost_micros=meta["cost_micros"], lease_seconds=lease_seconds,
        )
        logger.info(
            "inference_done run_id=%s alias=%s calls=%d tool_calls=%d duration_ms=%d",
            run["id"], meta["alias"], meta["inference_calls"], len(decision["tool_calls"]), duration_ms,
        )
        return decision, meta

    @staticmethod
    def _decision(response: ModelResponse, seq: int, keep: int) -> Dict[str, Any]:
        calls: List[Dict[str, Any]] = []
        for index, call in enumerate(list(response.tool_calls or [])[:keep]):
            name = call.name if isinstance(call.name, str) else ""
            entry: Dict[str, Any] = {
                # Id e nome vêm do modelo. Um NUL no nome vira U+FFFD: o nome
                # deixa de casar com qualquer ferramenta e a chamada é negada.
                "id": runs.storable(str(call.id or "call_%d_%d" % (seq, index))[:120]),
                "name": runs.storable(name[:120]),
                "arguments": {},
            }
            if not isinstance(call.arguments, dict):
                entry["invalid"] = "not_object"
            else:
                normalized = _normalize_args(call.arguments)
                if runs.has_unstorable(normalized):
                    # Argumento com NUL (ou substituto isolado) não pode ser
                    # gravado no checkpoint. Em vez de "consertar" o texto e
                    # executar a ferramenta com algo que o modelo não pediu, a
                    # chamada é recusada e o erro volta ao modelo.
                    entry["invalid"] = "bad_chars"
                elif len(canonical_json(normalized)) > MAX_TOOL_ARGS_CHARS:
                    entry["invalid"] = "too_large"
                else:
                    entry["arguments"] = normalized
            calls.append(entry)
        final = None if calls else {"summary_pt_br": _final_summary(response)}
        return {"tool_calls": calls, "final": final}

    def _tool_message(self, call: Dict[str, Any], outcome: _ToolOutcome) -> ChatMessage:
        """Resultado da ferramenta como DADO para o modelo (JSON, nunca instrução)."""
        name = call["name"] if self._definition(call["name"]) is not None else runs.UNKNOWN_TOOL_NAME
        if outcome.ok:
            body: Dict[str, Any] = {
                "kind": "tool_result", "tool": name, "status": "ok",
                "untrusted_data": True, "result": outcome.result,
            }
            text = canonical_json(body)
            if len(text) > MAX_TOOL_MESSAGE_CHARS:
                # Resultado grande demais para o prompt: o modelo recebe a parte
                # estruturada; o dado completo continua no checkpoint.
                result = dict(outcome.result or {})
                result["data"] = {"truncated": True}
                body["result"] = result
                text = canonical_json(body)
            if len(text) > MAX_TOOL_MESSAGE_CHARS:
                text = canonical_json(
                    {"kind": "tool_result", "tool": name, "status": "ok", "untrusted_data": True,
                     "result": {"truncated": True}}
                )
        else:
            text = canonical_json({"kind": "tool_result", "tool": name, "status": "error", "error": outcome.error})
        return ChatMessage(role="tool", content=text, tool_call_id=call["id"], tool_name=name)

    # ------------------------------------------------------------ ferramentas

    def _tool_action(
        self,
        run: Dict[str, Any],
        owner: str,
        state: _RunState,
        *,
        position: int,
        name: str,
        arguments: Dict[str, Any],
        invalid: Optional[str] = None,
    ) -> _ToolOutcome:
        """Uma chamada de ferramenta = uma etapa com checkpoint."""
        if state.tool_calls >= self._settings.max_tool_calls_per_run:
            raise AiError("budget_exceeded", MSG_TOOL_BUDGET)
        ctx, grants = self._before_action(run, owner)
        state.tool_calls += 1

        definition = self._definition(name)
        # Nome inventado pelo modelo não vira rótulo na tela do titular.
        step_name = name if definition is not None else runs.UNKNOWN_TOOL_NAME
        version = definition.version if definition is not None else None
        args_hash = ToolRegistry.args_hash(name, version or "-", arguments)
        step_key = "%03d:tool:%s:%s" % (position, step_name, args_hash[:16])
        lease_seconds = self._settings.lease_seconds

        step = runs.begin_step(
            self._pool, run["id"], run["tenant_id"], owner,
            step_key=step_key, kind="tool", name=step_name, version=version,
            args_hash=args_hash, lease_seconds=lease_seconds,
        )
        if step["state"] in ("succeeded", "failed"):
            outcome = self._outcome_from_checkpoint(step)
            if outcome.ok and run["task"] in TASK_TOOLS:
                # AC-05 na retomada. O resultado guardado seria enviado ao
                # modelo em uma NOVA inferência e entraria na resposta: isso é
                # uma ação nova que usa aquela capacidade. Se o grant dela foi
                # revogado enquanto a execução esperava (worker caiu, lease
                # venceu), a execução para aqui, antes de qualquer inferência.
                # Tarefas sem modelo ficam de fora de propósito: nelas o reuso
                # só registra um efeito já confirmado, que permanece.
                try:
                    policy.authorize(grants, step_name)
                except AiError:
                    state.tools.append({"name": step_name, "status": "revoked"})
                    logger.info("tool_checkpoint_revoked run_id=%s tool=%s seq=%d", run["id"], step_name, step["seq"])
                    raise AiError("capability_denied", MSG_CHECKPOINT_REVOKED)
            self._record_tool(state, step_name, outcome, grants)
            logger.info("tool_reused run_id=%s tool=%s seq=%d", run["id"], step_name, step["seq"])
            return outcome

        interrupted = step["state"] == "interrupted"
        is_write = definition is not None and definition.effect == "write"
        if interrupted:
            runs.restart_step(self._pool, run["id"], run["tenant_id"], owner, step["id"], lease_seconds=lease_seconds)

        started = time.monotonic()
        outcome: Optional[_ToolOutcome] = None
        try:
            if interrupted and is_write:
                # A tentativa anterior caiu no meio de uma ESCRITA. Não se repete
                # às cegas: primeiro se consulta se o efeito existe.
                outcome = self._recover_write(ctx, grants, name, arguments, resumed=True)
            if outcome is None:
                allowed = self._allowed_tools(run["task"], grants)
                outcome = self._call_tool(ctx, grants, definition, name, arguments, invalid, allowed)
        except _NeedsReconciliation:
            # A etapa fica "started" de propósito: é o registro de que o
            # resultado desta escrita é desconhecido.
            state.tools.append({"name": step_name, "status": "unknown"})
            raise
        duration_ms = int((time.monotonic() - started) * 1000)

        if outcome.ok:
            output: Dict[str, Any] = {"result": outcome.result}
            if outcome.reconciled:
                output["reconciled"] = True
            try:
                runs.finish_step(
                    self._pool, run["id"], run["tenant_id"], owner, step["id"],
                    status="succeeded", output=output, duration_ms=duration_ms, lease_seconds=lease_seconds,
                )
            except _CHECKPOINT_DATA_ERRORS as exc:
                if is_write:
                    # Escrita confirmada cujo registro o banco recusou: não dá
                    # para dizer ao modelo "a ferramenta falhou". A etapa fica
                    # "started" e o encerramento a trata como efeito a conciliar.
                    raise
                # Leitura cujo resultado não pôde ser gravado (dado que o banco
                # recusa e o saneamento não previu). Sem checkpoint não há reuso
                # seguro; o modelo recebe um erro de ferramenta e segue, em vez
                # de a execução inteira cair com erro interno.
                logger.error(
                    "tool_checkpoint_rejected run_id=%s tool=%s error_type=%s",
                    run["id"], step_name, type(exc).__name__,
                )
                outcome = _ToolOutcome(ok=False, error=_error_payload(AiError("internal_error")))
        if not outcome.ok:
            runs.finish_step(
                self._pool, run["id"], run["tenant_id"], owner, step["id"],
                status="failed", output={"error": outcome.error},
                error_code=(outcome.error or {}).get("code"), duration_ms=duration_ms,
                lease_seconds=lease_seconds,
            )
        self._record_tool(state, step_name, outcome, grants)
        logger.info(
            "tool_done run_id=%s tool=%s status=%s code=%s duration_ms=%d",
            run["id"], step_name, "ok" if outcome.ok else "error",
            (outcome.error or {}).get("code", "-"), duration_ms,
        )
        return outcome

    @staticmethod
    def _outcome_from_checkpoint(step: Dict[str, Any]) -> _ToolOutcome:
        output = step["output"] if isinstance(step["output"], dict) else {}
        if step["state"] == "succeeded":
            return _ToolOutcome(ok=True, result=dict(output.get("result") or {}), reused=True,
                                reconciled=bool(output.get("reconciled")))
        # Falha registrada também é checkpoint: o modelo já decidiu o passo
        # seguinte com base nela, então a retomada devolve o mesmo erro em vez
        # de chamar a ferramenta outra vez.
        error = output.get("error") if isinstance(output.get("error"), dict) else None
        if error is None:
            error = _error_payload(AiError("internal_error"))
        return _ToolOutcome(ok=False, error=error, reused=True)

    @staticmethod
    def _record_tool(state: _RunState, step_name: str, outcome: _ToolOutcome, grants: Sequence[policy.Grant]) -> None:
        state.tools.append({"name": step_name, "status": "ok" if outcome.ok else (outcome.error or {}).get("code", "error")})
        if not outcome.ok:
            return
        state.tools_succeeded += 1
        state.add_result(outcome.result or {})
        if outcome.reconciled:
            state.warn(WARN_RECONCILED)
        grant = policy.best_grant(grants, step_name)
        if grant is not None and grant.id not in state.grant_ids:
            state.grant_ids.append(grant.id)

    def _call_tool(
        self,
        ctx: ExecutionContext,
        grants: Sequence[policy.Grant],
        definition: Optional[ToolDefinition],
        name: str,
        arguments: Dict[str, Any],
        invalid: Optional[str],
        allowed: Sequence[str],
    ) -> _ToolOutcome:
        if definition is None or name not in allowed:
            # Ferramenta inexistente ou fora do subconjunto da tarefa: negada
            # antes de qualquer handler, tenha o ator o grant que tiver.
            return _ToolOutcome(ok=False, error=_error_payload(AiError("capability_denied", MSG_TOOL_OUTSIDE_TASK)))
        if invalid is not None:
            message = MSG_BAD_ARG_CHARS if invalid == "bad_chars" else "Argumentos de ferramenta inválidos."
            return _ToolOutcome(ok=False, error=_error_payload(AiError("invalid_request", message)))
        if _has_reserved_key(arguments):
            return _ToolOutcome(ok=False, error=_error_payload(AiError("invalid_request", MSG_RESERVED_ARG)))

        is_write = definition.effect == "write"
        try:
            # O registro confere flags, grant e schema (propriedade extra é
            # rejeitada) e entrega ao handler o contexto do SERVIDOR.
            result = self._registry.execute(name, arguments, ctx, grants)
        except AiError as exc:
            if is_write and exc.retryable:
                # Falha "tente de novo" em uma escrita = resultado desconhecido.
                return self._recover_write(ctx, grants, name, arguments, resumed=False)
            return _ToolOutcome(ok=False, error=_error_payload(exc))
        except Exception as exc:  # noqa: BLE001
            logger.error("tool_internal_error tool=%s error_type=%s", name, type(exc).__name__)
            if is_write:
                return self._recover_write(ctx, grants, name, arguments, resumed=False)
            return _ToolOutcome(ok=False, error=_error_payload(AiError("internal_error")))
        # Conteúdo de e-mail, PDF ou OCR é dado não confiável e pode trazer NUL.
        # O resultado é saneado UMA vez, aqui: o que vai para o modelo agora é
        # idêntico ao que fica no checkpoint e voltaria em uma retomada.
        return _ToolOutcome(ok=True, result=runs.storable(result.to_dict()))

    # ------------------------------------------------- recuperação de escrita

    def _can_consult_status(self, grants: Sequence[policy.Grant]) -> bool:
        if self._definition(STATUS_TOOL) is None:
            return False
        try:
            policy.authorize(grants, STATUS_TOOL)
        except AiError:
            return False
        return True

    def _find_operation(
        self, ctx: ExecutionContext, name: str, arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Deriva a operação de uma etapa de escrita a partir dos argumentos.

        Devolve ``(derivável, operação_gravada, operação_planejada)``.

        * ``operação_gravada``: id em ``ai_operations``. Essa linha nasce na
          mesma transação do efeito financeiro: se existe, o efeito existe.
        * ``operação_planejada``: id que a operação TERÁ quando for aplicada
          (determinístico, anotado pelo backend em
          ``expected_effect.planned_operation_id`` da proposta). Permite
          perguntar a ``finance.operation_status`` por algo que ainda não
          aconteceu e ouvir "não aplicada".
        """
        if name == APPLY_TOOL:
            target = _as_uuid(arguments.get("proposal_id"))
            column = "proposal_id"
        elif name == REVERSE_TOOL:
            target = _as_uuid(arguments.get("operation_id"))
            column = "reverses_operation_id"
        else:
            return False, None, None
        if target is None:
            return False, None, None
        planned = None
        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            cursor.execute(
                "SELECT id FROM ai_operations WHERE tenant_id = %s AND financial_space_id = %s AND "
                + column + " = %s ORDER BY applied_at, id LIMIT 1",
                (ctx.tenant_id, ctx.financial_space_id, target),
            )
            row = cursor.fetchone()
            if row is None and name == APPLY_TOOL:
                cursor.execute(
                    "SELECT expected_effect ->> 'planned_operation_id' AS planned FROM ai_proposals "
                    "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s",
                    (target, ctx.tenant_id, ctx.financial_space_id),
                )
                proposal = cursor.fetchone()
                planned = _as_uuid(proposal["planned"]) if proposal is not None and proposal["planned"] else None
        return True, (str(row["id"]) if row is not None else None), planned

    def _recover_write(
        self,
        ctx: ExecutionContext,
        grants: Sequence[policy.Grant],
        name: str,
        arguments: Dict[str, Any],
        *,
        resumed: bool,
    ) -> Optional[_ToolOutcome]:
        """Decide o que fazer com uma escrita de resultado desconhecido.

        A pergunta é sempre feita a ``finance.operation_status``, pelo registro:

        * a consulta confirma a operação -> usa esse resultado; a escrita NÃO é
          refeita;
        * a consulta mostra que não há efeito, em uma RETOMADA (o worker
          anterior está parado há pelo menos um lease) -> devolve ``None``: uma
          nova tentativa é permitida. A chave única de operação continua sendo
          a última barreira contra duplicidade;
        * a consulta mostra que não há efeito logo após uma falha NESTE worker
          -> o commit pode estar em trânsito: ``needs_reconciliation``, sem
          repetir;
        * sem como derivar a operação, sem acesso à consulta, ou consulta que
          falha ou contradiz o banco -> ``needs_reconciliation``.
        """
        if not self._can_consult_status(grants):
            raise _NeedsReconciliation(name, "status_unavailable")
        derivable, applied_id, planned_id = self._find_operation(ctx, name, arguments)
        if not derivable:
            raise _NeedsReconciliation(name, "operation_not_derivable")

        target = applied_id or planned_id
        if target is not None:
            try:
                status = self._registry.execute(STATUS_TOOL, {"operation_id": target}, ctx, grants)
            except AiError as exc:
                if exc.code != "operation_unknown" or applied_id is not None:
                    logger.error("operation_status_failed tool=%s code=%s", name, exc.code)
                    raise _NeedsReconciliation(name, "status_failed")
                status = None  # o backend não conhece a operação planejada: nada foi gravado
            except Exception as exc:  # noqa: BLE001
                logger.error("operation_status_failed tool=%s error_type=%s", name, type(exc).__name__)
                raise _NeedsReconciliation(name, "status_failed")
            if status is not None:
                result = runs.storable(status.to_dict())
                if target in [str(item) for item in result.get("operation_ids") or []]:
                    return _ToolOutcome(ok=True, result=result, reconciled=True)
            if applied_id is not None:
                # O banco tem a operação, mas a consulta não a confirmou.
                raise _NeedsReconciliation(name, "status_mismatch")

        if resumed:
            return None
        raise _NeedsReconciliation(name, "outcome_unknown")

    # --------------------------------------------- tarefas determinísticas

    @staticmethod
    def _raise_tool_error(outcome: _ToolOutcome) -> None:
        error = outcome.error or {}
        code = error.get("code") or "internal_error"
        try:
            raise AiError(code, error.get("safe_message"), retryable=error.get("retryable"))
        except ValueError:
            raise AiError("internal_error")

    def _settle_reviews(self, run: Dict[str, Any], proposal_id: Optional[str]) -> None:
        if not proposal_id:
            return
        with scoped_tx(self._pool, run["tenant_id"]) as cursor:
            runs.settle_waiting_review(cursor, run["tenant_id"], proposal_id)

    def _run_apply_proposal(self, run: Dict[str, Any], owner: str, state: _RunState) -> None:
        """Aplica uma proposta aprovada. Não chama modelo: funciona com a IA
        generativa fora do ar (AC-11)."""
        payload = run["input"] if isinstance(run["input"], dict) else {}
        outcome = self._tool_action(
            run, owner, state, position=1, name=APPLY_TOOL,
            arguments={
                "proposal_id": payload.get("proposal_id"),
                "expected_version": payload.get("expected_version"),
            },
        )
        if not outcome.ok:
            self._raise_tool_error(outcome)
        self._settle_reviews(run, payload.get("proposal_id"))

    def _run_reverse_operation(self, run: Dict[str, Any], owner: str, state: _RunState) -> None:
        """Reversão: aplica a compensação aprovada, ou cria a compensação.

        O orquestrador nunca aprova nada: a compensação só é aplicada aqui
        quando o backend já a marcou como ``approved`` (aprovação específica do
        titular ou grant delegado conferido pela ferramenta).
        """
        payload = run["input"] if isinstance(run["input"], dict) else {}
        if "proposal_id" in payload:
            self._run_apply_proposal(run, owner, state)
            return
        outcome = self._tool_action(
            run, owner, state, position=1, name=REVERSE_TOOL,
            arguments={"operation_id": payload.get("operation_id"), "reason": payload.get("reason")},
        )
        if not outcome.ok:
            self._raise_tool_error(outcome)
        result = outcome.result or {}
        if result.get("operation_ids"):
            return  # a ferramenta já registrou o evento compensatório
        approved = self._approved_proposals(run, [str(item) for item in result.get("proposal_ids") or []])
        position = 1
        for proposal_id, version in approved:
            position += 1
            applied = self._tool_action(
                run, owner, state, position=position, name=APPLY_TOOL,
                arguments={"proposal_id": proposal_id, "expected_version": version},
            )
            if not applied.ok:
                self._raise_tool_error(applied)
            self._settle_reviews(run, proposal_id)

    def _approved_proposals(self, run: Dict[str, Any], proposal_ids: Sequence[str]) -> List[Tuple[str, int]]:
        ids = [item for item in (_as_uuid(value) for value in proposal_ids) if item]
        if not ids:
            return []
        with scoped_tx(self._pool, run["tenant_id"]) as cursor:
            cursor.execute(
                "SELECT id, version FROM ai_proposals WHERE tenant_id = %s AND financial_space_id = %s "
                "AND id = ANY(%s::uuid[]) AND status = 'approved' ORDER BY created_at, id",
                (run["tenant_id"], str(run["financial_space_id"]), ids),
            )
            return [(str(row["id"]), int(row["version"])) for row in cursor.fetchall()]

    # ------------------------------------------------------------ conclusão

    def _waiting_review(self, run: Dict[str, Any], state: _RunState) -> bool:
        """Há proposta pendente de revisão? A resposta vem do estado no banco."""
        ids = [item for item in (_as_uuid(value) for value in state.proposal_ids) if item]
        statuses: Dict[str, str] = {}
        if ids:
            with scoped_tx(self._pool, run["tenant_id"]) as cursor:
                cursor.execute(
                    "SELECT id, status FROM ai_proposals WHERE tenant_id = %s AND financial_space_id = %s "
                    "AND id = ANY(%s::uuid[])",
                    (run["tenant_id"], str(run["financial_space_id"]), ids),
                )
                statuses = {str(row["id"]): row["status"] for row in cursor.fetchall()}
        if any(status in _LIVE_PROPOSAL_STATUSES for status in statuses.values()):
            return True
        unknown = [item for item in state.proposal_ids if _as_uuid(item) not in statuses]
        if unknown and not state.operation_ids:
            return True
        # A ferramenta sinalizou revisão e não há como provar, pelo banco, que
        # todas as propostas desta execução já foram resolvidas.
        return state.waiting_flag and not statuses

    def _conclude(self, run: Dict[str, Any], state: _RunState) -> str:
        waiting = self._waiting_review(run, state)
        if run["task"] in TASK_TOOLS:
            outcome = summary.guard_summary(
                state.model_summary, state.facts,
                tools_succeeded=state.tools_succeeded > 0,
                proposal_ids=state.proposal_ids, operation_ids=state.operation_ids,
                waiting_review=waiting,
            )
            state.summary = outcome.text
            state.summary_replaced = outcome.replaced
            for warning in outcome.warnings:
                state.warn(warning)
        else:
            state.summary = summary.deterministic_summary(
                state.facts, proposal_ids=state.proposal_ids, operation_ids=state.operation_ids,
                waiting_review=waiting,
            )
        return RunStatus.WAITING_REVIEW.value if waiting else RunStatus.COMPLETED.value

    def _merge_checkpoints(self, run: Dict[str, Any], state: _RunState) -> bool:
        """Inclui no agregado o que já está confirmado nos checkpoints.

        Em cancelamento ou falha logo após uma retomada, o estado em memória
        pode não ter relido as etapas anteriores. Um efeito já aplicado não
        pode sumir do resultado só porque a execução terminou de outro jeito.

        Devolve ``True`` se existe uma etapa de ESCRITA ainda ``started``: uma
        escrita cujo resultado ninguém confirmou.
        """
        with scoped_tx(self._pool, run["tenant_id"]) as cursor:
            cursor.execute(
                "SELECT kind, name, status, output, cost_micros FROM ai_run_steps "
                "WHERE tenant_id = %s AND run_id = %s ORDER BY seq",
                (run["tenant_id"], run["id"]),
            )
            rows = cursor.fetchall()
        tool_steps = inference_calls = cost_micros = 0
        last_meta: Optional[Dict[str, Any]] = None
        dangling_write = False
        for row in rows:
            output = row["output"] if isinstance(row["output"], dict) else {}
            cost_micros += int(row["cost_micros"] or 0)
            if row["kind"] == "tool":
                tool_steps += 1
                if row["status"] == "succeeded" and isinstance(output.get("result"), dict):
                    state.add_result(output["result"])
                elif row["status"] == "started":
                    definition = self._definition(row["name"])
                    # Sem definição não dá para saber o efeito: trata como escrita.
                    if definition is None or definition.effect == "write":
                        dangling_write = True
                continue
            meta = output.get("meta") if isinstance(output.get("meta"), dict) else {}
            inference_calls += int(meta.get("inference_calls") or 0)
            if row["status"] == "succeeded" and meta.get("alias"):
                last_meta = meta
                if meta.get("fallback_used"):
                    state.fallback_used = True
        # Os contadores gravados valem para a execução inteira, não só para a
        # tentativa deste worker.
        state.tool_calls = max(state.tool_calls, tool_steps)
        state.inference_calls = max(state.inference_calls, inference_calls)
        state.cost_micros = max(state.cost_micros, cost_micros)
        if not state.model and last_meta is not None:
            state.model = {
                "alias": last_meta.get("alias"),
                "provider": last_meta.get("provider"),
                "model_id": last_meta.get("model_id"),
                "effective_provider": last_meta.get("effective_provider"),
            }
        return dangling_write

    def _finalize(
        self,
        run: Dict[str, Any],
        owner: str,
        state: _RunState,
        status: str,
        error: Optional[Dict[str, Any]],
        started: float,
    ) -> Dict[str, Any]:
        dangling_write = self._merge_checkpoints(run, state)
        if status in (RunStatus.FAILED.value, RunStatus.CANCELLED.value):
            # Sem resposta do modelo a apresentar; o resumo fica vazio e o
            # estado (erro ou cancelamento) fala por si.
            state.summary = ""
            if dangling_write:
                # A execução parou (prazo, cancelamento, tentativas...) com uma
                # ESCRITA aberta de uma tentativa anterior. Dizer "falhou" ou
                # "cancelada" afirmaria que nada aconteceu, e isso não se sabe.
                status = RunStatus.NEEDS_RECONCILIATION.value
                state.summary = MSG_RECONCILE
                state.warn(MSG_RECONCILE)
                logger.warning("run_needs_reconciliation run_id=%s reason=dangling_write", run["id"])
        if status == RunStatus.CANCELLED.value and state.operation_ids:
            state.warn(WARN_CANCELLED_WITH_EFFECT)
        if status == RunStatus.FAILED.value and state.operation_ids:
            # "Falhou" não significa "nada aconteceu": o que já foi confirmado
            # continua listado em operation_ids e o titular é avisado.
            state.warn(WARN_FAILED_WITH_EFFECT)
        if state.fallback_used:
            state.warn(WARN_FALLBACK)
        if len(set(state.aliases)) > 1:
            state.warn(WARN_ROUTE_CHANGED)

        duration_ms = int((time.monotonic() - started) * 1000)
        model = dict(state.model)
        model["fallback_used"] = state.fallback_used
        # Auditoria por referência (contrato, seção 11): quem, com qual
        # autorização, qual modelo, quais ferramentas, resultado, tempo e custo.
        audit = {
            "task": run["task"],
            "status": status,
            "financial_space_id": str(run["financial_space_id"]),
            "grant_ids": list(state.grant_ids),
            "policy_version": int(run["policy_version"]),
            "contract_version": run["contract_version"],
            "prompt_version": prompts.PROMPT_VERSION if run["task"] in TASK_TOOLS else None,
            "source_refs": [str(source.get("ref")) for source in state.sources][:50],
            "model": {
                "alias": model.get("alias"),
                "provider": model.get("provider"),
                "model_id": model.get("model_id"),
                "effective_provider": model.get("effective_provider"),
                "fallback_used": state.fallback_used,
            },
            "inference_calls": state.inference_calls,
            "route_attempts": state.route_attempts,
            "run_attempts": int(run["attempts"]),
            "tools": state.tools[:50],
            "tool_calls": state.tool_calls,
            "result": {
                "facts": len(state.facts),
                "proposal_ids": list(state.proposal_ids),
                "operation_ids": list(state.operation_ids),
                "summary_replaced": state.summary_replaced,
                "error_code": error.get("code") if error else None,
                # Diagnóstico curto do erro (ex.: motivo do gateway). Fica só
                # aqui; o erro mostrado ao titular tem as quatro chaves do contrato.
                "error_details": dict(state.error_details) if error and state.error_details else None,
            },
            "duration_ms": duration_ms,
            "cost_micros": state.cost_micros,
            "cost_currency": self._settings.budget_currency,
            "trace_id": str(run["trace_id"]),
        }
        try:
            # ``finish_run`` devolve o estado gravado: se a revisão terminou
            # entre a conclusão (``_conclude``) e esta gravação, uma execução
            # que ia para "waiting_review" é encerrada como "completed".
            status = runs.finish_run(
                self._pool, run["id"], run["tenant_id"], owner,
                status=status, result=state.result_dict(), error=error, model=model,
                inference_calls=state.inference_calls, tool_calls=state.tool_calls,
                cost_micros=state.cost_micros, cost_currency=self._settings.budget_currency,
                actor_user_id=str(run["actor_user_id"]), audit=audit,
            )
        except runs.LeaseLost:
            logger.info("run_lease_lost run_id=%s owner=%s stage=finalize", run["id"], owner)
            return {"run_id": run["id"], "status": "lease_lost"}
        logger.info(
            "run_finished run_id=%s status=%s code=%s tool_calls=%d inference_calls=%d duration_ms=%d",
            run["id"], status, error.get("code") if error else "-",
            state.tool_calls, state.inference_calls, duration_ms,
        )
        return {"run_id": run["id"], "status": status}
