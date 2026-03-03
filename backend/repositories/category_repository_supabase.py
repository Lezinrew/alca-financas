"""
Category Repository para Supabase
"""
from typing import List, Dict, Any, Optional
from .base_repository_supabase import BaseRepository


class CategoryRepository(BaseRepository):
    def __init__(self):
        super().__init__("categories")
    
    def find_by_user(self, user_id: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Busca categorias por usuário (e opcionalmente por tenant)."""
        query: Dict[str, Any] = {"user_id": user_id}
        if tenant_id:
            query["tenant_id"] = tenant_id
        return self.find_all(query)
    
    def find_by_type(self, user_id: str, type: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Busca categorias por tipo (income/expense), opcionalmente scoped por tenant."""
        query: Dict[str, Any] = {"user_id": user_id, "type": type}
        if tenant_id:
            query["tenant_id"] = tenant_id
        return self.find_all(query)
    
    def find_by_name_and_type(
        self, 
        user_id: str, 
        name: str, 
        type: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Busca categoria por nome e tipo"""
        query: Dict[str, Any] = {"user_id": user_id, "name": name, "type": type}
        if tenant_id:
            query["tenant_id"] = tenant_id
        return self.find_one(query)
    
    def find_by_name(self, user_id: str, name: str, type: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Alias para find_by_name_and_type"""
        return self.find_by_name_and_type(user_id, name, type, tenant_id)

