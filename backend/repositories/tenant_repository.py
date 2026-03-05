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

    def ensure_default_tenant(self, user_id: str) -> Optional[str]:
        """
        Garante que o usuário tenha pelo menos um tenant (workspace).
        Se não tiver membership, cria um tenant pessoal e adiciona o usuário como owner.
        Retorna o tenant_id (existente ou recém-criado) ou None em caso de erro.
        """
        import logging
        logger = logging.getLogger(__name__)

        tenants = self.get_user_tenants(user_id)
        if tenants:
            logger.info(f"ensure_default_tenant: Usuário {user_id} já tem tenant {tenants[0].get('tenant_id')}")
            return tenants[0].get("tenant_id")

        supabase = get_supabase()
        try:
            # Slug único (usa user_id para garantir unicidade)
            slug = f"personal-{user_id}"
            # Nome amigável
            name = "Meu espaço"

            logger.info(f"ensure_default_tenant: Criando tenant para usuário {user_id} com slug {slug}")

            # Cria o tenant
            ins = supabase.table("tenants").insert({"name": name, "slug": slug}).execute()
            if not ins.data or len(ins.data) == 0:
                logger.error(f"ensure_default_tenant: Falha ao criar tenant - resposta vazia para usuário {user_id}")
                return None

            tenant_id = ins.data[0]["id"]
            logger.info(f"ensure_default_tenant: Tenant {tenant_id} criado, adicionando membership para usuário {user_id}")

            # Adiciona o usuário como owner
            supabase.table("tenant_members").insert(
                {"tenant_id": tenant_id, "user_id": user_id, "role": "owner"}
            ).execute()

            logger.info(f"ensure_default_tenant: Membership criado com sucesso para usuário {user_id} no tenant {tenant_id}")
            return str(tenant_id)
        except Exception as e:
            logger.error(f"ensure_default_tenant: Erro ao criar tenant para usuário {user_id}: {str(e)}", exc_info=True)
            return None

