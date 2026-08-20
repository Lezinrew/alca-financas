"""
Classificador de natureza financeira para transações bancárias e de faturas de cartão.

Resolve:
1. Cartão de crédito: ignora espelho de pagamentos e saldos anteriores/rotativos que duplicam despesas.
2. Identifica custos financeiros reais (Juros, Multas, IOF) direcionando para 'Financeiro'.
3. Identifica transferências internas (CDB, RDB, Mesma Titularidade, Pagamento de fatura) classificando como type='transfer'.
"""
import re
import unicodedata
from typing import Dict, Any, Optional, Tuple


def _normalize_text(text: str) -> str:
    """Normaliza texto removendo acentuação e espaços extras em maiúsculo."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', without_accents).strip().upper()


class TransactionNature:
    EXPENSE = 'expense'
    INCOME = 'income'
    TRANSFER = 'transfer'
    FINANCIAL_CHARGE = 'financial_charge'
    IGNORED_INVOICE_PAYMENT = 'ignored_invoice_payment'
    IGNORED_ROLLED_OVER_BALANCE = 'ignored_rolled_over_balance'


# Padrões para identificar saldos rolados e encargos de faturas de cartão
CC_ROLLED_OVER_PATTERNS = [
    r'VALOR PENDENTE DO M[EÊ]S ANTERIOR',
    r'SALDO ANTERIOR',
    r'PAGAMENTO MINIMO',
    r'ROTATIVO',
    r'FINANCIAMENTO DE FATURA',
    r'PARCELAMENTO DE FATURA',
]

CC_PAYMENT_MIRROR_PATTERNS = [
    r'PAGAMENTO RECEBIDO',
    r'PAGAMENTO EFETUADO',
    r'PAGAMENTO DE FATURA RECEBIDO',
]

FINANCIAL_CHARGE_PATTERNS = [
    r'MULTA POR FATURA ATRASADA',
    r'JUROS POR FATURA ATRASADA',
    r'JUROS DE MORA',
    r'MULTA DE MORA',
    r'IOF ROTATIVO',
    r'IOF ADICIONAL',
    r'IOF FINANCIAMENTO',
    r'IOF',
    r'ENCARGOS DE REFINANCIAMENTO',
    r'TARIFA BANCARIA',
]

# Padrões para transferências internas em conta corrente e faturas
INTERNAL_TRANSFER_PATTERNS = [
    r'APLICACAO:',
    r'APLICACAO RDB',
    r'APLICACAO EM CDB',
    r'APLICACAO CDB',
    r'RESGATE:',
    r'RESGATE RDB',
    r'RESGATE DE CDB',
    r'RESGATE CDB',
    r'CDB PORQUINHO',
    r'INTER HEDGE',
    r'RESERVA RDB',
    r'CREDITO RESGATE FUNDO:',
    r'CREDITO RESGATE RDB',
    r'PAGAMENTO DE FATURA',
    r'PAGAMENTO FATURA',
    r'VALOR ADICIONADO NA CONTA POR CARTAO DE CREDITO',
    r'VALOR ADICIONADO PARA PIX NO CREDITO',
    r'PIX NO CREDITO',
    r'GLENDA DAVID VAZ',
    r'ALAN DAVID XAVIER VAZ',
    r'ALAN VAZ',
    r'ALAN DAVID',
    r'STONE IP',
    r'MERCADO PAGO.*LEANDRO XAVIER',
    r'LEANDRO XAVIER.*MERCADO PAGO',
    r'TRANSFERENCIA MESMA TITULARIDADE',
    r'TRANSFERENCIA ENTRE CONTAS PROPRIAS',
    r'TRANSFERENCIA PARA CONTA PROPRIA',
    r'CP\s*:\s*\d+-(?:LEANDRO XAVIER DE PINHO|GLENDA DAVID VAZ)',
]


def classify_nature(
    memo: str,
    amount_signed: float,
    is_credit_card: bool,
    user_name: Optional[str] = None,
    user_cpf: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classifica a natureza da transação OFX.
    
    Retorna:
    {
        'nature': str,
        'type': 'income' | 'expense' | 'transfer',
        'should_ignore': bool,
        'ignore_reason': Optional[str],
        'suggested_category': Optional[str],
        'cleaned_description': str
    }
    """
    norm_memo = _normalize_text(memo)
    
    # 1. TRATAMENTO PARA FATURAS DE CARTÃO DE CRÉDITO
    if is_credit_card:
        # A. Saldos pendentes e rotativo da fatura anterior (NÃO são despesas novas)
        for pattern in CC_ROLLED_OVER_PATTERNS:
            if re.search(pattern, norm_memo, re.IGNORECASE):
                return {
                    'nature': TransactionNature.IGNORED_ROLLED_OVER_BALANCE,
                    'type': 'expense',
                    'should_ignore': True,
                    'ignore_reason': 'Saldo rolado / rotativo da fatura anterior (duplica despesas)',
                    'suggested_category': None,
                    'cleaned_description': memo.strip()
                }
                
        # B. Pagamentos da fatura recebidos (Espelho do débito na conta corrente)
        for pattern in CC_PAYMENT_MIRROR_PATTERNS:
            if re.search(pattern, norm_memo, re.IGNORECASE) or amount_signed < 0:
                # No cartão, pagamento entra com sinal oposto às compras (ou memo explicito)
                if any(re.search(p, norm_memo, re.IGNORECASE) for p in CC_PAYMENT_MIRROR_PATTERNS):
                    return {
                        'nature': TransactionNature.IGNORED_INVOICE_PAYMENT,
                        'type': 'income',
                        'should_ignore': True,
                        'ignore_reason': 'Espelho de pagamento de fatura (já debitado na conta corrente)',
                        'suggested_category': None,
                        'cleaned_description': memo.strip()
                    }
                    
        # C. Custos financeiros da fatura (Juros, multas, IOF)
        for pattern in FINANCIAL_CHARGE_PATTERNS:
            if re.search(pattern, norm_memo, re.IGNORECASE):
                return {
                    'nature': TransactionNature.FINANCIAL_CHARGE,
                    'type': 'expense',
                    'should_ignore': False,
                    'ignore_reason': None,
                    'suggested_category': 'Financeiro',
                    'cleaned_description': memo.strip()
                }
                
        # D. Transferências internas / repasses no cartão (ex: Pix no Crédito, repasse Glenda)
        for pattern in [r'PIX NO CREDITO', r'GLENDA DAVID VAZ']:
            if re.search(pattern, norm_memo, re.IGNORECASE):
                return {
                    'nature': TransactionNature.TRANSFER,
                    'type': 'transfer',
                    'should_ignore': False,
                    'ignore_reason': None,
                    'suggested_category': 'Transferência Interna',
                    'cleaned_description': memo.strip()
                }

        # E. Compras e despesas reais no cartão
        return {
            'nature': TransactionNature.EXPENSE if amount_signed >= 0 else TransactionNature.INCOME,
            'type': 'expense' if amount_signed >= 0 else 'income',
            'should_ignore': False,
            'ignore_reason': None,
            'suggested_category': None,
            'cleaned_description': memo.strip()
        }
        
    # 2. TRATAMENTO PARA CONTA CORRENTE
    else:
        # A. Transferências internas, aplicações e resgates
        for pattern in INTERNAL_TRANSFER_PATTERNS:
            if re.search(pattern, norm_memo, re.IGNORECASE):
                return {
                    'nature': TransactionNature.TRANSFER,
                    'type': 'transfer',
                    'should_ignore': False,
                    'ignore_reason': None,
                    'suggested_category': 'Transferência Interna',
                    'cleaned_description': memo.strip()
                }
                
        # B. Checagem de mesma titularidade (quando nome do titular ou CPF aparece)
        if user_name:
            norm_user = _normalize_text(user_name)
            if norm_user and norm_user in norm_memo:
                # Se for transferência entre contas próprias
                if any(k in norm_memo for k in ['TRANSFERENCIA', 'PIX', 'TED', 'DOC', 'MESMA TITULARIDADE']):
                    return {
                        'nature': TransactionNature.TRANSFER,
                        'type': 'transfer',
                        'should_ignore': False,
                        'ignore_reason': None,
                        'suggested_category': 'Transferência Interna',
                        'cleaned_description': memo.strip()
                    }

        # C. Receitas e Despesas normais de caixa
        if amount_signed > 0:
            return {
                'nature': TransactionNature.INCOME,
                'type': 'income',
                'should_ignore': False,
                'ignore_reason': None,
                'suggested_category': None,
                'cleaned_description': memo.strip()
            }
        else:
            return {
                'nature': TransactionNature.EXPENSE,
                'type': 'expense',
                'should_ignore': False,
                'ignore_reason': None,
                'suggested_category': None,
                'cleaned_description': memo.strip()
            }
