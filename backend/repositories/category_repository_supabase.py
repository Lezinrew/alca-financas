"""
Category Repository para Supabase
"""
import logging
from typing import List, Dict, Any, Optional

from utils.category_name import normalize_category_key

from .base_repository_supabase import BaseRepository

logger = logging.getLogger(__name__)


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

    def _find_same_user_type_tenant_or_legacy(
        self, user_id: str, category_type: str, tenant_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Categorias do mesmo utilizador e tipo no tenant actual ou com tenant_id NULL (legado)."""
        try:
            q = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("user_id", user_id)
                .eq("type", category_type)
            )
            if tenant_id:
                q = q.or_(f"tenant_id.eq.{tenant_id},tenant_id.is.null")
            else:
                q = q.is_("tenant_id", "null")
            response = q.execute()
            return response.data or []
        except Exception as e:
            logger.error(
                "Erro ao listar categorias tenant/legado em %s: %s",
                self.table_name,
                e,
                exc_info=True,
            )
            return []

    def find_equivalent_category(
        self,
        user_id: str,
        name: str,
        category_type: str,
        tenant_id: Optional[str],
        exclude_category_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Encontra categoria equivalente (nome normalizado + tipo), preferindo tenant actual
        sobre legado com tenant_id NULL.
        """
        target = normalize_category_key(name)
        if not target:
            return None

        candidates = self._find_same_user_type_tenant_or_legacy(user_id, category_type, tenant_id)
        matches: List[Dict[str, Any]] = []
        for row in candidates:
            rid = row.get("id") or row.get("_id")
            if exclude_category_id and str(rid) == str(exclude_category_id):
                continue
            if normalize_category_key(row.get("name") or "") == target:
                matches.append(row)

        if not matches:
            return None

        if tenant_id:
            for row in matches:
                if row.get("tenant_id") == tenant_id:
                    return row
            for row in matches:
                if row.get("tenant_id") in (None, ""):
                    return row
            return matches[0]

        for row in matches:
            if row.get("tenant_id") in (None, ""):
                return row
        return matches[0]

    def find_by_user_including_legacy_null_tenant(
        self, user_id: str, tenant_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Lista categorias do tenant e legadas (tenant_id NULL) para cache de importação."""
        if not tenant_id:
            return self.find_by_user(user_id, tenant_id=None)
        try:
            response = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("user_id", user_id)
                .or_(f"tenant_id.eq.{tenant_id},tenant_id.is.null")
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(
                "Erro em find_by_user_including_legacy_null_tenant %s: %s",
                self.table_name,
                e,
                exc_info=True,
            )
            return self.find_by_user(user_id, tenant_id=tenant_id)

