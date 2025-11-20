from typing import List, Dict, Any, Optional
from .base_repository import BaseRepository

class AccountRepository(BaseRepository):
    def find_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        return self.find_all({'user_id': user_id})
    
    def find_by_name(self, user_id: str, name: str) -> Optional[Dict[str, Any]]:
        return self.collection.find_one({'user_id': user_id, 'name': name})
