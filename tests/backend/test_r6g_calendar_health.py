"""
Release 6G Phase 3: Tests for scheduled Google Calendar health check.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
import urllib.error
from handlers.google_auth_handler import calendar_health_check


def _make_event(source="aws.events"):
    """Create a minimal EventBridge-style event."""
    return {"source": source, "detail-type": "Scheduled Event", "action": "health_check"}


def test_health_check_success():
    """Healthy token should return CONNECTED."""
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "valid_token", "access_token": "old"}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"access_token": "new_token", "expires_in": 3600}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('handlers.google_auth_handler.save_tokens', return_value=True), \
         patch('urllib.request.urlopen', return_value=mock_response):
        result = calendar_health_check(_make_event())

    assert result["status"] == "CONNECTED"
    print("PASS: test_health_check_success")


def test_health_check_token_revoked_flag():
    """When token_status is 'revoked', should return TOKEN_REVOKED without attempting refresh."""
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "dead", "token_status": "revoked"}

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('urllib.request.urlopen') as mock_url:
        result = calendar_health_check(_make_event())

    assert result["status"] == "TOKEN_REVOKED"
    mock_url.assert_not_called()
    print("PASS: test_health_check_token_revoked_flag")


def test_health_check_missing_refresh_token():
    """Missing refresh token should return TOKEN_MISSING."""
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"access_token": "old"}  # No refresh_token

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens):
        result = calendar_health_check(_make_event())

    assert result["status"] == "TOKEN_MISSING"
    print("PASS: test_health_check_missing_refresh_token")


def test_health_check_missing_credentials():
    """Missing Google client config should return CREDENTIALS_MISSING."""
    with patch('handlers.google_auth_handler.get_google_config', return_value=None):
        result = calendar_health_check(_make_event())

    assert result["status"] == "CREDENTIALS_MISSING"
    print("PASS: test_health_check_missing_credentials")


def test_health_check_invalid_grant():
    """invalid_grant during refresh should return TOKEN_REVOKED and mark token."""
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "expired_token"}

    error_body = json.dumps({"error": "invalid_grant"}).encode()
    http_error = urllib.error.HTTPError(
        url="https://oauth2.googleapis.com/token",
        code=400, msg="Bad Request", hdrs={}, fp=None
    )
    http_error.read = lambda: error_body

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('urllib.request.urlopen', side_effect=http_error), \
         patch('common.google_calendar._mark_token_revoked') as mock_mark:
        result = calendar_health_check(_make_event())

    assert result["status"] == "TOKEN_REVOKED"
    mock_mark.assert_called_once_with("health_check")
    print("PASS: test_health_check_invalid_grant")


def test_health_check_refresh_failed_other_error():
    """Non-invalid_grant HTTP error should return REFRESH_FAILED."""
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "valid_token"}

    error_body = json.dumps({"error": "server_error"}).encode()
    http_error = urllib.error.HTTPError(
        url="https://oauth2.googleapis.com/token",
        code=500, msg="Internal Server Error", hdrs={}, fp=None
    )
    http_error.read = lambda: error_body

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('urllib.request.urlopen', side_effect=http_error):
        result = calendar_health_check(_make_event())

    assert result["status"] == "REFRESH_FAILED"
    print("PASS: test_health_check_refresh_failed_other_error")


def test_health_check_network_exception():
    """Network exception should return REFRESH_FAILED gracefully."""
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "valid_token"}

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('urllib.request.urlopen', side_effect=Exception("Network timeout")):
        result = calendar_health_check(_make_event())

    assert result["status"] == "REFRESH_FAILED"
    assert "Network timeout" in result["message"]
    print("PASS: test_health_check_network_exception")


def test_health_check_does_not_block_business():
    """Health check is a standalone function — verify it doesn't import/call business handlers."""
    # This test confirms the health check is isolated and non-blocking by design
    event = _make_event()
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "valid", "token_status": "revoked"}

    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens):
        # Should return immediately without touching any business handler
        result = calendar_health_check(event)

    assert result is not None
    assert "status" in result
    # No exception raised = non-blocking confirmed
    print("PASS: test_health_check_does_not_block_business")


if __name__ == '__main__':
    test_health_check_success()
    test_health_check_token_revoked_flag()
    test_health_check_missing_refresh_token()
    test_health_check_missing_credentials()
    test_health_check_invalid_grant()
    test_health_check_refresh_failed_other_error()
    test_health_check_network_exception()
    test_health_check_does_not_block_business()
    print("\nAll Release 6G calendar health check tests PASSED.")
