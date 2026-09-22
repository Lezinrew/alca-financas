"""
Serviço: contas a pagar (financial_expenses).
Status persistidos: pending | partial | paid | canceled.
`overdue` é apenas derivado na API (is_overdue / display_status).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from utils.exceptions import AppException, NotFoundException, ValidationException
from utils.financial_expense_category_map import map_category_name_to_payable
from services.transaction_service import _category_for

ALLOWED_CATEGORIES = frozenset(
    {
        "moradia",
        "educação",
        "saúde",
        "transporte",
        "veículos",
        "cartões",
        "dívidas",
        "família",
        "serviços",
        "utilidades",
        "impostos",
        "alimentação",
        "pessoal",
        "outros",
    }
)

STORED_STATUSES = frozenset({"pending", "partial", "paid", "canceled"})


def _to_decimal(value: Any, field: str) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationException(f"Valor inválido em {field}")


def _derive_status(amount_expected: Decimal, amount_paid: Decimal, explicit: str) -> str:
    if explicit == "canceled":
        return "canceled"
    if amount_paid <= 0:
        return "pending"
    if amount_paid < amount_expected:
        return "partial"
    return "paid"


def _today_iso() -> str:
    return date.today().isoformat()


def enrich_expense(row: Dict[str, Any]) -> Dict[str, Any]:
    """Acrescenta is_overdue e display_status (não persistidos)."""
    base_status = row.get("status") or "pending"
    due = row.get("due_date")
    open_status = base_status in ("pending", "partial")
    is_overdue = False
    if open_status and due:
        try:
            is_overdue = str(due) < _today_iso()
        except Exception:
            is_overdue = False
    display = "overdue" if is_overdue else base_status
    out = dict(row)
    out["is_overdue"] = is_overdue
    out["display_status"] = display
    return out


class FinancialExpenseService:
    def __init__(self, repo, transaction_repo=None, categories_repo=None):
        self.repo = repo
        self.transaction_repo = transaction_repo
        self.categories_repo = categories_repo

    def list_expenses(
        self,
        user_id: str,
        tenant_id: str,
        query: Dict[str, Any],
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        filters = self._list_filters(query)
        result = self.repo.list_for_tenant(
            user_id, tenant_id, filters, page=page, per_page=per_page
        )
        data = [enrich_expense(r) for r in result.get("data") or []]
        return {"data": data, "pagination": result.get("pagination") or {}}

    @staticmethod
    def _period_value(value: Any, field: str, minimum: int, maximum: int) -> int:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            raise ValidationException(f"{field} inválido")
        if not minimum <= parsed <= maximum:
            raise ValidationException(f"{field} deve estar entre {minimum} e {maximum}")
        return parsed

    def _list_filters(self, query: Dict[str, Any]) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if query.get("month") not in (None, ""):
            filters["month"] = self._period_value(query["month"], "month", 1, 12)
            if not query.get("year"):
                raise ValidationException("year é obrigatório quando month é informado")
        if query.get("year") not in (None, ""):
            filters["year"] = self._period_value(query["year"], "year", 2000, 2100)
        if query.get("status"):
            st = str(query["status"]).strip().lower()
            if st == "overdue":
                filters["overdue_only"] = True
            elif st in STORED_STATUSES:
                filters["status"] = st
            else:
                raise ValidationException(
                    "status inválido; use pending, partial, paid, canceled ou overdue"
                )
        if query.get("category"):
            filters["category"] = str(query["category"]).strip()
        if query.get("responsible"):
            filters["responsible"] = str(query["responsible"]).strip()
        if query.get("is_recurring") is not None and str(query.get("is_recurring")).strip() != "":
            v = str(query["is_recurring"]).strip().lower()
            filters["is_recurring"] = v in ("1", "true", "yes")
        if query.get("outstanding_only") in (True, "true", "1", "yes"):
            filters["outstanding_only"] = True

        return filters

    def get_overview(
        self, user_id: str, tenant_id: str, query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate the complete filtered population, independently of table pagination."""
        filters = self._list_filters(query)
        today = _today_iso()
        reference_month = self._period_value(
            query.get("reference_month") or filters.get("month") or today[5:7],
            "reference_month", 1, 12,
        )
        reference_year = self._period_value(
            query.get("reference_year") or filters.get("year") or today[:4],
            "reference_year", 2000, 2100,
        )
        reference = f"{reference_year:04d}-{reference_month:02d}"
        # Freeze the date used by overdue filtering across every page.
        filters["as_of"] = today
        filters["stable_order"] = True
        counts = {status: 0 for status in ("pending", "partial", "paid", "canceled", "overdue")}
        groups = {
            key: {"count": 0, "remaining": Decimal("0")}
            for key in ("before", "month", "after", "undated")
        }
        competency_groups = {
            key: {"count": 0, "remaining": Decimal("0")}
            for key in ("before", "month", "after", "undated")
        }
        expected = paid = remaining = Decimal("0")
        seen = set()
        total = None
        page = 1
        page_size = 200
        while True:
            result = self.repo.list_for_tenant(
                user_id, tenant_id, filters, page=page, per_page=page_size
            )
            rows = result.get("data") or []
            reported_total = result.get("pagination", {}).get("total")
            if not isinstance(reported_total, int) or reported_total < 0:
                raise AppException("Não foi possível confirmar o resumo completo", status_code=503)
            if total is None:
                total = reported_total
            if reported_total != total:
                raise AppException("As contas mudaram durante a consulta. Atualize o resumo", status_code=503)
            for row in rows:
                row_id = row.get("id")
                if not row_id or row_id in seen:
                    raise AppException("Não foi possível confirmar o resumo completo", status_code=503)
                seen.add(row_id)
                status = row.get("status") or "pending"
                if status not in STORED_STATUSES:
                    raise AppException("Conta com situação inválida no resumo", status_code=503)
                counts[status] += 1
                if status == "canceled":
                    continue
                row_expected = _to_decimal(row.get("amount_expected"), "amount_expected")
                row_paid = _to_decimal(row.get("amount_paid"), "amount_paid")
                if not row_expected.is_finite() or not row_paid.is_finite():
                    raise AppException("Conta com valor inválido no resumo", status_code=503)
                expected += row_expected
                paid += row_paid
                if status in ("pending", "partial"):
                    row_remaining = max(Decimal("0"), row_expected - row_paid)
                    remaining += row_remaining
                    due = row.get("due_date")
                    if due and str(due) < today:
                        counts["overdue"] += 1
                    due_month = str(due)[:7] if due else None
                    group = ("undated" if not due_month else
                             "before" if due_month < reference else
                             "after" if due_month > reference else "month")
                    groups[group]["count"] += 1
                    groups[group]["remaining"] += row_remaining
                    cm, cy = row.get("competency_month"), row.get("competency_year")
                    competency = f"{int(cy):04d}-{int(cm):02d}" if cm and cy else None
                    competency_group = ("undated" if not competency else
                                        "before" if competency < reference else
                                        "after" if competency > reference else "month")
                    competency_groups[competency_group]["count"] += 1
                    competency_groups[competency_group]["remaining"] += row_remaining
            if len(seen) > total or (len(seen) < total and len(rows) != page_size):
                raise AppException("Não foi possível confirmar o resumo completo", status_code=503)
            if len(seen) == total:
                break
            page += 1
        return {
            "expected": float(expected), "paid": float(paid), "remaining": float(remaining),
            "total": total, "counts": counts,
            "due_groups": {
                key: {"count": group["count"], "remaining": float(group["remaining"])}
                for key, group in groups.items()
            },
            "competency_groups": {
                key: {"count": group["count"], "remaining": float(group["remaining"])}
                for key, group in competency_groups.items()
            },
            "complete": True, "as_of": today,
        }

    def get_summary(
        self,
        user_id: str,
        tenant_id: str,
        month: int,
        year: int,
    ) -> Dict[str, Any]:
        """
        Retorna resumo consolidado de contas a pagar para um mês/ano específico.

        OTIMIZAÇÃO: Faz 1 query única ao invés de 5 queries separadas.
        Retorna contadores (paid, open, overdue, canceled) e somas agregadas.
        """
        month = self._period_value(month, "month", 1, 12)
        year = self._period_value(year, "year", 2000, 2100)
        # Busca todas as despesas do mês/ano (limite alto para pegar tudo)
        filters = {"month": str(month), "year": str(year)}
        result = self.repo.list_for_tenant(
            user_id, tenant_id, filters, page=1, per_page=1000
        )
        rows = [enrich_expense(r) for r in result.get("data") or []]
        total_count = result.get("pagination", {}).get("total", len(rows))

        # Agregar contadores e somas em memória
        paid_count = 0
        open_count = 0
        overdue_count = 0
        canceled_count = 0
        paid_sum = Decimal("0")
        open_remaining_sum = Decimal("0")

        for r in rows:
            status = r.get("status", "pending")
            is_overdue = r.get("is_overdue", False)

            if status == "paid":
                paid_count += 1
                paid_sum += _to_decimal(r.get("amount_expected"), "amount_expected")
            elif status == "canceled":
                canceled_count += 1
            else:
                # pending ou partial
                if is_overdue:
                    overdue_count += 1
                else:
                    open_count += 1

                expected = _to_decimal(r.get("amount_expected"), "amount_expected")
                paid = _to_decimal(r.get("amount_paid"), "amount_paid")
                remaining = max(Decimal("0"), expected - paid)
                open_remaining_sum += remaining

        month_label = datetime(year, month, 1).strftime("%B/%Y")

        return {
            "month": month,
            "year": year,
            "month_label": month_label,
            "paid_count": paid_count,
            "open_count": open_count,
            "overdue_count": overdue_count,
            "canceled_count": canceled_count,
            "paid_sum_expected": float(paid_sum),
            "open_remaining_sum": float(open_remaining_sum),
            "total_in_month": total_count,
            "sample_size": len(rows),
            "sums_partial": len(rows) < total_count,
        }

    def get_expense(self, user_id: str, tenant_id: str, expense_id: str) -> Dict[str, Any]:
        row = self.repo.find_by_id_for_tenant(expense_id, user_id, tenant_id)
        if not row:
            raise NotFoundException("Despesa não encontrada")
        return enrich_expense(row)

    def _validate_category(self, category: str) -> str:
        c = (category or "").strip()
        if c not in ALLOWED_CATEGORIES:
            raise ValidationException("Categoria inválida")
        return c

    def _normalize_write_payload(
        self, data: Dict[str, Any], *, partial: bool = False
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if not partial or "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                raise ValidationException("title é obrigatório")
            out["title"] = title
        elif partial:
            pass

        if not partial or "category" in data:
            out["category"] = self._validate_category(data.get("category", ""))

        for key in (
            "description",
            "subcategory",
            "recurrence_type",
            "payment_method",
            "source_type",
            "responsible_person",
            "vehicle_name",
            "notes",
        ):
            if not partial or key in data:
                v = data.get(key)
                out[key] = (str(v).strip() if v is not None and v != "" else None)

        if not partial or "amount_expected" in data:
            out["amount_expected"] = str(
                _to_decimal(data.get("amount_expected", 0), "amount_expected")
            )
        if not partial or "amount_paid" in data:
            out["amount_paid"] = str(_to_decimal(data.get("amount_paid", 0), "amount_paid"))

        if not partial or "due_date" in data:
            out["due_date"] = data.get("due_date") or None
        if not partial or "paid_at" in data:
            pat = data.get("paid_at")
            out["paid_at"] = pat if pat else None

        if not partial or "competency_month" in data:
            cm = data.get("competency_month")
            out["competency_month"] = int(cm) if cm is not None and str(cm).strip() != "" else None
        if not partial or "competency_year" in data:
            cy = data.get("competency_year")
            out["competency_year"] = int(cy) if cy is not None and str(cy).strip() != "" else None

        if not partial or "is_recurring" in data:
            out["is_recurring"] = bool(data.get("is_recurring", False))

        for key in ("installment_current", "installment_total"):
            if not partial or key in data:
                v = data.get(key)
                out[key] = int(v) if v is not None and str(v).strip() != "" else None

        explicit_status = None
        if not partial or "status" in data:
            st = (data.get("status") or "pending").strip().lower()
            if st not in STORED_STATUSES:
                raise ValidationException("status inválido")
            explicit_status = st
            out["status"] = st

        exp = _to_decimal(out.get("amount_expected", 0), "amount_expected")
        paid = _to_decimal(out.get("amount_paid", 0), "amount_paid")
        if exp < 0 or paid < 0:
            raise ValidationException("Valores não podem ser negativos")

        if explicit_status != "canceled":
            out["status"] = _derive_status(exp, paid, explicit_status or "pending")

        return out

    def create_expense(self, user_id: str, tenant_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data or {})
        # Origem transação só via create_payables_from_transactions (evita forjar vínculo).
        data.pop("source_transaction_id", None)
        payload = self._normalize_write_payload(data, partial=False)
        payload["user_id"] = user_id
        payload["tenant_id"] = tenant_id
        new_id = self.repo.create_row(payload)
        row = self.repo.find_by_id_for_tenant(new_id, user_id, tenant_id)
        if not row:
            raise ValidationException("Erro ao criar despesa")
        return enrich_expense(row)

    def update_expense(
        self, user_id: str, tenant_id: str, expense_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        existing = self.repo.find_by_id_for_tenant(expense_id, user_id, tenant_id)
        if not existing:
            raise NotFoundException("Despesa não encontrada")
        data = dict(data or {})
        data.pop("source_transaction_id", None)
        merged = {**existing, **data}
        payload = self._normalize_write_payload(merged, partial=False)
        payload.pop("user_id", None)
        payload.pop("tenant_id", None)
        payload.pop("id", None)
        payload.pop("created_at", None)
        if not self.repo.update_row(expense_id, payload):
            raise AppException("Não foi possível atualizar a conta", status_code=503)
        row = self.repo.find_by_id_for_tenant(expense_id, user_id, tenant_id)
        return enrich_expense(row or existing)

    def delete_expense(self, user_id: str, tenant_id: str, expense_id: str) -> None:
        existing = self.repo.find_by_id_for_tenant(expense_id, user_id, tenant_id)
        if not existing:
            raise NotFoundException("Despesa não encontrada")
        if not self.repo.delete_row(expense_id):
            raise AppException("Não foi possível excluir a conta", status_code=503)

    def mark_paid(
        self,
        user_id: str,
        tenant_id: str,
        expense_id: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = body or {}
        existing = self.repo.find_by_id_for_tenant(expense_id, user_id, tenant_id)
        if not existing:
            raise NotFoundException("Despesa não encontrada")
        if existing.get("status") == "canceled":
            raise ValidationException("Despesa cancelada não pode ser paga")

        amount_expected = _to_decimal(existing.get("amount_expected"), "amount_expected")
        if body.get("amount_paid") is not None and str(body.get("amount_paid")).strip() != "":
            new_paid = _to_decimal(body.get("amount_paid"), "amount_paid")
        else:
            new_paid = amount_expected

        if new_paid < 0:
            raise ValidationException("amount_paid inválido")
        if new_paid > amount_expected:
            new_paid = amount_expected

        paid_at = body.get("paid_at")
        if paid_at:
            paid_at_val = paid_at
        else:
            paid_at_val = datetime.now(timezone.utc).isoformat()

        new_status = _derive_status(amount_expected, new_paid, "pending")
        update_payload = {
            "amount_paid": str(new_paid),
            "paid_at": paid_at_val,
            "status": new_status,
        }
        if not self.repo.update_row(expense_id, update_payload):
            raise AppException("Não foi possível registrar o pagamento", status_code=503)
        row = self.repo.find_by_id_for_tenant(expense_id, user_id, tenant_id)
        return enrich_expense(row or existing)

    def create_payables_from_transactions(
        self,
        user_id: str,
        tenant_id: str,
        transaction_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Cria contas a pagar a partir de transações de despesa do mesmo utilizador/tenant.
        Idempotente: ignora transações que já tenham financial_expense com o mesmo source_transaction_id.
        """
        if not self.transaction_repo:
            raise ValidationException("Repositório de transações indisponível")
        raw_ids = [str(x).strip() for x in (transaction_ids or []) if str(x).strip()]
        if not raw_ids:
            raise ValidationException("Informe transaction_ids (lista de UUIDs)")

        claimed = set(
            self.repo.find_existing_source_transaction_ids(user_id, tenant_id, raw_ids)
        )
        created: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        errors: List[Dict[str, str]] = []

        for tid in raw_ids:
            if tid in claimed:
                skipped.append({"id": tid, "reason": "already_linked"})
                continue
            tx = self.transaction_repo.find_by_id(tid)
            if (
                not tx
                or str(tx.get("user_id")) != str(user_id)
                or str(tx.get("tenant_id") or "") != str(tenant_id)
            ):
                errors.append({"id": tid, "error": "transação não encontrada"})
                continue
            if tx.get("type") != "expense":
                skipped.append({"id": tid, "reason": "not_expense"})
                continue

            cat_name = None
            cid = tx.get("category_id")
            if cid and self.categories_repo:
                c = _category_for(self.categories_repo, cid)
                if c:
                    cat_name = c.get("name")
            payable_cat = map_category_name_to_payable(cat_name)

            try:
                amt = abs(float(tx.get("amount") or 0))
            except (TypeError, ValueError):
                amt = 0.0
            if amt <= 0:
                errors.append({"id": tid, "error": "valor inválido"})
                continue

            date_val = tx.get("date")
            if hasattr(date_val, "strftime"):
                date_val = date_val.strftime("%Y-%m-%d")
            date_str = str(date_val) if date_val else None

            title = (tx.get("description") or "Despesa").strip() or "Despesa"
            if len(title) > 500:
                title = title[:500]

            payload_in: Dict[str, Any] = {
                "title": title,
                "category": payable_cat,
                "amount_expected": amt,
                "amount_paid": 0,
                "due_date": date_str,
                "is_recurring": bool(tx.get("is_recurring")),
                "responsible_person": tx.get("responsible_person"),
                "source_type": "transaction",
                "status": "pending",
            }
            if date_str and len(date_str) >= 7:
                try:
                    y, m, *_ = date_str.split("-")
                    payload_in["competency_year"] = int(y)
                    payload_in["competency_month"] = int(m)
                except (ValueError, TypeError):
                    pass

            normalized = self._normalize_write_payload(payload_in, partial=False)
            normalized["user_id"] = user_id
            normalized["tenant_id"] = tenant_id
            normalized["source_transaction_id"] = tid

            new_id = self.repo.create_row(normalized)
            claimed.add(tid)
            row = self.repo.find_by_id_for_tenant(new_id, user_id, tenant_id)
            if row:
                created.append(enrich_expense(row))

        return {"created": created, "skipped": skipped, "errors": errors}
