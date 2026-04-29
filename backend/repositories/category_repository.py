from typing import List, Dict, Any, Optional
from .base_repository import BaseRepository
from database import get_db
from utils.category_name import normalize_category_key

class CategoryRepository(BaseRepository):
    def __init__(self):
        db = get_db()
        super().__init__(db.categories)

    def find_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        return self.find_all({'user_id': user_id})

    def find_by_type(self, user_id: str, type: str) -> List[Dict[str, Any]]:
        return self.find_all({'user_id': user_id, 'type': type})
    
    def find_by_name_and_type(self, user_id: str, name: str, type: str) -> Optional[Dict[str, Any]]:
        return self.collection.find_one({'user_id': user_id, 'name': name, 'type': type})

    def find_by_name(self, user_id: str, name: str, type: str) -> Optional[Dict[str, Any]]:
        return self.find_by_name_and_type(user_id, name, type)

    def find_by_user_including_legacy_null_tenant(
        self, user_id: str, tenant_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        if not tenant_id:
            return self.find_by_user(user_id)
        return list(
            self.collection.find(
                {
                    "user_id": user_id,
                    "$or": [
                        {"tenant_id": tenant_id},
                        {"tenant_id": None},
                        {"tenant_id": {"$exists": False}},
                    ],
                }
            )
        )

    def find_equivalent_category(
        self,
        user_id: str,
        name: str,
        category_type: str,
        tenant_id: Optional[str],
        exclude_category_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        target = normalize_category_key(name)
        if not target:
            return None
        q: Dict[str, Any] = {"user_id": user_id, "type": category_type}
        if tenant_id:
            q["$or"] = [
                {"tenant_id": tenant_id},
                {"tenant_id": None},
                {"tenant_id": {"$exists": False}},
            ]
        matches: List[Dict[str, Any]] = []
        for doc in self.collection.find(q):
            rid = doc.get("_id") or doc.get("id")
            if exclude_category_id and str(rid) == str(exclude_category_id):
                continue
            if normalize_category_key(doc.get("name") or "") == target:
                matches.append(doc)
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
