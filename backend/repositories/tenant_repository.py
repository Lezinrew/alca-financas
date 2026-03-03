"""
Tenant Repository para Supabase
"""
from typing import List, Dict, Any, Optional

from .base_repository_supabase import BaseRepository
from database.connection import get_supabase


class TenantRepository(BaseRepository):
    def __init__(self):
        # Usa tenant_members como tabela principal para membership
        super().__init__("tenant_members")

    def get_user_tenants(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retorna lista de tenants do usuário com role.
        """
        supabase = get_supabase()
        # Usa join implícito: tenant_members + tenants
        response = (
            supabase.table("tenant_members")
            .select("tenant_id, role, tenants!inner(id, name, slug)")
            .eq("user_id", user_id)
            .execute()
        )
        data = response.data or []
        results: List[Dict[str, Any]] = []
        for row in data:
            tenant = row.get("tenants") or {}
            results.append(
                {
                    "tenant_id": row.get("tenant_id") or tenant.get("id"),
                    "role": row.get("role"),
                    "name": tenant.get("name"),
                    "slug": tenant.get("slug"),
                }
            )
        return results

    def get_default_tenant_id(self, user_id: str) -> Optional[str]:
        """
        Retorna o tenant_id padrão do usuário (primeiro membership encontrado).
        """
        tenants = self.get_user_tenants(user_id)
        if not tenants:
            return None
        # Por enquanto, usa o primeiro da lista (earliest membership na prática)
        return tenants[0].get("tenant_id")

    def user_is_member(self, user_id: str, tenant_id: str) -> bool:
        """
        Verifica se user_id é membro de tenant_id.
        """
        result = self.find_one({"user_id": user_id, "tenant_id": tenant_id})
        return result is not None

