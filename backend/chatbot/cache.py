"""
Cache em memória com TTL para respostas do chatbot.
Chave: (normalized_message, user_id, conversation_id opcional).
TTL padrão: 10 minutos.
"""
import time
import logging
from typing import Any, Dict, Optional, Tuple

from chatbot.intent import normalize_for_intent

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600  # 10 minutos


def _cache_key(normalized_message: str, user_id: str, conversation_id: Optional[str] = None) -> str:
    """Gera chave única para a entrada do cache."""
    cid = conversation_id or ""
    return f"{normalized_message}|{user_id}|{cid}"


class ChatbotCache:
    """
    Cache in-memory com TTL.
    Estrutura interna: key -> (value, expiry_ts).
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._store: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._ttl = ttl_seconds

    def get(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retorna resposta em cache se existir e não expirada.
        Valor esperado: dict com 'message' e opcionalmente 'conversation_id', 'metadata'.
        """
        key = _cache_key(normalize_for_intent(message), user_id, conversation_id)
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    def set(
        self,
        message: str,
        user_id: str,
        response: Dict[str, Any],
        conversation_id: Optional[str] = None,
    ) -> None:
        """Armazena resposta no cache com TTL."""
        key = _cache_key(normalize_for_intent(message), user_id, conversation_id)
        self._store[key] = (response, time.monotonic() + self._ttl)


# Instância global usada pelo router (um por processo)
_cache: Optional[ChatbotCache] = None


def get_cache(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> ChatbotCache:
    """Retorna instância do cache (singleton por processo)."""
    global _cache
    if _cache is None:
        _cache = ChatbotCache(ttl_seconds=ttl_seconds)
    return _cache
