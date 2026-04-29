"""
Normalização de nomes de categoria para busca/ deduplicação (import OFX, get_or_create).
"""
import re
from typing import Any, Dict, List, Tuple

# (chave normalizada, tipo, tenant ativo da requisição) -> category_id
ImportCategoryCacheKey = Tuple[str, str, str]


def collapse_whitespace_display(name: str) -> str:
    """Nome para persistência: trim + espaços internos colapsados."""
    if not name:
        return ""
    s = name.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_category_key(name: str) -> str:
    """Chave de comparação: case-insensitive após collapse de espaços."""
    return collapse_whitespace_display(name).lower()


def import_category_cache_key(name: str, category_type: str, active_tenant_id: str) -> ImportCategoryCacheKey:
    return (normalize_category_key(name), category_type, active_tenant_id or "")


def build_import_category_cache(
    categories: List[Dict[str, Any]],
    active_tenant_id: str,
) -> Dict[ImportCategoryCacheKey, str]:
    """
    Mapa para importação: reutiliza ID canónico por (nome normalizado, tipo, tenant da sessão).
    Categorias do tenant actual têm prioridade sobre legado com tenant_id NULL.
    """
    cache: Dict[ImportCategoryCacheKey, str] = {}
    legacy_entries: List[Tuple[ImportCategoryCacheKey, str]] = []
    tid = active_tenant_id or ""

    for cat in categories:
        raw_name = cat.get("name") or ""
        ctype = cat.get("type") or ""
        cid = cat.get("id") or cat.get("_id")
        if not cid:
            continue
        key = import_category_cache_key(raw_name, ctype, tid)
        ctenant = cat.get("tenant_id")

        if ctenant == active_tenant_id and active_tenant_id:
            cache[key] = str(cid)
        elif ctenant in (None, ""):
            legacy_entries.append((key, str(cid)))

    for key, cid in legacy_entries:
        cache.setdefault(key, cid)

    return cache
