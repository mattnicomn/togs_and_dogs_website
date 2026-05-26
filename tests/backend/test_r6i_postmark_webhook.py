"""
Release 6I Phase 1: Tests for Postmark webhook handler.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
from handlers.postmark_webhook_handler import handler as webhook_handler


VALID_SECRET = "test-webhook-secret-123"


def _make_event(body_dict, secret=VALID_SECRET, headers_override=None):
    """Create a webhook event with auth header."""
    headers = headers_override or {}
    if secret:
        headers['X-Postmark-Webhook-Secret'] = secret
    return {
        "httpMethod": "POST",
        "path": "/webhooks/postmark",
        "headers": headers,
        "body": json.dumps(body_dict),
    }


# --- Authentication Tests ---

def test_valid_auth_accepted():
    """Valid webhook secret should be accepted."""
    event = _make_event({"RecordType": "Delivery", "MessageID": "msg-1", "Recipient": "test@example.com"})
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 200
    print("PASS: test_valid_auth_accepted")


def test_missing_secret_rejected():
    """Missing webhook secret header should return 401."""
    event = _make_event({"RecordType": "Delivery", "MessageID": "msg-1"}, secret=None)
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 401
    print("PASS: test_missing_secret_rejected")


def test_wrong_secret_rejected():
    """Wrong webhook secret should return 401."""
    event = _make_event({"RecordType": "Delivery", "MessageID": "msg-1"}, secret="wrong-secret")
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 401
    print("PASS: test_wrong_secret_rejected")


def test_unconfigured_secret_rejects_all():
    """If POSTMARK_WEBHOOK_SECRET is not configured, reject all requests (fail-closed)."""
    event = _make_event({"RecordType": "Delivery", "MessageID": "msg-1"}, secret="anything")
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': ''}, clear=False):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 401
    print("PASS: test_unconfigured_secret_rejects_all")


# --- Bounce Handling Tests ---

def test_hard_bounce_suppresses():
    """Hard bounce should call suppress_email."""
    event = _make_event({
        "RecordType": "Bounce",
        "Type": "HardBounce",
        "Email": "bounced@example.com",
        "MessageID": "msg-bounce-1",
        "Description": "550 User unknown"
    })
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}), \
         patch('handlers.postmark_webhook_handler.suppress_email') as mock_suppress:
        resp = webhook_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "suppressed"
    mock_suppress.assert_called_once_with("bounced@example.com", reason="HARD_BOUNCE:550 User unknown")
    print("PASS: test_hard_bounce_suppresses")


def test_soft_bounce_does_not_suppress():
    """Soft bounce should NOT suppress."""
    event = _make_event({
        "RecordType": "Bounce",
        "Type": "SoftBounce",
        "Email": "temp-fail@example.com",
        "MessageID": "msg-bounce-2",
        "Description": "Mailbox full"
    })
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}), \
         patch('handlers.postmark_webhook_handler.suppress_email') as mock_suppress:
        resp = webhook_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "logged"
    mock_suppress.assert_not_called()
    print("PASS: test_soft_bounce_does_not_suppress")


# --- Spam Complaint Tests ---

def test_spam_complaint_suppresses():
    """Spam complaint should call suppress_email."""
    event = _make_event({
        "RecordType": "SpamComplaint",
        "Email": "complainer@example.com",
        "MessageID": "msg-spam-1"
    })
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}), \
         patch('handlers.postmark_webhook_handler.suppress_email') as mock_suppress:
        resp = webhook_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "suppressed"
    mock_suppress.assert_called_once_with("complainer@example.com", reason="SPAM_COMPLAINT")
    print("PASS: test_spam_complaint_suppresses")


# --- Non-Actionable Events ---

def test_delivery_event_logged_not_suppressed():
    """Delivery events should be acknowledged but not suppress."""
    event = _make_event({
        "RecordType": "Delivery",
        "Recipient": "delivered@example.com",
        "MessageID": "msg-del-1"
    })
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}), \
         patch('handlers.postmark_webhook_handler.suppress_email') as mock_suppress:
        resp = webhook_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "delivered"
    mock_suppress.assert_not_called()
    print("PASS: test_delivery_event_logged_not_suppressed")


def test_open_event_acknowledged():
    """Open events should be acknowledged."""
    event = _make_event({"RecordType": "Open", "MessageID": "msg-open-1"})
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 200
    print("PASS: test_open_event_acknowledged")


def test_unknown_record_type_ignored():
    """Unknown RecordType should return 200 with ignored status."""
    event = _make_event({"RecordType": "FutureType", "MessageID": "msg-future"})
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "ignored"
    print("PASS: test_unknown_record_type_ignored")


# --- Malformed Payload Tests ---

def test_malformed_json_returns_400():
    """Invalid JSON body should return 400."""
    event = {
        "httpMethod": "POST",
        "path": "/webhooks/postmark",
        "headers": {"X-Postmark-Webhook-Secret": VALID_SECRET},
        "body": "not valid json{{{",
    }
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 400
    print("PASS: test_malformed_json_returns_400")


def test_missing_record_type_returns_400():
    """Missing RecordType field should return 400."""
    event = _make_event({"MessageID": "msg-no-type"})
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}):
        resp = webhook_handler(event, None)
    assert resp["statusCode"] == 400
    print("PASS: test_missing_record_type_returns_400")


# --- No Send-Path Side Effects ---

def test_webhook_does_not_call_notify_event():
    """Webhook handler must not call notify_event or affect the send path."""
    event = _make_event({
        "RecordType": "Bounce",
        "Type": "HardBounce",
        "Email": "test@example.com",
        "MessageID": "msg-1"
    })
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': VALID_SECRET}), \
         patch('handlers.postmark_webhook_handler.suppress_email'), \
         patch('common.notifications.service.notify_event') as mock_notify:
        resp = webhook_handler(event, None)
    
    assert resp["statusCode"] == 200
    mock_notify.assert_not_called()
    print("PASS: test_webhook_does_not_call_notify_event")


if __name__ == '__main__':
    test_valid_auth_accepted()
    test_missing_secret_rejected()
    test_wrong_secret_rejected()
    test_unconfigured_secret_rejects_all()
    test_hard_bounce_suppresses()
    test_soft_bounce_does_not_suppress()
    test_spam_complaint_suppresses()
    test_delivery_event_logged_not_suppressed()
    test_open_event_acknowledged()
    test_unknown_record_type_ignored()
    test_malformed_json_returns_400()
    test_missing_record_type_returns_400()
    test_webhook_does_not_call_notify_event()
    print("\nAll Release 6I webhook tests PASSED.")
