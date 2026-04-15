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

    def _membership_rows(self, user_id: str) -> List[Dict[str, Any]]:
        """Linhas em tenant_members (sem join). Evita falhas do embed PostgREST tenants!inner."""
        try:
            supabase = get_supabase()
            response = (
                supabase.table("tenant_members")
                .select("tenant_id, role")
                .eq("user_id", user_id)
                .execute()
            )
            return response.data or []
        except Exception as e:
            import logging

            logging.error(f"tenant_members list failed for user {user_id}: {e}")
            return []

    def get_user_tenants(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retorna lista de tenants do usuário com role.
        Usa tenant_members como fonte de verdade e carrega tenants separadamente,
        sem depender de embed implícito (ex.: tenants!inner) no caminho crítico de login.
        """
        import logging

        logger = logging.getLogger(__name__)
        rows = self._membership_rows(user_id)
        if not rows:
            return []

        supabase = get_supabase()
        tenant_ids = [str(row.get("tenant_id")) for row in rows if row.get("tenant_id")]
        tenant_map: Dict[str, Dict[str, Any]] = {}

        if tenant_ids:
            try:
                batch = (
                    supabase.table("tenants")
                    .select("id, name, slug")
                    .in_("id", tenant_ids)
                    .execute()
                )
                for t in (batch.data or []):
                    if t.get("id"):
                        tenant_map[str(t["id"])] = t
            except Exception as e:
                logger.warning(f"batch tenant fetch failed for user_id={user_id}: {e}")

        results: List[Dict[str, Any]] = []
        for row in rows:
            tid = row.get("tenant_id")
            if not tid:
                continue
            tid = str(tid)
            name: Optional[str] = None
            slug: Optional[str] = None
            tenant_data = tenant_map.get(tid)
            if tenant_data is None:
                try:
                    tres = (
                        supabase.table("tenants")
                        .select("id, name, slug")
                        .eq("id", tid)
                        .limit(1)
                        .execute()
                    )
                    if tres.data:
                        tenant_data = tres.data[0]
                except Exception as e:
                    logger.warning(f"tenant fetch failed for tenant_id={tid}: {e}")

            if tenant_data:
                name = tenant_data.get("name")
                slug = tenant_data.get("slug")

            results.append(
                {
                    "tenant_id": tid,
                    "role": row.get("role"),
                    "name": name,
                    "slug": slug,
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

        # tenant_members.user_id → FK public.users(id). Sem linha em users, só gera tenant órfão e 23503.
        try:
            urow = supabase.table("users").select("id").eq("id", user_id).limit(1).execute()
            if not urow.data:
                logger.error(
                    "ensure_default_tenant: public.users sem registro para user_id=%s; "
                    "rode POST /api/auth/bootstrap antes de criar workspace.",
                    user_id,
                )
                return None
        except Exception as ex:
            logger.warning("ensure_default_tenant: não foi possível verificar public.users para %s: %s", user_id, ex)
            return None

        slug = f"personal-{user_id}"
        name = "Meu espaço"

        def _tenant_id_for_slug() -> Optional[str]:
            try:
                r = supabase.table("tenants").select("id").eq("slug", slug).limit(1).execute()
                if r.data:
                    return str(r.data[0]["id"])
            except Exception as ex:
                logger.warning(f"ensure_default_tenant: lookup slug {slug}: {ex}")
            return None

        def _link_membership(tenant_id: str) -> bool:
            if self.user_is_member(user_id, tenant_id):
                return True
            try:
                supabase.table("tenant_members").insert(
                    {"tenant_id": tenant_id, "user_id": user_id, "role": "owner"}
                ).execute()
                return True
            except Exception as ex:
                logger.error(
                    f"ensure_default_tenant: membership insert failed user={user_id} tenant={tenant_id}: {ex}",
                    exc_info=True,
                )
                return False

        try:
            logger.info(f"ensure_default_tenant: Criando tenant para usuário {user_id} com slug {slug}")
            ins = (
                supabase.table("tenants")
                .insert({"name": name, "slug": slug})
                .execute()
            )
            tenant_id = None
            if ins.data and len(ins.data) > 0:
                tenant_id = str(ins.data[0]["id"])
            else:
                # Inserção pode ter falhado por slug duplicado (tenant órfão sem membership)
                tenant_id = _tenant_id_for_slug()

            if not tenant_id:
                logger.error(f"ensure_default_tenant: sem tenant_id após insert para user {user_id}")
                return None

            if not _link_membership(tenant_id):
                return None
            logger.info(f"ensure_default_tenant: OK user={user_id} tenant={tenant_id}")
            return tenant_id
        except Exception as e:
            err = str(e).lower()
            if "duplicate" in err or "unique" in err or "23505" in err:
                tenant_id = _tenant_id_for_slug()
                if tenant_id and _link_membership(tenant_id):
                    logger.info(f"ensure_default_tenant: recuperado por slug duplicado user={user_id} tenant={tenant_id}")
                    return tenant_id
            logger.error(f"ensure_default_tenant: Erro ao criar tenant para usuário {user_id}: {str(e)}", exc_info=True)
            return None
