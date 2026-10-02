"""
Tests for report service functions
"""
import pytest
from datetime import datetime
from services.report_service import dashboard_summary, monthly_evolution, overview_report, comparison_report


def test_dashboard_summary_with_transactions(db, test_user, test_category, test_account):
    """Test dashboard summary with transactions"""
    transactions_collection = db['transactions']
    categories_collection = db['categories']
    
    # Create test transactions
    transactions_collection.insert_many([
        {
            '_id': 'tx1',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 1000.0,
            'type': 'income',
            'description': 'Salary',
            'date': datetime(2025, 1, 15)
        },
        {
            '_id': 'tx2',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 500.0,
            'type': 'expense',
            'description': 'Groceries',
            'date': datetime(2025, 1, 20)
        }
    ])
    
    result = dashboard_summary(transactions_collection, categories_collection, test_user['_id'], 1, 2025)
    
    assert result['summary']['total_income'] == 1000.0
    assert result['summary']['total_expense'] == 500.0
    assert result['summary']['balance'] == 500.0
    assert result['summary']['transactions_count'] == 2
    assert len(result['recent_transactions']) > 0


def test_monthly_evolution(db, test_user, test_category, test_account):
    """Test monthly evolution report"""
    transactions_collection = db['transactions']
    
    # Create transactions for different months
    transactions_collection.insert_many([
        {
            '_id': 'tx1',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 1000.0,
            'type': 'income',
            'description': 'Income',
            'date': datetime.now()
        },
        {
            '_id': 'tx2',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 300.0,
            'type': 'expense',
            'description': 'Expense',
            'date': datetime.now()
        }
    ])
    
    result = monthly_evolution(transactions_collection, test_user['_id'], 3)
    
    assert isinstance(result, list)
    assert len(result) == 3
    assert 'income' in result[0]
    assert 'expense' in result[0]
    assert 'balance' in result[0]


def test_overview_report_expenses_by_category(db, test_user, test_category, test_account):
    """Test overview report for expenses by category"""
    transactions_collection = db['transactions']
    categories_collection = db['categories']
    accounts_collection = db['accounts']
    
    # Create test transaction
    transactions_collection.insert_one({
        '_id': 'tx1',
        'user_id': test_user['_id'],
        'category_id': test_category['_id'],
        'account_id': test_account['_id'],
        'amount': 500.0,
        'type': 'expense',
        'description': 'Test',
        'date': datetime(2025, 1, 15)
    })
    
    result = overview_report(
        transactions_collection,
        categories_collection,
        accounts_collection,
        test_user['_id'],
        1,
        2025,
        'expenses_by_category'
    )
    
    assert result['report_type'] == 'expenses_by_category'
    assert 'data' in result
    assert result['total_amount'] == 500.0


def test_overview_report_income_by_category(db, test_user, test_category, test_account):
    """Test overview report for income by category"""
    transactions_collection = db['transactions']
    categories_collection = db['categories']
    accounts_collection = db['accounts']
    
    transactions_collection.insert_one({
        '_id': 'tx1',
        'user_id': test_user['_id'],
        'category_id': test_category['_id'],
        'account_id': test_account['_id'],
        'amount': 1000.0,
        'type': 'income',
        'description': 'Salary',
        'date': datetime(2025, 1, 15)
    })
    
    result = overview_report(
        transactions_collection,
        categories_collection,
        accounts_collection,
        test_user['_id'],
        1,
        2025,
        'income_by_category'
    )
    
    assert result['report_type'] == 'income_by_category'
    assert result['total_amount'] == 1000.0


def test_overview_report_balance_by_account(db, test_user, test_account):
    """Test overview report for balance by account"""
    transactions_collection = db['transactions']
    categories_collection = db['categories']
    accounts_collection = db['accounts']
    
    result = overview_report(
        transactions_collection,
        categories_collection,
        accounts_collection,
        test_user['_id'],
        1,
        2025,
        'balance_by_account'
    )
    
    assert result['report_type'] == 'balance_by_account'
    assert 'data' in result


def test_comparison_report(db, test_user, test_category, test_account):
    """Test comparison report between months"""
    transactions_collection = db['transactions']
    
    # Current month transactions
    transactions_collection.insert_many([
        {
            '_id': 'tx1',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 2000.0,
            'type': 'income',
            'description': 'Current Income',
            'date': datetime(2025, 1, 15)
        },
        {
            '_id': 'tx2',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 800.0,
            'type': 'expense',
            'description': 'Current Expense',
            'date': datetime(2025, 1, 20)
        },
        # Previous month transactions
        {
            '_id': 'tx3',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 1500.0,
            'type': 'income',
            'description': 'Previous Income',
            'date': datetime(2024, 12, 15)
        },
        {
            '_id': 'tx4',
            'user_id': test_user['_id'],
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'amount': 600.0,
            'type': 'expense',
            'description': 'Previous Expense',
            'date': datetime(2024, 12, 20)
        }
    ])
    
    result = comparison_report(transactions_collection, test_user['_id'], 1, 2025)
    
    assert 'current_period' in result
    assert 'previous_period' in result
    assert 'variations' in result
    assert result['current_period']['income'] == 2000.0
    assert result['current_period']['expense'] == 800.0
    assert result['previous_period']['income'] == 1500.0
    assert result['previous_period']['expense'] == 600.0
