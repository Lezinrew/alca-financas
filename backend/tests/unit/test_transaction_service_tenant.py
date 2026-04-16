"""
Unit tests for transaction service tenant resolution (account_tenant_id, category_tenant_id).
Garante que criação/parcelas/update usam registros reais de accounts e categories e validam tenant.
"""
import pytest
from services.transaction_service import (
    _resolve_transaction_tenant_ids,
    TransactionService,
)
from utils.exceptions import ValidationException


TENANT_ID = "tenant-uuid-1"
USER_ID = "user-uuid-1"
ACCOUNT_ID = "account-uuid-1"
CATEGORY_ID = "category-uuid-1"


def test_resolve_tenant_ids_sem_conta_nem_categoria():
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: None})()
    acc_tenant, cat_tenant = _resolve_transaction_tenant_ids(
        TENANT_ID, None, None, USER_ID, accounts_repo, categories_repo
    )
    assert acc_tenant == TENANT_ID
    assert cat_tenant == TENANT_ID


def test_resolve_tenant_ids_conta_encontrada_mesmo_tenant():
    account = {"user_id": USER_ID, "tenant_id": TENANT_ID}
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: account if x == ACCOUNT_ID else None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: None})()
    acc_tenant, cat_tenant = _resolve_transaction_tenant_ids(
        TENANT_ID, ACCOUNT_ID, None, USER_ID, accounts_repo, categories_repo
    )
    assert acc_tenant == TENANT_ID
    assert cat_tenant == TENANT_ID


def test_resolve_tenant_ids_conta_nao_encontrada():
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: None})()
    with pytest.raises(ValidationException) as exc:
        _resolve_transaction_tenant_ids(
            TENANT_ID, ACCOUNT_ID, None, USER_ID, accounts_repo, categories_repo
        )
    assert "Conta não encontrada" in str(exc.value)


def test_resolve_tenant_ids_conta_outro_tenant():
    account = {"user_id": USER_ID, "tenant_id": "outro-tenant"}
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: account if x == ACCOUNT_ID else None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: None})()
    with pytest.raises(ValidationException) as exc:
        _resolve_transaction_tenant_ids(
            TENANT_ID, ACCOUNT_ID, None, USER_ID, accounts_repo, categories_repo
        )
    assert "não pertence ao workspace" in str(exc.value)


def test_resolve_tenant_ids_categoria_nao_encontrada():
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: None})()
    with pytest.raises(ValidationException) as exc:
        _resolve_transaction_tenant_ids(
            TENANT_ID, None, CATEGORY_ID, USER_ID, accounts_repo, categories_repo
        )
    assert "Categoria não encontrada" in str(exc.value)


def test_resolve_tenant_ids_categoria_outro_tenant():
    category = {"tenant_id": "outro-tenant"}
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: category if x == CATEGORY_ID else None})()
    with pytest.raises(ValidationException) as exc:
        _resolve_transaction_tenant_ids(
            TENANT_ID, None, CATEGORY_ID, USER_ID, accounts_repo, categories_repo
        )
    assert "não pertence ao workspace" in str(exc.value)


def test_resolve_tenant_ids_conta_sem_tenant_id_usa_request_tenant():
    account = {"user_id": USER_ID, "tenant_id": None}
    accounts_repo = type("AccountsRepo", (), {"find_by_id": lambda self, x: account if x == ACCOUNT_ID else None})()
    categories_repo = type("CategoriesRepo", (), {"find_by_id": lambda self, x: None})()
    acc_tenant, cat_tenant = _resolve_transaction_tenant_ids(
        TENANT_ID, ACCOUNT_ID, None, USER_ID, accounts_repo, categories_repo
    )
    assert acc_tenant == TENANT_ID
    assert cat_tenant == TENANT_ID


def test_create_transaction_preenche_tenant_ids_no_payload():
    created_ids = []

    def mock_create(_self, data):
        if data.get("category_id") and not data.get("category_tenant_id"):
            raise ValueError("category_tenant_id obrigatório")
        if data.get("account_id") and not data.get("account_tenant_id"):
            raise ValueError("account_tenant_id obrigatório")
        created_ids.append(data)
        return data.get("id")

    account = {"user_id": USER_ID, "tenant_id": TENANT_ID}
    category = {"tenant_id": TENANT_ID}
    transaction_repo = type("TxRepo", (), {"create": mock_create})()
    accounts_repo = type("AccRepo", (), {"find_by_id": lambda self, x: account if x == ACCOUNT_ID else None})()
    categories_repo = type("CatRepo", (), {"find_by_id": lambda self, x: category if x == CATEGORY_ID else None})()
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)
    payload = {
        "description": "Despesa teste",
        "amount": "100,00",
        "date": "2026-03-15",
        "type": "expense",
        "account_id": ACCOUNT_ID,
        "category_id": CATEGORY_ID,
    }
    result = service.create_transaction(USER_ID, payload, tenant_id=TENANT_ID)
    assert result["count"] == 1
    assert len(created_ids) == 1
    tx_data = created_ids[0]
    assert tx_data["account_tenant_id"] == TENANT_ID
    assert tx_data["category_tenant_id"] == TENANT_ID
    assert tx_data["tenant_id"] == TENANT_ID


def test_create_transaction_sem_tenant_id_levanta():
    transaction_repo = type("TxRepo", (), {"create": lambda self, x: x.get("id")})()
    accounts_repo = type("AccRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CatRepo", (), {"find_by_id": lambda self, x: None})()
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)
    payload = {
        "description": "Despesa",
        "amount": "50",
        "date": "2026-03-15",
        "type": "expense",
    }
    with pytest.raises(ValidationException) as exc:
        service.create_transaction(USER_ID, payload, tenant_id=None)
    assert "Workspace" in str(exc.value)


def test_create_transaction_categoria_invalida_levanta():
    transaction_repo = type("TxRepo", (), {"create": lambda self, x: x.get("id")})()
    accounts_repo = type("AccRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CatRepo", (), {"find_by_id": lambda self, x: None})()
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)
    payload = {
        "description": "Despesa",
        "amount": "50",
        "date": "2026-03-15",
        "type": "expense",
        "category_id": "categoria-inexistente",
    }
    with pytest.raises(ValidationException) as exc:
        service.create_transaction(USER_ID, payload, tenant_id=TENANT_ID)
    assert "Categoria" in str(exc.value)


def test_create_transaction_conta_invalida_levanta():
    transaction_repo = type("TxRepo", (), {"create": lambda self, x: x.get("id")})()
    accounts_repo = type("AccRepo", (), {"find_by_id": lambda self, x: None})()
    categories_repo = type("CatRepo", (), {"find_by_id": lambda self, x: None})()
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)
    payload = {
        "description": "Despesa",
        "amount": "50",
        "date": "2026-03-15",
        "type": "expense",
        "account_id": "conta-inexistente",
    }
    with pytest.raises(ValidationException) as exc:
        service.create_transaction(USER_ID, payload, tenant_id=TENANT_ID)
    assert "Conta" in str(exc.value)
