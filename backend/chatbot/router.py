"""
Roteador do chatbot: intent → FAQ → cache → finance → OpenClaw (LLM).
Reduz custo de LLM encaminhando para respostas locais quando possível.
"""
import logging
from typing import Any, Dict, Optional

from chatbot.intent import detect_intent, normalize_for_intent
from chatbot.faq import get_faq_response
from chatbot.cache import get_cache
from chatbot.finance_handler import handle as finance_handle

logger = logging.getLogger(__name__)


def _success_response(
    message: str,
    conversation_id: Optional[str],
    route: str,
    metadata_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Monta resposta de sucesso no contrato da API do chatbot."""
    meta = {"route": route}
    if metadata_extra:
        meta.update(metadata_extra)
    return {
        "success": True,
        "message": message,
        "conversation_id": conversation_id,
        "metadata": meta,
    }


def route_message(
    user_id: str,
    message: str,
    conversation_id: Optional[str] = None,
    openclaw_service: Any = None,
) -> Dict[str, Any]:
    """
    Fluxo: detect intent → FAQ (se help e match) → cache → finance (se finance_query) → OpenClaw.
    Sempre retorna o mesmo contrato: success, message, conversation_id, metadata.
    metadata.route indica: FAQ | CACHE | FINANCE | LLM.
    openclaw_service deve ser passado pela rota (evita import circular e usa instância existente).
    """
    if openclaw_service is None:
        raise ValueError("route_message requer openclaw_service (passado pela rota)")

    normalized = normalize_for_intent(message)
    user_id_safe = (user_id or "")[:8] + ("..." if len(user_id or "") > 8 else "")
    msg_len = len(message or "")

    intent = detect_intent(message)

    # 1) FAQ para intenção help
    if intent == "help":
        faq_answer = get_faq_response(message)
        if faq_answer is not None:
            logger.info(
                "chatbot_route route=FAQ user_id_trunc=%s message_len=%s",
                user_id_safe, msg_len,
            )
            return _success_response(faq_answer, conversation_id, "FAQ")

    # 2) Cache
    cache = get_cache()
    cached = cache.get(message, user_id, conversation_id)
    if cached is not None:
        logger.info(
            "chatbot_route route=CACHE user_id_trunc=%s message_len=%s",
            user_id_safe, msg_len,
        )
        if cached.get("metadata"):
            cached["metadata"]["route"] = "CACHE"
        else:
            cached["metadata"] = {"route": "CACHE"}
        return cached

    # 3) Finance handler para finance_query
    if intent == "finance_query":
        result = finance_handle(user_id, message, conversation_id)
        logger.info(
            "chatbot_route route=FINANCE user_id_trunc=%s message_len=%s",
            user_id_safe, msg_len,
        )
        return result

    # 4) Fallback: OpenClaw (LLM)
    logger.info(
        "chatbot_route route=LLM user_id_trunc=%s message_len=%s",
        user_id_safe, msg_len,
    )
    result = openclaw_service.chat(
        message=message,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if result.get("success") and result.get("message"):
        if result.get("metadata") is None:
            result["metadata"] = {}
        result["metadata"]["route"] = "LLM"
        cache.set(message, user_id, result, conversation_id)
    else:
        # Erro do LLM: não cachear
        if result.get("metadata") is None:
            result["metadata"] = {}
        result["metadata"]["route"] = "LLM"
    return result
