"""Dublês e helpers dos testes de execuções, orquestrador e worker.

O que é dublê aqui é só o que está FORA do componente testado:

* ``ScriptedGateway``: no lugar do gateway real. Devolve respostas programadas
  e CONTA chamadas; nunca fala com modelo algum.
* ``ToolKit``: ferramentas com nomes do contrato registradas no ``ToolRegistry``
  real. Os handlers contam invocações e, quando o cenário pede, gravam no
  PostgreSQL real (proposta, operação, pagamento, outbox) em uma transação.

Banco, registro de ferramentas, política de grants, fila e orquestrador são os
de verdade. Tudo é sintético: nenhum valor ou nome vem de dado real.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from pydantic import Field

from services.ai import runs
from services.ai.db import enqueue_outbox, jsonb, scoped_tx
from services.ai.errors import AiError
from services.ai.gateway.base import (
    AttemptBudget,
    AttemptRecord,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ToolCall,
    Usage,
)
from services.ai.orchestrator import Orchestrator
from services.ai.registry import ToolArgs, ToolDefinition, ToolRegistry, ToolResult
from services.ai.types import ExecutionContext, Fact, Source, canonical_json, money_str

from . import seed


FIXED_AS_OF = "2026-10-01T12:00:00Z"

# Chaves obrigatórias de GET /runs/{id} (spec, seção 4.2).
VIEW_KEYS = {
    "run_id", "status", "task", "contract_version", "trace_id", "created_at", "finished_at",
    "cancel_requested", "scope", "progress", "summary_pt_br", "facts", "sources", "proposal_ids",
    "operation_ids", "warnings", "model", "error",
}
_OPERATION_NAMESPACE = uuid.UUID("6f1d2c0a-0000-4000-8000-00000000a1fa")


class WorkerKilled(BaseException):
    """Simula a morte do processo do worker.

    Herda de ``BaseException`` como ``KeyboardInterrupt``/``SystemExit``: o
    orquestrador só trata ``Exception``, então esta "queda" atravessa tudo sem
    que a execução seja finalizada — exatamente o que acontece em um kill.
    """


# ---------------------------------------------------------------------------
# Gateway roteirizado
# ---------------------------------------------------------------------------

def call(name: str, arguments: Optional[Dict[str, Any]] = None, call_id: Optional[str] = None) -> ToolCall:
    return ToolCall(id=call_id or "call-%s" % uuid.uuid4().hex[:8], name=name, arguments=dict(arguments or {}))


def response(
    *,
    tool_calls: Optional[Sequence[ToolCall]] = None,
    summary: Optional[str] = None,
    alias: str = "local-sintetico",
    provider: str = "ollama",
    model_id: str = "modelo-sintetico:1",
    fallback_used: bool = False,
    inference_calls: int = 1,
    cost_micros: int = 0,
    raw_content: Optional[str] = None,
) -> ModelResponse:
    """Resposta normalizada, como o gateway real entregaria ao orquestrador."""
    parsed = {"summary_pt_br": summary} if summary is not None else None
    content = raw_content if raw_content is not None else (canonical_json(parsed) if parsed else "")
    return ModelResponse(
        content=content,
        parsed=parsed,
        tool_calls=list(tool_calls or []),
        finish_reason="tool_calls" if tool_calls else "stop",
        alias=alias,
        provider=provider,
        model_id=model_id,
        effective_provider=None,
        usage=Usage(input_tokens=10, output_tokens=5),
        cost_micros=cost_micros,
        latency_ms=1,
        inference_calls=inference_calls,
        fallback_used=fallback_used,
        attempts=[AttemptRecord(alias=alias, provider=provider, outcome="ok", latency_ms=1)],
    )


def tool_messages(request: ModelRequest) -> List[Any]:
    return [message for message in request.messages if message.role == "tool"]


class ScriptedGateway(ModelGateway):
    """Gateway de teste.

    ``script`` pode ser:

    * uma lista: cada chamada consome o próximo item, em ordem;
    * uma função ``(request, ctx, budget) -> item``: decide pela conversa
      recebida (útil em retomadas, em que só parte das inferências é refeita).

    Um item é um ``ModelResponse``, uma exceção a levantar, ou outra função.
    """

    def __init__(self, script: Any) -> None:
        self._script = script
        self.calls = 0
        self.requests: List[ModelRequest] = []
        self.contexts: List[ExecutionContext] = []
        self.budget_limits: List[int] = []

    def complete(self, request: ModelRequest, ctx: ExecutionContext, budget: AttemptBudget) -> ModelResponse:
        self.calls += 1
        self.requests.append(request)
        self.contexts.append(ctx)
        self.budget_limits.append(budget.limit)
        budget.take(1)
        if callable(self._script):
            item = self._script(request, ctx, budget)
        else:
            if self.calls > len(self._script):
                raise AssertionError("gateway chamado além do roteiro (%d)" % self.calls)
            item = self._script[self.calls - 1]
        if callable(item) and not isinstance(item, BaseException):
            item = item(request, ctx, budget)
        if isinstance(item, BaseException):
            raise item
        return item

    def tool_names_offered(self) -> List[List[str]]:
        return [sorted(tool.name for tool in request.tools) for request in self.requests]


class ForbiddenGateway(ModelGateway):
    """Gateway que não pode ser chamado: prova que uma tarefa não depende de modelo."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request, ctx, budget):
        self.calls += 1
        raise AssertionError("o gateway não deveria ser chamado nesta tarefa")


# ---------------------------------------------------------------------------
# Ferramentas de teste (nomes do contrato)
# ---------------------------------------------------------------------------

class ReadArgs(ToolArgs):
    query: str = Field(min_length=1, max_length=60)


class SearchArgs(ToolArgs):
    query: str = Field(min_length=1, max_length=200)


class MessageArgs(ToolArgs):
    message_id: str = Field(min_length=1, max_length=120)


class PrepareArgs(ToolArgs):
    payable_id: str
    amount: str


class ApplyArgs(ToolArgs):
    proposal_id: str
    expected_version: int = Field(ge=1)


class StatusArgs(ToolArgs):
    operation_id: str


class ReverseArgs(ToolArgs):
    operation_id: str
    reason: str = Field(min_length=1, max_length=500)


class AttachmentArgs(ToolArgs):
    message_id: str = Field(min_length=1, max_length=120)
    attachment_id: str = Field(min_length=1, max_length=120)


class PreviewArgs(ToolArgs):
    artifact_id: str = Field(min_length=1, max_length=120)


class ToolKit:
    """Registro real + handlers de teste que contam chamadas."""

    def __init__(self, pool, settings) -> None:
        self.pool = pool
        self.settings = settings
        self.registry = ToolRegistry(settings)
        self.calls: Dict[str, int] = defaultdict(int)
        self.contexts: List[Tuple[str, ExecutionContext]] = []
        self.received_args: List[Tuple[str, Dict[str, Any]]] = []
        # Ganchos por ferramenta, chamados dentro do handler (antes do efeito).
        self.before: Dict[str, Callable[[ExecutionContext, Any], None]] = {}
        # Gancho chamado DEPOIS do commit do efeito de finance.apply_change.
        self.after_apply_commit: Optional[Callable[[ExecutionContext, str], None]] = None
        # Substitui a RESPOSTA de finance.operation_status (o handler continua
        # contando a chamada). Serve para simular um backend que não confirma
        # uma operação que existe no banco.
        self.status_override: Optional[Callable[[ExecutionContext, Any], ToolResult]] = None

    # -- infraestrutura ----------------------------------------------------

    def add(self, name: str, args_model, effect: str, handler, requires_flags: Sequence[str] = ()) -> "ToolKit":
        def counted(ctx: ExecutionContext, args: Any) -> ToolResult:
            self.calls[name] += 1
            self.contexts.append((name, ctx))
            self.received_args.append((name, args.model_dump()))
            hook = self.before.get(name)
            if hook is not None:
                hook(ctx, args)
            return handler(ctx, args)

        self.registry.register(
            ToolDefinition(
                name=name, version="1.0.0", description="Ferramenta de teste %s" % name,
                args_model=args_model, effect=effect, handler=counted, requires_flags=tuple(requires_flags),
            )
        )
        return self

    def total_calls(self) -> int:
        return sum(self.calls.values())

    # -- leitura -----------------------------------------------------------

    def with_finance_read(
        self,
        values: Optional[Dict[str, str]] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> "ToolKit":
        """``finance.read`` com um fato por consulta.

        Sem ``values``, o valor é calculado no banco real (soma das contas a
        pagar vinculadas ao espaço do contexto). Com ``values``, cada consulta
        devolve o valor sintético informado. ``extra_data`` entra em ``data``
        do resultado: é por onde um teste injeta texto não confiável (por
        exemplo, a descrição de um lançamento com uma instrução maliciosa).
        """
        pool = self.pool

        def handler(ctx: ExecutionContext, args: ReadArgs) -> ToolResult:
            if values is not None:
                if args.query not in values:
                    return ToolResult(data={"query": args.query, "found": False})
                value = money_str(values[args.query])
            else:
                with scoped_tx(pool, ctx.tenant_id) as cursor:
                    cursor.execute(
                        """
                        SELECT COALESCE(sum(p.amount_expected), 0) AS total
                        FROM payables p
                        JOIN financial_space_payables l
                          ON l.payable_id = p.id AND l.tenant_id = p.tenant_id
                        WHERE p.tenant_id = %s AND l.financial_space_id = %s AND p.canceled_at IS NULL
                        """,
                        (ctx.tenant_id, ctx.financial_space_id),
                    )
                    value = money_str(cursor.fetchone()["total"])
            ref = "sql:teste:%s" % args.query
            fact = Fact(
                key="teste.%s" % args.query,
                label="Valor de %s" % args.query,
                value=value,
                unit="money",
                currency="BRL",
                period={"kind": "month", "start": "2026-10-01", "end": "2026-10-31", "label": "outubro/2026"},
                scope={"financial_space_id": ctx.financial_space_id, "kind": ctx.space_kind},
                source_refs=[ref],
                as_of=FIXED_AS_OF,
            )
            data = {"query": args.query, "value": value}
            data.update(extra_data or {})
            return ToolResult(
                data=data,
                facts=[fact],
                sources=[Source(ref=ref, kind="sql", label="Consulta de teste %s" % args.query, as_of=FIXED_AS_OF)],
            )

        return self.add("finance.read", ReadArgs, "read", handler)

    def with_email(self, body: str = "Extrato sintético em anexo.") -> "ToolKit":
        """``email.search_financial`` e ``email.get_message`` com conteúdo configurável
        (é por aqui que entra a instrução maliciosa nos testes de AC-06)."""

        def search(ctx: ExecutionContext, args: SearchArgs) -> ToolResult:
            return ToolResult(
                data={"candidates": [{"message_id": "msg-sintetica-1", "subject": "Extrato de teste"}]},
                sources=[Source(ref="email:msg-sintetica-1", kind="email", label="Extrato de teste")],
            )

        def get_message(ctx: ExecutionContext, args: MessageArgs) -> ToolResult:
            return ToolResult(
                data={"message_id": args.message_id, "body": body, "attachments": []},
                sources=[Source(ref="email:%s" % args.message_id, kind="email", label="Mensagem de teste")],
            )

        self.add("email.search_financial", SearchArgs, "external_read", search, ("email_enabled",))
        self.add("email.get_message", MessageArgs, "external_read", get_message, ("email_enabled",))
        return self

    def with_import_tools(self) -> "ToolKit":
        """``email.download_attachment`` e ``imports.preview`` mínimos, para completar o
        conjunto de ferramentas da tarefa de importação."""

        def download(ctx: ExecutionContext, args: AttachmentArgs) -> ToolResult:
            return ToolResult(data={"artifact_id": "artefato-sintetico-1", "kind": "ofx"})

        def preview(ctx: ExecutionContext, args: PreviewArgs) -> ToolResult:
            return ToolResult(data={"artifact_id": args.artifact_id, "items": 0})

        self.add("email.download_attachment", AttachmentArgs, "external_read", download, ("email_enabled",))
        self.add("imports.preview", PreviewArgs, "read", preview)
        return self

    def with_extras(self) -> "ToolKit":
        """``rag.search_personal`` e ``whatsapp.respond`` de teste (contam chamadas)."""

        def rag_search(ctx: ExecutionContext, args: SearchArgs) -> ToolResult:
            return ToolResult(data={"count": 0, "chunks": []})

        def whatsapp(ctx: ExecutionContext, args: SearchArgs) -> ToolResult:
            return ToolResult(data={"delivered": False})

        self.add("rag.search_personal", SearchArgs, "read", rag_search)
        self.add("whatsapp.respond", SearchArgs, "message", whatsapp)
        return self

    # -- escrita (banco real) ---------------------------------------------

    def with_finance_write(self, include_status: bool = True) -> "ToolKit":
        pool = self.pool
        kit = self

        def prepare(ctx: ExecutionContext, args: PrepareArgs) -> ToolResult:
            proposal = insert_proposal(
                pool, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id,
                payable_id=args.payable_id, amount=args.amount, status="ready", run_id=ctx.run_id,
            )
            return ToolResult(
                data={"status": "waiting_review", "version": 1},
                proposal_ids=[proposal["proposal_id"]],
                sources=[Source(ref="proposal:%s" % proposal["proposal_id"], kind="proposal", label="Proposta de teste")],
            )

        def apply(ctx: ExecutionContext, args: ApplyArgs) -> ToolResult:
            with scoped_tx(pool, ctx.tenant_id) as cursor:
                cursor.execute(
                    """
                    SELECT id, status, version, payload, payload_hash, operation_key
                    FROM ai_proposals
                    WHERE id = %s AND tenant_id = %s AND financial_space_id = %s
                    FOR UPDATE
                    """,
                    (args.proposal_id, ctx.tenant_id, ctx.financial_space_id),
                )
                proposal = cursor.fetchone()
                if proposal is None:
                    raise AiError("not_found", "Proposta não encontrada.")
                if int(proposal["version"]) != args.expected_version:
                    raise AiError("stale_proposal")
                operation_id = str(uuid.uuid5(_OPERATION_NAMESPACE, proposal["operation_key"]))
                if proposal["status"] == "applied":
                    # Mesma chave e mesmo payload: devolve o resultado anterior.
                    return ToolResult(
                        data={"status": "applied", "idempotent": True},
                        operation_ids=[operation_id], proposal_ids=[str(proposal["id"])],
                    )
                if proposal["status"] != "approved":
                    return ToolResult(data={"status": "waiting_review"}, proposal_ids=[str(proposal["id"])])
                payload = proposal["payload"]
                # Efeito, operação e outbox na MESMA transação.
                cursor.execute(
                    """
                    INSERT INTO ai_operations (
                        id, tenant_id, financial_space_id, proposal_id, run_id, actor_user_id,
                        kind, operation_key, payload_hash, effect
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'payable_payment', %s, %s, %s)
                    """,
                    (
                        operation_id, ctx.tenant_id, ctx.financial_space_id, proposal["id"], ctx.run_id,
                        ctx.actor_id, proposal["operation_key"], proposal["payload_hash"],
                        jsonb({"paid": payload["amount"]}),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO payable_payments (tenant_id, payable_id, created_by_user_id, amount, paid_at)
                    VALUES (%s, %s, %s, %s, now())
                    """,
                    (ctx.tenant_id, payload["payable_id"], ctx.actor_id, Decimal(payload["amount"])),
                )
                cursor.execute(
                    "UPDATE ai_proposals SET status = 'applied' WHERE id = %s AND tenant_id = %s",
                    (proposal["id"], ctx.tenant_id),
                )
                enqueue_outbox(
                    cursor, tenant_id=ctx.tenant_id, topic="operation.applied",
                    dedup_key="operation:%s:applied" % operation_id,
                    payload={"operation_id": operation_id}, operation_id=operation_id, run_id=ctx.run_id,
                )
            if kit.after_apply_commit is not None:
                kit.after_apply_commit(ctx, operation_id)
            return ToolResult(
                data={"status": "applied"},
                operation_ids=[operation_id],
                proposal_ids=[str(proposal["id"])],
                sources=[Source(ref="operation:%s" % operation_id, kind="operation", label="Operação de teste")],
            )

        def status(ctx: ExecutionContext, args: StatusArgs) -> ToolResult:
            if kit.status_override is not None:
                return kit.status_override(ctx, args)
            with scoped_tx(pool, ctx.tenant_id) as cursor:
                cursor.execute(
                    "SELECT id, status FROM ai_operations WHERE id = %s AND tenant_id = %s AND financial_space_id = %s",
                    (args.operation_id, ctx.tenant_id, ctx.financial_space_id),
                )
                row = cursor.fetchone()
                planned = None
                if row is None:
                    # Como no backend real: um id PLANEJADO (anotado na proposta) que
                    # ainda não virou operação responde "not_applied".
                    cursor.execute(
                        "SELECT id FROM ai_proposals WHERE tenant_id = %s AND financial_space_id = %s "
                        "AND expected_effect ->> 'planned_operation_id' = %s",
                        (ctx.tenant_id, ctx.financial_space_id, args.operation_id),
                    )
                    planned = cursor.fetchone()
            if row is None:
                if planned is None:
                    raise AiError("operation_unknown")
                return ToolResult(data={"status": "not_applied"}, proposal_ids=[str(planned["id"])])
            return ToolResult(
                data={"status": row["status"], "confirmed": True},
                operation_ids=[str(row["id"])],
                sources=[Source(ref="operation:%s" % row["id"], kind="operation", label="Operação de teste")],
            )

        self.add("finance.prepare_change", PrepareArgs, "prepare", prepare)
        self.add("finance.apply_change", ApplyArgs, "write", apply, ("write_enabled",))
        if include_status:
            self.add("finance.operation_status", StatusArgs, "read", status)
        return self

    def with_reverse(self, world, mode: str) -> "ToolKit":
        """``finance.reverse_change`` de teste.

        ``mode``: ``ready`` (compensação aguardando revisão), ``approved``
        (compensação já aprovada pelo backend) ou ``direct`` (a própria
        ferramenta registrou o evento compensatório). A semântica real de
        reversão pertence ao componente financeiro; aqui interessa só o que o
        orquestrador faz com cada resposta.
        """
        pool = self.pool

        def reverse(ctx: ExecutionContext, args: ReverseArgs) -> ToolResult:
            if mode == "direct":
                return ToolResult(data={"status": "reversed"}, operation_ids=[str(uuid.uuid4())])
            proposal = approved_proposal(pool, world, "55.00", status=mode)
            data = {"status": "waiting_review"} if mode == "ready" else {"status": "approved"}
            return ToolResult(data=data, proposal_ids=[proposal["proposal_id"]])

        return self.add("finance.reverse_change", ReverseArgs, "write", reverse, ("write_enabled",))


# ---------------------------------------------------------------------------
# Cenários no banco
# ---------------------------------------------------------------------------

def insert_proposal(
    pool,
    tenant_id: str,
    space_id: str,
    user_id: str,
    *,
    payable_id: str,
    amount: str,
    status: str = "approved",
    run_id: Optional[str] = None,
    planned: bool = False,
) -> Dict[str, Any]:
    """Proposta de pagamento sintética, direto na tabela.

    ``planned=True`` anota ``expected_effect.planned_operation_id``, como o
    componente financeiro real faz.
    """
    payload = {"payable_id": payable_id, "amount": money_str(amount)}
    payload_hash = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    operation_key = hashlib.sha256(("%s|%s|payable_payment|%s" % (tenant_id, space_id, payable_id)).encode()).hexdigest()
    approved = status in ("approved", "applied")
    planned_id = str(uuid.uuid5(_OPERATION_NAMESPACE, operation_key))
    expected_effect = {"planned_operation_id": planned_id} if planned else {}
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO ai_proposals (
                tenant_id, financial_space_id, created_by_user_id, run_id, kind, status, payload,
                payload_hash, operation_key, approval_kind, approved_by_user_id, approved_hash,
                approved_at, expires_at, expected_effect
            ) VALUES (
                %s, %s, %s, %s, 'payable_payment', %s, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s THEN now() ELSE NULL END, now() + interval '24 hours', %s
            )
            RETURNING id, version
            """,
            (
                tenant_id, space_id, user_id, run_id, status, jsonb(payload), payload_hash, operation_key,
                "specific" if approved else None, user_id if approved else None,
                payload_hash if approved else None, approved, jsonb(expected_effect),
            ),
        )
        row = cursor.fetchone()
    return {
        "proposal_id": str(row["id"]),
        "version": int(row["version"]),
        "payable_id": payable_id,
        "operation_id": str(uuid.uuid5(_OPERATION_NAMESPACE, operation_key)),
    }


def approved_proposal(pool, world, amount: str = "100.00", status: str = "approved",
                      planned: bool = False) -> Dict[str, Any]:
    from datetime import date

    payable_id = seed.create_payable(
        pool, world.tenant_id, world.personal_space_id,
        title="Conta sintética %s" % uuid.uuid4().hex[:6], amount_expected=amount,
        competency_month=date(2026, 10, 1), due_date=date(2026, 10, 10),
    )
    return insert_proposal(
        pool, world.tenant_id, world.personal_space_id, world.user_id,
        payable_id=payable_id, amount=amount, status=status, planned=planned,
    )


def grant(pool, world, capabilities: Sequence[str], mode: str = "observe", space: str = "personal", **extra) -> str:
    space_id = world.personal_space_id if space == "personal" else world.business_space_id
    return seed.create_grant(
        pool, world.tenant_id, space_id, world.user_id, mode=mode, capabilities=list(capabilities), **extra
    )


def revoke_grant_row(pool, tenant_id: str, grant_id: str) -> None:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "UPDATE ai_grants SET revoked_at = now(), revocation_reason = 'teste' WHERE id = %s AND tenant_id = %s",
            (grant_id, tenant_id),
        )


def enqueue(pool, ctx, settings, *, task: str = "finance_question", message: str = "Quanto falta pagar em outubro?",
            key: Optional[str] = None, input_refs: Optional[Sequence[str]] = None) -> str:
    created = runs.create_run(
        pool, ctx, task=task, message=message, input_refs=input_refs, idempotency_key=key, settings=settings
    )
    return created["run_id"]


def claim(pool, settings, owner: str = "worker-a") -> Dict[str, Any]:
    claimed = runs.claim_next(pool, owner, settings.lease_seconds)
    assert claimed is not None, "nenhuma execução disponível para %s" % owner
    return claimed


def execute_next(pool, settings, registry, gateway, owner: str = "worker-a") -> Dict[str, Any]:
    """Assume a próxima execução e a conduz com o orquestrador real."""
    claimed = claim(pool, settings, owner)
    outcome = Orchestrator(pool, settings, registry, gateway).execute(claimed["run_id"], claimed["tenant_id"], owner)
    return {"run_id": claimed["run_id"], "tenant_id": claimed["tenant_id"], "outcome": outcome}


def run_row(pool, tenant_id: str, run_id: str) -> Dict[str, Any]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("SELECT * FROM ai_runs WHERE id = %s AND tenant_id = %s", (run_id, tenant_id))
        return dict(cursor.fetchone())


def step_rows(pool, tenant_id: str, run_id: str) -> List[Dict[str, Any]]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT * FROM ai_run_steps WHERE run_id = %s AND tenant_id = %s ORDER BY seq", (run_id, tenant_id)
        )
        return [dict(row) for row in cursor.fetchall()]


def expire_lease(pool, tenant_id: str, run_id: str) -> None:
    """Avança o relógio do lease: equivale a esperar o worker anterior "sumir"."""
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "UPDATE ai_runs SET lease_expires_at = now() - interval '1 second' "
            "WHERE id = %s AND tenant_id = %s AND lease_owner IS NOT NULL",
            (run_id, tenant_id),
        )


def audit_events(pool, tenant_id: str, event_type: str) -> List[Dict[str, Any]]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT * FROM audit_events WHERE tenant_id = %s AND event_type = %s ORDER BY created_at",
            (tenant_id, event_type),
        )
        return [dict(row) for row in cursor.fetchall()]
