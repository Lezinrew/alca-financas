"""Erros da plataforma de IA no formato do contrato (seção 6).

Todo erro que cruza a fronteira HTTP ou fica gravado em uma execução tem
``code``, ``retryable``, ``safe_message`` e ``trace_id``. Nunca carrega
stacktrace, token nem corpo bruto de provedor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# code -> (status HTTP, retryable padrão, mensagem segura padrão)
_CATALOG = {
    # Códigos mínimos do contrato.
    "unauthorized": (401, False, "Sessão ausente ou expirada."),
    "scope_denied": (403, False, "Este pedido está fora do escopo autorizado."),
    "connector_unavailable": (503, True, "O conector necessário está indisponível."),
    "model_unavailable": (503, True, "Nenhum modelo autorizado está disponível agora."),
    "budget_exceeded": (429, False, "O orçamento definido para a IA foi atingido."),
    "invalid_output": (502, True, "O modelo devolveu uma resposta que não pôde ser validada."),
    "ambiguous_evidence": (409, False, "A evidência é ambígua e precisa de revisão."),
    "stale_proposal": (409, False, "A proposta ficou desatualizada. Gere uma nova prévia."),
    "operation_unknown": (404, False, "Operação não encontrada."),
    # Detalhamento desta implementação (contrato 1.1.0, anexo A).
    "invalid_request": (400, False, "Pedido inválido."),
    "invalid_csrf": (403, False, "Token CSRF inválido."),
    "capability_denied": (403, False, "Esta capacidade não está autorizada."),
    "not_found": (404, False, "Recurso não encontrado."),
    "conflict": (409, False, "O pedido conflita com um pedido anterior."),
    "payload_too_large": (413, False, "O arquivo ou pedido excede o tamanho permitido."),
    "rate_limited": (429, True, "Muitos pedidos em pouco tempo. Tente novamente em instantes."),
    "ai_disabled": (503, False, "O operador de IA está desativado."),
    "cancelled": (409, False, "A execução foi cancelada."),
    # Recusa de conteúdo pelo modelo: não aciona troca de rota (seção 8).
    "model_refused": (422, False, "O modelo recusou este pedido."),
    # Limites globais de uma execução (seção 8): tempo e número de ferramentas.
    "deadline_exceeded": (504, True, "A execução passou do tempo permitido."),
    "tool_limit_exceeded": (429, False, "A execução atingiu o limite de ferramentas."),
    "internal_error": (500, True, "Não foi possível concluir o pedido."),
}

CONTRACT_MINIMUM_CODES = (
    "unauthorized",
    "scope_denied",
    "connector_unavailable",
    "model_unavailable",
    "budget_exceeded",
    "invalid_output",
    "ambiguous_evidence",
    "stale_proposal",
    "operation_unknown",
)


class AiError(Exception):
    """Erro com código estável e mensagem segura para o titular."""

    def __init__(
        self,
        code: str,
        safe_message: Optional[str] = None,
        *,
        retryable: Optional[bool] = None,
        http_status: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if code not in _CATALOG:
            raise ValueError("código de erro desconhecido: %s" % code)
        status, default_retryable, default_message = _CATALOG[code]
        self.code = code
        self.safe_message = safe_message or default_message
        self.retryable = default_retryable if retryable is None else retryable
        self.http_status = http_status or status
        # ``details`` é somente para chaves seguras e pequenas (ex.: campo
        # inválido). Não use para conteúdo de anexo, prompt ou resposta bruta.
        self.details = dict(details or {})
        # Preenchidos pelo gateway quando o erro encerra uma inferência: trilha
        # das tentativas (sem conteúdo), custo já cobrado e chamadas debitadas
        # do orçamento. Não entram em ``to_dict``; servem à auditoria.
        self.attempts: List[Any] = []
        self.cost_micros: int = 0
        self.inference_calls: int = 0
        super().__init__("%s: %s" % (code, self.safe_message))

    def to_dict(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": self.code,
            "retryable": self.retryable,
            "safe_message": self.safe_message,
            "trace_id": trace_id,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def error_dict(code: str, trace_id: Optional[str] = None, safe_message: Optional[str] = None) -> Dict[str, Any]:
    return AiError(code, safe_message).to_dict(trace_id)


def is_known_code(code: str) -> bool:
    return code in _CATALOG
