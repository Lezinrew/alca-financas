"""
Repositório para budget_monthly e budget_plans (módulo Planejamento).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_repository_supabase import BaseRepository
from database.connection import get_supabase


class BudgetRepositorySupabase:
    def __init__(self):
        self.supabase = get_supabase()
        self.monthly_table = "budget_monthly"
        self.plans_table = "budget_plans"

    def get_monthly(self, tenant_id: str, month: int, year: int) -> Optional[Dict[str, Any]]:
        try:
            r = (
                self.supabase.table(self.monthly_table)
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("month", month)
                .eq("year", year)
                .limit(1)
                .execute()
            )
            if r.data and len(r.data) > 0:
                return r.data[0]
            return None
        except Exception:
            return None

    def upsert_monthly(
        self,
        tenant_id: str,
        month: int,
        year: int,
        planned_income: float,
        savings_percentage: float,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        existing = self.get_monthly(tenant_id, month, year)
        if existing:
            r = (
                self.supabase.table(self.monthly_table)
                .update({
                    "planned_income": planned_income,
                    "savings_percentage": savings_percentage,
                    "updated_at": now,
                })
                .eq("id", existing["id"])
                .execute()
            )
            if r.data and len(r.data) > 0:
                return r.data[0]
        row = {
            "tenant_id": tenant_id,
            "month": month,
            "year": year,
            "planned_income": planned_income,
            "savings_percentage": savings_percentage,
            "created_at": now,
            "updated_at": now,
        }
        r = self.supabase.table(self.monthly_table).insert(row).execute()
        if r.data and len(r.data) > 0:
            return r.data[0]
        return row

    def get_plans_for_month(
        self,
        tenant_id: str,
        user_id: str,
        month: int,
        year: int,
    ) -> List[Dict[str, Any]]:
        try:
            r = (
                self.supabase.table(self.plans_table)
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .eq("month", month)
                .eq("year", year)
                .execute()
            )
            return r.data if r.data else []
        except Exception:
            return []

    def upsert_plans(
        self,
        tenant_id: str,
        user_id: str,
        month: int,
        year: int,
        category_plans: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not category_plans:
            return []
        self.delete_plans_for_month(tenant_id, user_id, month, year)
        now = datetime.utcnow().isoformat()
        rows = []
        for item in category_plans:
            category_id = item.get("category_id")
            planned_amount = float(item.get("planned_amount", 0))
            notes = item.get("notes")
            if not category_id:
                continue
            row = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "month": month,
                "year": year,
                "category_id": category_id,
                "planned_amount": planned_amount,
                "created_at": now,
                "updated_at": now,
            }
            if notes is not None:
                row["notes"] = notes
            rows.append(row)
        if not rows:
            return []
        r = self.supabase.table(self.plans_table).insert(rows).execute()
        return r.data if r.data else []

    def delete_plans_for_month(
        self,
        tenant_id: str,
        user_id: str,
        month: int,
        year: int,
    ) -> bool:
        try:
            (
                self.supabase.table(self.plans_table)
                .delete()
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .eq("month", month)
                .eq("year", year)
                .execute()
            )
            return True
        except Exception:
            return False

    def delete_plan_by_id(
        self,
        plan_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        try:
            (
                self.supabase.table(self.plans_table)
                .delete()
                .eq("id", plan_id)
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception:
            return False
