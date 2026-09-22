#!/usr/bin/env python3
"""
Corrige descrições gravadas com acentuação duplicada ("dÃ©bito" -> "débito").

Padrão: SIMULAÇÃO. Nada é gravado sem --apply.

Tabelas:
- transactions.description (e dedup_key, recalculada com a descrição corrigida)
- financial_expenses.title / description

Regras de segurança:
- Só altera texto em que o reparo reduz os marcadores de mojibake (texto correto fica igual).
- A dedup_key só é trocada quando a chave gravada é exatamente a calculada com o texto antigo;
  caso contrário mantém a chave e reporta.
- Se a nova dedup_key já pertence a outra transação (possível duplicata), a linha é pulada e reportada.
- Não apaga nem cria registros; não altera valores, datas, contas ou categorias.

Uso:
    python scripts/repair_mojibake_descriptions.py            # simulação
    python scripts/repair_mojibake_descriptions.py --apply    # grava
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.import_service import compute_dedup_key  # noqa: E402
from utils.text_repair import looks_like_mojibake, repair_mojibake  # noqa: E402

PAGE = 500


def fetch_all(query):
    rows, seen, start = [], set(), 0
    while True:
        page = query.range(start, start + PAGE - 1).execute().data or []
        new = [r for r in page if r.get("id") not in seen]
        if not new:
            return rows
        rows.extend(new)
        seen.update(r["id"] for r in new)
        start += len(page)


def plan_transactions(sb):
    rows = fetch_all(sb.table("transactions").select("id,tenant_id,description,dedup_key,date,amount,account_id,type").order("id"))
    keys = {}
    for r in rows:
        if r.get("dedup_key"):
            keys.setdefault((r.get("tenant_id"), r["dedup_key"]), r["id"])
    plan, skipped = [], []
    for r in rows:
        old = r.get("description")
        if not looks_like_mojibake(old):
            continue
        new = repair_mojibake(old)
        if new == old:
            skipped.append({"id": r["id"], "motivo": "reparo inconclusivo", "texto": old})
            continue
        change = {"description": new}
        stored = r.get("dedup_key")
        if stored and r.get("account_id") and r.get("date") is not None:
            old_key = compute_dedup_key(r["date"], r.get("amount") or 0, old, r["account_id"], r.get("type"))
            if stored == old_key:
                new_key = compute_dedup_key(r["date"], r.get("amount") or 0, new, r["account_id"], r.get("type"))
                owner = keys.get((r.get("tenant_id"), new_key))
                if owner and owner != r["id"]:
                    skipped.append({"id": r["id"], "motivo": f"chave nova já usada pela transação {owner} (possível duplicata)", "texto": new})
                    continue
                change["dedup_key"] = new_key
            else:
                skipped.append({"id": r["id"], "motivo": "dedup_key não confere com o texto antigo; chave mantida", "texto": new, "aplicar_texto": True})
        plan.append({"id": r["id"], "de": old, "para": new, "update": change})
    # Linhas com chave divergente ainda recebem o texto corrigido, sem mexer na chave.
    for s in skipped:
        if s.pop("aplicar_texto", False):
            plan.append({"id": s["id"], "de": None, "para": s["texto"], "update": {"description": s["texto"]}})
    return plan, skipped, len(rows)


def plan_expenses(sb):
    rows = fetch_all(sb.table("financial_expenses").select("id,title,description").order("id"))
    plan = []
    for r in rows:
        change = {}
        for field in ("title", "description"):
            value = r.get(field)
            if looks_like_mojibake(value):
                fixed = repair_mojibake(value)
                if fixed != value:
                    change[field] = fixed
        if change:
            plan.append({"id": r["id"], "update": change})
    return plan, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="grava as correções (padrão: simulação)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY ausentes")
    sb = create_client(url, key)

    tx_plan, tx_skipped, tx_total = plan_transactions(sb)
    fe_plan, fe_total = plan_expenses(sb)

    report = {
        "modo": "APLICAR" if args.apply else "SIMULAÇÃO",
        "transacoes_lidas": tx_total,
        "transacoes_a_corrigir": len(tx_plan),
        "transacoes_com_chave_recalculada": sum(1 for p in tx_plan if "dedup_key" in p["update"]),
        "transacoes_puladas": tx_skipped,
        "contas_a_pagar_lidas": fe_total,
        "contas_a_pagar_a_corrigir": len(fe_plan),
        "exemplos": [{"de": p["de"], "para": p["para"]} for p in tx_plan[:8] if p["de"]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not args.apply:
        print("\nSimulação concluída. Nada foi gravado. Rode com --apply para gravar.")
        return

    failures = 0
    for table, plan in (("transactions", tx_plan), ("financial_expenses", fe_plan)):
        for p in plan:
            res = sb.table(table).update(p["update"]).eq("id", p["id"]).execute()
            if not res.data:
                failures += 1
                print(f"FALHA ao atualizar {table} {p['id']}")
    print(f"\nConcluído. Atualizações: {len(tx_plan) + len(fe_plan) - failures}. Falhas: {failures}.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
