"""
Serviço de integração com OpenClaw via bridge HTTP interno
"""
import os
import time
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Defaults alinhados ao docker-compose.prod.yml e openclaw_bridge
DEFAULT_BRIDGE_URL = "http://openclaw-bridge:8089"
DEFAULT_TIMEOUT = 60

# Tipos de erro padronizados (não vazar erros brutos do CLI/gateway)
ERROR_TYPE_BRIDGE_TIMEOUT = "bridge_timeout"
ERROR_TYPE_BRIDGE_UNAVAILABLE = "bridge_unavailable"
ERROR_TYPE_GATEWAY_UNAVAILABLE = "gateway_unavailable"
ERROR_TYPE_LLM_AUTH_ERROR = "llm_auth_error"
ERROR_TYPE_LLM_FAILURE = "llm_failure"
ERROR_TYPE_INTERNAL = "internal_error"


def _error_response(error_type: str, message: str, retryable: bool) -> Dict[str, Any]:
    """Resposta de erro padronizada para o pipeline do chatbot. Inclui message no top-level e detail para compatibilidade com clientes."""
    return {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
            "retryable": retryable,
        },
        "message": message,
        "detail": message,
    }


def _truncate_user_id(user_id: str, length: int = 8) -> str:
    """Trunca user_id para logs (nunca logar conteúdo sensível)."""
    if not user_id or len(user_id) <= length:
        return (user_id or "")[:length]
    return f"{user_id[:length]}..."


class OpenClawService:
    def __init__(self):
        self.bridge_url = (
            os.getenv("OPENCLAW_BRIDGE_URL") or DEFAULT_BRIDGE_URL
        ).rstrip("/")
        raw_timeout = os.getenv("OPENCLAW_TIMEOUT", str(DEFAULT_TIMEOUT))
        try:
            self.timeout = max(10, min(300, int(raw_timeout)))
        except (TypeError, ValueError):
            self.timeout = DEFAULT_TIMEOUT

        logger.info(
            "openclaw_service_init bridge_url=%s timeout=%s",
            self.bridge_url, self.timeout
        )

    def chat(self, message: str, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        suspicious_keywords = [
            "ignore", "bypass", "admin", "root", "all users",
            "database", "sql", "select *", "show me all",
            "other user", "outros usuários", "password", "senha"
        ]
        user_id_trunc = _truncate_user_id(user_id)
        message_len = len(message) if message else 0

        message_lower = (message or "").lower()
        if any(keyword in message_lower for keyword in suspicious_keywords):
            logger.warning(
                "chatbot_filter_block user_id_trunc=%s conversation_id=%s message_len=%s",
                user_id_trunc, conversation_id, message_len
            )
            return {
                "success": True,
                "message": "Desculpe, não posso processar essa solicitação. Como posso ajudá-lo com o uso do Alça Finanças?",
                "conversation_id": conversation_id,
                "metadata": {}
            }

        t0 = time.perf_counter()
        logger.info(
            "bridge_request_start user_id_trunc=%s conversation_id=%s message_len=%s",
            user_id_trunc, conversation_id, message_len
        )

        try:
            payload = {
                "message": message,
                "user_id": user_id,
                "conversation_id": conversation_id,
            }

            response = requests.post(
                f"{self.bridge_url}/chat",
                json=payload,
                timeout=self.timeout,
            )

            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "bridge_request_end user_id_trunc=%s conversation_id=%s message_len=%s elapsed_ms=%s status_code=200 outcome=success",
                    user_id_trunc, conversation_id, message_len, elapsed_ms
                )
                return {
                    "success": True,
                    "message": data.get("message", ""),
                    "conversation_id": data.get("conversation_id"),
                    "metadata": data.get("metadata", {}),
                }

            logger.error(
                "bridge_request_end user_id_trunc=%s conversation_id=%s message_len=%s elapsed_ms=%s status_code=%s outcome=bridge_error",
                user_id_trunc, conversation_id, message_len, elapsed_ms, response.status_code
            )
            if response.status_code == 504:
                return _error_response(
                    ERROR_TYPE_BRIDGE_TIMEOUT,
                    "O chatbot demorou muito para responder. Tente novamente.",
                    retryable=True,
                )
            if response.status_code in (401, 403):
                return _error_response(
                    ERROR_TYPE_LLM_AUTH_ERROR,
                    "Erro de autorização do assistente. Tente fazer login novamente.",
                    retryable=False,
                )
            if response.status_code == 503:
                return _error_response(
                    ERROR_TYPE_GATEWAY_UNAVAILABLE,
                    "O assistente está temporariamente indisponível. Tente novamente em instantes.",
                    retryable=True,
                )
            if response.status_code in (502,):
                return _error_response(
                    ERROR_TYPE_BRIDGE_UNAVAILABLE,
                    "Erro ao conectar com o chatbot. Tente novamente mais tarde.",
                    retryable=True,
                )
            return _error_response(
                ERROR_TYPE_LLM_FAILURE,
                "Desculpe, houve um erro ao processar sua mensagem. Tente novamente.",
                retryable=True,
            )

        except requests.exceptions.Timeout:
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            logger.error(
                "bridge_timeout user_id_trunc=%s conversation_id=%s message_len=%s elapsed_ms=%s",
                user_id_trunc, conversation_id, message_len, elapsed_ms
            )
            return _error_response(
                ERROR_TYPE_BRIDGE_TIMEOUT,
                "O chatbot demorou muito para responder. Tente novamente.",
                retryable=True,
            )
        except requests.exceptions.RequestException as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            logger.error(
                "bridge_request_error user_id_trunc=%s conversation_id=%s message_len=%s elapsed_ms=%s error=%s",
                user_id_trunc, conversation_id, message_len, elapsed_ms, e
            )
            return _error_response(
                ERROR_TYPE_BRIDGE_UNAVAILABLE,
                "Erro ao conectar com o chatbot. Tente novamente mais tarde.",
                retryable=True,
            )
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            logger.exception(
                "openclaw_unexpected_error user_id_trunc=%s conversation_id=%s message_len=%s elapsed_ms=%s error=%s",
                user_id_trunc, conversation_id, message_len, elapsed_ms, e
            )
            return _error_response(
                ERROR_TYPE_INTERNAL,
                "Erro inesperado. Tente novamente.",
                retryable=True,
            )

    def get_conversation_history(self, conversation_id: str) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"{self.bridge_url}/conversations/{conversation_id}",
                timeout=15,
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "history": response.json().get("history", []),
                }

            return {
                "success": False,
                "error": f"Erro {response.status_code}",
            }

        except Exception as e:
            logger.error(f"Error fetching conversation history: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def health_check(self) -> bool:
        """Verifica disponibilidade do bridge; o bridge por sua vez verifica o gateway."""
        try:
            response = requests.get(f"{self.bridge_url}/health", timeout=5)
            if response.status_code != 200:
                logger.warning(
                    "gateway_health_failure bridge_url=%s status_code=%s",
                    self.bridge_url, response.status_code
                )
                return False

            data = response.json()
            ok = data.get("ok") is True
            if not ok:
                logger.warning(
                    "gateway_health_failure bridge_url=%s response_ok=False body=%s",
                    self.bridge_url, data
                )
            return ok
        except Exception as e:
            logger.warning(
                "gateway_health_failure bridge_url=%s error=%s",
                self.bridge_url, e
            )
            return False
