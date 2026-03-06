"""
Serviço de integração com OpenClaw - Chatbot AI
"""
import os
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenClawService:
    """Serviço para comunicação com OpenClaw chatbot"""

    def __init__(self):
        self.gateway_token = os.getenv('OPENCLAW_GATEWAY_TOKEN')
        self.openclaw_url = os.getenv('OPENCLAW_URL', 'http://localhost:40394')
        self.timeout = 30  # 30 segundos

        if not self.gateway_token:
            logger.warning("OPENCLAW_GATEWAY_TOKEN não configurado")

    def chat(self, message: str, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia mensagem para o chatbot OpenClaw

        Args:
            message: Mensagem do usuário
            user_id: ID do usuário
            conversation_id: ID da conversa (opcional, para manter contexto)

        Returns:
            Dict com a resposta do chatbot
        """
        if not self.gateway_token:
            return {
                'success': False,
                'error': 'OpenClaw não configurado',
                'message': 'Desculpe, o chatbot não está disponível no momento.'
            }

        # SEGURANÇA: Detectar possíveis tentativas de prompt injection
        suspicious_keywords = [
            'ignore', 'bypass', 'admin', 'root', 'all users',
            'database', 'sql', 'select *', 'show me all',
            'other user', 'outros usuários', 'password', 'senha'
        ]

        message_lower = message.lower()
        if any(keyword in message_lower for keyword in suspicious_keywords):
            logger.warning(f"🚨 Suspicious message detected from user {user_id[:8]}...: {message[:100]}")
            return {
                'success': True,
                'message': 'Desculpe, não posso processar essa solicitação. Como posso ajudá-lo com o uso do Alça Finanças?',
                'conversation_id': conversation_id
            }

        # Log para auditoria (sem dados sensíveis)
        logger.info(f"Chatbot request from user {user_id[:8]}... - Message length: {len(message)}")

        try:
            headers = {
                'Authorization': f'Bearer {self.gateway_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                'message': message,
                'user_id': user_id,
            }

            if conversation_id:
                payload['conversation_id'] = conversation_id

            response = requests.post(
                f'{self.openclaw_url}/api/chat',
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'message': data.get('message', ''),
                    'conversation_id': data.get('conversation_id'),
                    'metadata': data.get('metadata', {})
                }
            else:
                logger.error(f"OpenClaw error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Erro {response.status_code}',
                    'message': 'Desculpe, houve um erro ao processar sua mensagem.'
                }

        except requests.exceptions.Timeout:
            logger.error("OpenClaw timeout")
            return {
                'success': False,
                'error': 'Timeout',
                'message': 'O chatbot demorou muito para responder. Tente novamente.'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenClaw request error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Erro ao conectar com o chatbot. Tente novamente mais tarde.'
            }
        except Exception as e:
            logger.error(f"OpenClaw unexpected error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Erro inesperado. Tente novamente.'
            }

    def get_conversation_history(self, conversation_id: str) -> Dict[str, Any]:
        """
        Busca histórico de uma conversa

        Args:
            conversation_id: ID da conversa

        Returns:
            Dict com histórico da conversa
        """
        if not self.gateway_token:
            return {'success': False, 'error': 'OpenClaw não configurado'}

        try:
            headers = {
                'Authorization': f'Bearer {self.gateway_token}',
            }

            response = requests.get(
                f'{self.openclaw_url}/api/conversations/{conversation_id}',
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return {
                    'success': True,
                    'history': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'Erro {response.status_code}'
                }

        except Exception as e:
            logger.error(f"Error fetching conversation history: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def health_check(self) -> bool:
        """
        Verifica se o OpenClaw está respondendo

        Returns:
            True se está funcionando, False caso contrário
        """
        try:
            response = requests.get(
                f'{self.openclaw_url}/health',
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
