import csv
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
from io import StringIO
import xml.etree.ElementTree as ET


def detect_file_format(filename: str, content: bytes) -> str:
    """Detecta o formato do arquivo baseado na extensão e conteúdo"""
    filename_lower = filename.lower()
    
    if filename_lower.endswith('.ofx'):
        return 'ofx'
    elif filename_lower.endswith('.csv'):
        # Verifica se é CSV do Nubank
        try:
            content_str = content.decode('utf-8', errors='ignore')
            first_lines = content_str.split('\n')[:5]
            # CSV do Nubank pode ter dois formatos:
            # 1. Formato antigo: Data, Valor, Identificador, Descrição
            # 2. Formato novo (cartão): date, title, amount
            for line in first_lines:
                line_lower = line.lower()
                # Formato antigo: Data, Valor, Descrição
                has_data = 'data' in line_lower
                has_desc = 'descrição' in line_lower or 'descricao' in line_lower
                has_valor = 'valor' in line_lower
                has_id = 'identificador' in line_lower
                
                # Formato novo: date, title, amount
                has_date = 'date' in line_lower
                has_title = 'title' in line_lower
                has_amount = 'amount' in line_lower
                
                # Detecta formato antigo
                if has_data and has_desc and has_valor:
                    return 'nubank_csv'
                if has_data and has_valor and has_id:
                    return 'nubank_csv'
                
                # Detecta formato novo (cartão)
                if has_date and has_title and has_amount:
                    return 'nubank_csv'
            return 'csv'
        except:
            return 'csv'
    else:
        raise ValueError(f'Formato de arquivo não suportado: {filename}')


def parse_nubank_csv(content: bytes) -> List[Dict[str, Any]]:
    """Parse CSV do Nubank (suporta dois formatos: conta corrente e cartão de crédito)"""
    content_str = content.decode('utf-8')
    lines = content_str.strip().split('\n')
    
    if not lines:
        raise ValueError('Arquivo CSV vazio')
    
    # Detecta o separador (vírgula ou ponto e vírgula)
    first_line = lines[0]
    separator = ',' if ',' in first_line else ';'
    
    # Lê o CSV
    reader = csv.DictReader(StringIO(content_str), delimiter=separator)
    
    # Detecta qual formato está sendo usado
    headers = [h.lower().strip() for h in reader.fieldnames or []]
    is_new_format = 'date' in headers and 'title' in headers and 'amount' in headers
    is_old_format = any('data' in h for h in headers) and any('valor' in h for h in headers)
    
    transactions = []
    for row in reader:
        try:
            if is_new_format:
                # Formato novo (cartão): date, title, amount
                date_str = row.get('date') or row.get('Date') or row.get('DATE')
                description = row.get('title') or row.get('Title') or row.get('TITLE')
                amount_str = row.get('amount') or row.get('Amount') or row.get('AMOUNT')
                
                if not date_str or not description or not amount_str:
                    continue
                
                # Parse da data (formato ISO: YYYY-MM-DD)
                try:
                    if '-' in date_str:
                        date_parts = date_str.split('-')
                        if len(date_parts) == 3:
                            year, month, day = date_parts
                            transaction_date = datetime(int(year), int(month), int(day))
                        else:
                            continue
                    else:
                        continue
                except:
                    continue
                
                # Parse do valor
                amount_str_clean = amount_str.replace('R$', '').replace(' ', '').replace(',', '.')
                try:
                    amount = float(amount_str_clean)
                except:
                    continue
                
                # No formato novo: positivo = despesa, negativo = receita/pagamento
                transaction_type = 'expense' if amount > 0 else 'income'
                amount = abs(amount)
                
            elif is_old_format:
                # Formato antigo (conta corrente): Data, Valor, Identificador, Descrição
                date_str = row.get('Data') or row.get('data') or row.get('DATA') or row.get('date') or row.get('DATE')
                description = row.get('Descrição') or row.get('descrição') or row.get('DESCRIÇÃO') or row.get('description') or row.get('DESCRIPTION') or row.get('Descricao') or row.get('DESCRICAO')
                amount_str = row.get('Valor') or row.get('valor') or row.get('VALOR') or row.get('amount') or row.get('AMOUNT')
                
                if not date_str or not description or not amount_str:
                    continue
                
                # Parse da data (formato brasileiro: DD/MM/YYYY ou DD-MM-YYYY)
                try:
                    if '/' in date_str:
                        date_parts = date_str.split('/')
                    elif '-' in date_str:
                        date_parts = date_str.split('-')
                    else:
                        continue
                    
                    if len(date_parts) == 3:
                        # Formato brasileiro: DD/MM/YYYY (primeiro número é dia se > 12)
                        day, month, year = date_parts
                        # Se o primeiro número é > 12, é dia (formato DD/MM/YYYY)
                        if int(day) > 12:
                            transaction_date = datetime(int(year), int(month), int(day))
                        else:
                            # Pode ser formato ISO (YYYY-MM-DD) ou DD/MM/YYYY com dia <= 12
                            # Tenta como brasileiro primeiro
                            try:
                                transaction_date = datetime(int(year), int(month), int(day))
                            except:
                                # Se falhar, tenta como ISO
                                year, month, day = date_parts
                                transaction_date = datetime(int(year), int(month), int(day))
                    else:
                        continue
                except:
                    continue
                
                # Parse do valor (remove R$ e espaços, troca vírgula por ponto)
                amount_str_clean = amount_str.replace('R$', '').replace(' ', '').replace(',', '.')
                try:
                    amount = float(amount_str_clean)
                except:
                    continue
                
                # No formato antigo: negativo = despesa, positivo = receita
                transaction_type = 'expense' if amount < 0 else 'income'
                amount = abs(amount)
            else:
                # Formato não reconhecido, pula
                continue
            
            transactions.append({
                'date': transaction_date,
                'description': description.strip(),
                'amount': amount,
                'type': transaction_type,
                'raw_data': row
            })
        except Exception as e:
            continue
    
    return transactions


def parse_ofx(content: bytes) -> List[Dict[str, Any]]:
    """Parse arquivo OFX"""
    content_str = content.decode('utf-8', errors='ignore')
    
    # OFX pode ter headers SGML, precisamos extrair apenas o XML
    # Remove headers antes do <OFX>
    ofx_start = content_str.find('<OFX>')
    if ofx_start == -1:
        # Tenta encontrar sem case sensitive
        ofx_start = content_str.lower().find('<ofx>')
        if ofx_start == -1:
            raise ValueError('Formato OFX inválido: tag <OFX> não encontrada')
    
    xml_content = content_str[ofx_start:]
    
    # OFX pode ter tags sem fechamento, precisamos normalizar
    # Remove quebras de linha dentro das tags e espaços extras
    xml_content = re.sub(r'>\s+<', '><', xml_content)
    xml_content = re.sub(r'\s+', ' ', xml_content)
    
    # Tenta parsear o XML
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        # Tenta com namespace vazio
        try:
            xml_content_fixed = xml_content.replace('<OFX>', '<OFX xmlns="">').replace('<ofx>', '<ofx xmlns="">')
            root = ET.fromstring(xml_content_fixed)
        except:
            # Tenta método alternativo: busca direta por padrões
            return parse_ofx_alternative(content_str)
    
    transactions = []
    
    # Busca transações (pode estar em STMTTRN ou BANKTRANLIST)
    # Tenta diferentes caminhos possíveis
    stmttrn_list = root.findall('.//STMTTRN') or root.findall('.//stmttrn') or root.findall('.//StmtTrn')
    
    if not stmttrn_list:
        # Tenta método alternativo
        return parse_ofx_alternative(content_str)
    
    for stmttrn in stmttrn_list:
        try:
            # Data da transação
            dtposted = stmttrn.find('DTPOSTED') or stmttrn.find('dtposted') or stmttrn.find('DtPosted')
            if dtposted is None or dtposted.text is None:
                continue
            
            # OFX data format: YYYYMMDDHHMMSS ou YYYYMMDD
            dtposted_text = dtposted.text.strip()
            if len(dtposted_text) >= 8:
                year = int(dtposted_text[0:4])
                month = int(dtposted_text[4:6])
                day = int(dtposted_text[6:8])
                transaction_date = datetime(year, month, day)
            else:
                continue
            
            # Descrição
            memo = stmttrn.find('MEMO') or stmttrn.find('memo') or stmttrn.find('Memo')
            name = stmttrn.find('NAME') or stmttrn.find('name') or stmttrn.find('Name')
            description = (memo.text if memo is not None and memo.text else '') or \
                         (name.text if name is not None and name.text else '') or \
                         'Transação sem descrição'
            
            # Valor
            trnamt = stmttrn.find('TRNAMT') or stmttrn.find('trnamt') or stmttrn.find('TrnAmt')
            if trnamt is None or trnamt.text is None:
                continue
            
            try:
                amount = float(trnamt.text.strip().replace(',', '.'))
            except:
                continue
            
            # Tipo (negativo = despesa, positivo = receita)
            transaction_type = 'expense' if amount < 0 else 'income'
            amount = abs(amount)
            
            transactions.append({
                'date': transaction_date,
                'description': description.strip(),
                'amount': amount,
                'type': transaction_type,
                'raw_data': {
                    'fitid': (stmttrn.find('FITID') or stmttrn.find('fitid') or stmttrn.find('FitId')).text if (stmttrn.find('FITID') or stmttrn.find('fitid') or stmttrn.find('FitId')) is not None else None,
                    'trntype': (stmttrn.find('TRNTYPE') or stmttrn.find('trntype') or stmttrn.find('TrnType')).text if (stmttrn.find('TRNTYPE') or stmttrn.find('trntype') or stmttrn.find('TrnType')) is not None else None
                }
            })
        except Exception as e:
            continue
    
    return transactions


def parse_ofx_alternative(content_str: str) -> List[Dict[str, Any]]:
    """Método alternativo para parsear OFX usando regex quando XML parsing falha"""
    transactions = []
    
    # Busca padrões STMTTRN usando regex
    stmttrn_pattern = r'<STMTTRN>(.*?)</STMTTRN>'
    matches = re.findall(stmttrn_pattern, content_str, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        try:
            # Extrai DTPOSTED
            dtposted_match = re.search(r'<DTPOSTED[^>]*>([^<]+)', match, re.IGNORECASE)
            if not dtposted_match:
                continue
            
            dtposted_text = dtposted_match.group(1).strip()
            if len(dtposted_text) >= 8:
                year = int(dtposted_text[0:4])
                month = int(dtposted_text[4:6])
                day = int(dtposted_text[6:8])
                transaction_date = datetime(year, month, day)
            else:
                continue
            
            # Extrai MEMO ou NAME
            memo_match = re.search(r'<MEMO[^>]*>([^<]+)', match, re.IGNORECASE)
            name_match = re.search(r'<NAME[^>]*>([^<]+)', match, re.IGNORECASE)
            description = (memo_match.group(1) if memo_match else '') or \
                         (name_match.group(1) if name_match else '') or \
                         'Transação sem descrição'
            
            # Extrai TRNAMT
            trnamt_match = re.search(r'<TRNAMT[^>]*>([^<]+)', match, re.IGNORECASE)
            if not trnamt_match:
                continue
            
            try:
                amount = float(trnamt_match.group(1).strip().replace(',', '.'))
            except:
                continue
            
            transaction_type = 'expense' if amount < 0 else 'income'
            amount = abs(amount)
            
            transactions.append({
                'date': transaction_date,
                'description': description.strip(),
                'amount': amount,
                'type': transaction_type,
                'raw_data': {}
            })
        except Exception:
            continue
    
    return transactions


def parse_standard_csv(content: bytes) -> List[Dict[str, Any]]:
    """Parse CSV padrão (formato interno da aplicação)"""
    import pandas as pd
    
    content_str = content.decode('utf-8')
    reader = csv.DictReader(StringIO(content_str))
    
    transactions = []
    for row in reader:
        try:
            # Formato esperado: description, amount, type, category_name, date
            date_str = row.get('date') or row.get('Date') or row.get('DATE')
            description = row.get('description') or row.get('Description') or row.get('DESCRIPTION')
            amount_str = row.get('amount') or row.get('Amount') or row.get('AMOUNT')
            transaction_type = row.get('type') or row.get('Type') or row.get('TYPE')
            
            if not all([date_str, description, amount_str, transaction_type]):
                continue
            
            # Parse da data
            try:
                transaction_date = pd.to_datetime(date_str).to_pydatetime()
            except:
                continue
            
            # Parse do valor
            try:
                amount = float(amount_str)
            except:
                continue
            
            if transaction_type not in ['income', 'expense']:
                continue
            
            transactions.append({
                'date': transaction_date,
                'description': description.strip(),
                'amount': amount,
                'type': transaction_type,
                'category_name': row.get('category_name') or row.get('Category') or row.get('CATEGORY'),
                'raw_data': row
            })
        except Exception as e:
            continue
    
    return transactions


def parse_import_file(filename: str, content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Detecta o formato e parseia o arquivo
    Retorna: (formato_detectado, lista_de_transações)
    """
    file_format = detect_file_format(filename, content)
    
    if file_format == 'nubank_csv':
        transactions = parse_nubank_csv(content)
    elif file_format == 'ofx':
        transactions = parse_ofx(content)
    elif file_format == 'csv':
        transactions = parse_standard_csv(content)
    else:
        raise ValueError(f'Formato não suportado: {file_format}')
    
    return file_format, transactions

