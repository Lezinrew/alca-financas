"""
Parser especializado e robusto para arquivos OFX (SGML e XML).

Garante:
1. Decodificação UTF-8 pura independente de headers declarando USASCII/1252 (com fallback para latin-1).
2. Identificação da natureza da conta pelo bloco XML (<STMTRS> vs <CCSTMTRS>), nunca por nome de arquivo.
3. Extração completa de transações (<STMTTRN>), FITIDs, dados da conta e saldo (<LEDGERBAL>).
"""
import re
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import xml.etree.ElementTree as ET


def decode_ofx_bytes(content: bytes) -> str:
    """
    Decodifica o conteúdo de bytes do OFX.
    Ignora headers declarando USASCII/1252 e força decodificação UTF-8.
    Fallback para latin-1 apenas se UTF-8 levantar UnicodeDecodeError.
    """
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1', errors='replace')


def _clean_sgml_tags(text: str) -> str:
    """Normaliza tags SGML para parsing XML ou regex."""
    # Remove quebras de linha e múltiplos espaços entre tags
    cleaned = re.sub(r'>\s+<', '><', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


def _parse_signed_amount(amt_str: str) -> float:
    """Converte string de valor financeiro preservando o sinal original."""
    if not amt_str:
        return 0.0
    s = amt_str.strip().replace('R$', '').replace(' ', '')
    if not s:
        return 0.0
    # Suporte para formato pt-BR ou internacional
    if ',' in s and '.' in s:
        # Se vírgula for o separador decimal
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    return float(s)


def _parse_ofx_date(date_str: str) -> Optional[datetime]:
    """Parse de datas no formato OFX: YYYYMMDDHHMMSS[...] ou YYYYMMDD."""
    if not date_str:
        return None
    cleaned = re.sub(r'\[.*\]', '', date_str.strip())
    cleaned = re.sub(r'\D', '', cleaned)
    if len(cleaned) >= 8:
        try:
            year = int(cleaned[0:4])
            month = int(cleaned[4:6])
            day = int(cleaned[6:8])
            hour = int(cleaned[8:10]) if len(cleaned) >= 10 else 0
            minute = int(cleaned[10:12]) if len(cleaned) >= 12 else 0
            second = int(cleaned[12:14]) if len(cleaned) >= 14 else 0
            return datetime(year, month, day, hour, minute, second)
        except Exception:
            return None
    return None


def extract_account_metadata(content_str: str) -> Dict[str, Any]:
    """
    Extrai metadados da conta pelo bloco estrutural OFX:
    - Conta corrente: <BANKMSGSRSV1> ou <STMTRS> ou <BANKACCTFROM>
    - Cartão de crédito: <CREDITCARDMSGSRSV1> ou <CCSTMTRS> or <CCACCTFROM>
    """
    content_upper = content_str.upper()
    is_credit_card = (
        '<CREDITCARDMSGSRSV1>' in content_upper
        or '<CCSTMTRS>' in content_upper
        or '<CCACCTFROM>' in content_upper
    )
    
    account_type = 'credit_card' if is_credit_card else 'checking'
    
    bank_id = None
    branch_id = None
    account_id = None
    currency = 'BRL'
    
    # Extrai BANKID, BRANCHID, ACCTID
    bank_id_match = re.search(r'<BANKID>(.*?)(?=\n|<|\r)', content_str, re.IGNORECASE)
    if bank_id_match:
        bank_id = bank_id_match.group(1).strip()
        
    branch_id_match = re.search(r'<BRANCHID>(.*?)(?=\n|<|\r)', content_str, re.IGNORECASE)
    if branch_id_match:
        branch_id = branch_id_match.group(1).strip()
        
    acct_id_match = re.search(r'<ACCTID>(.*?)(?=\n|<|\r)', content_str, re.IGNORECASE)
    if acct_id_match:
        account_id = acct_id_match.group(1).strip()
        
    cur_match = re.search(r'<CURDEF>(.*?)(?=\n|<|\r)', content_str, re.IGNORECASE)
    if cur_match:
        currency = cur_match.group(1).strip()
        
    # Extrai Saldo (<LEDGERBAL>)
    ledger_balance = None
    ledger_date = None
    balamt_match = re.search(r'<LEDGERBAL>.*?<BALAMT>([-\d\.,]+)', content_str, re.IGNORECASE | re.DOTALL)
    if balamt_match:
        try:
            ledger_balance = _parse_signed_amount(balamt_match.group(1))
        except Exception:
            pass
            
    dtasof_match = re.search(r'<LEDGERBAL>.*?<DTASOF>(\d+)', content_str, re.IGNORECASE | re.DOTALL)
    if dtasof_match:
        ledger_date = _parse_ofx_date(dtasof_match.group(1))

    # Detecta instituição padrão
    institution = 'Desconhecido'
    if bank_id in ('260', '0260') or 'NUBANK' in content_upper or 'NU PAGAMENTOS' in content_upper:
        institution = 'Nubank'
    elif bank_id in ('077', '77') or 'INTER' in content_upper:
        institution = 'Banco Inter'
    elif bank_id in ('341', '0341') or 'ITAU' in content_upper or 'ITAÚ' in content_upper:
        institution = 'Itaú'
    elif bank_id in ('237', '0237') or 'BRADESCO' in content_upper:
        institution = 'Bradesco'
    elif bank_id in ('001', '1') or 'BANCO DO BRASIL' in content_upper:
        institution = 'Banco do Brasil'

    return {
        'account_type': account_type,
        'is_credit_card': is_credit_card,
        'bank_id': bank_id,
        'branch_id': branch_id,
        'account_number': account_id,
        'institution': institution,
        'currency': currency,
        'ledger_balance': ledger_balance,
        'ledger_date': ledger_date
    }


def parse_raw_ofx_transactions(content_str: str) -> List[Dict[str, Any]]:
    """
    Extrai lista bruta de transações contidas em blocos <STMTTRN>.
    """
    transactions = []
    # Regex robusto para blocos <STMTTRN>...</STMTTRN> ou <STMTTRN> até próximo bloco
    blocks = re.findall(r'<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>)|(?=</CCSTMTRS>)|$)', content_str, re.DOTALL | re.IGNORECASE)
    
    for idx, block in enumerate(blocks):
        block_clean = block.strip()
        if not block_clean:
            continue
            
        dtposted_m = re.search(r'<DTPOSTED>([^<\r\n]+)', block_clean, re.IGNORECASE)
        trnamt_m = re.search(r'<TRNAMT>([^<\r\n]+)', block_clean, re.IGNORECASE)
        fitid_m = re.search(r'<FITID>([^<\r\n]+)', block_clean, re.IGNORECASE)
        memo_m = re.search(r'<MEMO>([^<\r\n]+)', block_clean, re.IGNORECASE)
        name_m = re.search(r'<NAME>([^<\r\n]+)', block_clean, re.IGNORECASE)
        trntype_m = re.search(r'<TRNTYPE>([^<\r\n]+)', block_clean, re.IGNORECASE)
        
        if not dtposted_m or not trnamt_m:
            continue
            
        dt_obj = _parse_ofx_date(dtposted_m.group(1))
        if not dt_obj:
            continue
            
        try:
            amt = _parse_signed_amount(trnamt_m.group(1))
        except Exception:
            continue
            
        fitid = fitid_m.group(1).strip() if fitid_m else ''
        memo = memo_m.group(1).strip() if memo_m else ''
        name = name_m.group(1).strip() if name_m else ''
        trntype = trntype_m.group(1).strip().upper() if trntype_m else ''
        
        # Descrição canônica
        raw_description = memo or name or 'Transação sem descrição'
        
        transactions.append({
            'index': idx,
            'date': dt_obj,
            'amount_signed': amt,
            'fitid': fitid,
            'memo': memo,
            'name': name,
            'description_raw': raw_description,
            'trntype': trntype,
            'raw_block': block_clean
        })
        
    return transactions
