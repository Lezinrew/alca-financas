"""Unicidade de nome de conta por tipo (ex.: carteira e cartão podem compartilhar o mesmo nome)."""
import pytest
from unittest.mock import Mock

from services.account_service import AccountService
from utils.exceptions import ValidationException


def _service_with_repo(account_repo: Mock) -> AccountService:
    return AccountService(account_repo, Mock())


def test_create_credit_card_allowed_when_wallet_same_name_exists():
    repo = Mock(spec=["find_by_user", "find_by_id", "create", "find_by_name_and_type"])
    repo.find_by_name_and_type.return_value = None
    repo.create.return_value = "new-id"

    svc = _service_with_repo(repo)
    svc.create_account(
        "user-1",
        {"name": "Nubank", "type": "credit_card", "limit": 1500},
        tenant_id="tenant-1",
    )

    repo.find_by_name_and_type.assert_called_once_with(
        "user-1", "Nubank", "credit_card", tenant_id="tenant-1"
    )
    repo.create.assert_called_once()


def test_create_rejected_when_same_type_same_name():
    repo = Mock(spec=["find_by_user", "find_by_id", "create", "find_by_name_and_type"])
    repo.find_by_name_and_type.return_value = {
        "id": "existing",
        "name": "Nubank",
        "type": "credit_card",
    }

    svc = _service_with_repo(repo)
    with pytest.raises(ValidationException, match="cartão de crédito"):
        svc.create_account(
            "user-1",
            {"name": "Nubank", "type": "credit_card", "limit": 1500},
            tenant_id="tenant-1",
        )

    repo.create.assert_not_called()


def test_create_legacy_repo_without_find_by_name_and_type_filters_by_type():
    """Repositório só com find_by_name: ignora colisão se o tipo for diferente."""

    class _LegacyRepo:
        def find_by_name(self, user_id, name, tenant_id=None):
            if name == "Nubank":
                return {"id": "w1", "user_id": user_id, "name": "Nubank", "type": "wallet"}
            return None

        def create(self, data):
            return data.get("id", "created")

    repo = _LegacyRepo()
    svc = AccountService(repo, Mock())
    out = svc.create_account(
        "user-1",
        {"name": "Nubank", "type": "credit_card", "limit": 100},
        tenant_id="tenant-1",
    )
    assert out["name"] == "Nubank"
    assert out["type"] == "credit_card"
