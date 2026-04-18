"""
Limpeza completa dos dados de negócio de um utilizador (mantém public.users e auth).

Regras:
- Transações antes de contas/categorias (FK composto RESTRICT em transactions).
- Metas: apagar goals por user_id (goal_contributions em CASCADE).
- budget_plans: por user_id.
- budget_monthly: só em tenants onde o utilizador é o único membro (evita apagar planeamento partilhado).
- merchant_category_aliases: por user_id; + por tenant_id nos mesmos tenants “só membros”.
- Tabelas opcionais (ex.: transaction_tenant_inconsistencies): ignoradas se não existirem.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from database.connection import get_supabase
from repositories.base_repository_supabase import BaseRepository
from repositories.tenant_repository import TenantRepository

logger = logging.getLogger(__name__)


def _sole_tenant_ids(user_id: str) -> List[str]:
    """Tenants em que este utilizador é o único membro (para budget_monthly / aliases por tenant)."""
    tr = TenantRepository()
    tenants = tr.get_user_tenants(user_id)
    tenant_ids = [str(t["tenant_id"]) for t in tenants if t.get("tenant_id")]
    if not tenant_ids:
        return []
    supabase = get_supabase()
    r = supabase.table("tenant_members").select("tenant_id").in_("tenant_id", tenant_ids).execute()
    cnt = Counter(str(row["tenant_id"]) for row in (r.data or []))
    return [tid for tid in tenant_ids if cnt.get(tid, 0) == 1]


def _try_delete_many(table: str, filters: Dict[str, Any]) -> int:
    try:
        return BaseRepository(table).delete_many(filters)
    except Exception as e:
        logger.warning("wipe: ignorar tabela %s com filtro %s: %s", table, filters, e)
        return 0


def wipe_user_business_data(user_id: str, config: Dict[str, Any]) -> Dict[str, int]:
    """
    Apaga dados de negócio do utilizador. `config` deve ser flask current_app.config
    (CATEGORY_REPO, TRANSACTION_REPO, etc.).
    """
    counts: Dict[str, int] = {}
    sole_tenants = _sole_tenant_ids(user_id)

    # Opcional / legado
    counts["transaction_tenant_inconsistencies"] = _try_delete_many(
        "transaction_tenant_inconsistencies", {"user_id": user_id}
    )

    tx_repo = config["TRANSACTIONS"]
    counts["transactions"] = tx_repo.delete_many({"user_id": user_id})

    fe_repo = config.get("FINANCIAL_EXPENSE_REPO")
    if fe_repo is not None:
        counts["financial_expenses"] = fe_repo.delete_many({"user_id": user_id})
    else:
        counts["financial_expenses"] = _try_delete_many("financial_expenses", {"user_id": user_id})

    counts["goals"] = _try_delete_many("goals", {"user_id": user_id})

    counts["budget_plans"] = _try_delete_many("budget_plans", {"user_id": user_id})

    bm_deleted = 0
    for tid in sole_tenants:
        bm_deleted += _try_delete_many("budget_monthly", {"tenant_id": tid})
    counts["budget_monthly"] = bm_deleted

    counts["merchant_category_aliases_user"] = _try_delete_many(
        "merchant_category_aliases", {"user_id": user_id}
    )
    ma_tenant = 0
    for tid in sole_tenants:
        ma_tenant += _try_delete_many("merchant_category_aliases", {"tenant_id": tid})
    counts["merchant_category_aliases_tenant"] = ma_tenant

    counts["chatbot_conversations"] = _try_delete_many("chatbot_conversations", {"user_id": user_id})

    counts["admin_notification_delivery"] = _try_delete_many(
        "admin_notification_delivery", {"subject_user_id": user_id}
    )
    counts["admin_audit_logs_target"] = _try_delete_many(
        "admin_audit_logs", {"target_user_id": user_id}
    )
    counts["admin_audit_logs_actor"] = _try_delete_many(
        "admin_audit_logs", {"actor_user_id": user_id}
    )

    acc_repo = config["ACCOUNTS"]
    counts["accounts"] = acc_repo.delete_many({"user_id": user_id})

    cat_repo = config["CATEGORIES"]
    counts["categories"] = cat_repo.delete_many({"user_id": user_id})

    return counts
