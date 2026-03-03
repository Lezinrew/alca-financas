"""
Account Repository para Supabase
"""
from typing import List, Dict, Any, Optional
from .base_repository_supabase import BaseRepository


class AccountRepository(BaseRepository):
    def __init__(self):
        super().__init__("accounts")
    
    def find_by_user(self, user_id: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Busca contas por usuário (e opcionalmente por tenant)."""
        query: Dict[str, Any] = {"user_id": user_id}
        if tenant_id:
            query["tenant_id"] = tenant_id
        return self.find_all(query)
    
    def find_by_name(
        self,
        user_id: str,
        name: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Busca conta por nome (scoped por usuário e opcionalmente tenant)."""
        query: Dict[str, Any] = {"user_id": user_id, "name": name}
        if tenant_id:
            query["tenant_id"] = tenant_id
        return self.find_one(query)

