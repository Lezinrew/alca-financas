"""
Serviço para resolução de aliases de comerciante/descrição -> categoria.
"""
from typing import Optional, Tuple


class MerchantAliasService:
    def __init__(self, alias_repo):
        self.alias_repo = alias_repo

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").strip().lower()

    def find_category_for_description(
        self,
        user_id: Optional[str],
        tenant_id: Optional[str],
        description: str,
        category_type: str,
    ) -> Optional[Tuple[str, str]]:
        """
        Retorna (category_name, category_type) para uma descrição, se houver alias.
        """
        if not self.alias_repo:
            return None

        alias = self.alias_repo.find_best_alias(user_id, tenant_id, description, category_type)
        if not alias:
            return None

        name = alias.get("category_name")
        ctype = alias.get("category_type") or category_type
        if not name:
            return None
        return name, ctype

