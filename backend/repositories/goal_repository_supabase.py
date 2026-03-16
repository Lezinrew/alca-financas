"""
Repositório para goals e goal_contributions (módulo Metas).
Isolamento por tenant_id e user_id.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from database.connection import get_supabase


class GoalRepositorySupabase:
    def __init__(self):
        self.supabase = get_supabase()
        self.goals_table = "goals"
        self.contributions_table = "goal_contributions"

    def list_goals(
        self,
        tenant_id: str,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            q = (
                self.supabase.table(self.goals_table)
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .order("target_date", desc=False)
                .order("created_at", desc=True)
            )
            if status:
                q = q.eq("status", status)
            r = q.execute()
            return r.data if r.data else []
        except Exception:
            return []

    def get_goal_by_id(
        self,
        goal_id: str,
        tenant_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            r = (
                self.supabase.table(self.goals_table)
                .select("*")
                .eq("id", goal_id)
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if r.data and len(r.data) > 0:
                return r.data[0]
            return None
        except Exception:
            return None

    def create_goal(
        self,
        tenant_id: str,
        user_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        row = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "title": data.get("title", ""),
            "description": data.get("description") or None,
            "target_amount": float(data.get("target_amount", 0)),
            "current_amount": float(data.get("current_amount", 0)),
            "target_date": data.get("target_date"),
            "image_url": data.get("image_url"),
            "status": (data.get("status") or "active").lower(),
            "created_at": now,
            "updated_at": now,
        }
        r = self.supabase.table(self.goals_table).insert(row).execute()
        if r.data and len(r.data) > 0:
            return r.data[0]
        return row

    def update_goal(
        self,
        goal_id: str,
        tenant_id: str,
        user_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        existing = self.get_goal_by_id(goal_id, tenant_id, user_id)
        if not existing:
            return None
        allowed = {
            "title", "description", "target_amount", "current_amount",
            "target_date", "image_url", "status",
        }
        payload = {k: v for k, v in data.items() if k in allowed and v is not None}
        if not payload:
            return existing
        r = (
            self.supabase.table(self.goals_table)
            .update(payload)
            .eq("id", goal_id)
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .execute()
        )
        if r.data and len(r.data) > 0:
            return r.data[0]
        return existing

    def delete_goal(
        self,
        goal_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        try:
            (
                self.supabase.table(self.goals_table)
                .delete()
                .eq("id", goal_id)
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception:
            return False

    def list_contributions(
        self,
        goal_id: str,
        tenant_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        try:
            r = (
                self.supabase.table(self.contributions_table)
                .select("*")
                .eq("goal_id", goal_id)
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .order("date", desc=True)
                .execute()
            )
            return r.data if r.data else []
        except Exception:
            return []

    def add_contribution(
        self,
        goal_id: str,
        tenant_id: str,
        user_id: str,
        amount: float,
        date: Optional[str] = None,
        source_type: Optional[str] = None,
        source_reference_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        goal = self.get_goal_by_id(goal_id, tenant_id, user_id)
        if not goal:
            return None
        now = datetime.utcnow().isoformat()
        row = {
            "goal_id": goal_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "amount": amount,
            "date": date or now,
            "created_at": now,
        }
        if source_type is not None:
            row["source_type"] = source_type
        if source_reference_id is not None:
            row["source_reference_id"] = source_reference_id
        if notes is not None:
            row["notes"] = notes
        r = self.supabase.table(self.contributions_table).insert(row).execute()
        if r.data and len(r.data) > 0:
            new_current = float(goal.get("current_amount", 0)) + amount
            self.update_goal(goal_id, tenant_id, user_id, {"current_amount": new_current})
            return r.data[0]
        return None
