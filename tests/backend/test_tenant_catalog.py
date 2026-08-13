"""
tests/backend/test_tenant_catalog.py
Unit tests for src/backend/common/tenant_catalog.py
"""

import pytest
from common.tenant_catalog import (
    CATALOG_VERSION,
    DEFAULT_STATUS,
    DEFAULT_TIER,
    VALID_STATUSES,
    VALID_TIERS,
    get_all_statuses,
    get_all_tier_limits,
    get_all_tiers,
    get_tier_limits,
    get_tier_summary,
    is_valid_status,
    is_valid_tier,
)


class TestTenantCatalog:
    def test_catalog_version_present(self):
        assert CATALOG_VERSION == 'v1'

    def test_default_tier_and_status(self):
        assert DEFAULT_TIER == 'starter'
        assert DEFAULT_STATUS == 'disabled'

    def test_valid_tiers_contains_all_four(self):
        assert VALID_TIERS == frozenset({'starter', 'professional', 'premium', 'enterprise'})
        assert get_all_tiers() == ['enterprise', 'premium', 'professional', 'starter']

    def test_valid_statuses_contains_all_six(self):
        expected = {'active', 'trialing', 'past_due', 'canceled', 'paused', 'disabled'}
        assert VALID_STATUSES == frozenset(expected)
        assert sorted(get_all_statuses()) == sorted(list(expected))

    def test_get_tier_limits_starter(self):
        limits = get_tier_limits('starter')
        assert limits['max_active_clients'] == 20
        assert limits['max_staff'] == 1
        assert limits['google_calendar_enabled'] is False

    def test_get_tier_limits_returns_copy(self):
        limits1 = get_tier_limits('starter')
        limits1['max_staff'] = 999
        limits2 = get_tier_limits('starter')
        assert limits2['max_staff'] == 1  # catalog was not mutated

    def test_complete_catalog_returns_deep_copy(self):
        catalog1 = get_all_tier_limits()
        catalog1['starter']['max_staff'] = 999
        catalog2 = get_all_tier_limits()
        assert catalog2['starter']['max_staff'] == 1

    def test_billing_consumes_catalog_without_exposing_catalog_state(self):
        from common import billing

        assert billing.TIER_LIMITS == get_all_tier_limits()
        original = billing.TIER_LIMITS['starter']['max_staff']
        try:
            billing.TIER_LIMITS['starter']['max_staff'] = 999
            assert get_tier_limits('starter')['max_staff'] == 1
        finally:
            billing.TIER_LIMITS['starter']['max_staff'] = original

    def test_get_tier_limits_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown subscription tier"):
            get_tier_limits('super_ultra_tier')

    def test_get_tier_limits_case_insensitive(self):
        limits = get_tier_limits('PROfessional  ')
        assert limits['max_staff'] == 5
        assert limits['google_calendar_enabled'] is True

    def test_is_valid_tier(self):
        assert is_valid_tier('starter') is True
        assert is_valid_tier('ENTERPRISE') is True
        assert is_valid_tier('invalid') is False
        assert is_valid_tier(None) is False
        assert is_valid_tier(123) is False

    def test_is_valid_status(self):
        assert is_valid_status('active') is True
        assert is_valid_status('DISABLED') is True
        assert is_valid_status('unknown') is False
        assert is_valid_status(None) is False
        assert is_valid_status([]) is False

    def test_get_tier_summary(self):
        summary = get_tier_summary()
        assert len(summary) == 4
        tier_names = [s['tier'] for s in summary]
        assert tier_names == ['starter', 'professional', 'premium', 'enterprise']
        for item in summary:
            assert item['catalog_version'] == 'v1'
            assert 'max_staff' in item['limits']
