"""
Serviço de integração com OpenClaw via bridge HTTP interno
"""
import os
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenClawService:
    def __init__(self):
        self.bridge_url = (
            os.getenv("OPENCLAW_BRIDGE_URL")
            or "http://openclaw-bridge:8089"
        ).rstrip("/")
        self.timeout = int(os.getenv("OPENCLAW_TIMEOUT", "60"))

        logger.info(f"OpenClaw Bridge URL configurada: {self.bridge_url}")

    def chat(self, message: str, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        suspicious_keywords = [
            "ignore", "bypass", "admin", "root", "all users",
            "database", "sql", "select *", "show me all",
            "other user", "outros usuários", "password", "senha"
        ]

        message_lower = message.lower()
        if any(keyword in message_lower for keyword in suspicious_keywords):
            logger.warning(f"🚨 Suspicious message detected from user {user_id[:8]}...: {message[:100]}")
            return {
                "success": True,
                "message": "Desculpe, não posso processar essa solicitação. Como posso ajudá-lo com o uso do Alça Finanças?",
                "conversation_id": conversation_id,
                "metadata": {}
            }

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

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": data.get("message", ""),
                    "conversation_id": data.get("conversation_id"),
                    "metadata": data.get("metadata", {}),
                }

            logger.error(f"OpenClaw bridge error: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Erro {response.status_code}",
                "message": "Desculpe, houve um erro ao processar sua mensagem.",
            }

        except requests.exceptions.Timeout:
            logger.error("OpenClaw bridge timeout")
            return {
                "success": False,
                "error": "Timeout",
                "message": "O chatbot demorou muito para responder. Tente novamente.",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenClaw bridge request error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Erro ao conectar com o chatbot. Tente novamente mais tarde.",
            }
        except Exception as e:
            logger.error(f"OpenClaw unexpected error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Erro inesperado. Tente novamente.",
            }

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
        try:
            response = requests.get(f"{self.bridge_url}/health", timeout=5)
            if response.status_code != 200:
                return False

            data = response.json()
            return data.get("ok") is True
        except Exception as e:
            logger.warning(f"OpenClaw bridge health failed: {e}")
            return False
