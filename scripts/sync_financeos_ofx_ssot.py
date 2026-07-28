#!/usr/bin/env python3
"""Sincroniza o SSOT OFX do FinanceOS com o modelo multi-tenant do Alça."""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.import_service import compute_dedup_key


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).upper().split())


def tx_signature(row, tx_type):
    return (
        str(row.get("data") or row.get("date") or "")[:10],
        round(float(row.get("valor") or row.get("amount") or 0), 2),
        normalize(row.get("descricao") or row.get("description")),
        tx_type,
    )


def latest_card_balance(financeos_root: Path):
    candidates = []
    for path in (financeos_root / "data" / "input").rglob("*.ofx"):
        content = path.read_text(encoding="latin-1", errors="ignore")
        if "<CCACCTFROM>" not in content.upper():
            continue
        end = re.search(r"<DTEND>(\d{8})", content, re.I)
        balance = re.search(r"<BALAMT>([-\d.]+)", content, re.I)
        if end and balance:
            candidates.append((end.group(1), float(balance.group(1))))
    return max(candidates)[1] if candidates else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--financeos-root",
        default=r"C:\Users\lezin\OneDrive\Documentos\FinanceOS",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY ausentes")
    sb = create_client(url, key)

    source = (
        sb.table("transacoes")
        .select("*")
        .ilike("arquivo_origem", "%.ofx")
        .execute()
        .data
        or []
    )
    operational = [row for row in source if normalize(row.get("tipo")) in {"RECEITA", "DESPESA"}]
    transfers = len(source) - len(operational)

    accounts = sb.table("accounts").select("*").execute().data or []
    tenant_ids = {row.get("tenant_id") for row in accounts if row.get("tenant_id")}
    user_ids = {row.get("user_id") for row in accounts if row.get("user_id")}
    if len(tenant_ids) != 1 or len(user_ids) != 1:
        raise SystemExit("Sincronização exige exatamente um tenant e um usuário nas contas")
    tenant_id, user_id = next(iter(tenant_ids)), next(iter(user_ids))

    checking = next((a for a in accounts if a.get("type") != "credit_card"), None)
    card = next((a for a in accounts if a.get("type") == "credit_card"), None)
    if not checking or not card:
        raise SystemExit("Contas corrente e cartão são obrigatórias")

    categories = (
        sb.table("categories")
        .select("id,name,type")
        .eq("tenant_id", tenant_id)
        .execute()
        .data
        or []
    )
    category_map = {(normalize(c["name"]), c["type"]): c["id"] for c in categories}

    existing = (
        sb.table("transactions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .execute()
        .data
        or []
    )
    by_signature = defaultdict(list)
    by_dedup = {}
    for row in existing:
        by_signature[tx_signature(row, row.get("type"))].append(row)
        if row.get("dedup_key"):
            current = by_dedup.get(row["dedup_key"])
            if current is None or str(current.get("source_file") or "").startswith("legacy:"):
                by_dedup[row["dedup_key"]] = row

    updates, inserts, new_categories = [], [], {}
    for row in operational:
        tx_type = "income" if normalize(row["tipo"]) == "RECEITA" else "expense"
        account = card if "CART" in normalize(row.get("conta")) else checking
        category_name = str(row.get("categoria") or "Outros").strip()
        cat_key = (normalize(category_name), tx_type)
        if cat_key not in category_map:
            new_categories[cat_key] = category_name

        dedup = compute_dedup_key(
            row["data"], row["valor"], row["descricao"], account["id"], tx_type
        )
        candidates = sorted(
            by_signature.get(tx_signature(row, tx_type), []),
            key=lambda candidate: str(candidate.get("source_file") or "").startswith("legacy:"),
        )
        match = by_dedup.get(dedup) or (candidates[0] if len(candidates) == 1 else None)
        canonical = {
            "source_file": row["arquivo_origem"],
            "entry_source": "ofx",
            "status": "paid",
            "responsible_person": row.get("responsavel"),
            "account_id": account["id"],
            "account_tenant_id": tenant_id,
            "dedup_key": dedup,
        }
        if match:
            updates.append((match["id"], canonical, cat_key))
        else:
            inserts.append(
                {
                    **canonical,
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "category_tenant_id": tenant_id,
                    "description": row["descricao"],
                    "amount": abs(float(row["valor"])),
                    "type": tx_type,
                    "date": row["data"],
                    "is_recurring": False,
                    "_category_key": cat_key,
                }
            )

    print(
        {
            "ofx": len(source),
            "operacionais": len(operational),
            "transferencias_excluidas_fluxo": transfers,
            "atualizacoes": len(updates),
            "insercoes": len(inserts),
            "categorias_novas": len(new_categories),
            "ofx_legados_a_desconsiderar": max(
                0,
                sum(
                    str(row.get("source_file") or "").lower().endswith(".ofx")
                    for row in existing
                )
                - len(updates),
            ),
            "modo": "APPLY" if args.apply else "DRY_RUN",
        }
    )
    if not args.apply:
        return

    for cat_key, name in new_categories.items():
        created = (
            sb.table("categories")
            .insert(
                {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "name": name,
                    "type": cat_key[1],
                    "color": "#6C757D",
                    "icon": "circle",
                }
            )
            .execute()
            .data[0]
        )
        category_map[cat_key] = created["id"]

    for tx_id, payload, cat_key in updates:
        payload["category_id"] = category_map[cat_key]
        payload["category_tenant_id"] = tenant_id
        sb.table("transactions").update(payload).eq("id", tx_id).execute()
    for row in inserts:
        cat_key = row.pop("_category_key")
        row["category_id"] = category_map[cat_key]
        sb.table("transactions").insert(row).execute()

    canonical_ids = {tx_id for tx_id, _, _ in updates}
    active_ofx = [
        row
        for row in existing
        if str(row.get("source_file") or "").lower().endswith(".ofx")
    ]
    for row in active_ofx:
        if row["id"] not in canonical_ids:
            original = str(row.get("source_file") or "sem-origem")
            sb.table("transactions").update(
                {"source_file": f"legacy:{original}:excluded"}
            ).eq("id", row["id"]).execute()

    financeos_root = Path(args.financeos_root)
    balance_rows = (
        sb.table("patrimonio")
        .select("valor_atual")
        .eq("item", "Saldo disponível Nubank")
        .limit(1)
        .execute()
        .data
        or []
    )
    if balance_rows:
        sb.table("accounts").update(
            {
                "balance": balance_rows[0]["valor_atual"],
                "current_balance": balance_rows[0]["valor_atual"],
            }
        ).eq("id", checking["id"]).execute()
    card_balance = latest_card_balance(financeos_root)
    if card_balance is not None:
        sb.table("accounts").update(
            {"balance": card_balance, "current_balance": card_balance}
        ).eq(
            "id", card["id"]
        ).execute()

    print("Sincronização canônica concluída.")


if __name__ == "__main__":
    main()
