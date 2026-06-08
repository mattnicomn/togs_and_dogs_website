"""
Release 9C: Tests for Google Calendar connection status validation and caching.
"""
import sys
import os
import json
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

import handlers.google_auth_handler as google_auth_handler

def create_event(role, body_dict=None):
    claims = {"email": "admin@test.com"}
    claims["cognito:groups"] = "Admin"
    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
        "httpMethod": "GET",
        "path": "/admin/auth/status"
    }

def test_get_status_credentials_missing():
    """Returns CREDENTIALS_MISSING when Google Client ID/Secret is missing."""
    event = create_event("Admin")
    with patch('handlers.google_auth_handler.get_google_config', return_value=None):
        resp = google_auth_handler.handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "CREDENTIALS_MISSING"

def test_get_status_not_connected():
    """Returns NOT_CONNECTED when refresh token is missing."""
    event = create_event("Admin")
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {} # Empty
    
    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens):
        resp = google_auth_handler.handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "NOT_CONNECTED"

def test_get_status_validation_failed_on_revoked():
    """Returns VALIDATION_FAILED immediately when tokens are marked revoked."""
    event = create_event("Admin")
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    mock_tokens = {
        "refresh_token": "refresh_val",
        "token_status": "revoked"
    }
    
    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens):
        resp = google_auth_handler.handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "VALIDATION_FAILED"
    assert "revoked" in body["message"].lower()

def test_get_status_connected_from_cache():
    """Returns CONNECTED directly from cached access token without hitting Google API."""
    event = create_event("Admin")
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    
    # Set updated_at to 10 minutes ago (well within 1 hour expiry)
    updated_at_str = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
    mock_tokens = {
        "refresh_token": "refresh_val",
        "access_token": "cached_access_val",
        "updated_at": updated_at_str,
        "expires_in": 3600
    }
    
    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('urllib.request.urlopen') as mock_urlopen:
        
        resp = google_auth_handler.handler(event, None)
        
    # urlopen should NOT have been called (hit cache)
    mock_urlopen.assert_not_called()
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "CONNECTED"

def test_get_status_refreshes_when_expired():
    """Refreshes and returns CONNECTED when cached access token is expired."""
    event = create_event("Admin")
    mock_config = {"client_id": "test_id", "client_secret": "test_secret"}
    
    # Set updated_at to 2 hours ago (expired)
    updated_at_str = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
    mock_tokens = {
        "refresh_token": "refresh_val",
        "access_token": "expired_access_val",
        "updated_at": updated_at_str,
        "expires_in": 3600
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"access_token": "new_access_val", "expires_in": 3600}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    
    with patch('handlers.google_auth_handler.get_google_config', return_value=mock_config), \
         patch('handlers.google_auth_handler.get_stored_tokens', return_value=mock_tokens), \
         patch('handlers.google_auth_handler.save_tokens', return_value=True) as mock_save, \
         patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
        
        resp = google_auth_handler.handler(event, None)
        
    # urlopen should have been called to refresh
    mock_urlopen.assert_called_once()
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "CONNECTED"
    mock_save.assert_called_once()
