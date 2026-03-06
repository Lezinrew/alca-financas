"""
Repository para gerenciar conversas do chatbot
"""
from typing import Optional, Dict, Any
from database import get_db
import logging

logger = logging.getLogger(__name__)


class ChatbotRepository:
    """Repository para operações de conversas do chatbot"""

    def __init__(self):
        self.db = get_db()
        self.table = 'chatbot_conversations'

    def create_conversation(self, user_id: str, conversation_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Cria um novo registro de conversa

        Args:
            user_id: ID do usuário
            conversation_id: ID da conversa do OpenClaw
            metadata: Metadados opcionais

        Returns:
            Dict com os dados da conversa criada
        """
        try:
            data = {
                'user_id': user_id,
                'conversation_id': conversation_id,
                'metadata': metadata or {}
            }

            result = self.db.table(self.table).insert(data).execute()

            if result.data:
                logger.info(f"Conversation created: {conversation_id} for user {user_id[:8]}...")
                return result.data[0]
            else:
                raise Exception("Failed to create conversation")

        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            # Se já existe, apenas retornar
            if "duplicate key" in str(e).lower():
                return self.get_by_conversation_id(conversation_id)
            raise

    def get_by_conversation_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca conversa por conversation_id

        Args:
            conversation_id: ID da conversa

        Returns:
            Dict com dados da conversa ou None
        """
        try:
            result = self.db.table(self.table)\
                .select('*')\
                .eq('conversation_id', conversation_id)\
                .execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Error fetching conversation: {e}")
            return None

    def validate_ownership(self, conversation_id: str, user_id: str) -> bool:
        """
        Valida se a conversa pertence ao usuário

        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário

        Returns:
            True se a conversa pertence ao usuário, False caso contrário
        """
        try:
            result = self.db.table(self.table)\
                .select('user_id')\
                .eq('conversation_id', conversation_id)\
                .execute()

            if not result.data:
                return False

            return result.data[0]['user_id'] == user_id

        except Exception as e:
            logger.error(f"Error validating conversation ownership: {e}")
            return False

    def get_user_conversations(self, user_id: str, active_only: bool = True, limit: int = 50) -> list:
        """
        Busca todas as conversas de um usuário

        Args:
            user_id: ID do usuário
            active_only: Se True, retorna apenas conversas ativas
            limit: Número máximo de conversas a retornar

        Returns:
            Lista de conversas
        """
        try:
            query = self.db.table(self.table)\
                .select('*')\
                .eq('user_id', user_id)

            if active_only:
                query = query.eq('is_active', True)

            result = query.order('updated_at', desc=True)\
                .limit(limit)\
                .execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Error fetching user conversations: {e}")
            return []

    def update_metadata(self, conversation_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Atualiza metadados de uma conversa

        Args:
            conversation_id: ID da conversa
            metadata: Novos metadados

        Returns:
            True se atualizado com sucesso
        """
        try:
            result = self.db.table(self.table)\
                .update({'metadata': metadata})\
                .eq('conversation_id', conversation_id)\
                .execute()

            return bool(result.data)

        except Exception as e:
            logger.error(f"Error updating conversation metadata: {e}")
            return False

    def archive_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        Arquiva uma conversa (soft delete)

        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário (validação de ownership)

        Returns:
            True se arquivado com sucesso
        """
        # Validar ownership primeiro
        if not self.validate_ownership(conversation_id, user_id):
            logger.warning(f"Attempted to archive conversation {conversation_id} by unauthorized user {user_id[:8]}...")
            return False

        try:
            result = self.db.table(self.table)\
                .update({'is_active': False})\
                .eq('conversation_id', conversation_id)\
                .execute()

            return bool(result.data)

        except Exception as e:
            logger.error(f"Error archiving conversation: {e}")
            return False

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        Deleta permanentemente uma conversa

        Args:
            conversation_id: ID da conversa
            user_id: ID do usuário (validação de ownership)

        Returns:
            True se deletado com sucesso
        """
        # Validar ownership primeiro
        if not self.validate_ownership(conversation_id, user_id):
            logger.warning(f"Attempted to delete conversation {conversation_id} by unauthorized user {user_id[:8]}...")
            return False

        try:
            result = self.db.table(self.table)\
                .delete()\
                .eq('conversation_id', conversation_id)\
                .execute()

            return True

        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return False
