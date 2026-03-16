"""
Repositório para merchant_category_aliases (mapeia descrição/comerciante -> categoria).
"""
from typing import Dict, Any, Optional, List

from .base_repository_supabase import BaseRepository


class MerchantAliasRepositorySupabase(BaseRepository):
    def __init__(self):
        super().__init__("merchant_category_aliases")

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").strip().lower()

    def find_all_active(self, category_type: str) -> List[Dict[str, Any]]:
        return self.find_all(
            {
                "category_type": category_type,
                "active": True,
            }
        )

    def find_best_alias(
        self,
        user_id: Optional[str],
        tenant_id: Optional[str],
        description: str,
        category_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retorna o melhor alias para uma descrição, considerando escopo:
        1) user+tenant, 2) tenant, 3) global.
        """
        desc_norm = self._normalize(description)
        if not desc_norm:
            return None

        aliases = self.find_all_active(category_type)
        best_score = -1
        best_alias: Optional[Dict[str, Any]] = None

        for alias in aliases:
            alias_norm = alias.get("normalized_value") or ""
            match_type = alias.get("match_type") or "contains"

            scope_score = 0
            if user_id and alias.get("user_id") == user_id:
                scope_score = 20
            elif tenant_id and alias.get("tenant_id") == tenant_id:
                scope_score = 10

            match_score = -1
            if match_type == "exact" and desc_norm == alias_norm:
                match_score = 3
            elif match_type == "prefix" and desc_norm.startswith(alias_norm):
                match_score = 2
            elif match_type == "contains" and alias_norm in desc_norm:
                match_score = 1

            if match_score < 0:
                continue

            total = scope_score + match_score
            if total > best_score:
                best_score = total
                best_alias = alias

        return best_alias

