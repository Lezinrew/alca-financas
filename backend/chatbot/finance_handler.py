"""
Handler de consultas financeiras sem LLM.
Estrutura preparada para injeção de repositórios/serviços (dashboard, reports) depois.
Por enquanto retorna respostas placeholder seguras.
"""
import logging
from typing import Any, Dict, Optional

from chatbot.intent import normalize_for_intent

logger = logging.getLogger(__name__)

# Placeholder: quando consultas reais não estiverem disponíveis
PLACEHOLDER_MESSAGE = (
    "Você pode consultar gastos, receitas e categorias pela seção **Relatórios** ou pelo **Dashboard** no menu. "
    "Em breve poderei responder essas perguntas diretamente aqui."
)


def handle(
    user_id: str,
    message: str,
    conversation_id: Optional[str] = None,
    # Futuro: dashboard_service=None, report_service=None, transaction_repo=None
) -> Dict[str, Any]:
    """
    Processa pergunta financeira (ex.: quanto gastei, maior gasto por categoria).
    Retorna o mesmo formato da API: success, message, conversation_id, metadata.
    Por enquanto não chama repositórios; estrutura permite extensão incremental.
    """
    normalized = normalize_for_intent(message)

    # Placeholder: detectar padrões comuns e responder de forma segura
    # Extensão futura: chamar report_service / dashboard com user_id e retornar dados reais
    if any(
        k in normalized
        for k in ("quanto gastei", "quanto entrou", "maior gasto", "categoria", "total", "saldo")
    ):
        logger.info(
            "finance_handler_placeholder user_id_len=%s message_len=%s",
            len(user_id or ""), len(message or ""),
        )
        return {
            "success": True,
            "message": PLACEHOLDER_MESSAGE,
            "conversation_id": conversation_id,
            "metadata": {"route": "FINANCE", "placeholder": True},
        }

    # Fallback para qualquer finance_query não mapeado
    return {
        "success": True,
        "message": PLACEHOLDER_MESSAGE,
        "conversation_id": conversation_id,
        "metadata": {"route": "FINANCE", "placeholder": True},
    }
