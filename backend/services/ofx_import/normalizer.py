"""
Normalizador de lote para inserções no Supabase / PostgREST.

Garante que todos os dicionários de um lote compartilhem exatamente
o mesmo conjunto canônico de chaves (preenchendo com None para campos ausentes),
eliminando definitivamente o erro `PGRST102: All object keys must match`.
"""
from typing import List, Dict, Any, Set, Optional


CANONICAL_TRANSACTION_KEYS = [
    'id',
    'user_id',
    'tenant_id',
    'account_id',
    'account_tenant_id',
    'category_id',
    'category_tenant_id',
    'description',
    'amount',
    'type',
    'date',
    'is_recurring',
    'status',
    'responsible_person',
    'installment_info',
    'entry_source',
    'source_file',
    'fitid',
    'dedup_key',
    'import_batch_id',
    'legacy_id',
    'created_at',
    'updated_at'
]


def normalize_batch_objects(
    objects: List[Dict[str, Any]],
    extra_keys: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Normaliza uma lista de dicionários para garantir chaves idênticas em todos os itens.
    """
    if not objects:
        return []

    # Coleta todas as chaves presentes em qualquer objeto do lote
    all_keys: Set[str] = set(CANONICAL_TRANSACTION_KEYS)
    if extra_keys:
        all_keys.update(extra_keys)
        
    for obj in objects:
        all_keys.update(obj.keys())

    sorted_keys = sorted(all_keys)
    
    normalized_list = []
    for obj in objects:
        norm_obj = {}
        for k in sorted_keys:
            norm_obj[k] = obj.get(k, None)
        normalized_list.append(norm_obj)

    return normalized_list
