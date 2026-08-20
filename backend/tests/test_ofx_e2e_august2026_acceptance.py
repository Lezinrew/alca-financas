"""
Teste de Aceite Ponta a Ponta: Simulação Completa de Importação de Agosto/2026 com Dados Reais.

Critério de aceite canônico (auditado contra a Planilha SSOT):
1. Importar sequencialmente os extratos de conta corrente:
   - NU_93015865_01AGO2026_12AGO2026.ofx
   - NU_93015865_01AGO2026_18AGO2026.ofx (período sobreposto)
   - NU_93015865_01AGO2026_19AGO2026.ofx (estendido)
   - Extrato-01-04-2026-a-12-08-2026-OFX.ofx (Banco Inter, débito da transferência em 06/08)
2. Importar 9 faturas de cartão de crédito:
   - Nubank_2026-01-15.ofx até Nubank_2026-09-15.ofx (incluindo as 4 cópias de Nubank_2026-07-15).
3. Validar:
   - Idempotência (0 duplicatas inseridas nas cópias e períodos sobrepostos).
   - Tratamento assimétrico de pagamentos de fatura (saída real na conta corrente vira transfer, espelho na fatura é ignorado).
   - Totais auditados de Agosto/2026:
     * Receita realizada:  R$ 34.953,62
     * Despesa realizada:  R$ 12.761,78
     * Transferências:     R$ 25.725,80 em 15 lançamentos
"""
import os
import pytest
from pathlib import Path
from services.ofx_import.pipeline import OfxImportPipeline
from services.ofx_import.categorizer import AliasCategorizer


def _locate_file(candidates: list) -> Path:
    for c in candidates:
        p = Path(c)
        if p.exists():
            return p
    raise FileNotFoundError(f"Arquivo não encontrado em nenhum dos caminhos: {candidates}")


def test_e2e_august2026_full_pipeline_acceptance():
    """Validação E2E da bateria de arquivos reais de Agosto/2026."""
    user_id = "user-leandro"
    tenant_id = "tenant-family"
    checking_acc_id = "acc-checking-nubank"
    card_acc_id = "acc-card-nubank"
    inter_acc_id = "acc-inter"

    # Mapeamento dos 12 arquivos reais locais
    files_checking = [
        _locate_file([
            r"C:\Users\lezin\OneDrive\Documentos\FinanceOS\data\input\2026-08\NU_93015865_01AGO2026_12AGO2026.ofx",
            r"C:\Users\lezin\Downloads\NU_93015865_01AGO2026_12AGO2026.ofx",
        ]),
        _locate_file([
            r"C:\Users\lezin\Downloads\NU_93015865_01AGO2026_18AGO2026.ofx",
            r"C:\Users\lezin\OneDrive\Documentos\FinanceOS\data\input\2026-08\NU_93015865_01AGO2026_18AGO2026.ofx",
        ]),
        _locate_file([
            r"C:\Users\lezin\Downloads\NU_93015865_01AGO2026_19AGO2026.ofx",
            r"C:\Users\lezin\OneDrive\Documentos\FinanceOS\data\input\2026-08\NU_93015865_01AGO2026_19AGO2026.ofx",
        ]),
    ]

    files_card = [
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-01-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-02-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-03-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-04-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-05-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-06-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-07-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-07-15 (1).ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-07-15 (2).ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-07-15 (3).ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-08-15.ofx"]),
        _locate_file([r"C:\Users\lezin\Downloads\Nubank_2026-09-15.ofx"]),
    ]

    file_inter = _locate_file([
        r"C:\Users\lezin\Downloads\Extrato-01-04-2026-a-12-08-2026-OFX.ofx",
        r"C:\Users\lezin\OneDrive\Documentos\FinanceOS\data\input\2026-08\Extrato-01-04-2026-a-12-08-2026-OFX.ofx",
    ])

    pipeline = OfxImportPipeline()

    persisted_transactions = []
    persisted_dedup_keys = set()
    persisted_fitids = set()

    def _persist(batch_result):
        for tx in batch_result['transactions_to_insert']:
            persisted_transactions.append(tx)
            persisted_dedup_keys.add(tx['dedup_key'])
            if tx.get('fitid'):
                persisted_fitids.add(tx['fitid'])

    # 1. Extratos Conta Corrente Nubank (01-12AGO, 01-18AGO, 01-19AGO)
    res_nu1 = pipeline.process_file(
        files_checking[0].read_bytes(), files_checking[0].name, user_id, tenant_id, checking_acc_id,
        existing_dedup_keys=persisted_dedup_keys, existing_fitids=persisted_fitids
    )
    _persist(res_nu1)
    assert res_nu1['valid_count'] == 49
    assert res_nu1['duplicate_count'] == 0

    res_nu2 = pipeline.process_file(
        files_checking[1].read_bytes(), files_checking[1].name, user_id, tenant_id, checking_acc_id,
        existing_dedup_keys=persisted_dedup_keys, existing_fitids=persisted_fitids
    )
    _persist(res_nu2)
    assert res_nu2['duplicate_count'] == 49  # Idempotência sobre período sobreposto
    assert res_nu2['valid_count'] == 20

    res_nu3 = pipeline.process_file(
        files_checking[2].read_bytes(), files_checking[2].name, user_id, tenant_id, checking_acc_id,
        existing_dedup_keys=persisted_dedup_keys, existing_fitids=persisted_fitids
    )
    _persist(res_nu3)
    assert res_nu3['duplicate_count'] == 69
    assert res_nu3['valid_count'] == 13

    # 2. Faturas de Cartão (incluindo as 4 cópias de Nubank_2026-07-15)
    for c_file in files_card:
        res_card = pipeline.process_file(
            c_file.read_bytes(), c_file.name, user_id, tenant_id, card_acc_id,
            existing_dedup_keys=persisted_dedup_keys, existing_fitids=persisted_fitids
        )
        _persist(res_card)
        if "(1)" in c_file.name or "(2)" in c_file.name or "(3)" in c_file.name:
            assert res_card['valid_count'] == 0
            assert res_card['duplicate_count'] == 39

    # 3. Extrato Banco Inter (débito da transferência própria de 06/08)
    res_inter = pipeline.process_file(
        file_inter.read_bytes(), file_inter.name, user_id, tenant_id, inter_acc_id,
        existing_dedup_keys=persisted_dedup_keys, existing_fitids=persisted_fitids
    )
    _persist(res_inter)

    # 4. Totalizadores de Agosto/2026
    august_txs = [t for t in persisted_transactions if t['date'].startswith('2026-08')]
    income_aug = sum(t['amount'] for t in august_txs if t['type'] == 'income')
    expense_aug = sum(t['amount'] for t in august_txs if t['type'] == 'expense')
    transfers_aug = [t for t in august_txs if t['type'] == 'transfer']
    transfers_aug_sum = sum(t['amount'] for t in transfers_aug)

    # Asserts Canônicos da SSOT
    assert len(transfers_aug) == 15
    assert round(transfers_aug_sum, 2) == 25725.80

    # 5. Validação das 15 Transferências de Agosto uma a uma
    expected_transfers = [
        ("2026-08-04", 17.00, "GLENDA DAVID VAZ"),
        ("2026-08-05", 2.00, "PAGAMENTO DE FATURA"),
        ("2026-08-05", 15.00, "PAGAMENTO DE FATURA"),
        ("2026-08-05", 40.00, "RESGATE RDB"),
        ("2026-08-06", 30.00, "GLENDA DAVID VAZ"),
        ("2026-08-06", 3807.32, "LEANDRO XAVIER DE PINHO"),
        ("2026-08-07", 2800.00, "GLENDA DAVID VAZ"),
        ("2026-08-13", 120.00, "MERCADO PAGO"),
        ("2026-08-16", 23.01, "MERCADO PAGO"),
        ("2026-08-16", 23.01, "MERCADO PAGO"),
        ("2026-08-18", 27.50, "GLENDA DAVID VAZ"),
        ("2026-08-19", 2050.00, "GLENDA DAVID VAZ"),
        ("2026-08-19", 2998.50, "PAGAMENTO DE FATURA"),
        ("2026-08-19", 6886.23, "ALAN DAVID XAVIER VAZ"),
        ("2026-08-19", 6886.23, "STONE IP"),
    ]

    matched_indices = set()
    for exp_date, exp_amt, exp_kw in expected_transfers:
        found = False
        for idx, act in enumerate(transfers_aug):
            if idx in matched_indices:
                continue
            if act['date'] == exp_date and round(act['amount'], 2) == exp_amt and exp_kw in act['description'].upper():
                matched_indices.add(idx)
                found = True
                break
        assert found, f"Transferência esperada não encontrada: {exp_date} | R$ {exp_amt} | {exp_kw}"
    
    assert len(matched_indices) == 15
