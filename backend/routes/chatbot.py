"""
Rotas para o Chatbot OpenClaw
"""
import time
import logging
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils_supabase import token_required
from services.openclaw_service import OpenClawService
from repositories.chatbot_repository import ChatbotRepository
from extensions import limiter

logger = logging.getLogger(__name__)


def _truncate_user_id(user_id: str, length: int = 8) -> str:
    """Trunca user_id para logs (nunca logar conteúdo sensível)."""
    if not user_id or len(user_id) <= length:
        return (user_id or "")[:length]
    return f"{user_id[:length]}..."

bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

openclaw_service = OpenClawService()
chatbot_repo = ChatbotRepository()


@bp.route('/chat', methods=['POST'])
@token_required
@limiter.limit("20 per minute")  # Rate limiting: 20 mensagens por minuto
def chat(current_user):
    """
    Endpoint para enviar mensagem ao chatbot

    Request body:
        {
            "message": "Como criar uma transação?",
            "conversation_id": "optional-conversation-id"
        }

    Returns:
        {
            "success": true,
            "message": "Para criar uma transação...",
            "conversation_id": "conv-123",
            "metadata": {}
        }
    """
    t0 = time.perf_counter()
    user_id = current_user.get('id') or ''
    user_id_trunc = _truncate_user_id(user_id)

    try:
        data = request.get_json()

        if not data or 'message' not in data:
            logger.info(
                "chatbot_request_end user_id_trunc=%s conversation_id=%s message_len=0 outcome=validation_fail",
                user_id_trunc, None
            )
            return jsonify({
                'error': 'Mensagem é obrigatória'
            }), 400

        message = data['message'].strip()
        if not message:
            logger.info(
                "chatbot_request_end user_id_trunc=%s conversation_id=%s message_len=0 outcome=validation_fail",
                user_id_trunc, None
            )
            return jsonify({
                'error': 'Mensagem não pode estar vazia'
            }), 400

        if len(message) > 1000:
            logger.info(
                "chatbot_request_end user_id_trunc=%s conversation_id=%s message_len=%s outcome=validation_fail",
                user_id_trunc, None, len(message)
            )
            return jsonify({
                'error': 'Mensagem muito longa (máximo 1000 caracteres)'
            }), 400

        conversation_id = data.get('conversation_id')

        logger.info(
            "chatbot_request_start user_id_trunc=%s conversation_id=%s message_len=%s",
            user_id_trunc, conversation_id, len(message)
        )

        # Validar ownership se conversation_id for fornecido
        if conversation_id:
            if not chatbot_repo.validate_ownership(conversation_id, user_id):
                logger.warning(
                    "chatbot_ownership_validation_failure user_id_trunc=%s conversation_id=%s",
                    user_id_trunc, conversation_id
                )
                return jsonify({
                    'error': 'Conversa não encontrada ou não autorizada'
                }), 403

        # Enviar mensagem para o OpenClaw
        result = openclaw_service.chat(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        outcome = "success" if result.get('success') else "bridge_error"

        logger.info(
            "chatbot_request_end user_id_trunc=%s conversation_id=%s message_len=%s elapsed_ms=%s outcome=%s",
            user_id_trunc, conversation_id, len(message), elapsed_ms, outcome
        )

        if result['success']:
            # Salvar/atualizar conversa no banco
            new_conversation_id = result.get('conversation_id')
            if new_conversation_id:
                try:
                    chatbot_repo.create_conversation(
                        user_id=user_id,
                        conversation_id=new_conversation_id,
                        metadata={'last_message': message[:100]}
                    )
                except Exception as e:
                    # Não falhar se houver erro ao salvar
                    logger.error("chatbot_conversation_save_failed conversation_id=%s error=%s", new_conversation_id, e)

            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.exception(
            "chatbot_unexpected_exception user_id_trunc=%s elapsed_ms=%s error=%s",
            user_id_trunc, elapsed_ms, e
        )
        return jsonify({
            'error': 'Erro ao processar mensagem',
            'message': 'Ocorreu um erro inesperado. Tente novamente.'
        }), 500


@bp.route('/conversations/<conversation_id>', methods=['GET'])
@token_required
def get_conversation(current_user, conversation_id):
    """
    Busca histórico de uma conversa

    ✅ SEGURANÇA: Validação de ownership implementada

    Returns:
        {
            "success": true,
            "history": [...]
        }
    """
    try:
        user_id = current_user['id']

        # Validar ownership
        if not chatbot_repo.validate_ownership(conversation_id, user_id):
            logger.warning(f"🚨 Unauthorized conversation access attempt - User: {user_id[:8]}... Conv: {conversation_id}")
            return jsonify({
                'error': 'Conversa não encontrada ou não autorizada'
            }), 403

        result = openclaw_service.get_conversation_history(conversation_id)

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404

    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        return jsonify({
            'error': 'Erro ao buscar conversa'
        }), 500


@bp.route('/conversations', methods=['GET'])
@token_required
def list_conversations(current_user):
    """
    Lista todas as conversas do usuário

    Returns:
        {
            "success": true,
            "conversations": [...]
        }
    """
    try:
        user_id = current_user['id']
        conversations = chatbot_repo.get_user_conversations(user_id)

        return jsonify({
            'success': True,
            'conversations': conversations
        }), 200

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return jsonify({
            'error': 'Erro ao listar conversas'
        }), 500


@bp.route('/conversations/<conversation_id>', methods=['DELETE'])
@token_required
def delete_conversation(current_user, conversation_id):
    """
    Deleta uma conversa

    Returns:
        {
            "success": true
        }
    """
    try:
        user_id = current_user['id']

        # Validar ownership está dentro do método delete_conversation
        success = chatbot_repo.delete_conversation(conversation_id, user_id)

        if success:
            return jsonify({'success': True}), 200
        else:
            return jsonify({
                'error': 'Conversa não encontrada ou não autorizada'
            }), 403

    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return jsonify({
            'error': 'Erro ao deletar conversa'
        }), 500


@bp.route('/health', methods=['GET'])
def health():
    """
    Verifica se o chatbot está disponível

    Returns:
        {
            "available": true
        }
    """
    is_available = openclaw_service.health_check()

    return jsonify({
        'available': is_available
    }), 200 if is_available else 503
