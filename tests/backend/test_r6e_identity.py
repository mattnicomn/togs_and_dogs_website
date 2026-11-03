"""
Release 6E: Tests for phone normalization and protected email guardrails.
"""
import sys
import os

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.admin_handler import normalize_phone_e164


# --- Network isolation (Gate C3b.3j.2) ---
#
# Function-scoped, autouse guard: any UNMOCKED AWS/botocore call fails loudly
# rather than silently reaching the network. The protected-email path performs
# no DynamoDB query/write for a profile (it only records link status, which the
# tests mock via common.client_profile.table), and the non-protected path mocks
# query/put_item. This only fires on a genuine leak. Auto-restored per test.

@pytest.fixture(autouse=True)
def _no_network():
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked AWS/botocore network call attempted in an isolated identity "
            "test. Add an explicit scoped mock for the operation reached."
        )
    with patch('botocore.httpsession.URLLib3Session.send', _blocked):
        yield


# --- Phone Normalization Tests ---

def test_phone_10_digits():
    """10-digit US number normalizes to +1 prefix."""
    assert normalize_phone_e164("5551234567") == "+15551234567"

def test_phone_with_parens_and_dashes():
    """(555) 123-4567 normalizes correctly."""
    assert normalize_phone_e164("(555) 123-4567") == "+15551234567"

def test_phone_with_country_code_dashes():
    """1-555-123-4567 normalizes correctly."""
    assert normalize_phone_e164("1-555-123-4567") == "+15551234567"

def test_phone_already_e164():
    """+15551234567 remains unchanged."""
    assert normalize_phone_e164("+15551234567") == "+15551234567"

def test_phone_11_digits_with_1():
    """15551234567 normalizes to +15551234567."""
    assert normalize_phone_e164("15551234567") == "+15551234567"

def test_phone_with_spaces():
    """555 123 4567 normalizes correctly."""
    assert normalize_phone_e164("555 123 4567") == "+15551234567"

def test_phone_with_dots():
    """555.123.4567 normalizes correctly."""
    assert normalize_phone_e164("555.123.4567") == "+15551234567"

def test_phone_empty():
    """Empty string returns None."""
    assert normalize_phone_e164("") is None

def test_phone_none():
    """None returns None."""
    assert normalize_phone_e164(None) is None

def test_phone_too_short():
    """Too few digits returns None."""
    assert normalize_phone_e164("12345") is None

def test_phone_too_long():
    """Too many digits (not starting with +) returns None."""
    assert normalize_phone_e164("123456789012345678") is None

def test_phone_international_passthrough():
    """+44 numbers pass through if valid E.164."""
    assert normalize_phone_e164("+447911123456") == "+447911123456"

def test_phone_letters_only():
    """Non-numeric input returns None."""
    assert normalize_phone_e164("call me") is None

def test_phone_whitespace_only():
    """Whitespace-only returns None."""
    assert normalize_phone_e164("   ") is None


# --- Protected Email Guardrail Tests ---

def test_protected_email_blocks_auto_profile():
    """A hardcoded-fallback protected admin email must NOT get an auto-created
    client profile.

    Gate C3b.3j.2: the prior fixture used 'mbn@usmissionhero.com', which is not
    in the protected set, so the real is_protected_email correctly returned
    False and a profile was created (the test, not the control, was stale). This
    uses the guaranteed-protected hardcoded fallback 'support@usmissionhero.com'
    (common.protected_accounts._FALLBACK_EMAILS) so the REAL is_protected_email /
    auto_create_or_link_client_profile logic exercises the protection branch
    without any env dependency. Asserts the request is skipped AND that NO
    profile lookup or creation write occurs (query/put_item never called).
    """
    from unittest.mock import MagicMock
    from common.client_profile import auto_create_or_link_client_profile

    request_item = {
        "client_email": "support@usmissionhero.com",
        "client_name": "Admin Test",
        "pet_names": "Buddy",
    }

    with patch('common.client_profile.table') as mock_table:
        mock_table.query = MagicMock()
        mock_table.put_item = MagicMock()
        mock_table.update_item = MagicMock()
        result = auto_create_or_link_client_profile(
            request_item=request_item,
            request_id="test-123",
            client_id="client-456",
            company_id="tog_and_dogs",
            updated_by="system"
        )

    assert result["action"] == "skipped"
    assert result["link_status"] == "SKIPPED_PROTECTED_EMAIL"
    assert "protected" in result["message"].lower()
    assert result["client_profile_id"] is None
    # No unauthorized identity association: no profile lookup or creation write.
    mock_table.query.assert_not_called()
    mock_table.put_item.assert_not_called()


def test_env_configured_protected_email_blocks_auto_profile():
    """An email configured via PROTECTED_ADMIN_EMAILS (not a fallback default)
    must also be blocked, proving the real env-driven protection path is honored.

    Uses a scoped, auto-restored environment override so no global state leaks.
    The real is_protected_email reads PROTECTED_ADMIN_EMAILS at call time.
    """
    from unittest.mock import MagicMock
    from common.client_profile import auto_create_or_link_client_profile

    request_item = {
        "client_email": "owner-admin@example-tenant.com",
        "client_name": "Env Protected Admin",
        "pet_names": "Rex",
    }

    with patch.dict(os.environ, {'PROTECTED_ADMIN_EMAILS': 'owner-admin@example-tenant.com'}), \
         patch('common.client_profile.table') as mock_table:
        mock_table.query = MagicMock()
        mock_table.put_item = MagicMock()
        mock_table.update_item = MagicMock()
        result = auto_create_or_link_client_profile(
            request_item=request_item,
            request_id="test-env-123",
            client_id="client-env-456",
            company_id="tog_and_dogs",
            updated_by="system"
        )

    assert result["action"] == "skipped"
    assert result["link_status"] == "SKIPPED_PROTECTED_EMAIL"
    assert "protected" in result["message"].lower()
    assert result["client_profile_id"] is None
    mock_table.query.assert_not_called()
    mock_table.put_item.assert_not_called()


def test_protected_email_matching_is_case_insensitive():
    """Protected-email matching normalizes case (uppercase fallback address is
    still blocked), confirming the normalization in is_protected_email."""
    from unittest.mock import MagicMock
    from common.client_profile import auto_create_or_link_client_profile

    request_item = {
        "client_email": "SUPPORT@USMISSIONHERO.COM",
        "client_name": "Admin Test Upper",
        "pet_names": "Buddy",
    }

    with patch('common.client_profile.table') as mock_table:
        mock_table.query = MagicMock()
        mock_table.put_item = MagicMock()
        mock_table.update_item = MagicMock()
        result = auto_create_or_link_client_profile(
            request_item=request_item,
            request_id="test-upper-123",
            client_id="client-upper-456",
            company_id="tog_and_dogs",
            updated_by="system"
        )

    assert result["action"] == "skipped"
    assert result["link_status"] == "SKIPPED_PROTECTED_EMAIL"
    mock_table.put_item.assert_not_called()

def test_non_protected_email_proceeds():
    """Normal client emails should not be blocked."""
    from unittest.mock import patch, MagicMock
    from common.client_profile import auto_create_or_link_client_profile
    
    request_item = {
        "client_email": "normalclient@gmail.com",
        "client_name": "Normal Client",
        "pet_names": "Fido",
    }
    
    with patch('common.client_profile.table') as mock_table:
        # Mock the query to return empty (no existing profiles)
        mock_table.query = MagicMock(return_value={"Items": []})
        mock_table.put_item = MagicMock()
        mock_table.update_item = MagicMock()
        
        result = auto_create_or_link_client_profile(
            request_item=request_item,
            request_id="test-789",
            client_id="client-012",
            company_id="tog_and_dogs",
            updated_by="system"
        )
    
    # Should proceed to create (not be blocked)
    assert result["action"] == "created"
    assert result["link_status"] == "CREATED_NEW"


if __name__ == '__main__':
    test_phone_10_digits()
    test_phone_with_parens_and_dashes()
    test_phone_with_country_code_dashes()
    test_phone_already_e164()
    test_phone_11_digits_with_1()
    test_phone_with_spaces()
    test_phone_with_dots()
    test_phone_empty()
    test_phone_none()
    test_phone_too_short()
    test_phone_too_long()
    test_phone_international_passthrough()
    test_phone_letters_only()
    test_phone_whitespace_only()
    test_protected_email_blocks_auto_profile()
    test_non_protected_email_proceeds()
    print("\nAll Release 6E identity tests PASSED.")
