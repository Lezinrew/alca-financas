from routes.transactions import _build_transaction_summary


def test_transaction_summary_counts_only_paid_values_and_flags_uncategorized():
    category_map = {
        'salary': {'name': 'Salário'},
        'food': {'name': 'Alimentação'},
        'unknown': {'name': 'Não classificado'},
    }
    transactions = [
        {'type': 'income', 'amount': 1200.10, 'status': 'paid', 'category_id': 'salary'},
        {'type': 'expense', 'amount': 200.05, 'status': 'paid', 'category_id': 'food'},
        {'type': 'expense', 'amount': 50, 'status': 'pending', 'category_id': 'unknown'},
        {'type': 'expense', 'amount': 25, 'status': 'paid', 'category_id': None},
    ]

    assert _build_transaction_summary(transactions, category_map) == {
        'paid_income': 1200.10,
        'paid_expense': 225.05,
        'net_paid': 975.05,
        'transaction_count': 4,
        'uncategorized_count': 2,
    }
