"""
Módulo universal de deduplicação para importação financeira.

Garante:
1. Função pura `build_dedup_key(...)` estável e invariante a espaços múltiplos, acentuação e caracteres invisíveis.
2. Tratamento determinístico de FITIDs sem colisão de dicionário para múltiplas transações no mesmo dia.
3. Compatibilidade retroativa com `compute_dedup_key`.
"""
import re
import unicodedata
from datetime import datetime, date as date_cls
from typing import Any, Optional, Dict, List, Set, Tuple


def _sanitize_string(value: str) -> str:
    """
    Remove caracteres invisíveis, remove diacríticos (acentos) via NFKD,
    e substitui múltiplos espaços em branco por um único underscore.
    """
    if not value:
        return ""
    # Remove caracteres de largura zero e formatadores invisíveis
    cleaned = re.sub(r'[\u200b\u200c\u200d\ufeff\u00a0\r\n\t]', ' ', str(value))
    # Normalização NFKD para decomposição de acentos
    nfkd = unicodedata.normalize('NFKD', cleaned)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove aspas externas e substitui qualquer sequência de espaços em branco por underscore
    without_accents = without_accents.strip().strip('"\'')
    return re.sub(r'\s+', '_', without_accents).upper()


def build_dedup_key(
    tx_date: Any,
    amount_signed: float,
    description: str,
    bank_or_account: str,
    fitid_or_seq: Optional[str] = None,
) -> str:
    """
    Gera a chave de deduplicação universal e pura para qualquer transação.
    
    Fórmula canônica:
    {data_iso}|{valor_com_sinal_2casas}|{slug_descricao}|{banco_ou_conta}|{fitid_ou_seq}
    """
    if hasattr(tx_date, 'strftime'):
        date_str = tx_date.strftime('%Y-%m-%d')
    elif isinstance(tx_date, (date_cls, datetime)):
        date_str = tx_date.isoformat()[:10]
    else:
        date_str = str(tx_date)[:10]

    amount_val = round(float(amount_signed), 2)
    amount_str = f"{amount_val:.2f}"
    
    desc_slug = _sanitize_string(description)
    bank_slug = _sanitize_string(bank_or_account)
    fitid_slug = _sanitize_string(fitid_or_seq or '')

    parts = [date_str, amount_str, desc_slug, bank_slug]
    if fitid_slug:
        parts.append(fitid_slug)

    return "|".join(parts)


def compute_dedup_key(
    tx_date: Any,
    amount: float,
    description: str,
    account_id: str,
    tx_type: str
) -> str:
    """
    Chave de deduplicação compatível com schema existente.
    Fórmula: {date}|{amount:.2f}|{desc_norm}|{account_id}|{tx_type}
    """
    if hasattr(tx_date, 'strftime'):
        date_str = tx_date.strftime('%Y-%m-%d')
    elif isinstance(tx_date, (date_cls, datetime)):
        date_str = tx_date.isoformat()[:10]
    else:
        date_str = str(tx_date)[:10]

    desc_slug = _sanitize_string(description)
    # Para o schema legado do alca, usa espaço normalizado simples
    desc_norm = desc_slug.replace('_', ' ')
    
    return f"{date_str}|{round(float(amount), 2):.2f}|{desc_norm}|{account_id}|{tx_type}"


def deduplicate_batch(
    transactions: List[Dict[str, Any]],
    existing_dedup_keys: Optional[Set[str]] = None,
    existing_fitids: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Deduplica o lote de transações contra si mesmo e contra chaves existentes no banco.
    
    Preserva a integridade de FITIDs sem perdas por chave de busca comum.
    Retorna: (transacoes_validas, transacoes_duplicadas)
    """
    existing_keys = set(existing_dedup_keys or set())
    existing_fits = set(existing_fitids or set())
    
    seen_in_batch: Set[str] = set()
    seen_fitids_in_batch: Set[str] = set()
    
    valid_transactions: List[Dict[str, Any]] = []
    duplicate_transactions: List[Dict[str, Any]] = []
    
    for tx in transactions:
        dedup_k = tx.get('dedup_key')
        fitid = tx.get('fitid')
        
        is_dup = False
        reason = ""
        
        if fitid and fitid in existing_fits:
            is_dup = True
            reason = f"FITID já existente no banco: {fitid}"
        elif dedup_k and dedup_k in existing_keys:
            is_dup = True
            reason = f"Chave dedup_key já existente no banco: {dedup_k}"
        elif fitid and fitid in seen_fitids_in_batch:
            is_dup = True
            reason = f"FITID duplicado dentro do próprio arquivo: {fitid}"
        elif dedup_k and dedup_k in seen_in_batch:
            is_dup = True
            reason = f"Lançamento idêntico repetido no próprio arquivo: {dedup_k}"
            
        if is_dup:
            dup_tx = dict(tx)
            dup_tx['duplicate_reason'] = reason
            duplicate_transactions.append(dup_tx)
        else:
            if dedup_k:
                seen_in_batch.add(dedup_k)
            if fitid:
                seen_fitids_in_batch.add(fitid)
            valid_transactions.append(tx)
            
    return valid_transactions, duplicate_transactions
