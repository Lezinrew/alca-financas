"""
Repositório de despesas / contas a pagar (financial_expenses) — Supabase.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from database.connection import get_supabase
from .base_repository_supabase import BaseRepository


class FinancialExpenseRepository(BaseRepository):
    def __init__(self):
        super().__init__("financial_expenses")

    def find_by_id_for_tenant(
        self, expense_id: str, user_id: str, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            res = (
                get_supabase()
                .table(self.table_name)
                .select("*")
                .eq("id", expense_id)
                .eq("user_id", user_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
            return None
        except Exception:
            return None

    def list_for_tenant(
        self,
        user_id: str,
        tenant_id: str,
        filters: Dict[str, Any],
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        """
        Lista despesas com filtros e paginação.
        Filtros suportados: month, year, status, category, responsible, is_recurring,
        overdue_only (bool), outstanding_only (bool).
        """
        try:
            supabase = get_supabase()
            query = supabase.table(self.table_name).select("*", count="exact")
            query = query.eq("user_id", user_id).eq("tenant_id", tenant_id)

            if filters.get("month") and filters.get("year"):
                query = query.eq("competency_month", int(filters["month"])).eq(
                    "competency_year", int(filters["year"])
                )
            elif filters.get("year"):
                query = query.eq("competency_year", int(filters["year"]))

            if filters.get("status"):
                query = query.eq("status", filters["status"])

            if filters.get("category"):
                query = query.eq("category", filters["category"])

            if filters.get("responsible"):
                query = query.ilike(
                    "responsible_person", f"%{filters['responsible'].strip()}%"
                )

            if filters.get("is_recurring") is not None:
                ir = filters["is_recurring"]
                if isinstance(ir, str):
                    ir = ir.lower() in ("1", "true", "yes")
                query = query.eq("is_recurring", bool(ir))

            today_iso = date.today().isoformat()
            if filters.get("overdue_only"):
                query = query.in_("status", ["pending", "partial"]).lt(
                    "due_date", today_iso
                )

            if filters.get("outstanding_only"):
                query = query.in_("status", ["pending", "partial"])

            if filters.get("outstanding_only"):
                query = query.order("due_date", desc=False)
            else:
                query = query.order("created_at", desc=True)

            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            response = query.execute()
            total = response.count if hasattr(response, "count") else len(response.data or [])
            rows: List[Dict[str, Any]] = response.data or []

            return {
                "data": rows,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page if total > 0 else 0,
                },
            }
        except Exception as e:
            import logging

            logging.error("Erro ao listar financial_expenses: %s", e)
            return {
                "data": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "per_page": per_page,
                    "pages": 0,
                },
            }

    def create_row(self, data: Dict[str, Any]) -> str:
        return self.create(data)

    def update_row(self, expense_id: str, data: Dict[str, Any]) -> bool:
        return self.update(expense_id, data)

    def delete_row(self, expense_id: str) -> bool:
        return self.delete(expense_id)

    def find_existing_source_transaction_ids(
        self, user_id: str, tenant_id: str, transaction_ids: List[str]
    ) -> List[str]:
        """IDs de transação que já têm conta a pagar ligada (idempotência)."""
        if not transaction_ids:
            return []
        try:
            res = (
                get_supabase()
                .table(self.table_name)
                .select("source_transaction_id")
                .eq("user_id", user_id)
                .eq("tenant_id", tenant_id)
                .in_("source_transaction_id", transaction_ids)
                .execute()
            )
            out: List[str] = []
            for row in res.data or []:
                sid = row.get("source_transaction_id")
                if sid:
                    out.append(str(sid))
            return out
        except Exception:
            return []
