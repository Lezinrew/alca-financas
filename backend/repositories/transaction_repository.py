from typing import List, Dict, Any, Optional
from datetime import datetime
from .base_repository import BaseRepository

class TransactionRepository(BaseRepository):
    def find_by_filter(self, user_id: str, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        query = {'user_id': user_id}
        
        if filters.get('month') and filters.get('year'):
            month = int(filters['month'])
            year = int(filters['year'])
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            query['date'] = {'$gte': start_date, '$lt': end_date}
            
        if filters.get('category_id'):
            query['category_id'] = filters['category_id']
            
        if filters.get('type'):
            query['type'] = filters['type']
            
        if filters.get('account_id'):
            query['account_id'] = filters['account_id']

        total = self.collection.count_documents(query)
        skip = (page - 1) * per_page
        
        cursor = self.collection.find(query).sort('date', -1).skip(skip).limit(per_page)
        
        return {
            'data': list(cursor),
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }

    def create_many(self, transactions: List[Dict[str, Any]]) -> List[str]:
        if not transactions:
            return []
        for tx in transactions:
            if 'created_at' not in tx:
                tx['created_at'] = datetime.utcnow()
        result = self.collection.insert_many(transactions)
        return [str(id) for id in result.inserted_ids]
