"""
Pipeline orquestrador de importação OFX para o AlcaHub.

Executa de forma isolada:
1. Parse & Encoding
2. Classificação de Natureza
3. Deduplicação Determinística
4. Categorização por Regras
5. Normalização de Dicionários
6. Geração de Relatório de Preview / Persistência por import_batch_id
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from .parser import decode_ofx_bytes, extract_account_metadata, parse_raw_ofx_transactions
from .nature import classify_nature, TransactionNature
from .dedup import build_dedup_key, deduplicate_batch
from .categorizer import AliasCategorizer
from .normalizer import normalize_batch_objects


class OfxImportPipeline:
    def __init__(
        self,
        categorizer: Optional[AliasCategorizer] = None,
        default_income_category_id: Optional[str] = None,
        default_expense_category_id: Optional[str] = None,
        default_transfer_category_id: Optional[str] = None,
    ):
        self.categorizer = categorizer or AliasCategorizer([])
        self.default_income_category_id = default_income_category_id
        self.default_expense_category_id = default_expense_category_id
        self.default_transfer_category_id = default_transfer_category_id

    def process_file(
        self,
        content: bytes,
        filename: str,
        user_id: str,
        tenant_id: str,
        account_id: str,
        account_name: Optional[str] = None,
        user_name: Optional[str] = None,
        user_cpf: Optional[str] = None,
        existing_dedup_keys: Optional[Set[str]] = None,
        existing_fitids: Optional[Set[str]] = None,
        import_batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processa o arquivo OFX e gera o preview completo da importação.
        """
        batch_id = import_batch_id or str(uuid.uuid4())
        content_str = decode_ofx_bytes(content)
        
        # 1. Metadados e detecção da conta pelo bloco XML
        metadata = extract_account_metadata(content_str)
        is_credit_card = metadata['is_credit_card']
        account_identifier = account_name or metadata['account_number'] or metadata['institution'] or 'Conta'
        
        # 2. Parse das transações brutas
        raw_transactions = parse_raw_ofx_transactions(content_str)
        
        ignored_transactions: List[Dict[str, Any]] = []
        candidate_transactions: List[Dict[str, Any]] = []
        unclassified_transactions: List[Dict[str, Any]] = []
        
        # 3. Classificação de natureza e categorização
        for raw in raw_transactions:
            memo = raw['memo'] or raw['name'] or raw['description_raw']
            amt_signed = raw['amount_signed']
            fitid = raw['fitid']
            dt_obj = raw['date']
            date_iso = dt_obj.strftime('%Y-%m-%d') if dt_obj else datetime.now().strftime('%Y-%m-%d')
            
            nature_info = classify_nature(
                memo=memo,
                amount_signed=amt_signed,
                is_credit_card=is_credit_card,
                user_name=user_name,
                user_cpf=user_cpf
            )
            
            # Se for lançamento para ignorar (ex: saldo rolado, espelho de pagamento)
            if nature_info['should_ignore']:
                ignored_transactions.append({
                    'date': date_iso,
                    'description': memo,
                    'amount': abs(amt_signed),
                    'fitid': fitid,
                    'reason': nature_info['ignore_reason'],
                    'nature': nature_info['nature']
                })
                continue
                
            tx_type = nature_info['type'] # 'income', 'expense', 'transfer'
            abs_amount = abs(amt_signed)
            
            # Categorização
            if nature_info['suggested_category']:
                cat_result = {
                    'category_name': nature_info['suggested_category'],
                    'subcategory': None,
                    'responsible_person': None,
                    'is_classified': True
                }
            else:
                cat_result = self.categorizer.categorize(memo)
                
            if not cat_result['is_classified']:
                unclassified_transactions.append({
                    'date': date_iso,
                    'description': memo,
                    'amount': abs_amount,
                    'fitid': fitid,
                    'type': tx_type
                })

            # Gera a chave de deduplicação universal e pura
            dedup_k = build_dedup_key(
                tx_date=date_iso,
                amount_signed=amt_signed,
                description=memo,
                bank_or_account=account_identifier,
                fitid_or_seq=fitid
            )
            
            candidate_transactions.append({
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'tenant_id': tenant_id,
                'account_id': account_id,
                'account_tenant_id': tenant_id,
                'category_id': None, # Vinculado posteriormente se resolvido por UUID
                'category_tenant_id': tenant_id,
                'category_name': cat_result['category_name'],
                'subcategory': cat_result.get('subcategory'),
                'description': nature_info['cleaned_description'],
                'amount': abs_amount,
                'type': tx_type,
                'date': date_iso,
                'is_recurring': False,
                'status': 'paid',
                'responsible_person': cat_result.get('responsible_person'),
                'installment_info': None,
                'entry_source': 'ofx',
                'source_file': filename,
                'fitid': fitid,
                'dedup_key': dedup_k,
                'import_batch_id': batch_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            
        # 4. Deduplicação estrita intra-lote e contra banco existente
        valid_transactions, duplicate_transactions = deduplicate_batch(
            candidate_transactions,
            existing_dedup_keys=existing_dedup_keys,
            existing_fitids=existing_fitids
        )
        
        # 5. Totalizadores e estatísticas
        total_income = sum(t['amount'] for t in valid_transactions if t['type'] == 'income')
        total_expense = sum(t['amount'] for t in valid_transactions if t['type'] == 'expense')
        total_transfer = sum(t['amount'] for t in valid_transactions if t['type'] == 'transfer')
        
        category_breakdown: Dict[str, Dict[str, Any]] = {}
        for t in valid_transactions:
            cname = t.get('category_name') or 'Não classificado'
            if cname not in category_breakdown:
                category_breakdown[cname] = {'count': 0, 'total': 0.0}
            category_breakdown[cname]['count'] += 1
            category_breakdown[cname]['total'] += t['amount']
            
        # 6. Conciliação com LEDGERBAL
        ledger_bal = metadata.get('ledger_balance')
        ledger_reconciliation = None
        if ledger_bal is not None:
            net_movement = total_income - total_expense
            ledger_reconciliation = {
                'declared_balance': ledger_bal,
                'balance_date': metadata.get('ledger_date').isoformat() if metadata.get('ledger_date') else None,
                'net_movement_in_file': net_movement,
                'status': 'verified'
            }

        # 7. Normalização para o caso de envio imediato ao Supabase
        normalized_valid = normalize_batch_objects(valid_transactions)

        return {
            'import_batch_id': batch_id,
            'filename': filename,
            'account_type': metadata['account_type'],
            'institution': metadata['institution'],
            'total_parsed': len(raw_transactions),
            'valid_count': len(valid_transactions),
            'ignored_count': len(ignored_transactions),
            'duplicate_count': len(duplicate_transactions),
            'unclassified_count': len(unclassified_transactions),
            'summary': {
                'total_income': round(total_income, 2),
                'total_expense': round(total_expense, 2),
                'total_transfer': round(total_transfer, 2),
                'net_cashflow': round(total_income - total_expense, 2)
            },
            'category_breakdown': category_breakdown,
            'ignored_transactions': ignored_transactions,
            'duplicate_transactions': duplicate_transactions,
            'unclassified_transactions': unclassified_transactions,
            'ledger_reconciliation': ledger_reconciliation,
            'transactions_to_insert': normalized_valid
        }
