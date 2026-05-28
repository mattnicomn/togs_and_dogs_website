import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from common.notifications.service import _is_recent_duplicate, notify_event

@pytest.fixture
def mock_table():
    with patch('common.db.table') as mock:
        yield mock

def test_dedup_skips_recent_same_event(mock_table):
    # Setup mock to return a duplicate on the first query (status='sent')
    mock_table.query.return_value = {'Items': [{'status': 'sent', 'request_id': 'REQ123'}]}
    
    result = _is_recent_duplicate('STAFF_ASSIGNED', 'test@example.com', 'REQ123')
    assert result is True

def test_dedup_allows_different_event_type(mock_table):
    # Mock returns empty, simulating different event type or no recent entry
    mock_table.query.return_value = {'Items': []}
    
    result = _is_recent_duplicate('VISIT_SCHEDULED', 'test@example.com', 'REQ123')
    assert result is False

def test_dedup_allows_different_request_id(mock_table):
    mock_table.query.return_value = {'Items': []}
    result = _is_recent_duplicate('STAFF_ASSIGNED', 'test@example.com', 'REQ999')
    assert result is False

def test_dedup_allows_after_window_expires(mock_table):
    mock_table.query.return_value = {'Items': []}
    result = _is_recent_duplicate('STAFF_ASSIGNED', 'test@example.com', 'REQ123')
    assert result is False

def test_dedup_fail_open_on_query_error(mock_table):
    # Setup mock to raise Exception (simulating DynamoDB failure)
    mock_table.query.side_effect = Exception("DynamoDB error")
    
    result = _is_recent_duplicate('STAFF_ASSIGNED', 'test@example.com', 'REQ123')
    assert result is False # fail open guarantees it allows the send

@patch('common.notifications.service._write_ledger_entry')
@patch('common.notifications.service.resolve_notification_recipients')
@patch('common.notifications.service.NotificationTemplates.get_template')
@patch('common.notifications.service.get_notification_client')
@patch('common.notifications.service._is_recent_duplicate')
def test_notify_event_skips_duplicate(mock_is_duplicate, mock_get_client, mock_get_template, mock_resolve, mock_write_ledger):
    mock_resolve.return_value = ['test@example.com']
    mock_is_duplicate.return_value = True # Simulate that it IS a duplicate
    
    record = {'request_id': 'REQ123'}
    res = notify_event('STAFF_ASSIGNED', record)
    
    assert res['success'] is True
    assert "Skipped: recent duplicate notification" in res['message']
    mock_get_template.assert_not_called()
    mock_write_ledger.assert_called_with(
        request_id='REQ123',
        event_type='STAFF_ASSIGNED',
        recipient='test@example.com',
        status='skipped_duplicate_window',
        provider='dedup',
        error_message='Skipped: recent duplicate notification in window',
        record=record
    )

@patch('common.notifications.service._write_ledger_entry')
@patch('common.notifications.service.resolve_notification_recipients')
@patch('common.notifications.service.NotificationTemplates.get_template')
@patch('common.notifications.service.get_notification_client')
@patch('common.notifications.service._is_recent_duplicate')
@patch('common.notifications.service._get_monthly_send_count')
def test_single_day_not_affected_by_dedup(mock_quota, mock_is_duplicate, mock_get_client, mock_get_template, mock_resolve, mock_write_ledger):
    mock_quota.return_value = 0
    mock_resolve.return_value = ['test@example.com']
    mock_is_duplicate.return_value = False # NOT a duplicate
    mock_get_template.return_value = ('Subject', 'Text', 'HTML')
    
    mock_client = MagicMock()
    mock_client.send_email.return_value = {'delivered': True, 'message': 'Sent', 'mode': 'test', 'provider': 'test', 'message_id': '123'}
    mock_get_client.return_value = mock_client
    
    record = {'request_id': 'REQ123', 'client_email': 'test@example.com', 'client_name': 'Test'}
    res = notify_event('STAFF_ASSIGNED', record)
    
    assert res['success'] is True
    mock_client.send_email.assert_called_once()
