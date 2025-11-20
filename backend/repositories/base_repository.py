from typing import Optional, List, Dict, Any
from pymongo.collection import Collection
from bson import ObjectId
from datetime import datetime

class BaseRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def find_all(self, filter_query: Dict[str, Any] = None, sort_by: str = None, ascending: bool = True) -> List[Dict[str, Any]]:
        query = filter_query or {}
        cursor = self.collection.find(query)
        if sort_by:
            direction = 1 if ascending else -1
            cursor = cursor.sort(sort_by, direction)
        return list(cursor)

    def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        try:
            # Tenta buscar por string direta ou ObjectId se for válido
            return self.collection.find_one({'_id': id})
        except:
            return None

    def create(self, data: Dict[str, Any]) -> str:
        if 'created_at' not in data:
            data['created_at'] = datetime.utcnow()
        result = self.collection.insert_one(data)
        return str(result.inserted_id)

    def update(self, id: str, data: Dict[str, Any]) -> bool:
        if 'updated_at' not in data:
            data['updated_at'] = datetime.utcnow()
        result = self.collection.update_one({'_id': id}, {'$set': data})
        return result.modified_count > 0

    def delete(self, id: str) -> bool:
        result = self.collection.delete_one({'_id': id})
        return result.deleted_count > 0
