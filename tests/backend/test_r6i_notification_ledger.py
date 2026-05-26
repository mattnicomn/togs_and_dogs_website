"""
Release 6I Phase 2: Tests for the Notification Ledger.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
from common.notifications.service import notify_event
from handlers.postmark_webhook_handler import handler as webhook_handler

# Mock data
TEST_RECORD = {
    "request_id": "req-123",
    "client_id": "client-456",
    "client_email": "test-client@example.com",
    "client_name": "John Doe",
    "company_id": "company-xyz",
    "approval_notification_status": None,
}

@patch('common.db.put_item')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_successful_send_writes_ledger_sent(mock_send, mock_put):
    """A successful live notification send should write a 'sent' ledger entry."""
    mock_send.return_value = {
        "delivered": True,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Email sent.",
        "message_id": "postmark-msg-111"
    }
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'):
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    # Verify mock_put was called
    assert mock_put.call_count >= 1
    
    # Let's inspect the item written
    called_item = mock_put.call_args[0][0]
    assert called_item["PK"] == "NOTIF#postmark-msg-111"
    assert called_item["SK"] == "REQUEST#req-123"
    assert called_item["status"] == "sent"
    assert called_item["recipient_email"] == "test-client@example.com"
    assert called_item["company_id"] == "company-xyz"
    assert called_item["provider"] == "postmark"
    assert called_item["provider_message_id"] == "postmark-msg-111"

@patch('common.db.put_item')
def test_disabled_notifications_writes_ledger_skipped_disabled(mock_put):
    """When notifications are disabled globally, we write a 'skipped_disabled' ledger entry."""
    with patch('common.notifications.config.NotificationConfig.ENABLED', False), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False):
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    assert mock_put.call_count == 1
    called_item = mock_put.call_args[0][0]
    assert called_item["status"] == "skipped_disabled"
    assert called_item["recipient_email"] == "test-client@example.com"

@patch('common.db.put_item')
def test_duplicate_approval_writes_ledger_skipped_duplicate(mock_put):
    """If the approval notification has already been sent, write a 'skipped_duplicate' ledger entry."""
    record_dup = TEST_RECORD.copy()
    record_dup["approval_notification_status"] = "Email sent."
    
    res = notify_event("CUSTOMER_APPROVED", record=record_dup)
    
    assert res["success"] is True
    assert mock_put.call_count == 1
    called_item = mock_put.call_args[0][0]
    assert called_item["status"] == "skipped_duplicate"
    assert called_item["recipient_email"] == "test-client@example.com"

@patch('common.db.put_item')
@patch('common.notifications.suppression.is_suppressed')
def test_suppressed_recipient_writes_ledger_suppressed(mock_suppressed, mock_put):
    """If the recipient email is suppressed, write a 'suppressed' ledger entry."""
    mock_suppressed.return_value = True
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False):
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    assert mock_put.call_count == 1
    called_item = mock_put.call_args[0][0]
    assert called_item["status"] == "suppressed"
    assert called_item["recipient_email"] == "test-client@example.com"

@patch('common.db.put_item')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_provider_failure_writes_ledger_failed(mock_send, mock_put):
    """If the provider API call fails, write a 'failed' ledger entry with error message."""
    mock_send.return_value = {
        "delivered": False,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Postmark delivery failed: 401 - Invalid token",
        "message_id": None
    }
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'):
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is False
    assert mock_put.call_count >= 1
    
    post_dispatch_call = [call[0][0] for call in mock_put.call_args_list if call[0][0]["status"] == "failed"]
    assert len(post_dispatch_call) == 1
    called_item = post_dispatch_call[0]
    assert called_item["status"] == "failed"
    assert called_item["error_message"] == "Postmark delivery failed: 401 - Invalid token"
    assert called_item["provider"] == "postmark"

@patch('common.db.put_item')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_ledger_write_failure_does_not_block_notification(mock_send, mock_put):
    """A DynamoDB put_item failure in ledger writes must not block notification sending."""
    mock_send.return_value = {
        "delivered": True,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Email sent.",
        "message_id": "postmark-msg-999"
    }
    mock_put.side_effect = Exception("DynamoDB ProvisionedThroughputExceededException")
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'):
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True


# --- Webhook Ledger Update Tests ---

@patch('common.db.table')
@patch('common.db.update_item')
def test_webhook_delivery_updates_ledger_to_delivered(mock_update, mock_table):
    """A webhook Delivery event should update matching ledger status to 'delivered'."""
    mock_table.query.return_value = {
        "Items": [
            {"PK": "NOTIF#msg-abc", "SK": "REQUEST#req-123", "status": "sent"}
        ]
    }
    
    event = {
        "httpMethod": "POST",
        "path": "/webhooks/postmark",
        "headers": {"X-Postmark-Webhook-Secret": "test-webhook-secret-123"},
        "body": json.dumps({
            "RecordType": "Delivery",
            "MessageID": "msg-abc",
            "Recipient": "test-client@example.com"
        })
    }
    
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': "test-webhook-secret-123"}):
        resp = webhook_handler(event, None)
        
    assert resp["statusCode"] == 200
    mock_update.assert_called_once_with("NOTIF#msg-abc", "REQUEST#req-123", {"status": "delivered"})

@patch('common.db.table')
@patch('common.db.update_item')
@patch('handlers.postmark_webhook_handler.suppress_email')
def test_webhook_bounce_updates_ledger_and_suppresses(mock_suppress, mock_update, mock_table):
    """A webhook HardBounce event should update ledger to 'bounced' and trigger suppression."""
    mock_table.query.return_value = {
        "Items": [
            {"PK": "NOTIF#msg-abc", "SK": "REQUEST#req-123", "status": "sent"}
        ]
    }
    
    event = {
        "httpMethod": "POST",
        "path": "/webhooks/postmark",
        "headers": {"X-Postmark-Webhook-Secret": "test-webhook-secret-123"},
        "body": json.dumps({
            "RecordType": "Bounce",
            "Type": "HardBounce",
            "Description": "Invalid address",
            "MessageID": "msg-abc",
            "Email": "test-client@example.com"
        })
    }
    
    with patch.dict(os.environ, {'POSTMARK_WEBHOOK_SECRET': "test-webhook-secret-123"}):
        resp = webhook_handler(event, None)
        
    assert resp["statusCode"] == 200
    mock_update.assert_called_once_with(
        "NOTIF#msg-abc", 
        "REQUEST#req-123", 
        {"status": "bounced", "error_message": "Bounce type: HardBounce - Invalid address"}
    )
    mock_suppress.assert_called_once_with("test-client@example.com", reason="HARD_BOUNCE:Invalid address")
