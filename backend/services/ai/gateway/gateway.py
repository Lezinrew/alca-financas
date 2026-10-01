"""Gateway de IA: escolhe a rota, controla tentativas, custo e failover.

O orquestrador chama ``complete(request, ctx, budget)`` e recebe uma resposta
normalizada ou um ``AiError``. Tudo o que acontece no meio é decidido aqui, e
só aqui (contrato, seção 8: "o gateway é o único responsável pelo orçamento
global de tentativas").

Roteiro de uma chamada:

1. **Elegibilidade estática** (``ModelRegistry``): classe da tarefa, capacidades
   exigidas, privacidade, estado e propósito. A lista de candidatas JÁ SAI sem
   rota externa quando a política não admite; nenhuma falha posterior consegue
   "promover" uma rota que não estava na lista (AC-07).
2. **Travas de execução**, por rota, na ordem de prioridade: privacidade (de
   novo), livro de orçamento presente, rota suspensa, credencial suspensa,
   custo desconhecido, disjuntor aberto, espera de ``Retry-After``, sonda do
   disjuntor, conferência do modelo local, reserva de orçamento.
3. **Uma tentativa** no adaptador. Cada tentativa consome o ``AttemptBudget``
   da etapa (tentativas internas de um agregador contam também).
4. **Tratamento do resultado**:

   =====================  ====================================================
   resultado              o que o gateway faz
   =====================  ====================================================
   sucesso                valida a saída estruturada; se ok, devolve
   saída inválida         UMA correção na mesma rota; nova falha troca de rota
                          (inclui chamada de ferramenta cortada pelo limite)
   transitória            marca no disjuntor e vai para a próxima rota; com
                          ``Retry-After`` curto e sem alternativa, espera e repete
   credencial rejeitada   suspende a credencial, avisa o operador, próxima rota
   fornecedor trocado     suspende a ROTA, avisa o operador, próxima rota
   recusa de conteúdo     ``model_refused``, SEM tentar outra rota
   pedido inválido        ``internal_error``, SEM tentar outra rota
   =====================  ====================================================

Recusa e pedido inválido não trocam de rota porque trocar seria usar o
failover para contornar uma decisão (do modelo ou das nossas regras).

Custo: a reserva é feita antes da chamada e fechada depois. O que decide entre
devolver e manter a reserva é o que se sabe da REQUISIÇÃO, não só o tipo do
erro (ver ``_possibly_billed``). Um problema no livro de orçamento (banco fora,
pool esgotado) tira de jogo só a rota paga: as rotas locais, que não custam
nada, continuam sendo tentadas.

Estado em memória (por processo, perdido ao reiniciar): credenciais e rotas
suspensas, esperas de ``Retry-After`` e conferência de modelos locais. O teto
de custo fica no banco (``BudgetLedger``) e vale para todos os processos.

Nada de conteúdo em log: a trilha registra alias, provedor, desfecho, status e
duração. Prompt, resposta, cabeçalho e corpo de erro do provedor ficam de fora.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..errors import AiError
from ..settings import AiSettings
from ..types import ExecutionContext
from .adapters import DETAIL_UPSTREAM_MISMATCH, NOT_ATTEMPTED_DETAILS, NOT_SENT_DETAILS
from .base import (
    AdapterResult,
    AttemptBudget,
    AttemptRecord,
    ChatMessage,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ModelRoute,
    ProviderAdapter,
    ProviderError,
    Usage,
    privacy_allows_external,
)
from .budget import BudgetLedger
from .circuit import OPEN, CircuitBreaker
from .models import ModelRegistry
from .validation import safe_label, unsupported_keywords, validate_structured_output


logger = logging.getLogger("ai.gateway")

# Espera máxima por um ``Retry-After`` dentro de uma chamada. Acima disso o
# gateway devolve ``model_unavailable`` (retentável) em vez de segurar a
# execução interativa, que tem prazo total de 180 s.
DEFAULT_MAX_RETRY_AFTER_WAIT_S = 10.0
# De quanto em quanto tempo o modelo local é reconferido (presença, digest e
# execução local) antes de receber pedidos.
DEFAULT_LOCAL_VERIFY_TTL_S = 300.0
DEFAULT_PROBE_TIMEOUT_S = 5.0
_MAX_CORRECTION_ERRORS = 10
_MAX_ECHO_CHARS = 4000

# Tipos de falha em que o provedor pode ter processado (e cobrado) o pedido
# mesmo sem resposta aproveitável. "network" está aqui porque, depois de o
# pedido sair, uma conexão que cai não diz se o provedor chegou a processar; a
# falha de CONEXÃO (nada saiu) é separada pelo ``detail_code``.
_POSSIBLY_BILLED_KINDS = frozenset({"timeout", "refusal", "invalid_output", "network"})

_TRUNCATED_TOOL_CALL = (
    "a resposta foi cortada pelo limite de tamanho no meio de uma chamada de ferramenta; "
    "refaça a chamada de forma mais curta"
)
_MALFORMED_OUTPUT = "a resposta anterior tinha formato inválido (chamada de ferramenta ou JSON)"


def _possibly_billed(error: ProviderError) -> bool:
    """O provedor pode ter cobrado por esta tentativa que falhou?

    Na dúvida a reserva é MANTIDA pelo valor máximo: no orçamento, errar para
    mais é o lado seguro (devolver a reserva de uma chamada cobrada faria o
    gasto real ultrapassar o teto sem ninguém ver).

    1. Nada saiu da máquina (sem credencial, conexão recusada, DNS, timeout de
       conexão, pedido que nem pôde ser montado): não houve cobrança.
    2. O provedor respondeu HTTP 200 e a resposta não serviu (corpo que não é
       JSON, ``finish_reason: error``, corpo grande demais, fornecedor trocado
       pelo agregador): ele processou o pedido; cobrança provável.
    3. Timeout, conexão perdida depois do envio, recusa e saída inválida: o
       provedor pode ter processado.
    4. Erro HTTP explícito (4xx, 5xx, 429): o provedor diz que não atendeu.
    """
    if error.detail_code in NOT_SENT_DETAILS:
        return False
    if error.status == 200:
        return True
    return error.kind in _POSSIBLY_BILLED_KINDS


class DefaultModelGateway(ModelGateway):
    """Implementação de ``ModelGateway``.

    ``clock`` é monotônico em segundos (esperas e validade de conferências);
    ``sleep`` é a função de espera. Os dois são injetáveis para os testes não
    dormirem de verdade.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        adapters: Dict[str, ProviderAdapter],
        circuit: CircuitBreaker,
        budget_ledger: Optional[BudgetLedger],
        settings: AiSettings,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        *,
        max_retry_after_wait_s: float = DEFAULT_MAX_RETRY_AFTER_WAIT_S,
        verify_local_routes: bool = True,
        local_verify_ttl_s: float = DEFAULT_LOCAL_VERIFY_TTL_S,
        probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    ) -> None:
        self._registry = registry
        self._adapters = dict(adapters)
        self._circuit = circuit
        self._ledger = budget_ledger
        self._settings = settings
        self._clock = clock
        self._sleep = sleep
        self._max_wait_s = float(max_retry_after_wait_s)
        self._verify_local = bool(verify_local_routes)
        self._verify_ttl_s = float(local_verify_ttl_s)
        self._probe_timeout_s = float(probe_timeout_s)
        self._lock = threading.Lock()
        self._suspended: Dict[str, float] = {}
        self._suspended_routes: Dict[str, str] = {}
        self._cooldown_until: Dict[str, float] = {}
        self._verified_until: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Estado operacional
    # ------------------------------------------------------------------

    @staticmethod
    def _credential_key(route: ModelRoute) -> str:
        # A suspensão é por CREDENCIAL: duas rotas com a mesma chave caem juntas.
        return route.credential_env or "alias:%s" % route.alias

    def suspended_credentials(self) -> List[str]:
        """Nomes (nunca valores) das credenciais suspensas neste processo."""
        with self._lock:
            return sorted(self._suspended)

    def reinstate_credential(self, name: str) -> bool:
        """Reativa uma credencial depois que o operador corrigiu o problema."""
        with self._lock:
            return self._suspended.pop(name, None) is not None

    def suspended_routes(self) -> Dict[str, str]:
        """Rotas suspensas neste processo: ``{alias: motivo}``."""
        with self._lock:
            return dict(self._suspended_routes)

    def reinstate_route(self, alias: str) -> bool:
        """Reativa uma rota suspensa depois que o operador conferiu o registro."""
        with self._lock:
            return self._suspended_routes.pop(alias, None) is not None

    def _is_suspended(self, route: ModelRoute) -> bool:
        with self._lock:
            return self._credential_key(route) in self._suspended

    def _is_route_suspended(self, route: ModelRoute) -> bool:
        with self._lock:
            return route.alias in self._suspended_routes

    def _suspend(self, route: ModelRoute, error: ProviderError, ctx: ExecutionContext) -> None:
        key = self._credential_key(route)
        with self._lock:
            already = key in self._suspended
            self._suspended.setdefault(key, self._clock())
        if not already:
            # Aviso ao operador: nome da variável, status e código, nunca o valor.
            logger.warning(
                "credential_suspended alias=%s provider=%s credential=%s status=%s detail=%s trace_id=%s",
                route.alias, route.provider, key, error.status, error.detail_code, ctx.trace_id,
            )

    def _suspend_route(self, route: ModelRoute, reason: str, ctx: ExecutionContext) -> None:
        """Tira a ROTA de uso até o operador reativá-la.

        Usada quando a rota entregou algo fora do que foi autorizado (agregador
        atendendo por outro fornecedor ou outro modelo). Diferente do
        disjuntor, não volta sozinha: o problema não é de saúde, é de política.
        """
        with self._lock:
            already = route.alias in self._suspended_routes
            self._suspended_routes.setdefault(route.alias, reason)
        if not already:
            logger.warning(
                "route_suspended alias=%s provider=%s reason=%s trace_id=%s",
                route.alias, route.provider, reason, ctx.trace_id,
            )

    def _timeout_for(self, route: ModelRoute) -> float:
        timeout = float(self._settings.inference_timeout_s)
        override = route.extra.get("timeout_s")
        if isinstance(override, (int, float)) and not isinstance(override, bool) and 0 < override < timeout:
            # A rota pode pedir MENOS tempo que o teto global, nunca mais.
            timeout = float(override)
        return timeout

    @property
    def registry(self) -> ModelRegistry:
        """Registro de modelos em uso (a montagem liga nele o dono do plano)."""
        return self._registry

    def _cost_known(self, route: ModelRoute) -> bool:
        return route.is_local or route.is_subscription or (
            isinstance(route.max_cost_micros_per_call, int)
            and not isinstance(route.max_cost_micros_per_call, bool)
            and route.max_cost_micros_per_call > 0
        )

    def _cooldown_remaining(self, alias: str) -> float:
        with self._lock:
            until = self._cooldown_until.get(alias)
        return 0.0 if until is None else max(0.0, until - self._clock())

    def _has_alternative(self, routes: List[ModelRoute], index: int) -> bool:
        """Existe, depois desta, outra rota que parece utilizável agora?"""
        for route in routes[index + 1:]:
            if route.provider not in self._adapters or self._is_suspended(route) or self._is_route_suspended(route):
                continue
            if not self._cost_known(route) or (
                not route.is_local and not route.is_subscription and self._ledger is None
            ):
                continue
            if self._circuit.state(route.alias) == OPEN or self._cooldown_remaining(route.alias) > 0:
                continue
            return True
        return False

    def _probe(self, adapter: ProviderAdapter, route: ModelRoute) -> bool:
        return bool(adapter.probe(route, min(self._probe_timeout_s, self._timeout_for(route))))

    def _mark_verified(self, alias: str) -> None:
        with self._lock:
            self._verified_until[alias] = self._clock() + self._verify_ttl_s

    def _local_route_verified(self, adapter: ProviderAdapter, route: ModelRoute) -> bool:
        """Antes de usar um modelo local, confere se ele é o que foi homologado.

        A sonda do adaptador checa presença, digest e se o modelo não é remoto.
        O resultado positivo vale por ``local_verify_ttl_s``; o negativo é
        reconferido a cada pedido (é uma requisição barata).
        """
        with self._lock:
            until = self._verified_until.get(route.alias)
        if until is not None and self._clock() < until:
            return True
        try:
            healthy = self._probe(adapter, route)
        except NotImplementedError:
            healthy = True  # adaptador sem sonda: não há o que conferir
        except Exception:  # noqa: BLE001 - sonda com defeito conta como rota não conferida
            healthy = False
        if healthy:
            self._mark_verified(route.alias)
        return healthy

    def _gate(
        self,
        route: ModelRoute,
        request: ModelRequest,
        ctx: ExecutionContext,
        routes: List[ModelRoute],
        index: int,
    ) -> Optional[str]:
        """Travas de execução. Devolve o motivo para pular a rota, ou ``None``."""
        adapter = self._adapters.get(route.provider)
        if adapter is None:
            return "no_adapter"
        if not route.is_local:
            # Segunda conferência da privacidade, colada na chamada: mesmo que o
            # registro tivesse um defeito, rota externa não roda fora da política.
            if not self._settings.cloud_enabled or not privacy_allows_external(
                ctx.privacy, request.redaction_verified
            ):
                return "privacy"
            if self._ledger is None and not route.is_subscription:
                # Sem livro de orçamento não existe reserva nem teto: a rota
                # paga rodaria sem nenhum controle de custo. Não roda.
                return "no_budget_ledger"
        if self._is_route_suspended(route):
            return "route_suspended"
        if self._is_suspended(route):
            return "credential_suspended"
        if not self._cost_known(route):
            return "cost_unknown"
        if self._circuit.state(route.alias) == OPEN:
            # Conferido ANTES da espera de Retry-After: dormir os segundos que o
            # provedor pediu para depois descobrir que o circuito está aberto
            # gastaria o prazo da execução sem nenhuma tentativa.
            return "circuit_open"

        remaining = self._cooldown_remaining(route.alias)
        if remaining > 0:
            if remaining > self._max_wait_s or self._has_alternative(routes, index):
                return "retry_after"
            # Respeita o Retry-After: espera o que o provedor pediu e segue.
            self._sleep(remaining)
            with self._lock:
                self._cooldown_until.pop(route.alias, None)

        def half_open_probe() -> bool:
            healthy = self._probe(adapter, route)
            if healthy:
                self._mark_verified(route.alias)
            return healthy

        if not self._circuit.acquire(route.alias, half_open_probe):
            return "circuit_open"
        if route.is_local and self._verify_local and not self._local_route_verified(adapter, route):
            self._circuit.record_failure(route.alias)
            return "probe_failed"
        return None

    # ------------------------------------------------------------------
    # Custo
    # ------------------------------------------------------------------

    def _actual_cost(self, route: ModelRoute, result: AdapterResult) -> int:
        """Custo real em micros da moeda do orçamento."""
        if route.is_local or route.is_subscription:
            # Assinatura: a franquia mensal já foi paga; não há custo por chamada.
            return 0
        reported_currency = str(route.extra.get("cost_currency", "USD")).upper()
        if (
            isinstance(result.cost_micros, int)
            and not isinstance(result.cost_micros, bool)
            and result.cost_micros >= 0
            and reported_currency == self._settings.budget_currency
        ):
            # Custo informado pelo provedor, na mesma moeda do orçamento.
            return result.cost_micros
        rate_in, rate_out = route.input_cost_micros_per_mtok, route.output_cost_micros_per_mtok
        tokens_in, tokens_out = result.usage.input_tokens, result.usage.output_tokens
        if rate_in is not None and rate_out is not None and tokens_in is not None and tokens_out is not None:
            total = tokens_in * rate_in + tokens_out * rate_out
            # Divisão inteira arredondando PARA CIMA: fração de micro conta como
            # um micro inteiro. Arredondar para baixo faria muitas chamadas
            # pequenas custarem zero no livro e passarem por baixo do teto.
            return -(-total // 1_000_000)
        # Sem custo informado nem tarifa registrada: assume o máximo reservado.
        logger.warning("cost_assumed_max alias=%s", route.alias)
        return int(route.max_cost_micros_per_call or 0)

    def _reserve(self, ctx: ExecutionContext, route: ModelRoute) -> Tuple[Optional[str], Optional[str]]:
        """Reserva o custo máximo da chamada: ``(entry_id, None)`` ou ``(None, motivo)``.

        A rota paga NUNCA é chamada sem reserva. Dois motivos para pular:

        * ``budget_exceeded``: o teto do titular não comporta a chamada;
        * ``budget_unavailable``: o livro falhou (banco fora, pool esgotado,
          qualquer exceção). Isso tira de jogo só ESTA rota: a exceção não sai
          de ``complete``, e as rotas seguintes (uma rota local não depende do
          livro) continuam sendo tentadas.
        """
        if route.is_local or route.is_subscription or self._ledger is None:
            return None, None
        failure: Optional[str] = None
        try:
            return self._ledger.reserve(ctx, route.alias, route.max_cost_micros_per_call), None
        except AiError as error:
            if error.code == "budget_exceeded":
                return None, "budget_exceeded"
            failure = error.code
        except Exception as error:  # noqa: BLE001 - falha de infraestrutura do livro
            failure = type(error).__name__
        # Só o tipo do erro: a mensagem de um erro de banco pode citar a consulta.
        logger.error(
            "budget_reserve_failed alias=%s error=%s trace_id=%s run_id=%s",
            route.alias, failure, ctx.trace_id, ctx.run_id,
        )
        return None, "budget_unavailable"

    def _settle(self, ctx: ExecutionContext, route: ModelRoute, entry_id: Optional[str], micros: Optional[int]) -> int:
        """Fecha a reserva: ``micros`` reconcilia; ``None`` libera. Devolve o custo."""
        if entry_id is None or self._ledger is None:
            return 0
        try:
            if micros is None:
                self._ledger.release(ctx, entry_id)
                return 0
            self._ledger.reconcile(ctx, entry_id, micros)
            return micros
        except Exception as error:  # noqa: BLE001
            # Falha ao fechar a reserva não pode esconder o desfecho da chamada.
            # A reserva fica aberta e continua contando no teto (lado seguro).
            logger.error(
                "budget_settle_failed alias=%s entry_id=%s error=%s trace_id=%s",
                route.alias, entry_id, type(error).__name__, ctx.trace_id,
            )
            return micros or 0

    # ------------------------------------------------------------------
    # Correção de saída estruturada
    # ------------------------------------------------------------------

    @staticmethod
    def _correction_request(original: ModelRequest, bad_content: str, errors: List[str]) -> ModelRequest:
        """Pedido de correção: a conversa original + o que estava errado.

        A lista de problemas cita caminhos e regras, não valores. O texto
        anterior do modelo volta para ele mesmo (mesma rota, mesma política de
        privacidade) e não é registrado em lugar nenhum.
        """
        messages = list(original.messages)
        if bad_content:
            messages.append(ChatMessage(role="assistant", content=bad_content[:_MAX_ECHO_CHARS]))
        problems = "\n".join("- %s" % item for item in errors[:_MAX_CORRECTION_ERRORS])
        messages.append(
            ChatMessage(
                role="user",
                content=(
                    "A resposta anterior não pôde ser validada. Responda de novo SOMENTE com um objeto JSON "
                    "válido, seguindo exatamente o schema pedido, sem nenhum texto fora do JSON.\n"
                    "Problemas encontrados:\n%s" % problems
                ),
            )
        )
        return replace(original, messages=messages)

    # ------------------------------------------------------------------
    # Falha final
    # ------------------------------------------------------------------

    @staticmethod
    def _fail(
        code: str,
        attempts: List[AttemptRecord],
        ctx: ExecutionContext,
        reason: str,
        cost_micros: int = 0,
        inference_calls: int = 0,
        **details: Any,
    ) -> AiError:
        payload: Dict[str, Any] = {"reason": reason}
        payload.update({key: value for key, value in details.items() if value is not None})
        error = AiError(code, details=payload)
        # Para a auditoria do orquestrador, lidos com ``getattr(error, nome, padrão)``.
        # Não vão em ``details`` porque ``details`` segue para a resposta HTTP.
        # ``cost_micros`` existe porque uma chamada que TERMINA em erro pode ter
        # custado dinheiro nas tentativas anteriores (JSON inválido é cobrado):
        # sem ele, o custo da execução na auditoria ficaria menor que o lançado
        # no livro de orçamento.
        error.attempts = list(attempts)  # type: ignore[attr-defined]
        error.cost_micros = int(cost_micros)  # type: ignore[attr-defined]
        error.inference_calls = int(inference_calls)  # type: ignore[attr-defined]
        logger.warning(
            "gateway_failed code=%s reason=%s attempts=%d calls=%d cost_micros=%d trace_id=%s run_id=%s",
            code, reason, len(attempts), int(inference_calls), int(cost_micros), ctx.trace_id, ctx.run_id,
        )
        return error

    # ------------------------------------------------------------------
    # Chamada
    # ------------------------------------------------------------------

    def complete(self, request: ModelRequest, ctx: ExecutionContext, budget: AttemptBudget) -> ModelResponse:
        started = time.perf_counter()
        attempts: List[AttemptRecord] = []
        calls = 0
        cost_total = 0

        def fail(code: str, reason: str, **details: Any) -> AiError:
            # Lê ``calls`` e ``cost_total`` no momento da falha (fechamento).
            return self._fail(
                code, attempts, ctx, reason, cost_micros=cost_total, inference_calls=calls, **details
            )

        if request.response_schema is not None:
            unknown = unsupported_keywords(request.response_schema)
            if unknown:
                # Defeito de quem montou o pedido; descoberto antes de gastar chamada.
                raise fail("internal_error", "schema_unsupported")

        eligibility = self._registry.eligible(request, ctx)
        for exclusion in eligibility.excluded:
            logger.debug(
                "route_excluded alias=%s reason=%s trace_id=%s", exclusion.alias, exclusion.reason, ctx.trace_id
            )
        routes = eligibility.routes
        if not routes:
            raise fail("model_unavailable", "no_eligible_route")

        index = 0
        working = request
        corrected = set()
        real_attempts = 0
        last_failure: Optional[str] = None
        last_retry_after: Optional[float] = None
        budget_blocked = False
        ledger_failed = False

        def skip(route: ModelRoute, reason: str) -> None:
            attempts.append(AttemptRecord(alias=route.alias, provider=route.provider, outcome="skipped:%s" % reason))
            logger.info(
                "route_skipped alias=%s reason=%s trace_id=%s run_id=%s", route.alias, reason, ctx.trace_id, ctx.run_id
            )

        while index < len(routes) and budget.remaining() > 0:
            route = routes[index]
            reason = self._gate(route, request, ctx, routes, index)
            if reason is not None:
                skip(route, reason)
                index, working = index + 1, request
                continue
            adapter = self._adapters[route.provider]

            entry_id, blocked = self._reserve(ctx, route)
            if blocked is not None:
                if blocked == "budget_exceeded":
                    budget_blocked = True
                else:
                    ledger_failed = True
                skip(route, blocked)
                index, working = index + 1, request
                continue

            attempt_started = time.perf_counter()
            result: Optional[AdapterResult] = None
            failure: Optional[ProviderError] = None
            crash: Optional[str] = None
            try:
                result = adapter.complete(route, working, self._timeout_for(route))
            except ProviderError as error:
                failure = error
            except Exception as error:  # noqa: BLE001 - defeito do adaptador, não do provedor
                crash = type(error).__name__
            if crash is None and failure is None and not isinstance(result, AdapterResult):
                crash = "InvalidAdapterResult"  # adaptador devolveu outra coisa (ex.: None)
            # O tratamento fica FORA do ``try``: um AiError levantado dentro do
            # ``except`` carregaria a exceção do adaptador em ``__context__``, e
            # ela pode guardar o pedido (com credencial) ou a resposta.

            if crash is not None:
                # Não se sabe se a requisição saiu: conta a tentativa e mantém a
                # reserva pelo máximo (lado seguro nos dois orçamentos).
                budget.take(1)
                calls += 1
                cost_total += self._settle(ctx, route, entry_id, route.max_cost_micros_per_call)
                logger.error(
                    "adapter_crashed alias=%s provider=%s error=%s trace_id=%s",
                    route.alias, route.provider, crash, ctx.trace_id,
                )
                attempts.append(AttemptRecord(alias=route.alias, provider=route.provider, outcome="bad_request"))
                raise fail("internal_error", "adapter_error")

            if failure is not None:
                error = failure
                latency_ms = int((time.perf_counter() - attempt_started) * 1000)
                if error.detail_code not in NOT_ATTEMPTED_DETAILS:
                    # Tentativas internas de um agregador contam também quando
                    # ele termina em ERRO: foram chamadas de inferência reais.
                    used = max(1, int(getattr(error, "upstream_attempts", 1) or 1))
                    budget.take(used)
                    calls += used
                    real_attempts += 1
                # else: credencial ausente ou malformada. Nem tentativa de
                # conexão houve, então o orçamento de tentativas fica intacto.
                billed = route.max_cost_micros_per_call if _possibly_billed(error) else None
                cost_total += self._settle(ctx, route, entry_id, billed)
                attempts.append(
                    AttemptRecord(
                        alias=route.alias, provider=route.provider, outcome=error.kind,
                        latency_ms=latency_ms, status=error.status,
                    )
                )
                logger.info(
                    "attempt alias=%s provider=%s outcome=%s status=%s detail=%s latency_ms=%d trace_id=%s run_id=%s",
                    route.alias, route.provider, error.kind, error.status, error.detail_code, latency_ms,
                    ctx.trace_id, ctx.run_id,
                )
                last_failure = error.kind
                last_retry_after = error.retry_after_s

                if error.kind == "refusal":
                    raise fail("model_refused", "refusal")
                if error.kind == "bad_request":
                    raise fail("internal_error", "bad_request", detail_code=error.detail_code)
                if error.detail_code == DETAIL_UPSTREAM_MISMATCH:
                    # Violação de política, não de saúde: não conta no disjuntor
                    # (que reabriria sozinho); a rota fica fora até o operador
                    # reativar. Segue só por outra rota já autorizada.
                    self._suspend_route(route, DETAIL_UPSTREAM_MISMATCH, ctx)
                    index, working = index + 1, request
                    continue
                if error.kind == "auth":
                    self._suspend(route, error, ctx)
                    index, working = index + 1, request
                    continue
                if error.kind == "invalid_output":
                    if route.alias not in corrected and budget.remaining() > 0:
                        corrected.add(route.alias)
                        working = self._correction_request(request, "", [_MALFORMED_OUTPUT])
                        continue
                    index, working = index + 1, request
                    continue

                # Falha transitória: timeout, rede, 429, 5xx, indisponível.
                opened = self._circuit.record_failure(route.alias)
                if error.retry_after_s is not None:
                    if error.retry_after_s > 0:
                        with self._lock:
                            self._cooldown_until[route.alias] = self._clock() + error.retry_after_s
                    if (
                        not opened
                        and error.retry_after_s <= self._max_wait_s
                        and budget.remaining() > 0
                        and not self._has_alternative(routes, index)
                    ):
                        # Sem outra rota e com espera curta: a trava de
                        # Retry-After espera e a MESMA rota é tentada de novo.
                        # Se esta falha ABRIU o circuito, não: a rota não seria
                        # tentada depois da espera, que só gastaria o prazo.
                        continue
                index, working = index + 1, request
                continue

            # ---- o provedor respondeu ------------------------------------
            latency_ms = result.latency_ms or int((time.perf_counter() - attempt_started) * 1000)
            used = max(1, int(result.upstream_attempts or 1))
            budget.take(used)
            calls += used
            real_attempts += 1
            self._circuit.record_success(route.alias)
            cost_total += self._settle(ctx, route, entry_id, self._actual_cost(route, result))

            parsed: Optional[Dict[str, Any]] = None
            errors: List[str] = []
            echo = ""
            if result.tool_calls:
                if result.finish_reason == "length":
                    # Chamada de ferramenta cortada pelo limite de tokens: os
                    # argumentos podem estar pela metade (ou vazios). Entregar
                    # isso ao orquestrador seria executar uma ferramenta com o
                    # que sobrou do corte. Tratada como saída inválida.
                    errors = [_TRUNCATED_TOOL_CALL]
            elif request.response_schema is not None:
                parsed, errors = self._validate_output(result, request.response_schema)
                echo = result.content
            if errors:
                attempts.append(
                    AttemptRecord(
                        alias=route.alias, provider=route.provider, outcome="invalid_output",
                        latency_ms=latency_ms, status=200,
                    )
                )
                logger.info(
                    "attempt alias=%s provider=%s outcome=invalid_output errors=%d latency_ms=%d "
                    "trace_id=%s run_id=%s",
                    route.alias, route.provider, len(errors), latency_ms, ctx.trace_id, ctx.run_id,
                )
                last_failure, last_retry_after = "invalid_output", None
                if route.alias not in corrected and budget.remaining() > 0:
                    # Exatamente UMA correção por rota.
                    corrected.add(route.alias)
                    working = self._correction_request(request, echo, errors)
                    continue
                index, working = index + 1, request
                continue

            attempts.append(
                AttemptRecord(
                    alias=route.alias, provider=route.provider, outcome="ok", latency_ms=latency_ms, status=200
                )
            )
            total_ms = int((time.perf_counter() - started) * 1000)
            fallback_used = route.alias != routes[0].alias
            logger.info(
                "attempt alias=%s provider=%s outcome=ok latency_ms=%d calls=%d fallback=%s cost_micros=%d "
                "trace_id=%s run_id=%s",
                route.alias, route.provider, latency_ms, calls, "yes" if fallback_used else "no", cost_total,
                ctx.trace_id, ctx.run_id,
            )
            return ModelResponse(
                content=result.content,
                parsed=parsed,
                tool_calls=list(result.tool_calls),
                finish_reason=result.finish_reason,
                alias=route.alias,
                provider=route.provider,
                model_id=self._effective_model(route, result, ctx),
                effective_provider=safe_label(result.effective_provider, allow_spaces=True),
                usage=result.usage if isinstance(result.usage, Usage) else Usage(),
                cost_micros=cost_total,
                latency_ms=total_ms,
                inference_calls=calls,
                fallback_used=fallback_used,
                attempts=attempts,
            )

        # ---- nenhuma rota respondeu de forma aproveitável -----------------
        if last_failure == "invalid_output":
            raise fail("invalid_output", "invalid_output")
        if real_attempts == 0 and budget_blocked:
            # Nenhuma chamada foi feita e o motivo foi o teto de custo.
            raise fail("budget_exceeded", "cost_ceiling")
        if budget.remaining() <= 0 and index < len(routes):
            reason = "attempt_budget_exhausted"
        elif real_attempts == 0 and ledger_failed:
            # Nada foi tentado porque o livro de orçamento falhou. Não é teto
            # atingido (isso seria ``budget_exceeded``): é indisponibilidade.
            reason = "budget_unavailable"
        else:
            reason = "all_routes_failed"
        retry_after = int(last_retry_after) + 1 if last_failure == "rate_limited" and last_retry_after else None
        raise fail("model_unavailable", reason, retry_after_s=retry_after)

    @staticmethod
    def _effective_model(route: ModelRoute, result: AdapterResult, ctx: ExecutionContext) -> str:
        """Modelo efetivo para a auditoria, filtrado.

        Os adaptadores deste pacote já filtram o rótulo; a conferência se
        repete aqui porque ``ModelResponse`` é gravado pelo orquestrador e um
        adaptador de terceiros poderia repassar o texto do provedor como veio.
        """
        label = safe_label(result.model_id)
        if label is None:
            if result.model_id:
                logger.warning(
                    "provider_label_rejected alias=%s field=model trace_id=%s", route.alias, ctx.trace_id
                )
            return route.model_id
        return label

    @staticmethod
    def _validate_output(result: AdapterResult, schema: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        if result.finish_reason == "length":
            # Resposta cortada pelo limite de tokens não é JSON confiável mesmo
            # que, por acaso, feche as chaves.
            return None, ["a resposta foi cortada pelo limite de tamanho; responda de forma mais curta"]
        return validate_structured_output(result.content, schema)


def build_gateway(
    pool, settings: AiSettings, *, adapters: Optional[Dict[str, ProviderAdapter]] = None,
) -> DefaultModelGateway:
    """Monta o gateway padrão a partir da configuração.

    Lê o registro de modelos do caminho configurado; não abre conexão com
    provedor nem lê credenciais (isso só acontece na hora de cada chamada).
    Sem ``pool`` não há livro de orçamento, e rota externa nenhuma é usada
    (``skipped:no_budget_ledger``).
    """
    from .adapters import build_default_adapters

    return DefaultModelGateway(
        registry=ModelRegistry.from_settings(settings),
        adapters=build_default_adapters(settings) if adapters is None else adapters,
        circuit=CircuitBreaker(settings),
        budget_ledger=BudgetLedger(pool, settings) if pool is not None else None,
        settings=settings,
    )
