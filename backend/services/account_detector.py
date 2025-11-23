"""
Serviço para detectar e criar contas/cartões automaticamente baseado em arquivos importados
"""
import re
from typing import Dict, Any, Optional, Tuple
import xml.etree.ElementTree as ET


def extract_account_info_from_ofx(content: bytes) -> Optional[Dict[str, Any]]:
    """
    Extrai informações da conta do arquivo OFX.
    Retorna: {
        'institution': str,
        'account_number': str,
        'account_type': str,  # 'checking', 'savings', 'credit_card', etc.
        'bank_id': str,
        'branch_id': str
    }
    """
    try:
        content_str = content.decode('utf-8', errors='ignore')
        
        # Remove headers antes do <OFX>
        ofx_start = content_str.find('<OFX>')
        if ofx_start == -1:
            ofx_start = content_str.lower().find('<ofx>')
            if ofx_start == -1:
                return None
        
        xml_content = content_str[ofx_start:]
        xml_content = re.sub(r'>\s+<', '><', xml_content)
        xml_content = re.sub(r'\s+', ' ', xml_content)
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            try:
                xml_content_fixed = xml_content.replace('<OFX>', '<OFX xmlns="">').replace('<ofx>', '<ofx xmlns="">')
                root = ET.fromstring(xml_content_fixed)
            except:
                # Tenta método alternativo com regex
                return extract_account_info_from_ofx_regex(content_str)
        
        # Busca informações da instituição financeira
        fi_org = root.find('.//FI/ORG') or root.find('.//fi/org') or root.find('.//Fi/Org')
        institution = fi_org.text.strip() if fi_org is not None and fi_org.text else None
        
        # Busca BANKID
        bank_id = None
        bankid_elem = root.find('.//BANKID') or root.find('.//bankid') or root.find('.//BankId')
        if bankid_elem is not None and bankid_elem.text:
            bank_id = bankid_elem.text.strip()
            
        # Se não encontrou instituição no ORG, tenta pelo BANKID
        if not institution and bank_id:
            bank_map = {
                '001': 'Banco do Brasil',
                '033': 'Santander',
                '077': 'Banco Inter',
                '104': 'Caixa Econômica Federal',
                '237': 'Bradesco',
                '260': 'Nubank',
                '341': 'Itaú'
            }
            institution = bank_map.get(bank_id)
        
        # Busca informações da conta
        acct_from = root.find('.//BANKACCTFROM') or root.find('.//bankacctfrom') or root.find('.//BankAcctFrom')
        if acct_from is None:
            # Tenta método alternativo
            return extract_account_info_from_ofx_regex(content_str)
        
        # ACCTID (número da conta)
        acctid_elem = acct_from.find('ACCTID') or acct_from.find('acctid') or acct_from.find('AcctId')
        account_number = acctid_elem.text.strip() if acctid_elem is not None and acctid_elem.text else None
        
        # ACCTTYPE (tipo da conta)
        accttype_elem = acct_from.find('ACCTTYPE') or acct_from.find('accttype') or acct_from.find('AcctType')
        acct_type_raw = accttype_elem.text.strip() if accttype_elem is not None and accttype_elem.text else None
        
        # BRANCHID (agência)
        branchid_elem = acct_from.find('BRANCHID') or acct_from.find('branchid') or acct_from.find('BranchId')
        branch_id = branchid_elem.text.strip() if branchid_elem is not None and branchid_elem.text else None
        
        # Mapeia ACCTTYPE para tipo do sistema
        account_type_map = {
            'CHECKING': 'checking',
            'SAVINGS': 'savings',
            'CREDITLINE': 'credit_card',
            'CREDITCARD': 'credit_card',
            'MONEYMRKT': 'savings',
            'INVESTMENT': 'investment'
        }
        
        account_type = account_type_map.get(acct_type_raw.upper() if acct_type_raw else '', 'wallet')
        
        if not account_number:
            return None
        
        return {
            'institution': institution or 'Banco Desconhecido',
            'account_number': account_number,
            'account_type': account_type,
            'bank_id': bank_id,
            'branch_id': branch_id
        }
    except Exception as e:
        return None


def extract_account_info_from_ofx_regex(content_str: str) -> Optional[Dict[str, Any]]:
    """Método alternativo usando regex para extrair informações do OFX"""
    try:
        # Extrai ORG
        org_match = re.search(r'<ORG[^>]*>([^<]+)', content_str, re.IGNORECASE)
        institution = org_match.group(1).strip() if org_match else None
        
        # Extrai BANKID
        bankid_match = re.search(r'<BANKID[^>]*>([^<]+)', content_str, re.IGNORECASE)
        bank_id = bankid_match.group(1).strip() if bankid_match else None
        
        if not institution and bank_id:
            bank_map = {
                '001': 'Banco do Brasil',
                '033': 'Santander',
                '077': 'Banco Inter',
                '104': 'Caixa Econômica Federal',
                '237': 'Bradesco',
                '260': 'Nubank',
                '341': 'Itaú'
            }
            institution = bank_map.get(bank_id)
        
        # Extrai ACCTID
        acctid_match = re.search(r'<ACCTID[^>]*>([^<]+)', content_str, re.IGNORECASE)
        account_number = acctid_match.group(1).strip() if acctid_match else None
        
        # Extrai ACCTTYPE
        accttype_match = re.search(r'<ACCTTYPE[^>]*>([^<]+)', content_str, re.IGNORECASE)
        acct_type_raw = accttype_match.group(1).strip() if accttype_match else None
        
        # Extrai BRANCHID
        branchid_match = re.search(r'<BRANCHID[^>]*>([^<]+)', content_str, re.IGNORECASE)
        branch_id = branchid_match.group(1).strip() if branchid_match else None
        
        if not account_number:
            return None
        
        account_type_map = {
            'CHECKING': 'checking',
            'SAVINGS': 'savings',
            'CREDITLINE': 'credit_card',
            'CREDITCARD': 'credit_card',
            'MONEYMRKT': 'savings',
            'INVESTMENT': 'investment'
        }
        
        account_type = account_type_map.get(acct_type_raw.upper() if acct_type_raw else '', 'wallet')
        
        return {
            'institution': institution or 'Banco Desconhecido',
            'account_number': account_number,
            'account_type': account_type,
            'bank_id': bank_id,
            'branch_id': branch_id
        }
    except Exception:
        return None


def extract_account_info_from_csv(filename: str, content: bytes) -> Optional[Dict[str, Any]]:
    """
    Extrai informações da conta do arquivo CSV (principalmente Nubank).
    Retorna informações inferidas do nome do arquivo e padrões.
    """
    try:
        filename_lower = filename.lower()
        
        # Detecta instituição pelo nome do arquivo
        institution = None
        if 'nubank' in filename_lower:
            institution = 'Nubank'
        elif 'inter' in filename_lower:
            institution = 'Banco Inter'
        elif 'itau' in filename_lower or 'itaú' in filename_lower:
            institution = 'Itaú'
        elif 'bradesco' in filename_lower:
            institution = 'Bradesco'
        elif 'santander' in filename_lower:
            institution = 'Santander'
        elif 'bb' in filename_lower or 'brasil' in filename_lower:
            institution = 'Banco do Brasil'
        
        # Tenta extrair número da conta do nome do arquivo
        # Exemplo: NU_93015865_01OUT2025_31OUT2025.ofx ou NU_93015865_01OUT2025_31OUT2025.csv
        # Padrões: NU_XXXXX, NUBANK_XXXXX, etc.
        account_number_match = re.search(r'[A-Z]+[_-](\d+)', filename.upper())
        account_number = account_number_match.group(1) if account_number_match else None
        
        # Se não encontrou no nome, tenta no conteúdo do CSV (primeira linha pode ter info)
        if not account_number:
            try:
                content_str = content.decode('utf-8', errors='ignore')
                # Alguns CSVs têm informações da conta no cabeçalho ou comentários
                # Por enquanto, não extraímos do conteúdo, apenas do nome
            except:
                pass
        
        # Para CSV do Nubank, detecta tipo baseado no formato e conteúdo
        account_type = 'checking'  # Padrão
        
        # Verifica se pode ser cartão de crédito (pelo nome do arquivo)
        if 'cartao' in filename_lower or 'cartão' in filename_lower or 'credito' in filename_lower or 'crédito' in filename_lower:
            account_type = 'credit_card'
        
        # Verifica pelo formato do CSV (formato date,title,amount geralmente é cartão)
        try:
            content_str = content.decode('utf-8', errors='ignore')
            first_line = content_str.split('\n')[0].lower()
            # Se tem date, title, amount, provavelmente é cartão de crédito
            if 'date' in first_line and 'title' in first_line and 'amount' in first_line:
                account_type = 'credit_card'
        except:
            pass
        
        return {
            'institution': institution or 'Banco Desconhecido',
            'account_number': account_number,
            'account_type': account_type,
            'bank_id': None,
            'branch_id': None
        }
    except Exception:
        return None


def find_or_create_account(
    accounts_collection,
    user_id: str,
    account_info: Dict[str, Any],
    filename: str = None
) -> Tuple[Optional[str], bool]:
    """
    Busca uma conta existente ou cria uma nova baseado nas informações extraídas.
    Retorna: (account_id, was_created)
    """
    if not account_info:
        return None, False
    
    institution = account_info.get('institution', 'Banco Desconhecido')
    account_number = account_info.get('account_number')
    account_type = account_info.get('account_type', 'wallet')
    
    # Normaliza o nome da instituição para busca
    institution_lower = institution.lower()
    
    # Busca contas existentes do usuário
    existing_accounts = list(accounts_collection.find({
        'user_id': user_id,
        'is_active': True
    }))
    
    # Tenta encontrar conta existente por:
    # 1. Número da conta e instituição (mais preciso)
    # 2. Nome similar da instituição e tipo
    # 3. Apenas instituição e tipo (menos preciso)
    
    best_match = None
    best_match_score = 0
    
    for account in existing_accounts:
        account_name_lower = account.get('name', '').lower()
        account_institution_lower = (account.get('institution') or '').lower()
        account_type_match = account.get('type') == account_type
        
        score = 0
        
        # Pontuação por número da conta (mais importante)
        if account_number:
            if account_number in str(account.get('name', '')):
                score += 10
            # Verifica últimos 4 dígitos
            if len(account_number) >= 4:
                last_4 = account_number[-4:]
                if last_4 in str(account.get('name', '')):
                    score += 5
        
        # Pontuação por instituição
        if institution_lower in account_name_lower:
            score += 3
        if institution_lower in account_institution_lower:
            score += 3
        
        # Pontuação por tipo
        if account_type_match:
            score += 2
        
        # Se tem número da conta e instituição, é muito provável que seja a mesma
        if account_number and score >= 13:  # Número + instituição + tipo
            return account['_id'], False
        
        # Mantém o melhor match
        if score > best_match_score:
            best_match_score = score
            best_match = account
    
    # Se encontrou um match razoável (score >= 5), usa ele
    if best_match and best_match_score >= 5:
        return best_match['_id'], False
    
    # Se não encontrou, cria nova conta
    from repositories.account_repository import AccountRepository
    from services.account_service import AccountService
    
    # Gera nome da conta
    account_name = f"{institution}"
    if account_number:
        # Formata número da conta (últimos 4 dígitos)
        account_number_short = account_number[-4:] if len(account_number) > 4 else account_number
        account_name = f"{institution} - {account_number_short}"
    
    # Define cor e ícone baseado no tipo
    type_config = {
        'checking': {'color': '#3B82F6', 'icon': 'bank'},
        'savings': {'color': '#10B981', 'icon': 'piggy-bank'},
        'credit_card': {'color': '#8B5CF6', 'icon': 'credit-card'},
        'wallet': {'color': '#6366F1', 'icon': 'wallet2'},
        'investment': {'color': '#F59E0B', 'icon': 'graph-up-arrow'}
    }
    
    config = type_config.get(account_type, type_config['wallet'])
    
    account_data = {
        'name': account_name,
        'type': account_type,
        'institution': institution,
        'initial_balance': 0,
        'current_balance': 0,
        'color': config['color'],
        'icon': config['icon'],
        'is_active': True
    }
    
    # Se for cartão de crédito, adiciona campos específicos
    if account_type == 'credit_card':
        account_data['closing_day'] = 10  # Padrão
        account_data['due_day'] = 15  # Padrão
    
    try:
        import uuid
        from repositories.account_repository import AccountRepository
        from services.account_service import AccountService
        
        account_repo = AccountRepository(accounts_collection)
        # Cria service com transactions_collection como None (não é necessário para criar conta)
        account_service = AccountService(account_repo, None)
        new_account = account_service.create_account(user_id, account_data)
        return new_account.get('id'), True
    except Exception as e:
        # Se falhar ao criar, retorna None mas não quebra a importação
        return None, False

