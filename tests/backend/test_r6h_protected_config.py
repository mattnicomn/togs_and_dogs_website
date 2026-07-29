"""
Release 6H: Tests for configurable protected admin accounts.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock


# --- Shared Module Tests ---

def test_fallback_defaults_when_env_empty():
    """When env vars are empty, fallback defaults are still protected."""
    with patch.dict(os.environ, {'PROTECTED_ADMIN_EMAILS': '', 'PROTECTED_ADMIN_SUBS': ''}, clear=False):
        from common.protected_accounts import get_protected_emails, get_protected_subs, is_protected_email, is_protected_sub
        import importlib
        import common.protected_accounts as pa
        importlib.reload(pa)
        
        emails = pa.get_protected_emails()
        assert "support@usmissionhero.com" in emails
        assert "admin@toganddogs.com" not in emails
        assert "mbn@usmissionhero.com" not in emails
        
        subs = pa.get_protected_subs()
        assert len(subs) == 0
        
        assert pa.is_protected_email("support@usmissionhero.com") == True
        assert pa.is_protected_email("admin@toganddogs.com") == False
    print("PASS: test_fallback_defaults_when_env_empty")


def test_configured_env_values_are_protected():
    """Emails added via env var should be protected."""
    with patch.dict(os.environ, {'PROTECTED_ADMIN_EMAILS': 'new-admin@example.com,extra@test.com', 'PROTECTED_ADMIN_SUBS': 'new-sub-123'}, clear=False):
        import importlib
        import common.protected_accounts as pa
        importlib.reload(pa)
        
        assert pa.is_protected_email("new-admin@example.com") == True
        assert pa.is_protected_email("extra@test.com") == True
        assert pa.is_protected_sub("new-sub-123") == True
        # Fallback defaults still included
        assert pa.is_protected_email("support@usmissionhero.com") == True
    print("PASS: test_configured_env_values_are_protected")


def test_non_protected_email_not_blocked():
    """Normal emails should not be protected."""
    with patch.dict(os.environ, {'PROTECTED_ADMIN_EMAILS': '', 'PROTECTED_ADMIN_SUBS': ''}, clear=False):
        import importlib
        import common.protected_accounts as pa
        importlib.reload(pa)
        
        assert pa.is_protected_email("normalclient@gmail.com") == False
        assert pa.is_protected_email("staff@toganddogs.com") == False
        assert pa.is_protected_sub("random-sub-456") == False
    print("PASS: test_non_protected_email_not_blocked")


def test_is_protected_profile_checks_both():
    """is_protected_profile should check both email and sub."""
    with patch.dict(os.environ, {'PROTECTED_ADMIN_EMAILS': '', 'PROTECTED_ADMIN_SUBS': 'sub-protected-123'}, clear=False):
        import importlib
        import common.protected_accounts as pa
        importlib.reload(pa)
        
        # Protected by email
        assert pa.is_protected_profile({"email": "support@usmissionhero.com", "cognito_sub": None}) == True
        # Protected by sub
        assert pa.is_protected_profile({"email": "other@test.com", "cognito_sub": "sub-protected-123"}) == True
        # Not protected
        assert pa.is_protected_profile({"email": "normal@test.com", "cognito_sub": "random"}) == False
        # None/empty
        assert pa.is_protected_profile(None) == False
        assert pa.is_protected_profile({}) == False
    print("PASS: test_is_protected_profile_checks_both")


def test_case_insensitive_email():
    """Email matching should be case-insensitive."""
    with patch.dict(os.environ, {'PROTECTED_ADMIN_EMAILS': '', 'PROTECTED_ADMIN_SUBS': ''}, clear=False):
        import importlib
        import common.protected_accounts as pa
        importlib.reload(pa)
        
        assert pa.is_protected_email("SUPPORT@USMISSIONHERO.COM") == True
        assert pa.is_protected_email("Support@USMissionHero.com") == True
    print("PASS: test_case_insensitive_email")


# --- Client Profile Auto-Creation Tests ---

def test_client_profile_skips_protected_email():
    """auto_create_or_link_client_profile should skip protected emails."""
    from unittest.mock import MagicMock
    from common.client_profile import auto_create_or_link_client_profile
    
    request_item = {"client_email": "support@usmissionhero.com", "client_name": "Admin"}
    
    with patch('common.client_profile.table') as mock_table:
        mock_table.update_item = MagicMock()
        result = auto_create_or_link_client_profile(
            request_item=request_item, request_id="test-1", client_id="c-1",
            company_id="tog_and_dogs", updated_by="system"
        )
    
    assert result["action"] == "skipped"
    assert result["link_status"] == "SKIPPED_PROTECTED_EMAIL"
    print("PASS: test_client_profile_skips_protected_email")


def test_client_profile_allows_normal_email():
    """Normal emails should proceed to profile creation."""
    from unittest.mock import MagicMock
    from common.client_profile import auto_create_or_link_client_profile
    
    request_item = {"client_email": "normalclient@gmail.com", "client_name": "Normal"}
    
    with patch('common.client_profile.table') as mock_table:
        mock_table.query = MagicMock(return_value={"Items": []})
        mock_table.put_item = MagicMock()
        mock_table.update_item = MagicMock()
        result = auto_create_or_link_client_profile(
            request_item=request_item, request_id="test-2", client_id="c-2",
            company_id="tog_and_dogs", updated_by="system"
        )
    
    assert result["action"] == "created"
    print("PASS: test_client_profile_allows_normal_email")


# --- Admin Handler Integration Tests (via shared module) ---

def test_admin_handler_uses_shared_module():
    """admin_handler should import from common.protected_accounts."""
    from handlers.admin_handler import is_protected_profile, is_protected_email
    # These should be the shared module functions
    assert is_protected_email("support@usmissionhero.com") == True
    assert is_protected_email("random@test.com") == False
    print("PASS: test_admin_handler_uses_shared_module")


def test_link_cognito_blocks_protected_identities():
    """link-cognito should block linking a protected sub/email to an unprotected profile."""
    from handlers.admin_handler import handler as admin_handler
    
    unprotected_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#staff_1',
        'staff_id': 'staff_1',
        'email': 'normal@toganddogs.com',
        'cognito_sub': None
    }
    
    # Payload trying to link a protected Cognito sub
    event = {
        'httpMethod': 'POST',
        'path': '/admin/staff/staff_1/link-cognito',
        'pathParameters': {'staff_id': 'staff_1'},
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'admin-sub',
                    'email': 'support@usmissionhero.com',
                    'cognito:groups': 'Admin'
                }
            }
        },
        'body': '{"username": "support@usmissionhero.com"}'
    }
    
    # Mock admin_get_user to return a protected sub/email
    mock_cognito = MagicMock()
    mock_cognito.admin_get_user.return_value = {
        'UserStatus': 'CONFIRMED',
        'UserAttributes': [
            {'Name': 'sub', 'Value': 'protected-sub-999'},
            {'Name': 'email', 'Value': 'support@usmissionhero.com'}
        ]
    }
    
    mock_table = MagicMock()
    mock_table.get_item.return_value = {'Item': unprotected_staff}
    
    with patch('common.db.table', mock_table), \
         patch('handlers.admin_handler.get_item', return_value=unprotected_staff), \
         patch('boto3.client', return_value=mock_cognito):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "Cannot link a protected admin account" in resp["body"]
    print("PASS: test_link_cognito_blocks_protected_identities")


def test_patch_blocks_promotion_hijacking():
    """PATCH should block assigning a protected email/sub to an unprotected profile."""
    from handlers.admin_handler import handler as admin_handler
    
    unprotected_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#staff_1',
        'staff_id': 'staff_1',
        'email': 'normal@toganddogs.com',
        'cognito_sub': 'normal-sub'
    }
    
    event = {
        'httpMethod': 'PATCH',
        'path': '/admin/staff/staff_1',
        'pathParameters': {'staff_id': 'staff_1'},
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'admin-sub',
                    'email': 'support@usmissionhero.com',
                    'cognito:groups': 'Admin'
                }
            }
        },
        'body': '{"email": "support@usmissionhero.com"}'
    }
    
    mock_table = MagicMock()
    mock_table.get_item.return_value = {'Item': unprotected_staff}
    
    with patch('common.db.table', mock_table), \
         patch('handlers.admin_handler.get_item', return_value=unprotected_staff):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "Cannot assign a protected admin email" in resp["body"]
    print("PASS: test_patch_blocks_promotion_hijacking")


def test_post_creation_blocks_protected_identity():
    """POST /admin/staff should block creating a standard profile with a protected email."""
    from handlers.admin_handler import handler as admin_handler
    
    event = {
        'httpMethod': 'POST',
        'path': '/admin/staff',
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'admin-sub',
                    'email': 'support@usmissionhero.com',
                    'cognito:groups': 'Admin'
                }
            }
        },
        'body': '{"email": "support@usmissionhero.com", "display_name": "New Admin"}'
    }
    
    mock_table = MagicMock()
    mock_table.query.return_value = {'Items': []}
    
    with patch('common.db.table', mock_table):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "Cannot create a standard profile using a protected account identity" in resp["body"]
    print("PASS: test_post_creation_blocks_protected_identity")


if __name__ == '__main__':
    test_fallback_defaults_when_env_empty()
    test_configured_env_values_are_protected()
    test_non_protected_email_not_blocked()
    test_is_protected_profile_checks_both()
    test_case_insensitive_email()
    test_client_profile_skips_protected_email()
    test_client_profile_allows_normal_email()
    test_admin_handler_uses_shared_module()
    test_link_cognito_blocks_protected_identities()
    test_patch_blocks_promotion_hijacking()
    test_post_creation_blocks_protected_identity()
    print("\nAll Release 6H protected config tests PASSED.")
