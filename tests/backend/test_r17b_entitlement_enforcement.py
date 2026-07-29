import pytest
import os
from unittest.mock import patch, MagicMock
from common.entitlement import (
    check_subscription_active,
    check_feature,
    check_limit,
    EntitlementDenied
)
from common.billing import TenantEntitlement


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure environment is reset between tests."""
    old_enforcement = os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED')
    old_stripe_env = os.environ.get('STRIPE_ENV')
    
    # Defaults
    os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = 'true'
    os.environ['STRIPE_ENV'] = 'production'  # Live mode by default for tests to verify checks
    
    yield
    
    if old_enforcement is not None:
        os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = old_enforcement
    else:
        os.environ.pop('ENTITLEMENT_ENFORCEMENT_ENABLED', None)
        
    if old_stripe_env is not None:
        os.environ['STRIPE_ENV'] = old_stripe_env
    else:
        os.environ.pop('STRIPE_ENV', None)


# 1. Enforcement disabled allows all
def test_enforcement_disabled_allows_all():
    os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = 'false'
    
    # Should allow disabled/canceled status
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }
        
        # Allows subscription check
        ent = check_subscription_active('test_company')
        assert ent.subscription_status == 'active'  # Default fail-open tier status returned when disabled

        # Allows any feature
        check_feature('test_company', 'nonexistent_feature')
        
        # Allows limits over threshold
        check_limit('test_company', 'max_staff', 99999)


# 2. Active professional tenant allows expected professional features
def test_active_professional_tenant_features():
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'professional',
            'subscription_status': 'active'
        }
        
        # Subscription active check
        ent = check_subscription_active('test_company')
        assert ent.subscription_tier == 'professional'
        assert ent.subscription_status == 'active'

        # Feature allowed (professional features)
        check_feature('test_company', 'google_calendar_enabled')
        check_feature('test_company', 'export_enabled')

        # Feature denied (premium feature)
        with pytest.raises(EntitlementDenied) as exc_info:
            check_feature('test_company', 'custom_branding_enabled')
        assert "feature requires a higher plan" in str(exc_info.value)
        assert exc_info.value.upgrade_hint == 'upgrade'


# 3. Blocked/canceled/suspended status behavior
def test_blocked_canceled_suspended_status():
    with patch('common.db.get_item') as mock_get:
        # Canceled status
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }
        with pytest.raises(EntitlementDenied) as exc_info:
            check_subscription_active('test_company')
        assert "inactive" in str(exc_info.value)
        assert exc_info.value.upgrade_hint == 'resubscribe'

        # Paused status
        mock_get.return_value['subscription_status'] = 'paused'
        with pytest.raises(EntitlementDenied) as exc_info:
            check_subscription_active('test_company')
        assert "inactive" in str(exc_info.value)
        
        # Disabled status
        mock_get.return_value['subscription_status'] = 'disabled'
        with pytest.raises(EntitlementDenied) as exc_info:
            check_subscription_active('test_company')
        assert "inactive" in str(exc_info.value)

        # Past due - within grace period (default when no changed_at provided)
        mock_get.return_value['subscription_status'] = 'past_due'
        ent = check_subscription_active('test_company')
        assert ent.subscription_status == 'past_due'

        # Past due - expired grace, within read-only period (e.g. changed 10 days ago)
        import datetime
        from common.billing import GRACE_PERIOD_SECONDS
        ten_days_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)).isoformat()
        mock_get.return_value['billing_status_changed_at'] = ten_days_ago
        
        with pytest.raises(EntitlementDenied) as exc_info:
            check_subscription_active('test_company')
        assert "past due. Read-only access" in str(exc_info.value)
        assert exc_info.value.upgrade_hint == 'update_payment'

        # Past due - completely blocked (e.g. changed 20 days ago)
        twenty_days_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=20)).isoformat()
        mock_get.return_value['billing_status_changed_at'] = twenty_days_ago
        
        with pytest.raises(EntitlementDenied) as exc_info:
            check_subscription_active('test_company')
        assert "inactive" in str(exc_info.value)
        assert exc_info.value.upgrade_hint == 'resubscribe'


# 4. Limit behavior (under, at, over threshold)
def test_limit_thresholds():
    with patch('common.db.get_item') as mock_get:
        # Starter limits: max_staff = 1, max_active_clients = 20
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'active'
        }

        # Under threshold: current_value = 0 (max 1) -> allows
        check_limit('test_company', 'max_staff', 0)

        # At threshold: current_value = 1 (max 1) -> denies
        with pytest.raises(EntitlementDenied) as exc_info:
            check_limit('test_company', 'max_staff', 1)
        assert "Limit reached" in str(exc_info.value)
        assert exc_info.value.upgrade_hint == 'upgrade'

        # Over threshold: current_value = 2 (max 1) -> denies
        with pytest.raises(EntitlementDenied) as exc_info:
            check_limit('test_company', 'max_staff', 2)
        assert "Limit reached" in str(exc_info.value)


# 5. Missing tenant behavior (fails open)
def test_missing_tenant_fails_open():
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = None
        
        # Should allow subscription and return active starter tier
        ent = check_subscription_active('missing_company')
        assert ent.subscription_tier == 'starter'
        assert ent.subscription_status == 'active'


# 6. Load error behavior (fails open)
def test_load_error_fails_open():
    with patch('common.db.get_item') as mock_get:
        mock_get.side_effect = Exception("DynamoDB connection timeout")
        
        # Should allow subscription and return active starter tier
        ent = check_subscription_active('test_company')
        assert ent.subscription_tier == 'starter'
        assert ent.subscription_status == 'active'


# 7. Protected/root admin bypass
def test_protected_admin_bypass():
    with patch('common.db.get_item') as mock_get:
        # A canceled/blocked tenant
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }

        # Context: Protected root admin email (support@usmissionhero.com fallback)
        context_email = {'email': 'support@usmissionhero.com'}
        check_subscription_active('test_company', context=context_email)
        
        # Context: Protected sub in claims (via environment variable configuration)
        with patch.dict(os.environ, {'PROTECTED_ADMIN_SUBS': 'custom-protected-sub'}):
            context_sub = {'sub': 'custom-protected-sub'}
            check_subscription_active('test_company', context=context_sub)

        # Context: API Gateway Event with protected claims
        event = {
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'email': 'support@usmissionhero.com',
                        'sub': 'some-sub'
                    }
                }
            }
        }
        check_subscription_active('test_company', context=event)


# 8. Sandbox behavior
def test_sandbox_behavior():
    os.environ['STRIPE_ENV'] = 'sandbox'
    
    with patch('common.db.get_item') as mock_get:
        # Canceled status
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }
        
        # Sandbox skips lifecycle blocks -> allows active check
        check_subscription_active('test_company')

        # Sandbox STILL evaluates limits
        with pytest.raises(EntitlementDenied):
            check_limit('test_company', 'max_staff', 1)


# 9. Unknown tier fallback behavior
def test_unknown_tier_fallback():
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'nonexistent_tier',
            'subscription_status': 'active'
        }
        
        ent = check_subscription_active('test_company')
        # Should fall back to starter limits (max_staff = 1)
        assert ent.limits.get('max_staff') == 1
        
        with pytest.raises(EntitlementDenied):
            check_limit('test_company', 'max_staff', 1)
