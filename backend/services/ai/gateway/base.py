"""Interface comum do gateway e dos adaptadores de provedor.

O orquestrador conhece apenas ``ModelGateway.complete``. Cada provedor (Ollama,
OpenAI-compatível/OpenRouter, Anthropic...) implementa ``ProviderAdapter`` e
faz UMA tentativa por chamada: retentativas e troca de rota pertencem
exclusivamente ao gateway, dono do orçamento global (contrato, seção 8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..types import ExecutionContext, Privacy


# Classes de tarefa do contrato (seção 7).
TASK_SIMPLE = "simple_extraction"
TASK_COMPLEX = "complex_tools"
TASK_VISION = "vision"
TASK_CLASSES = (TASK_SIMPLE, TASK_COMPLEX, TASK_VISION)

# Propósito da inferência: uma rota homologada só para leitura/resumo não pode
# atender, por degradação silenciosa, uma inferência que conduz escrita.
PURPOSE_READ = "read"
PURPOSE_WRITE = "write"

LOCALITY_LOCAL = "local"
LOCALITY_EXTERNAL = "external"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class ModelRequest:
    task_class: str
    messages: List[ChatMessage]
    purpose: str = PURPOSE_READ
    tools: List[ToolSpec] = field(default_factory=list)
    # JSON Schema da resposta final. Quando presente, a saída é validada pelo
    # gateway; JSON inválido consome uma tentativa de correção do orçamento.
    response_schema: Optional[Dict[str, Any]] = None
    images: List[bytes] = field(default_factory=list)
    max_output_tokens: int = 1024
    temperature: float = 0.0
    # Só é verdadeiro quando uma etapa de redução verificável removeu dados
    # pessoais das mensagens. Exigido para tráfego externo em cloud_redacted.
    redaction_verified: bool = False

    @property
    def needs_tools(self) -> bool:
        return bool(self.tools)

    @property
    def needs_vision(self) -> bool:
        return bool(self.images) or self.task_class == TASK_VISION

    @property
    def needs_json(self) -> bool:
        return self.response_schema is not None


@dataclass(frozen=True)
class ModelRoute:
    """Uma entrada do registro de modelos (contrato, seção 7)."""

    alias: str
    provider: str            # ollama | openai_compatible | anthropic
    model_id: str            # fixado; "latest" não entra em estado approved
    locality: str            # local | external
    priority: int
    task_classes: tuple
    supports_tools: bool
    supports_json: bool
    supports_vision: bool
    context_window: int
    state: str               # candidate | approved | suspended
    approved_purposes: tuple  # read | write
    # Privacidades que a rota pode atender. Rota local atende todas.
    privacy: tuple
    base_url: Optional[str] = None
    digest: Optional[str] = None
    # Nome da variável de ambiente com a credencial (nunca o valor).
    credential_env: Optional[str] = None
    # Fornecedor efetivo fixado atrás de um agregador (ex.: OpenRouter).
    upstream_provider: Optional[str] = None
    # Custo estimado máximo por chamada, em micros da moeda do orçamento.
    # None em rota externa = custo desconhecido = rota paga bloqueada.
    max_cost_micros_per_call: Optional[int] = None
    input_cost_micros_per_mtok: Optional[int] = None
    output_cost_micros_per_mtok: Optional[int] = None
    evidence: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_local(self) -> bool:
        return self.locality == LOCALITY_LOCAL


@dataclass
class Usage:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


@dataclass
class AdapterResult:
    """Resposta normalizada de uma única tentativa em um provedor."""

    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # stop | tool_calls | length | refusal
    model_id: Optional[str] = None           # modelo efetivo devolvido pelo provedor
    effective_provider: Optional[str] = None  # fornecedor efetivo (agregadores)
    usage: Usage = field(default_factory=Usage)
    cost_micros: Optional[int] = None
    latency_ms: int = 0
    # Tentativas feitas pelo próprio provedor/agregador (contam no orçamento).
    upstream_attempts: int = 1
    metrics: Dict[str, Any] = field(default_factory=dict)


# Tipos de falha de provedor e o tratamento no gateway:
#   timeout, network, rate_limited, server_error, unavailable -> próxima rota
#   auth          -> suspende a credencial, avisa o operador, próxima rota autorizada
#   invalid_output-> uma correção dentro do orçamento; nova falha muda de rota
#   refusal, bad_request -> NÃO troca de rota para contornar
PROVIDER_ERROR_KINDS = (
    "timeout",
    "network",
    "rate_limited",
    "server_error",
    "unavailable",
    "auth",
    "invalid_output",
    "refusal",
    "bad_request",
)

TRANSIENT_KINDS = frozenset({"timeout", "network", "rate_limited", "server_error", "unavailable"})


class ProviderError(Exception):
    """Falha de uma tentativa. Não carrega corpo bruto do provedor."""

    def __init__(
        self,
        kind: str,
        *,
        status: Optional[int] = None,
        retry_after_s: Optional[float] = None,
        detail_code: Optional[str] = None,
        upstream_attempts: int = 1,
        cost_micros: Optional[int] = None,
    ) -> None:
        if kind not in PROVIDER_ERROR_KINDS:
            raise ValueError("tipo de erro de provedor desconhecido: %s" % kind)
        self.kind = kind
        self.status = status
        self.retry_after_s = retry_after_s
        # Código curto e seguro (ex.: "model_not_found"), nunca texto do provedor.
        self.detail_code = detail_code
        # Tentativas feitas por dentro de um agregador nesta chamada (contam
        # no orçamento) e custo cobrado mesmo com falha, quando informado.
        self.upstream_attempts = upstream_attempts
        self.cost_micros = cost_micros
        super().__init__(kind)

    @property
    def transient(self) -> bool:
        return self.kind in TRANSIENT_KINDS


class ProviderAdapter:
    """Contrato de um adaptador. Uma chamada = uma tentativa, sem retry interno."""

    provider: str = ""

    def complete(self, route: ModelRoute, request: ModelRequest, timeout_s: float) -> AdapterResult:
        raise NotImplementedError

    def probe(self, route: ModelRoute, timeout_s: float) -> bool:
        """Sonda barata usada para decidir se um circuito aberto pode fechar."""
        raise NotImplementedError


@dataclass
class AttemptRecord:
    alias: str
    provider: str
    outcome: str  # ok | <kind de ProviderError> | skipped:<motivo>
    latency_ms: int = 0
    status: Optional[int] = None


@dataclass
class ModelResponse:
    """Resposta do gateway ao orquestrador."""

    content: str
    parsed: Optional[Dict[str, Any]]
    tool_calls: List[ToolCall]
    finish_reason: str
    alias: str
    provider: str
    model_id: str
    effective_provider: Optional[str]
    usage: Usage
    cost_micros: int
    latency_ms: int
    inference_calls: int
    fallback_used: bool
    attempts: List[AttemptRecord] = field(default_factory=list)


@dataclass
class AttemptBudget:
    """Orçamento de chamadas de inferência de UMA etapa do orquestrador."""

    limit: int
    used: int = 0

    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def take(self, count: int = 1) -> None:
        self.used += count


class ModelGateway:
    """Interface que o orquestrador usa. Implementação em ``gateway.gateway``."""

    def complete(self, request: ModelRequest, ctx: ExecutionContext, budget: AttemptBudget) -> ModelResponse:
        raise NotImplementedError


def privacy_allows_external(privacy: Privacy, redaction_verified: bool = False) -> bool:
    """Decide se a política da tarefa admite rota externa.

    ``local_only`` nunca gera tráfego externo, nem sob falha local (AC-07).
    ``cloud_redacted`` só admite rota externa com redução verificada; na
    dúvida, mantém local. A troca de modelo nunca amplia a política.
    """
    if privacy == Privacy.CLOUD_ALLOWED:
        return True
    if privacy == Privacy.CLOUD_REDACTED:
        return bool(redaction_verified)
    return False
