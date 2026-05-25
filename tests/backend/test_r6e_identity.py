"""
Release 6E: Tests for phone normalization and protected email guardrails.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.admin_handler import normalize_phone_e164


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
    """Protected admin emails should not get auto-created client profiles."""
    from unittest.mock import patch, MagicMock
    from common.client_profile import auto_create_or_link_client_profile
    
    request_item = {
        "client_email": "mbn@usmissionhero.com",
        "client_name": "Admin Test",
        "pet_names": "Buddy",
    }
    
    with patch('common.client_profile.table') as mock_table:
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
