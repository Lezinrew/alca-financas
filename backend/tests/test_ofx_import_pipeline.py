"""
Suíte de testes automatizados para o novo Pipeline de Importação OFX do AlcaHub.

Cobre exaustivamente as 8 falhas identificadas na importação de agosto/2026:
1. Reimportação de arquivo idêntico (idempotência -> 0 duplicatas).
2. Importação incremental de períodos sobrepostos.
3. Fatura de cartão com saldo rotativo e espelhos de pagamento (não infla despesa).
4. Transações simultâneas no mesmo dia com FITIDs distintos.
5. Resiliência de `build_dedup_key` a espaços múltiplos, acentos e zero-width chars.
6. Decodificação UTF-8 pura em OFX com header declarando USASCII/1252.
7. Classificação e exclusão de transferências internas dos totais de receita/despesa.
8. Normalização de lote contra erro PostgREST PGRST102.
"""
import pytest
from datetime import datetime

from services.ofx_import.parser import decode_ofx_bytes, extract_account_metadata, parse_raw_ofx_transactions
from services.ofx_import.nature import classify_nature, TransactionNature
from services.ofx_import.dedup import build_dedup_key, deduplicate_batch
from services.ofx_import.categorizer import AliasCategorizer
from services.ofx_import.normalizer import normalize_batch_objects
from services.ofx_import.pipeline import OfxImportPipeline


# ---------------------------------------------------------------------------
# CENÁRIO 1 & 6: Encoding UTF-8 com Header USASCII/1252
# ---------------------------------------------------------------------------
def test_ofx_encoding_usascii_header_with_utf8_body():
    """Valida que o parser lê UTF-8 mesmo quando o header declara USASCII/1252."""
    ofx_raw = b"""OFXHEADER:100
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
<STMTRS>
<BANKACCTFROM>
<BANKID>0260</BANKID>
<ACCTID>9301586-5</ACCTID>
<ACCTTYPE>CHECKING</ACCTTYPE>
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260801000000
<DTEND>20260819000000
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260816120000</DTPOSTED>
<TRNAMT>-23.01</TRNAMT>
<FITID>nu-tx-001</FITID>
<MEMO>Compra no d\xc3\xa9bito - Ara\xc3\xbajo Loja S\xc3\xa3o Jo\xc3\xa3o</MEMO>
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    decoded = decode_ofx_bytes(ofx_raw)
    assert "Compra no débito - Araujo Loja São João" in decoded or "Araújo" in decoded
    assert "Ã©" not in decoded
    assert "Ãº" not in decoded
    assert "Ã£" not in decoded

    parsed = parse_raw_ofx_transactions(decoded)
    assert len(parsed) == 1
    assert "Araújo" in parsed[0]['memo'] or "Araujo" in parsed[0]['memo']
    assert parsed[0]['amount_signed'] == -23.01


# ---------------------------------------------------------------------------
# CENÁRIO 2 & 5: Deduplicação e Invariância da Chave (`build_dedup_key`)
# ---------------------------------------------------------------------------
def test_build_dedup_key_invariance():
    """Valida que espaços múltiplos, acentos, aspas e caracteres invisíveis geram a mesma chave."""
    # Descrição limpa
    k1 = build_dedup_key("2026-08-16", -23.01, "Compra no debito - Araujo Loja", "Nubank", "fitid-123")
    # Descrição com espaços múltiplos e acentos
    k2 = build_dedup_key("2026-08-16", -23.01, "Compra no débito  -  Araújo   Loja", "Nubank", "fitid-123")
    # Descrição com zero-width space e aspas
    k3 = build_dedup_key("2026-08-16", -23.01, '"Compra no débito\u200b - Araújo  Loja"', "Nubank", "fitid-123")

    assert k1 == k2
    assert k2 == k3
    assert k1 == "2026-08-16|-23.01|COMPRA_NO_DEBITO_-_ARAUJO_LOJA|NUBANK|FITID-123"


# ---------------------------------------------------------------------------
# CENÁRIO 3: Cartão de Crédito com Rotativo e Pagamento Espelho
# ---------------------------------------------------------------------------
def test_credit_card_nature_classification_ignores_rotativo_and_payments():
    """Garante que rotativo, saldo anterior e pagamento de fatura são ignorados no cartão."""
    # 1. Compra normal
    c1 = classify_nature("Restaurante Outback", 150.00, is_credit_card=True)
    assert c1['should_ignore'] is False
    assert c1['type'] == 'expense'

    # 2. Multa e juros (Custo financeiro real)
    c2 = classify_nature("Multa por fatura atrasada", 25.50, is_credit_card=True)
    assert c2['should_ignore'] is False
    assert c2['type'] == 'expense'
    assert c2['suggested_category'] == 'Financeiro'

    # 3. Pagamento de fatura recebido (Espelho do débito em conta corrente)
    c3 = classify_nature("Pagamento recebido", -5000.00, is_credit_card=True)
    assert c3['should_ignore'] is True
    assert "Espelho de pagamento" in c3['ignore_reason']

    # 4. Saldo anterior e rotativo
    c4 = classify_nature("Valor pendente do mês anterior", 9153.62, is_credit_card=True)
    assert c4['should_ignore'] is True
    assert "Saldo rolado" in c4['ignore_reason']

    c5 = classify_nature("Juros de mora e rotativo da fatura", 2132.42, is_credit_card=True)
    assert c5['should_ignore'] is True


# ---------------------------------------------------------------------------
# CENÁRIO 4: Transações Simultâneas no Mesmo Dia com FITIDs Diferentes
# ---------------------------------------------------------------------------
def test_duplicate_amount_same_day_different_fitids_not_collided():
    """Valida que duas transações de mesmo valor no mesmo dia com FITIDs distintos são ambas importadas."""
    pipeline = OfxImportPipeline()
    ofx_content = b"""<OFX>
<CREDITCARDMSGSRSV1>
<CCSTMTTRNRS>
<CCSTMTRS>
<CCACCTFROM>
<ACCTID>62a4e658-8919-4132-9f86-99ef128e2f8c</ACCTID>
</CCACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260816100000</DTPOSTED>
<TRNAMT>23.01</TRNAMT>
<FITID>fitid-alpha-001</FITID>
<MEMO>Drogaria Araujo</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260816140000</DTPOSTED>
<TRNAMT>23.01</TRNAMT>
<FITID>fitid-beta-002</FITID>
<MEMO>Drogaria Araujo</MEMO>
</STMTTRN>
</BANKTRANLIST>
</CCSTMTRS>
</CCSTMTTRNRS>
</CREDITCARDMSGSRSV1>
</OFX>"""

    res = pipeline.process_file(
        content=ofx_content,
        filename="Nubank_2026-08-16.ofx",
        user_id="user-1",
        tenant_id="tenant-1",
        account_id="acc-card-1",
    )

    assert res['total_parsed'] == 2
    assert res['valid_count'] == 2
    assert res['duplicate_count'] == 0
    assert len(res['transactions_to_insert']) == 2
    # FITIDs preservados individualmente
    assert res['transactions_to_insert'][0]['fitid'] == 'fitid-alpha-001'
    assert res['transactions_to_insert'][1]['fitid'] == 'fitid-beta-002'
    assert res['transactions_to_insert'][0]['dedup_key'] != res['transactions_to_insert'][1]['dedup_key']


# ---------------------------------------------------------------------------
# CENÁRIO 7: Transferência Interna com type='transfer'
# ---------------------------------------------------------------------------
def test_internal_transfer_classified_and_excluded_from_cashflow():
    """Valida que aplicações, resgates e Pix próprio viram type='transfer'."""
    # Aplicação RDB
    n1 = classify_nature("Aplicacao: RDB Resgate Diario", -1000.00, is_credit_card=False)
    assert n1['type'] == 'transfer'
    assert n1['nature'] == TransactionNature.TRANSFER

    # Resgate RDB
    n2 = classify_nature("Resgate RDB", 500.00, is_credit_card=False)
    assert n2['type'] == 'transfer'

    # Pix para mesma titularidade
    n3 = classify_nature(
        "Transferência enviada pelo Pix - LEANDRO XAVIER DE PINHO",
        -350.00,
        is_credit_card=False,
        user_name="Leandro Xavier de Pinho"
    )
    assert n3['type'] == 'transfer'

    # Processamento em pipeline
    pipeline = OfxImportPipeline()
    ofx_content = b"""<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM><ACCTID>9301586-5</ACCTID></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20260805120000</DTPOSTED>
<TRNAMT>5000.00</TRNAMT>
<FITID>salario-001</FITID>
<MEMO>Pagamento Salario PDCase</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260805130000</DTPOSTED>
<TRNAMT>-2000.00</TRNAMT>
<FITID>invest-001</FITID>
<MEMO>Aplicacao: RDB Resgate Diario</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260805140000</DTPOSTED>
<TRNAMT>-100.00</TRNAMT>
<FITID>super-001</FITID>
<MEMO>Supermercado EPA</MEMO>
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""

    res = pipeline.process_file(
        content=ofx_content,
        filename="nu_conta.ofx",
        user_id="user-1",
        tenant_id="tenant-1",
        account_id="acc-checking-1",
    )

    # 1 receita (R$ 5.000), 1 despesa (R$ 100), 1 transferência (R$ 2.000)
    assert res['summary']['total_income'] == 5000.00
    assert res['summary']['total_expense'] == 100.00
    assert res['summary']['total_transfer'] == 2000.00
    assert res['summary']['net_cashflow'] == 4900.00  # 5000 - 100 (a transferência não entra na despesa)


# ---------------------------------------------------------------------------
# CENÁRIO 8: Normalização de Lote de Objetos (Elimina PGRST102)
# ---------------------------------------------------------------------------
def test_normalize_batch_objects_ensures_identical_keys():
    """Garante que dicionários heterogêneos ganham todas as chaves com None."""
    obj1 = {'id': '1', 'amount': 100.0, 'description': 'Item 1'}
    obj2 = {'id': '2', 'amount': 50.0, 'fitid': 'fit-99', 'source_file': 'extrato.ofx'}
    obj3 = {'id': '3', 'amount': 20.0, 'installment_info': {'current': 1, 'total': 3}}

    normalized = normalize_batch_objects([obj1, obj2, obj3])
    assert len(normalized) == 3

    # Todos devem possuir exatamente as mesmas chaves
    keys1 = set(normalized[0].keys())
    keys2 = set(normalized[1].keys())
    keys3 = set(normalized[2].keys())

    assert keys1 == keys2 == keys3
    assert 'fitid' in keys1
    assert 'installment_info' in keys1
    assert 'source_file' in keys1

    assert normalized[0]['fitid'] is None
    assert normalized[1]['installment_info'] is None
    assert normalized[0]['description'] == 'Item 1'


# ---------------------------------------------------------------------------
# TESTE INTEGRADO: Importação Sequencial com Sobreposição
# ---------------------------------------------------------------------------
def test_sequential_overlapping_import_idempotency():
    """Testa importação sequencial de períodos sobrepostos (01-12AGO -> 01-18AGO)."""
    # Lote 1: Dias 01 e 05
    ofx_p1 = b"""<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260801</DTPOSTED><TRNAMT>-50.00</TRNAMT><FITID>tx-01</FITID><MEMO>Compra A</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260805</DTPOSTED><TRNAMT>-70.00</TRNAMT><FITID>tx-02</FITID><MEMO>Compra B</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""

    # Lote 2: Dias 01, 05 e 18 (Incremento do dia 18)
    ofx_p2 = b"""<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260801</DTPOSTED><TRNAMT>-50.00</TRNAMT><FITID>tx-01</FITID><MEMO>Compra A</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260805</DTPOSTED><TRNAMT>-70.00</TRNAMT><FITID>tx-02</FITID><MEMO>Compra B</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260818</DTPOSTED><TRNAMT>-120.00</TRNAMT><FITID>tx-03</FITID><MEMO>Compra C Nova</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""

    pipeline = OfxImportPipeline()
    
    # 1ª Importação
    res1 = pipeline.process_file(ofx_p1, "p1.ofx", "u1", "t1", "acc1")
    assert res1['valid_count'] == 2
    assert res1['duplicate_count'] == 0

    # Simula chaves já persistidas no banco a partir do Lote 1
    existing_keys = {t['dedup_key'] for t in res1['transactions_to_insert']}
    existing_fits = {t['fitid'] for t in res1['transactions_to_insert']}

    # 2ª Importação (Período estendido sobreposto)
    res2 = pipeline.process_file(
        ofx_p2,
        "p2.ofx",
        "u1",
        "t1",
        "acc1",
        existing_dedup_keys=existing_keys,
        existing_fitids=existing_fits
    )
    assert res2['total_parsed'] == 3
    assert res2['duplicate_count'] == 2  # As duas primeiras foram detectadas como duplicatas
    assert res2['valid_count'] == 1      # Apenas a nova 'Compra C Nova' entra
    assert res2['transactions_to_insert'][0]['fitid'] == 'tx-03'


# ---------------------------------------------------------------------------
# CENÁRIO 9: Tratamento Assimétrico de Pagamento de Fatura (Tarefa 3)
# ---------------------------------------------------------------------------
def test_asymmetric_invoice_payment_treatment():
    """
    Garante tratamento assimétrico entre Conta Corrente e Fatura de Cartão:
    1. Extrato de Conta Corrente com 'Pagamento de fatura' -> saída real de caixa -> type='transfer', should_ignore=False.
    2. Fatura de Cartão com 'Pagamento recebido' -> espelho do mesmo movimento -> should_ignore=True (ignored_invoice_payment).
    Valida que a conta corrente vira transfer e o cartão é descartado (nunca ambos descartados, nunca ambos lançados).
    """
    pipeline = OfxImportPipeline()

    # 1. Extrato Conta Corrente com pagamento de fatura
    ofx_checking = b"""<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><ACCTID>9301586-5</ACCTID></BANKACCTFROM><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260819120000</DTPOSTED>
<TRNAMT>-2998.50</TRNAMT>
<FITID>fitid-cc-pay-01</FITID>
<MEMO>Pagamento de fatura</MEMO>
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""

    # 2. Fatura de Cartão com espelho de pagamento recebido
    ofx_card = b"""<OFX>
<CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS><CCACCTFROM><ACCTID>card-nubank-001</ACCTID></CCACCTFROM><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20260819120000</DTPOSTED>
<TRNAMT>-2998.50</TRNAMT>
<FITID>fitid-card-pay-mirror-01</FITID>
<MEMO>Pagamento recebido</MEMO>
</STMTTRN>
</BANKTRANLIST></CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1>
</OFX>"""

    # Processa Conta Corrente
    res_cc = pipeline.process_file(
        content=ofx_checking,
        filename="extrato_conta_corrente.ofx",
        user_id="user-1",
        tenant_id="tenant-1",
        account_id="acc-checking",
    )
    assert res_cc['valid_count'] == 1
    assert res_cc['ignored_count'] == 0
    assert len(res_cc['transactions_to_insert']) == 1
    assert res_cc['transactions_to_insert'][0]['type'] == 'transfer'
    assert res_cc['transactions_to_insert'][0]['amount'] == 2998.50
    assert res_cc['summary']['total_transfer'] == 2998.50
    assert res_cc['summary']['total_expense'] == 0.00
    assert res_cc['summary']['total_income'] == 0.00

    # Processa Fatura do Cartão
    res_card = pipeline.process_file(
        content=ofx_card,
        filename="fatura_cartao.ofx",
        user_id="user-1",
        tenant_id="tenant-1",
        account_id="acc-card",
    )
    assert res_card['valid_count'] == 0
    assert res_card['ignored_count'] == 1
    assert len(res_card['transactions_to_insert']) == 0
    assert res_card['ignored_transactions'][0]['nature'] == TransactionNature.IGNORED_INVOICE_PAYMENT
    assert res_card['summary']['total_expense'] == 0.00
    assert res_card['summary']['total_income'] == 0.00
    assert res_card['summary']['total_transfer'] == 0.00

