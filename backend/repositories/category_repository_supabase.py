"""
Category Repository para Supabase
"""
from typing import List, Dict, Any, Optional
from .base_repository_supabase import BaseRepository


class CategoryRepository(BaseRepository):
    def __init__(self):
        super().__init__("categories")
    
    def find_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Busca categorias por usuário"""
        return self.find_all({'user_id': user_id})
    
    def find_by_type(self, user_id: str, type: str) -> List[Dict[str, Any]]:
        """Busca categorias por tipo (income/expense)"""
        return self.find_all({'user_id': user_id, 'type': type})
    
    def find_by_name_and_type(
        self, 
        user_id: str, 
        name: str, 
        type: str
    ) -> Optional[Dict[str, Any]]:
        """Busca categoria por nome e tipo"""
        return self.find_one({'user_id': user_id, 'name': name, 'type': type})
    
    def find_by_name(self, user_id: str, name: str, type: str) -> Optional[Dict[str, Any]]:
        """Alias para find_by_name_and_type"""
        return self.find_by_name_and_type(user_id, name, type)

