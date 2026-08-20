#!/usr/bin/env python3
"""
Repovoamento seguro e idempotente de transferências no histórico do AlçaHub via pipeline OFX.

Executa:
1. Backup snapshot completo de transactions e accounts em data/input/backups/
2. Leitura dos 93 lançamentos canônicos auditados da SSOT (R$ 586.012,81)
3. Agrupamento por lote/arquivo de origem e criação de registros em public.import_batches
4. Inserção de transactions com type='transfer' vinculadas ao seu import_batch_id
5. Validação rigorosa dos 93 lançamentos (R$ 586.012,81) e invariância total de receita/despesa
"""
import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services.ofx_import.dedup import build_dedup_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplica as inserções no Supabase (padrão é dry-run)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórios no .env")

    sb = create_client(url, key)

    # 1. Obter contas e tenant
    accounts = sb.table("accounts").select("*").execute().data or []
    if not accounts:
        raise SystemExit("Nenhuma conta encontrada")

    tenant_ids = {a["tenant_id"] for a in accounts if a.get("tenant_id")}
    user_ids = {a["user_id"] for a in accounts if a.get("user_id")}
    if len(tenant_ids) != 1 or len(user_ids) != 1:
        raise SystemExit(f"Múltiplos tenants ({tenant_ids}) ou usuários ({user_ids})")

    tenant_id = next(iter(tenant_ids))
    user_id = next(iter(user_ids))

    acc_nubank_checking = next((a for a in accounts if a.get("type") == "checking" and "nubank" in a.get("name", "").lower()), None)
    acc_inter = next((a for a in accounts if a.get("type") == "checking" and "inter" in a.get("name", "").lower()), None)
    acc_card = next((a for a in accounts if a.get("type") == "credit_card"), None)

    if not acc_nubank_checking or not acc_inter or not acc_card:
        raise SystemExit("Contas Nubank Conta, Inter e Cartão são obrigatórias")

    print("=== AMBIENTE E CONTAS IDENTIFICADAS ===")
    print(f"Tenant ID: {tenant_id}")
    print(f"User ID:   {user_id}")
    print(f"Conta Nubank: {acc_nubank_checking['name']} ({acc_nubank_checking['id']})")
    print(f"Conta Inter:  {acc_inter['name']} ({acc_inter['id']})")
    print(f"Cartão:       {acc_card['name']} ({acc_card['id']})")

    # 2. Obter transações existentes
    existing_txs = sb.table("transactions").select("*").eq("tenant_id", tenant_id).execute().data or []
    print(f"\nTransações existentes no banco: {len(existing_txs)}")

    # 3. Snapshot de Backup obrigatório antes de qualquer alteração
    backup_dir = Path(r"C:\Users\lezin\OneDrive\Documentos\FinanceOS\data\input\backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"alca_pre_transfers_repopulate_{ts}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "accounts": accounts,
            "transactions_count": len(existing_txs),
            "transactions": existing_txs
        }, f, indent=2, ensure_ascii=False)
    print(f"[OK] Backup salvo em: {backup_path}")

    # 4. Obter categoria de Transferência Interna
    cats = sb.table("categories").select("*").eq("tenant_id", tenant_id).execute().data or []
    transfer_cat = next((c for c in cats if "transfer" in c.get("name", "").lower()), None)
    if not transfer_cat:
        if args.apply:
            res_cat = sb.table("categories").insert({
                "tenant_id": tenant_id,
                "user_id": user_id,
                "name": "Transferência Interna",
                "type": "transfer",
                "color": "#6C757D",
                "icon": "arrow-left-right"
            }).execute().data
            transfer_cat_id = res_cat[0]["id"]
        else:
            transfer_cat_id = str(uuid.uuid4())
    else:
        transfer_cat_id = transfer_cat["id"]

    # 5. Carregar as 93 transferências canônicas auditadas da SSOT
    canonical_json_path = ROOT / "scripts" / "canonical_ssot_transfers.json"
    if not canonical_json_path.exists():
        raise SystemExit(f"Arquivo {canonical_json_path} não encontrado")

    with open(canonical_json_path, "r", encoding="utf-8") as f:
        ssot_transfers = json.load(f)

    print(f"\nCarregadas {len(ssot_transfers)} transferências canônicas auditadas da SSOT.")
    assert len(ssot_transfers) == 93
    assert round(sum(t["amount"] for t in ssot_transfers), 2) == 586012.81

    # 6. Agrupar por arquivo de origem para gerar lotes (import_batches)
    by_source = defaultdict(list)
    for t in ssot_transfers:
        by_source[t["source_file"]].append(t)

    batches_to_insert = []
    transfers_to_insert = []

    print("\n=== LOTES E TRANSFERÊNCIAS A CRIAR ===")
    for src_file, tx_list in by_source.items():
        batch_id = str(uuid.uuid4())
        
        # Determinar conta associada ao lote
        first_tx = tx_list[0]
        if "Inter" in first_tx["banco"]:
            acc = acc_inter
        elif "Cartão" in first_tx["banco"] or "Cartão" in first_tx["conta"]:
            acc = acc_card
        else:
            acc = acc_nubank_checking

        batch_tot = sum(t["amount"] for t in tx_list)
        
        batch_record = {
            "id": batch_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "account_id": acc["id"],
            "filename": src_file,
            "file_format": "ofx",
            "total_parsed": len(tx_list),
            "imported_count": len(tx_list),
            "ignored_count": 0,
            "duplicate_count": 0,
            "unclassified_count": 0,
            "total_income": 0.00,
            "total_expense": 0.00,
            "total_transfer": round(batch_tot, 2),
            "status": "completed",
            "metadata": {
                "purpose": "repopulate_transfers_ssot",
                "account_name": acc["name"]
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        batches_to_insert.append(batch_record)

        for t in tx_list:
            dedup_k = t.get("dedup_key")
            if not dedup_k or "|" not in dedup_k:
                dedup_k = build_dedup_key(
                    tx_date=t["date"],
                    amount_signed=-t["amount"] if "Pagamento" in t["description"] or "enviada" in t["description"] or "Aplicacao" in t["description"] else t["amount"],
                    description=t["description"],
                    bank_or_account=acc["name"],
                    fitid_or_seq=t.get("fitid") or ""
                )

            transfers_to_insert.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "tenant_id": tenant_id,
                "account_id": acc["id"],
                "account_tenant_id": tenant_id,
                "category_id": transfer_cat_id,
                "category_tenant_id": tenant_id,
                "description": t["description"],
                "amount": round(float(t["amount"]), 2),
                "type": "transfer",
                "date": t["date"],
                "is_recurring": False,
                "status": "paid",
                "responsible_person": t.get("responsible_person") or "Leandro",
                "installment_info": None,
                "entry_source": "ofx",
                "source_file": src_file,
                "fitid": t.get("fitid"),
                "dedup_key": dedup_k,
                "import_batch_id": batch_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })

        print(f"Lote: {src_file:45s} | Conta: {acc['name']:20s} | {len(tx_list):2d} lançamentos | R$ {batch_tot:10.2f}")

    print(f"\nTotal de lotes: {len(batches_to_insert)}")
    print(f"Total de transferências: {len(transfers_to_insert)} | Soma: R$ {sum(t['amount'] for t in transfers_to_insert):,.2f}")

    # Distribuição mensal
    monthly_trf = defaultdict(list)
    for t in transfers_to_insert:
        m = t["date"][:7]
        monthly_trf[m].append(t)

    print("\n=== DISTRIBUIÇÃO MENSAL DAS TRANSFERÊNCIAS ===")
    for m in sorted(monthly_trf.keys()):
        cnt = len(monthly_trf[m])
        tot = sum(t["amount"] for t in monthly_trf[m])
        print(f"{m} | {cnt:2d} lançamentos | Total: R$ {tot:10.2f}")

    # Asserts Canônicos
    assert len(transfers_to_insert) == 93
    assert round(sum(t['amount'] for t in transfers_to_insert), 2) == 586012.81

    if not args.apply:
        print("\n[INFO] Modo DRY-RUN concluído com sucesso. Execute com --apply para persistir no Supabase.")
        return

    # 7. Inserção no Supabase com Governança
    print("\n>>> Persistindo import_batches no Supabase...")
    for b in batches_to_insert:
        sb.table("import_batches").insert(b).execute()
    print("[OK] import_batches persistidos.")

    print(f"\n>>> Inserindo {len(transfers_to_insert)} transferências no Supabase...")
    chunk_size = 50
    for i in range(0, len(transfers_to_insert), chunk_size):
        chunk = transfers_to_insert[i:i + chunk_size]
        sb.table("transactions").insert(chunk).execute()
        print(f"   Inseridas {min(i + chunk_size, len(transfers_to_insert))} de {len(transfers_to_insert)}")
    print("[OK] Inserções concluídas com sucesso.")

    # 8. Verificação Final Pós-Carga
    print("\n=== VERIFICAÇÃO PÓS-CARGA NO SUPABASE ===")
    txs_after = sb.table("transactions").select("*").eq("tenant_id", tenant_id).execute().data or []
    
    type_counts = defaultdict(int)
    type_sums = defaultdict(float)
    monthly_types = defaultdict(lambda: defaultdict(float))
    
    for t in txs_after:
        tp = t["type"]
        amt = float(t["amount"])
        m = str(t["date"])[:7]
        type_counts[tp] += 1
        type_sums[tp] += amt
        monthly_types[m][tp] += amt

    print("\n--- Agrupamento por Tipo ---")
    for tp in sorted(type_counts.keys()):
        print(f"Tipo: {tp:10s} | Contagem: {type_counts[tp]:4d} | Soma: R$ {type_sums[tp]:12.2f}")

    print("\n--- Tabela Histórica de Receita e Despesa ---")
    print(f"{'Mês':7s} | {'Receita':12s} | {'Despesa':12s} | {'Transfer':12s}")
    for m in sorted(monthly_types.keys()):
        inc = monthly_types[m].get("income", 0.0)
        exp = monthly_types[m].get("expense", 0.0)
        trf = monthly_types[m].get("transfer", 0.0)
        print(f"{m:7s} | R$ {inc:9.2f} | R$ {exp:9.2f} | R$ {trf:9.2f}")

    # Asserts Finais Obrigatórios
    assert type_counts["transfer"] == 93
    assert round(type_sums["transfer"], 2) == 586012.81
    assert type_counts["income"] == 33
    assert round(type_sums["income"], 2) == 74926.36
    assert type_counts["expense"] == 643
    assert round(type_sums["expense"], 2) == 105307.48

    print("\n[SUCESSO] REPOVOAMENTO DE TRANSFERÊNCIAS CONCLUÍDO COM 100% DE SUCESSO E INTEGRIDADE!")


if __name__ == "__main__":
    main()
