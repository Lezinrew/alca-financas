"""
User Repository para MongoDB
"""
from typing import Optional, Dict, Any
from .base_repository import BaseRepository
from database import get_db


class UserRepository(BaseRepository):
    def __init__(self):
        db = get_db()
        super().__init__(db.users)
    
    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Busca usuário por email"""
        return self.collection.find_one({'email': email})
    
    def update_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Atualiza configurações do usuário"""
        return self.update(user_id, {'settings': settings})
