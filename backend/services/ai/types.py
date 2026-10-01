"""Tipos compartilhados: contexto autenticado, fatos e fontes.

O ``ExecutionContext`` é sempre montado pelo servidor (``services.ai.scope``).
Ferramentas recebem esse contexto fora dos argumentos do modelo; o modelo nunca
escolhe tenant, ator, espaço financeiro nem contas.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional
from uuid import UUID


class Privacy(str, Enum):
    LOCAL_ONLY = "local_only"
    CLOUD_REDACTED = "cloud_redacted"
    CLOUD_ALLOWED = "cloud_allowed"


class Mode(str, Enum):
    OBSERVE = "observe"
    ASSISTED = "assisted"
    DELEGATED = "delegated"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_RECONCILIATION = "needs_reconciliation"


TERMINAL_RUN_STATUSES = frozenset(
    {RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
)


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
    STALE = "stale"


@dataclass(frozen=True)
class ExecutionContext:
    """Escopo autenticado de uma execução, resolvido no servidor."""

    tenant_id: str
    actor_id: str
    financial_space_id: str
    space_kind: str
    space_name: str
    allowed_account_ids: FrozenSet[str]
    channel: str
    privacy: Privacy
    request_id: str
    trace_id: str
    policy_version: int = 1
    locale: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"
    run_id: Optional[str] = None

    def with_run(self, run_id: str) -> "ExecutionContext":
        return replace(self, run_id=str(run_id))

    def envelope(self, contract_version: str, task: str, input_refs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Envelope de execução do contrato (seção 6)."""
        return {
            "contract_version": contract_version,
            "run_id": self.run_id,
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "financial_space_id": self.financial_space_id,
            "channel": self.channel,
            "locale": self.locale,
            "timezone": self.timezone,
            "policy_version": str(self.policy_version),
            "task": task,
            "privacy": self.privacy.value,
            "input_refs": list(input_refs or []),
        }


@dataclass
class Source:
    """Origem rastreável de um fato ou de um trecho usado na resposta."""

    ref: str
    kind: str  # sql | artifact | email | rag | proposal | operation
    label: str
    as_of: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Fact:
    """Fato financeiro calculado pelo backend.

    ``value`` é decimal em string (nunca float). Ausência de dado é
    ``value=None`` com ``missing_reason``; jamais zero.
    """

    key: str
    label: str
    value: Optional[str]
    unit: str  # money | count | text | date
    period: Dict[str, Any]
    scope: Dict[str, Any]
    source_refs: List[str]
    as_of: str
    currency: Optional[str] = None
    missing_reason: Optional[str] = None
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: Optional[datetime] = None) -> str:
    value = value or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


_CENT = Decimal("0.01")


def to_decimal(value: Any) -> Decimal:
    """Converte para Decimal sem passar por float binário."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("valor monetário inválido")
    if isinstance(value, float):
        return Decimal(repr(value))
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("valor monetário inválido")


def money_str(value: Any) -> str:
    """Valor monetário como string decimal com duas casas (ex.: ``"1234.50"``)."""
    return str(to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP))


def json_safe(value: Any) -> Any:
    """Converte estruturas com Decimal/UUID/datas em tipos JSON, sem float."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float):
        raise TypeError("float não é permitido em resultados; use Decimal ou string")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return iso_utc(value) if value.tzinfo else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(item) for item in value]
    raise TypeError("tipo não serializável em resultado: %s" % type(value).__name__)


def canonical_json(value: Any) -> str:
    """JSON determinístico para hashes de proposta, pedido e argumentos."""
    return json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
