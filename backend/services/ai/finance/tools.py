"""Ferramentas financeiras registradas no ``ToolRegistry`` (contrato, seção 5).

Cada ferramenta é uma casca fina: valida os argumentos com pydantic
(``extra="forbid"``) e chama ``read``, ``proposals`` ou ``operations``.

O que NÃO existe nos argumentos, de propósito: ``tenant_id``, ``actor_id``,
``financial_space_id``. O escopo chega pelo ``ExecutionContext`` montado no
servidor. Como propriedades extras são rejeitadas, se o modelo (ou um texto
malicioso lido por ele) tentar mandar um desses campos, a chamada falha com
``invalid_request`` em vez de ser "quase atendida".

Flags: ``finance.apply_change`` e ``finance.reverse_change`` exigem
``write_enabled``. Com a escrita desligada o registro nem mostra essas
ferramentas ao modelo.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import Field

from ..db import scoped_tx
from ..errors import AiError
from ..imports_types import ImportPreview
from ..registry import ToolArgs, ToolDefinition, ToolResult
from ..settings import AiSettings
from ..types import ExecutionContext, Source
from . import operations, proposals, read, repository


TOOL_VERSION = "1.0.0"

PreviewProvider = Callable[[ExecutionContext, str, str], ImportPreview]

_UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
# Valor monetário entra como STRING decimal ("1234.50"). Número JSON viraria
# float no caminho e 0.1 + 0.2 deixaria de ser 0.30.
_AMOUNT_PATTERN = r"^\d{1,15}(\.\d{1,2})?$"


class ReadQuery(str, Enum):
    PAYABLES_OVERVIEW = "payables_overview"
    PAYABLES_LIST = "payables_list"
    REALIZED_TOTALS = "realized_totals"
    SPENDING_BY_CATEGORY = "spending_by_category"
    ACCOUNTS = "accounts"
    CONSOLIDATED_REALIZED_TOTALS = "consolidated_realized_totals"


class ChangeKind(str, Enum):
    PAYABLE_PAYMENT = "payable_payment"
    STATEMENT_IMPORT = "statement_import"


class EvidenceKind(str, Enum):
    OFX_TRANSACTION = "ofx_transaction"
    RECEIPT = "receipt"
    EMAIL = "email"
    MANUAL = "manual"


def _inline_refs(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Troca cada ``$ref`` pela definição e remove ``$defs``.

    O pydantic descreve enums e objetos aninhados por referência. Nem todo
    modelo (em especial os locais) segue ``$ref`` ao ler a ferramenta; com a
    definição embutida, a lista de consultas e de tipos fica visível no
    próprio campo.
    """
    definitions = schema.get("$defs") or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                merged = dict(resolve(definitions[node["$ref"].rsplit("/", 1)[-1]]))
                merged.update({key: resolve(value) for key, value in node.items() if key != "$ref"})
                return merged
            resolved = {key: resolve(value) for key, value in node.items() if key != "$defs"}
            wrapper = resolved.get("allOf")
            if isinstance(wrapper, list) and len(wrapper) == 1 and isinstance(wrapper[0], dict):
                # O pydantic embrulha "referência + descrição" em um allOf de
                # um item só; desembrulhado, o enum fica direto no campo.
                flattened = dict(wrapper[0])
                flattened.update({key: value for key, value in resolved.items() if key != "allOf"})
                return flattened
            return resolved
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


class FinanceArgs(ToolArgs):
    """Base dos argumentos financeiros: schema JSON sem referências."""

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return _inline_refs(super().model_json_schema(*args, **kwargs))


class FinanceReadArgs(FinanceArgs):
    query: ReadQuery = Field(description="Consulta enumerada a executar.")
    month: Optional[int] = Field(default=None, ge=1, le=12, description="Mês (1-12). Exige year.")
    year: Optional[int] = Field(default=None, ge=2000, le=2100, description="Ano com quatro dígitos.")
    account_id: Optional[str] = Field(
        default=None, pattern=_UUID_PATTERN, description="Conta do espaço (só nas consultas de realizado)."
    )
    date_from: Optional[date] = Field(default=None, description="Início do intervalo (AAAA-MM-DD), inclusive.")
    date_to: Optional[date] = Field(default=None, description="Fim do intervalo (AAAA-MM-DD), inclusive.")
    cursor: Optional[str] = Field(
        default=None, min_length=1, max_length=400, description="Cursor devolvido pela página anterior."
    )
    limit: Optional[int] = Field(default=None, ge=1, le=read.MAX_PAGE_SIZE, description="Itens por página.")


class EvidenceItem(FinanceArgs):
    # ``kind`` é só a descrição que o modelo dá. O backend confere a referência
    # e decide o tipo de verdade (um anexo de imagem/PDF é comprovante, venha
    # com o rótulo que vier); o que não dá para conferir fica como anotação.
    kind: EvidenceKind = Field(description="Tipo declarado da evidência. O sistema confere e pode reclassificar.")
    ref: str = Field(
        min_length=1, max_length=200, description="Referência da evidência (ex.: artifact:<id>), sem texto livre."
    )


class PrepareChangeArgs(FinanceArgs):
    kind: ChangeKind = Field(description="Tipo de alteração a preparar.")
    payable_id: Optional[str] = Field(default=None, pattern=_UUID_PATTERN, description="Conta a pagar (baixa).")
    amount: Optional[str] = Field(
        default=None, pattern=_AMOUNT_PATTERN, description='Valor pago em string decimal, ex.: "150.00".'
    )
    paid_on: Optional[date] = Field(default=None, description="Data do pagamento (AAAA-MM-DD).")
    transaction_id: Optional[str] = Field(
        default=None, pattern=_UUID_PATTERN, description="Transação do extrato OFX que comprova o pagamento."
    )
    payment_method: Optional[str] = Field(default=None, max_length=60, description="Forma de pagamento.")
    artifact_id: Optional[str] = Field(default=None, pattern=_UUID_PATTERN, description="Anexo OFX (importação).")
    account_id: Optional[str] = Field(default=None, pattern=_UUID_PATTERN, description="Conta de destino (importação).")
    evidence: Optional[List[EvidenceItem]] = Field(
        default=None, max_length=proposals.MAX_EVIDENCE_ITEMS, description="Evidências do pagamento."
    )


class ApplyChangeArgs(FinanceArgs):
    proposal_id: str = Field(pattern=_UUID_PATTERN, description="Proposta devolvida por finance.prepare_change.")
    expected_version: int = Field(ge=1, description="Versão da proposta que foi apresentada.")


class OperationStatusArgs(FinanceArgs):
    operation_id: str = Field(pattern=_UUID_PATTERN, description="Operação (ou id planejado da proposta).")


class ReverseChangeArgs(FinanceArgs):
    operation_id: str = Field(pattern=_UUID_PATTERN, description="Operação aplicada a compensar.")
    reason: str = Field(min_length=3, max_length=500, description="Motivo da reversão.")


def _forbid(args: PrepareChangeArgs, fields: List[str]) -> None:
    """Campo de outro tipo de alteração é erro, não é ignorado."""
    present = [name for name in fields if getattr(args, name) is not None]
    if present:
        raise AiError(
            "invalid_request",
            "Campos que não se aplicam a este tipo de alteração.",
            details={"fields": present},
        )


def _require(args: PrepareChangeArgs, fields: List[str]) -> None:
    missing = [name for name in fields if getattr(args, name) is None]
    if missing:
        raise AiError("invalid_request", "Faltam campos obrigatórios.", details={"fields": missing})


def _proposal_result(view: Dict[str, Any]) -> ToolResult:
    warnings = []  # type: List[str]
    operation_ids = []  # type: List[str]
    if view["status"] == "applied" and view.get("operation_id"):
        operation_ids.append(view["operation_id"])
        warnings.append("Esta ação já havia sido aplicada antes; nenhum efeito novo foi criado.")
    elif view["status"] == "draft":
        warnings.append("A proposta tem pendências que impedem a aplicação.")
    elif view["requires_review"]:
        warnings.append("A proposta exige revisão e aprovação do titular.")
    return ToolResult(
        # Os campos de cima repetem o essencial para o próximo passo
        # (finance.apply_change pede proposal_id e expected_version).
        data={
            "proposal_id": view["proposal_id"],
            "version": view["version"],
            "proposal_status": view["status"],
            "requires_review": view["requires_review"],
            "proposal": view,
        },
        sources=[
            Source(
                ref="proposal:%s" % view["proposal_id"],
                kind="proposal",
                label=view["summary_pt_br"],
                as_of=view["created_at"],
                extra={"status": view["status"], "payload_hash": view["payload_hash"], "version": view["version"]},
            )
        ],
        warnings=warnings,
        proposal_ids=[view["proposal_id"]],
        operation_ids=operation_ids,
    )


def build_finance_tools(pool, settings: AiSettings, preview_provider: PreviewProvider) -> List[ToolDefinition]:
    """Monta as cinco ferramentas financeiras.

    ``preview_provider(ctx, artifact_id, account_id)`` vem do componente de
    importação e devolve a ``ImportPreview`` do importador determinístico.
    Nada é aberto aqui: ``pool`` só é usado quando um handler roda.
    """

    def finance_read(ctx: ExecutionContext, args: FinanceReadArgs) -> ToolResult:
        return read.run_query(
            pool,
            ctx,
            args.query.value,
            month=args.month,
            year=args.year,
            account_id=args.account_id,
            date_from=args.date_from,
            date_to=args.date_to,
            cursor=args.cursor,
            limit=args.limit,
        )

    def finance_prepare_change(ctx: ExecutionContext, args: PrepareChangeArgs) -> ToolResult:
        if args.kind == ChangeKind.PAYABLE_PAYMENT:
            _require(args, ["payable_id"])
            _forbid(args, ["artifact_id", "account_id"])
            view = proposals.prepare_payable_payment(
                pool,
                ctx,
                payable_id=args.payable_id,
                amount=args.amount,
                paid_on=args.paid_on,
                evidence=[{"kind": item.kind.value, "ref": item.ref} for item in args.evidence or []],
                transaction_id=args.transaction_id,
                payment_method=args.payment_method,
                run_id=ctx.run_id,
                settings=settings,
            )
            return _proposal_result(view)

        _require(args, ["artifact_id", "account_id"])
        _forbid(args, ["payable_id", "amount", "paid_on", "transaction_id", "payment_method", "evidence"])
        artifact_id = proposals.as_uuid(args.artifact_id, "artifact_id")
        account_id = proposals.as_uuid(args.account_id, "account_id")
        if account_id not in ctx.allowed_account_ids:
            raise AiError("not_found", "Conta não encontrada neste espaço.")
        # O anexo precisa estar na quarentena DESTE espaço. É daqui também que
        # sai a origem (email/upload/whatsapp): o modelo não a declara.
        artifact = _artifact_in_scope(pool, ctx, artifact_id)
        preview = preview_provider(ctx, artifact_id, account_id)
        if (
            not isinstance(preview, ImportPreview)
            or str(preview.artifact_id) != artifact_id
            or str(preview.account_id) != account_id
            or preview.artifact_sha256 != artifact["sha256"]
        ):
            raise AiError("conflict", "A prévia não corresponde ao anexo e à conta informados.")
        view = proposals.prepare_statement_import(
            pool, ctx, preview=preview, source_kind=artifact["source_kind"], run_id=ctx.run_id, settings=settings
        )
        return _proposal_result(view)

    def finance_apply_change(ctx: ExecutionContext, args: ApplyChangeArgs) -> ToolResult:
        result = operations.apply_proposal(
            pool, ctx, args.proposal_id, expected_version=args.expected_version, settings=settings
        )
        if result["status"] != "applied":
            return ToolResult(
                data=result,
                warnings=["A proposta aguarda a aprovação do titular; nada foi alterado."],
                proposal_ids=[result["proposal_id"]],
            )
        return ToolResult(
            data=result,
            sources=[_operation_source(result["operation_id"], result["kind"], result["applied_at"])],
            proposal_ids=[result["proposal_id"]],
            operation_ids=[result["operation_id"]],
        )

    def finance_operation_status(ctx: ExecutionContext, args: OperationStatusArgs) -> ToolResult:
        status = operations.operation_status(pool, ctx, args.operation_id)
        if status["status"] == "not_applied":
            return ToolResult(
                data=status,
                warnings=["A operação não foi aplicada. É seguro tentar de novo."],
                proposal_ids=[status["proposal_id"]],
            )
        return ToolResult(
            data=status,
            sources=[_operation_source(status["operation_id"], status["kind"], status["applied_at"])],
            proposal_ids=[status["proposal_id"]],
            operation_ids=[status["operation_id"]],
        )

    def finance_reverse_change(ctx: ExecutionContext, args: ReverseChangeArgs) -> ToolResult:
        # Só CRIA a proposta de compensação. Aplicar passa por
        # ``finance.apply_change``, com a mesma aprovação de qualquer efeito.
        view = proposals.prepare_reversal(
            pool, ctx, args.operation_id, args.reason, run_id=ctx.run_id, settings=settings
        )
        return _proposal_result(view)

    return [
        ToolDefinition(
            name="finance.read",
            version=TOOL_VERSION,
            description=(
                "Consulta financeira enumerada no espaço autorizado. Escolha 'query' e, se couber, o período "
                "(month+year, só year, ou date_from+date_to). Os valores vêm calculados pelo sistema, com "
                "escopo declarado e fontes. Valor ausente (null) significa que não há dados, não que é zero."
            ),
            args_model=FinanceReadArgs,
            effect="read",
            handler=finance_read,
        ),
        ToolDefinition(
            name="finance.prepare_change",
            version=TOOL_VERSION,
            description=(
                "Prepara uma proposta (não altera nada): baixa de conta a pagar (kind=payable_payment, com "
                "payable_id, amount em string decimal, paid_on e evidências) ou importação de extrato OFX "
                "(kind=statement_import, com artifact_id e account_id). Devolve proposal_id e o efeito esperado. "
                "Baixa sem transaction_id de um lançamento do extrato OFX sempre fica aguardando a aprovação do "
                "titular, seja qual for a evidência informada."
            ),
            args_model=PrepareChangeArgs,
            effect="prepare",
            handler=finance_prepare_change,
        ),
        ToolDefinition(
            name="finance.apply_change",
            version=TOOL_VERSION,
            description=(
                "Aplica uma proposta já preparada. Só tem efeito com aprovação específica do titular ou "
                "autorização permanente que cubra a proposta; senão devolve waiting_review. Registra no "
                "aplicativo; não movimenta dinheiro no banco."
            ),
            args_model=ApplyChangeArgs,
            effect="write",
            handler=finance_apply_change,
            requires_flags=("write_enabled",),
        ),
        ToolDefinition(
            name="finance.operation_status",
            version=TOOL_VERSION,
            description=(
                "Consulta o estado durável de uma operação (applied, reversed ou not_applied). Use antes de "
                "repetir uma aplicação que falhou por tempo esgotado."
            ),
            args_model=OperationStatusArgs,
            effect="read",
            handler=finance_operation_status,
        ),
        ToolDefinition(
            name="finance.reverse_change",
            version=TOOL_VERSION,
            description=(
                "Cria a proposta de compensação de uma operação aplicada, com o motivo. Não aplica: a "
                "reversão segue para aprovação e é aplicada por finance.apply_change. O histórico é preservado."
            ),
            args_model=ReverseChangeArgs,
            effect="write",
            handler=finance_reverse_change,
            requires_flags=("write_enabled",),
        ),
    ]


@repository.guarded("tools.artifact_in_scope")
def _artifact_in_scope(pool, ctx: ExecutionContext, artifact_id: str) -> Dict[str, Any]:
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        artifact = repository.fetch_artifact(cursor, ctx, artifact_id)
    if artifact is None:
        raise AiError("not_found", "Anexo não encontrado neste espaço.")
    return artifact


def _operation_source(operation_id: str, kind: str, applied_at: Optional[str]) -> Source:
    return Source(
        ref="operation:%s" % operation_id,
        kind="operation",
        label="Operação %s" % kind,
        as_of=applied_at,
        extra={},
    )
