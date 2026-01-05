"""
User Repository para Supabase
"""
from typing import Optional, Dict, Any
from .base_repository_supabase import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")
    
    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Busca usuário por email"""
        return self.find_one({'email': email})
    
    def update_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Atualiza configurações do usuário"""
        return self.update(user_id, {'settings': settings})

