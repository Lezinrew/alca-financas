"""Categorias: normalização, get_or_create e equivalência tenant/legado."""
import uuid
from unittest.mock import MagicMock

from services.category_detector import get_or_create_category
from utils.category_name import (
    build_import_category_cache,
    collapse_whitespace_display,
    import_category_cache_key,
    normalize_category_key,
)


def test_normalize_category_key_case_and_spaces():
    assert normalize_category_key("Casa") == normalize_category_key(" casa ")
    assert normalize_category_key("CASA") == "casa"
    assert collapse_whitespace_display("  a   b  ") == "a b"


def test_import_cache_key_includes_type():
    tid = str(uuid.uuid4())
    assert import_category_cache_key("X", "expense", tid) != import_category_cache_key("X", "income", tid)


def test_build_import_category_cache_prefers_tenant_over_legacy():
    tid = str(uuid.uuid4())
    legacy_id = str(uuid.uuid4())
    tenant_id_cat = str(uuid.uuid4())
    cats = [
        {"id": legacy_id, "name": "  Casa ", "type": "expense", "tenant_id": None},
        {"id": tenant_id_cat, "name": "Casa", "type": "expense", "tenant_id": tid},
    ]
    cache = build_import_category_cache(cats, tid)
    k = import_category_cache_key("casa", "expense", tid)
    assert cache[k] == tenant_id_cat


def test_get_or_create_reuses_equivalent_and_does_not_call_create():
    repo = MagicMock()
    existing = {"id": "cat-1", "tenant_id": "t1"}
    repo.find_equivalent_category.return_value = existing
    repo.update = MagicMock(return_value=True)

    svc = MagicMock()
    svc.category_repo = repo
    svc.create_category = MagicMock()

    cid = get_or_create_category(
        svc,
        "user-1",
        "  casa ",
        "expense",
        tenant_id="t1",
    )
    assert cid == "cat-1"
    svc.create_category.assert_not_called()


def test_get_or_create_migrates_legacy_tenant_when_missing():
    repo = MagicMock()
    legacy_id = str(uuid.uuid4())
    repo.find_equivalent_category.return_value = {
        "id": legacy_id,
        "tenant_id": None,
    }
    repo.update = MagicMock(return_value=True)

    svc = MagicMock()
    svc.category_repo = repo
    svc.create_category = MagicMock()

    tid = str(uuid.uuid4())
    cid = get_or_create_category(svc, "user-1", "Pix", "expense", tenant_id=tid)
    assert cid == legacy_id
    repo.update.assert_called_once_with(legacy_id, {"tenant_id": tid})
    svc.create_category.assert_not_called()


def test_get_or_create_creates_when_missing():
    repo = MagicMock()
    repo.find_equivalent_category.return_value = None
    new_id = str(uuid.uuid4())
    svc = MagicMock()
    svc.category_repo = repo
    svc.create_category.return_value = {"id": new_id}

    tid = str(uuid.uuid4())
    cid = get_or_create_category(
        svc,
        "user-1",
        "  Nova Cat  ",
        "income",
        color="#fff",
        icon="x",
        tenant_id=tid,
    )
    assert cid == new_id
    svc.create_category.assert_called_once()
    args, kwargs = svc.create_category.call_args
    assert args[1]["name"] == "Nova Cat"
    assert args[1]["type"] == "income"
