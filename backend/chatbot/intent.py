"""
Detecção leve de intenção sem LLM.
Classifica mensagem em: help, finance_query, chat (fallback).
"""
from typing import Literal

Intent = Literal["help", "finance_query", "chat"]

HELP_KEYWORDS = [
    "como", "cadastrar", "editar", "excluir", "criar", "registrar",
]
FINANCE_QUERY_KEYWORDS = [
    "quanto", "gastei", "saldo", "total", "categoria", "receita", "despesa",
]


def normalize_for_intent(text: str) -> str:
    """Normaliza texto para comparação (lower, strip, collapse spaces)."""
    if not text or not isinstance(text, str):
        return ""
    return " ".join(text.strip().lower().split())


def detect_intent(message: str) -> Intent:
    """
    Detecta intenção por palavras-chave.
    Ordem: help (qualquer keyword de ajuda) > finance_query > chat.
    """
    normalized = normalize_for_intent(message)
    if not normalized:
        return "chat"

    words = set(normalized.split())
    help_hits = sum(1 for k in HELP_KEYWORDS if k in normalized)
    finance_hits = sum(1 for k in FINANCE_QUERY_KEYWORDS if k in normalized)

    if help_hits > 0 and help_hits >= finance_hits:
        return "help"
    if finance_hits > 0:
        return "finance_query"
    return "chat"
