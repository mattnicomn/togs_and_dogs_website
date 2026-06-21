import pytest
import os
import json
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
    
    os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = 'true'
    os.environ['STRIPE_ENV'] = 'production'
    
    yield
    
    if old_enforcement is not None:
        os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = old_enforcement
    else:
        os.environ.pop('ENTITLEMENT_ENFORCEMENT_ENABLED', None)
        
    if old_stripe_env is not None:
        os.environ['STRIPE_ENV'] = old_stripe_env
    else:
        os.environ.pop('STRIPE_ENV', None)


# Helper to parse the JSON logs emitted to common.entitlement.logger
def get_logged_payloads(mock_logger):
    payloads = []
    for call in mock_logger.info.call_args_list:
        log_str = call[0][0]
        try:
            payloads.append(json.loads(log_str))
        except Exception:
            pass
    return payloads


@patch('common.entitlement.logger')
def test_observability_disabled_no_logs(mock_logger):
    """Confirm no logs are written when enforcement is disabled."""
    os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = 'false'
    
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }
        check_subscription_active('test_company')
        check_feature('test_company', 'nonexistent_feature')
        check_limit('test_company', 'max_staff', 999)
        
    assert mock_logger.info.call_count == 0


@patch('common.entitlement.logger')
def test_observability_feature_allowed_denied(mock_logger):
    """Confirm logging of ENTITLEMENT_ALLOWED / ENTITLEMENT_DENIED for feature checks."""
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'professional',
            'subscription_status': 'active'
        }
        
        # 1. Allowed feature
        check_feature('test_company', 'export_enabled')
        
        payloads = get_logged_payloads(mock_logger)
        assert len(payloads) == 2  # 1 for subscription, 1 for feature
        
        # Sub check allowed
        sub_log = payloads[0]
        assert sub_log['event'] == 'ENTITLEMENT_ALLOWED'
        assert sub_log['check_type'] == 'subscription'
        assert sub_log['company_id'] == 'test_company'
        assert sub_log['allowed'] is True
        assert sub_log['protected_admin_bypass'] is False
        
        # Feature check allowed
        feat_log = payloads[1]
        assert feat_log['event'] == 'ENTITLEMENT_ALLOWED'
        assert feat_log['check_type'] == 'feature'
        assert feat_log['feature_key'] == 'export_enabled'
        assert feat_log['company_id'] == 'test_company'
        assert feat_log['allowed'] is True
        assert feat_log['protected_admin_bypass'] is False
        
        # Clear mock call list
        mock_logger.reset_mock()
        
        # 2. Denied feature
        with pytest.raises(EntitlementDenied):
            check_feature('test_company', 'custom_branding_enabled')
            
        payloads2 = get_logged_payloads(mock_logger)
        assert len(payloads2) == 2
        # Feature check denied
        feat_denied_log = payloads2[1]
        assert feat_denied_log['event'] == 'ENTITLEMENT_DENIED'
        assert feat_denied_log['check_type'] == 'feature'
        assert feat_denied_log['feature_key'] == 'custom_branding_enabled'
        assert feat_denied_log['allowed'] is False


@patch('common.entitlement.logger')
def test_observability_limit_allowed_denied(mock_logger):
    """Confirm logging of ENTITLEMENT_ALLOWED / ENTITLEMENT_DENIED for limit checks."""
    with patch('common.db.get_item') as mock_get:
        # Starter limits: max_staff = 1, max_active_clients = 20
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'active'
        }
        
        # 1. Below limit (current=0, max=1)
        check_limit('test_company', 'max_staff', 0)
        
        payloads = get_logged_payloads(mock_logger)
        assert len(payloads) == 2
        limit_log = payloads[1]
        assert limit_log['event'] == 'ENTITLEMENT_ALLOWED'
        assert limit_log['check_type'] == 'limit'
        assert limit_log['limit_key'] == 'max_staff'
        assert limit_log['allowed'] is True
        assert limit_log['current_count'] == 0
        assert limit_log['max_allowed'] == 1
        
        mock_logger.reset_mock()
        
        # 2. At limit (current=1, max=1)
        with pytest.raises(EntitlementDenied):
            check_limit('test_company', 'max_staff', 1)
            
        payloads2 = get_logged_payloads(mock_logger)
        assert len(payloads2) == 2
        limit_denied_log = payloads2[1]
        assert limit_denied_log['event'] == 'ENTITLEMENT_DENIED'
        assert limit_denied_log['check_type'] == 'limit'
        assert limit_denied_log['limit_key'] == 'max_staff'
        assert limit_denied_log['allowed'] is False
        assert limit_denied_log['current_count'] == 1
        assert limit_denied_log['max_allowed'] == 1


@patch('common.entitlement.logger')
def test_observability_subscription_denied(mock_logger):
    """Confirm logging of subscription denials (inactive/past-due)."""
    with patch('common.db.get_item') as mock_get:
        # Inactive/Canceled
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }
        
        with pytest.raises(EntitlementDenied):
            check_subscription_active('test_company')
            
        payloads = get_logged_payloads(mock_logger)
        assert len(payloads) == 1
        assert payloads[0]['event'] == 'ENTITLEMENT_DENIED'
        assert payloads[0]['check_type'] == 'subscription'
        assert payloads[0]['allowed'] is False
        assert "inactive" in payloads[0]['reason'].lower()


@patch('common.entitlement.logger')
def test_observability_protected_admin_bypass(mock_logger):
    """Confirm logging when protected admin bypass is active."""
    with patch('common.db.get_item') as mock_get:
        mock_get.return_value = {
            'PK': 'TENANT#test_company',
            'SK': 'METADATA',
            'company_id': 'test_company',
            'subscription_tier': 'starter',
            'subscription_status': 'canceled'
        }
        
        # Correctly formatted Cognito authorizer event with email and request ID
        context = {
            'requestContext': {
                'requestId': 'req-12345',
                'authorizer': {
                    'claims': {
                        'email': 'support@usmissionhero.com',
                        'sub': '74b86488-1011-7029-bb6d-dad984e1463c'
                    }
                }
            }
        }
        check_subscription_active('test_company', context=context)
        
        payloads = get_logged_payloads(mock_logger)
        assert len(payloads) == 1
        assert payloads[0]['event'] == 'ENTITLEMENT_ALLOWED'
        assert payloads[0]['check_type'] == 'subscription'
        assert payloads[0]['allowed'] is True
        assert payloads[0]['protected_admin_bypass'] is True
        assert payloads[0]['request_id'] == 'req-12345'
        
        # Verify sensitive info is NOT logged
        for k, v in payloads[0].items():
            val_str = str(v)
            assert 'support@usmissionhero.com' not in val_str
            assert 'email' not in val_str

