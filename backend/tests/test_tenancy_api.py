import os
import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Supabase test database not configured (TEST_DATABASE_URL not set).",
)


def test_tenant_context_placeholder():
    """
    Placeholder test for tenant isolation.

    This test is intentionally minimal and is skipped unless TEST_DATABASE_URL
    is configured. Once a Supabase test instance is wired up, replace this
    with real tenant-aware API tests (see skills/tenant-core/tests/test-strategy.md).
    """
    assert True

