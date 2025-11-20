import pytest
from unittest.mock import Mock, MagicMock, patch
from services.import_service import parse_import_file
from services.account_detector import extract_account_info_from_ofx, extract_account_info_from_csv, find_or_create_account
from services.category_detector import detect_category_from_description

def test_parse_import_file_csv():
    csv_content = b"""date,description,amount,type,category
2023-01-01,Test Transaction,100.00,expense,Food
2023-01-02,Salary,5000.00,income,Income
"""
    format, transactions = parse_import_file('test.csv', csv_content)
    assert format == 'csv'
    assert len(transactions) == 2
    assert transactions[0]['description'] == 'Test Transaction'
    assert transactions[0]['amount'] == 100.00
    assert transactions[0]['type'] == 'expense'


def test_extract_account_info_csv_nubank():
    """Test extracting account info from Nubank CSV filename"""
    
    filename = "nubank_fatura_12345678.csv"
    content = b"date,title,amount\n2025-01-15,Uber,50.00"
    
    info = extract_account_info_from_csv(filename, content)
    
    assert info is not None
    assert info['institution'] == 'Nubank'
    assert info['account_number'] == '12345678'
    assert info['account_type'] == 'credit_card'  # CSV com date,title,amount é cartão


def test_extract_account_info_csv_inter():
    """Test extracting account info from Inter CSV"""
    
    filename = "inter_extrato_98765.csv"
    content = b"data,descricao,valor\n2025-01-15,Compra,100.00"
    
    info = extract_account_info_from_csv(filename, content)
    
    assert info is not None
    assert info['institution'] == 'Banco Inter'
    assert info['account_number'] == '98765'


def test_extract_account_info_csv_unknown():
    """Test extracting account info from unknown bank CSV"""
    
    filename = "extrato.csv"
    content = b"data,descricao,valor\n2025-01-15,Compra,100.00"
    
    info = extract_account_info_from_csv(filename, content)
    
    assert info is not None
    assert info['institution'] == 'Banco Desconhecido'
    assert info['account_type'] == 'checking'  # Padrão


def test_find_or_create_account_finds_existing(db):
    """Test find_or_create_account finds existing account"""
    import uuid
    
    accounts_collection = db['accounts']
    user_id = 'test-user-456'
    
    # Create existing account
    existing_account_id = str(uuid.uuid4())
    accounts_collection.insert_one({
        '_id': existing_account_id,
        'user_id': user_id,
        'name': 'Nubank - Cartão 12345',
        'type': 'credit_card',
        'institution': 'Nubank',
        'is_active': True,
        'balance': 0
    })
    
    account_info = {
        'institution': 'Nubank',
        'account_number': '12345',
        'account_type': 'credit_card'
    }
    
    account_id, was_created = find_or_create_account(
        accounts_collection,
        user_id,
        account_info,
        filename='nubank_12345.csv'
    )
    
    assert account_id == existing_account_id
    assert was_created is False


def test_find_or_create_account_none_info():
    """Test find_or_create_account with None account_info"""
    
    account_id, was_created = find_or_create_account(
        None,
        'user-id',
        None,
        filename='test.csv'
    )
    
    assert account_id is None
    assert was_created is False

def test_parse_import_file_ofx():
    ofx_content = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1001
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>001
<ACCTID>12345
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20230101000000
<DTEND>20230131000000
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20230101000000
<TRNAMT>-100.00
<FITID>20230101001
<MEMO>Test Transaction
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    format, transactions = parse_import_file('test.ofx', ofx_content)
    assert format == 'ofx'
    assert len(transactions) == 1
    assert transactions[0]['description'] == 'Test Transaction'
    assert transactions[0]['amount'] == 100.00 # OFX debit is negative, but usually imported as positive amount with type expense
    assert transactions[0]['type'] == 'expense'

def test_detect_category():
    # Test exact match keywords
    cat = detect_category_from_description('Uber Trip')
    assert cat is not None
    assert cat[0] == 'Transporte'

    cat = detect_category_from_description('Supermercado')
    assert cat is not None
    assert cat[0] == 'Alimentação'

    cat = detect_category_from_description('Unknown Transaction')
    assert cat is not None
    assert cat[0] == 'Outros'

def test_extract_account_info_ofx():
    ofx_content = b"""<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<BANKID>260
<ACCTID>123456
<ACCTTYPE>CHECKING
</BANKACCTFROM>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    info = extract_account_info_from_ofx(ofx_content)
    assert info['bank_id'] == '260' # NuBank
    assert info['account_number'] == '123456'

    assert info['institution'] == 'Nubank'

def test_parse_nubank_csv_old_format():
    csv_content = b"""Data,Valor,Identificador,Descri\xc3\xa7\xc3\xa3o
01/01/2023,-100.00,123,Compra Teste
02/01/2023,5000.00,124,Sal\xc3\xa1rio
"""
    format, transactions = parse_import_file('nubank.csv', csv_content)
    assert format == 'nubank_csv'
    assert len(transactions) == 2
    assert transactions[0]['amount'] == 100.00
    assert transactions[0]['type'] == 'expense'
    assert transactions[1]['amount'] == 5000.00
    assert transactions[1]['type'] == 'income'

def test_parse_nubank_csv_new_format():
    csv_content = b"""date,category,title,amount
2023-01-01,Transporte,Uber,15.90
2023-01-02,Alimentacao,iFood,30.50
"""
    format, transactions = parse_import_file('nubank_card.csv', csv_content)
    assert format == 'nubank_csv'
    assert len(transactions) == 2
    assert transactions[0]['amount'] == 15.90
    assert transactions[0]['type'] == 'expense'

def test_parse_ofx_alternative_fallback():
    # Malformed XML that forces fallback to regex parsing
    ofx_content = b"""<OFX>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20230101
<TRNAMT>-50.00
<MEMO>Fallback Test
</STMTTRN>
</OFX>
"""
    format, transactions = parse_import_file('test.ofx', ofx_content)
    assert format == 'ofx'
    assert len(transactions) == 1
    assert transactions[0]['description'] == 'Fallback Test'
    assert transactions[0]['amount'] == 50.00

def test_parse_ofx_valid_xml():
    # Valid XML OFX that should be parsed by ElementTree
    ofx_content = b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT</TRNTYPE>
            <DTPOSTED>20230101120000</DTPOSTED>
            <TRNAMT>-75.50</TRNAMT>
            <FITID>20230101002</FITID>
            <MEMO>Valid XML Test</MEMO>
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""
    format, transactions = parse_import_file('valid.ofx', ofx_content)
    assert format == 'ofx'
    assert len(transactions) == 1
    assert transactions[0]['description'] == 'Valid XML Test'
    assert transactions[0]['amount'] == 75.50
