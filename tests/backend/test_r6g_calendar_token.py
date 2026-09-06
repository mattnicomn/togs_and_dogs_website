"""
Release 6G Phase 0C: Tests for Google Calendar token revocation handling.
"""
import sys
import os
import json
import pytest

pytestmark = pytest.mark.usefixtures('primary_google_binding')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
import urllib.error


# --- Token Revocation Detection Tests ---

def test_invalid_grant_marks_token_revoked():
    """When Google returns invalid_grant, token should be marked as revoked."""
    from common.google_calendar import _refresh_access_token

    # Simulate invalid_grant HTTP error from Google
    error_body = json.dumps({"error": "invalid_grant", "error_description": "Token has been revoked."}).encode()
    http_error = urllib.error.HTTPError(
        url="https://oauth2.googleapis.com/token",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=None
    )
    http_error.read = lambda: error_body

    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "old_refresh_token", "access_token": "old_access"}

    with patch('common.google_calendar._get_google_config', return_value=mock_config), \
         patch('common.google_calendar._mark_bound_token_revoked') as mock_mark, \
         patch('urllib.request.urlopen', side_effect=http_error):
        result = _refresh_access_token(mock_tokens, request_id="test-123", company_id="tog_and_dogs")

    assert result is None
    mock_mark.assert_called_once_with("test-123", 'arn:aws:secretsmanager:us-east-1:123456789012:secret:togs-and-dogs-prod/google/user-tokens-Ab1234')
    print("PASS: test_invalid_grant_marks_token_revoked")


def test_other_http_error_does_not_mark_revoked():
    """Non-invalid_grant errors should not mark token as revoked."""
    from common.google_calendar import _refresh_access_token

    error_body = json.dumps({"error": "server_error", "error_description": "Internal error."}).encode()
    http_error = urllib.error.HTTPError(
        url="https://oauth2.googleapis.com/token",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=None
    )
    http_error.read = lambda: error_body

    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "valid_refresh", "access_token": "old_access"}

    with patch('common.google_calendar._get_google_config', return_value=mock_config), \
         patch('common.google_calendar._mark_bound_token_revoked') as mock_mark, \
         patch('urllib.request.urlopen', side_effect=http_error):
        result = _refresh_access_token(mock_tokens, request_id="test-456", company_id="tog_and_dogs")

    assert result is None
    mock_mark.assert_not_called()
    print("PASS: test_other_http_error_does_not_mark_revoked")


def test_revoked_token_skips_refresh():
    """When token_status is 'revoked', _get_valid_token should return None immediately."""
    from common.google_calendar import _get_valid_token

    revoked_tokens = {
        "refresh_token": "old_token",
        "access_token": "old_access",
        "token_status": "revoked",
        "revoked_at": "2026-05-22T00:00:00"
    }

    with patch('common.google_calendar._read_bound_tokens', return_value=revoked_tokens), \
         patch('common.google_calendar._refresh_bound_tokens') as mock_refresh:
        result = _get_valid_token(request_id="test-789", company_id="tog_and_dogs")

    assert result is None
    mock_refresh.assert_not_called()
    print("PASS: test_revoked_token_skips_refresh")


def test_normal_refresh_still_works():
    """Normal token refresh should work when token is not revoked."""
    from common.google_calendar import _refresh_access_token

    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {"refresh_token": "valid_refresh", "access_token": "old_access"}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"access_token": "new_access", "expires_in": 3600}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('common.google_calendar._get_google_config', return_value=mock_config), \
         patch('common.google_calendar._save_bound_tokens', return_value=True), \
         patch('urllib.request.urlopen', return_value=mock_response):
        result = _refresh_access_token(mock_tokens, request_id="test-normal", company_id="tog_and_dogs")

    assert result == "new_access"
    print("PASS: test_normal_refresh_still_works")


def test_sync_calendar_event_nonblocking_on_revoked_token():
    """sync_calendar_event must return gracefully when token is revoked, not raise."""
    from common.google_calendar import sync_calendar_event

    revoked_tokens = {"token_status": "revoked", "refresh_token": "dead"}
    mock_item = {
        "company_id": "tog_and_dogs",
        "request_id": "req-001",
        "client_name": "Test",
        "pet_names": "Buddy",
        "service_type": "WALK_30MIN",
        "start_date": "2026-07-01",
        "scheduled_time": "09:00"
    }

    with patch('common.google_calendar._read_bound_tokens', return_value=revoked_tokens):
        result = sync_calendar_event(mock_item)

    assert result is not None
    assert result.get("status") == "calendar_failed"
    assert "disconnected" in result.get("message", "").lower() or "expired" in result.get("message", "").lower()
    print("PASS: test_sync_calendar_event_nonblocking_on_revoked_token")


def test_mark_token_revoked_updates_secret():
    """_mark_token_revoked should update the secret with revoked status."""
    from common.google_calendar import _mark_token_revoked

    existing_tokens = {"refresh_token": "old", "access_token": "old_access", "updated_at": "2026-01-01"}

    with patch('common.google_calendar._read_bound_tokens', return_value=existing_tokens), \
         patch('common.google_calendar.secrets.put_secret_value') as mock_put:
        _mark_token_revoked("test-mark", company_id="tog_and_dogs")

    mock_put.assert_called_once()
    call_args = mock_put.call_args
    saved_data = json.loads(call_args.kwargs.get('SecretString') or call_args[1].get('SecretString'))
    assert saved_data['token_status'] == 'revoked'
    assert saved_data['revoked_reason'] == 'invalid_grant'
    assert 'access_token' not in saved_data
    print("PASS: test_mark_token_revoked_updates_secret")


if __name__ == '__main__':
    test_invalid_grant_marks_token_revoked()
    test_other_http_error_does_not_mark_revoked()
    test_revoked_token_skips_refresh()
    test_normal_refresh_still_works()
    test_sync_calendar_event_nonblocking_on_revoked_token()
    test_mark_token_revoked_updates_secret()
    print("\nAll Release 6G calendar token tests PASSED.")
