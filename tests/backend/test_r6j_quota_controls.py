"""
Release 6J Phase 1: Tests for monthly Postmark quota controls.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
from common.notifications.service import notify_event

# Mock data
TEST_RECORD = {
    "request_id": "req-123",
    "client_id": "client-456",
    "client_email": "test-client@example.com",
    "client_name": "John Doe",
    "company_id": "tog_and_dogs",
    "approval_notification_status": None,
}

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_successful_send_increments_quota_count(mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """A successful live notification send should increment the monthly send count atomically."""
    mock_send.return_value = {
        "delivered": True,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Email sent.",
        "message_id": "postmark-msg-111"
    }
    
    mock_get.return_value = {"sent_count": 5}
    mock_suppress.return_value = None
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 100), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', False):
        
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    # Verify _get_monthly_send_count was called
    quota_query_called = any(call[0][0] == "QUOTA#tog_and_dogs" for call in mock_get.call_args_list)
    assert quota_query_called is True
    
    # Verify _increment_monthly_send_count (update_item) was called atomically
    mock_table.update_item.assert_called_once()
    call_args = mock_table.update_item.call_args[1]
    assert call_args["Key"]["PK"] == "QUOTA#tog_and_dogs"
    assert call_args["UpdateExpression"] == "ADD sent_count :inc SET updated_at = :now, entity_type = :type"

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_dry_run_does_not_increment_quota_count(mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """A dry-run notification send should not increment the monthly send count."""
    mock_send.return_value = {
        "delivered": False,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Notification logged only (Dry Run or Disabled).",
        "message_id": None
    }
    
    mock_get.return_value = {"sent_count": 5}
    mock_suppress.return_value = None
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', True), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'):
        
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    # update_item should not be called because it was a dry run
    mock_table.update_item.assert_not_called()

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
@patch('builtins.print')
def test_quota_threshold_warning_logged(mock_print, mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """If the current send count crosses the warning threshold, log a standard CloudWatch warning."""
    mock_send.return_value = {
        "delivered": True,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Email sent.",
        "message_id": "postmark-msg-111"
    }
    
    # 85 is above the 80% threshold of 100 limit
    mock_get.return_value = {"sent_count": 85}
    mock_suppress.return_value = None
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 100), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', False):
        
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    # Verify standard warning printed
    warning_logged = any("NOTIFICATION_QUOTA_WARNING:" in str(call[0][0]) for call in mock_print.call_args_list)
    assert warning_logged is True

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_hard_stop_disabled_by_default(mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """If hard stop is disabled (default), sends should still go through even if limit is exceeded."""
    mock_send.return_value = {
        "delivered": True,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Email sent.",
        "message_id": "postmark-msg-111"
    }
    
    # 105 is above 100 limit
    mock_get.return_value = {"sent_count": 105}
    mock_suppress.return_value = None
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 100), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', False):
        
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    # Send email should be called because hard stop is disabled
    mock_send.assert_called_once()

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_hard_stop_enabled_blocks_sending(mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """If hard stop is enabled and limit is reached, block the email and write skipped_disabled to ledger."""
    # 100 reaches the 100 limit
    mock_get.return_value = {"sent_count": 100}
    mock_suppress.return_value = None
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 100), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', True):
        
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    assert res["success"] is True
    # Send email should NOT be called because hard stop blocked it
    mock_send.assert_not_called()
    
    # Ledger should have recorded 'skipped_quota_exceeded' with the quota skip details
    assert mock_put.call_count >= 1
    called_item = mock_put.call_args[0][0]
    assert called_item["status"] == "skipped_quota_exceeded"
    assert "Monthly Postmark quota limit" in called_item["error_message"]

@patch('common.notifications.suppression.get_item')
@patch('common.db.put_item')
@patch('common.db.get_item')
@patch('common.db.table')
@patch('common.notifications.service.PostmarkClient.send_email')
def test_quota_write_failure_is_non_blocking(mock_send, mock_table, mock_get, mock_put, mock_suppress):
    """If DynamoDB update_item fails during quota increment, notification should still succeed."""
    mock_send.return_value = {
        "delivered": True,
        "mode": "external_provider",
        "provider": "postmark",
        "message": "Email sent.",
        "message_id": "postmark-msg-111"
    }
    
    mock_get.return_value = {"sent_count": 5}
    mock_suppress.return_value = None
    # Simulate DB error on increment
    mock_table.update_item.side_effect = Exception("ProvisionedThroughputExceededException")
    
    with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
         patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
         patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_MONTHLY_LIMIT', 100), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_WARN_THRESHOLD', 80), \
         patch('common.notifications.config.NotificationConfig.POSTMARK_QUOTA_HARD_STOP', False):
        
        res = notify_event("CUSTOMER_APPROVED", record=TEST_RECORD)
        
    # The notification must still report success
    assert res["success"] is True
