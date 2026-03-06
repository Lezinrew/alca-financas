"""
Rotas para o Chatbot OpenClaw
"""
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils_supabase import token_required
from services.openclaw_service import OpenClawService
from repositories.chatbot_repository import ChatbotRepository
from extensions import limiter
import logging

logger = logging.getLogger(__name__)

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
    try:
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({
                'error': 'Mensagem é obrigatória'
            }), 400

        message = data['message'].strip()
        if not message:
            return jsonify({
                'error': 'Mensagem não pode estar vazia'
            }), 400

        if len(message) > 1000:
            return jsonify({
                'error': 'Mensagem muito longa (máximo 1000 caracteres)'
            }), 400

        conversation_id = data.get('conversation_id')
        user_id = current_user['id']

        # Validar ownership se conversation_id for fornecido
        if conversation_id:
            if not chatbot_repo.validate_ownership(conversation_id, user_id):
                logger.warning(f"🚨 Unauthorized conversation access attempt - User: {user_id[:8]}... Conv: {conversation_id}")
                return jsonify({
                    'error': 'Conversa não encontrada ou não autorizada'
                }), 403

        # Enviar mensagem para o OpenClaw
        result = openclaw_service.chat(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id
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
                    logger.error(f"Error saving conversation: {e}")

            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error in chatbot endpoint: {e}")
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
