"""
Release 12T: Backend Payment Link Email Endpoint and Notification Ledger Tests
"""
import sys
import os
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

# Set required environment variables
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

from handlers.admin_handler import handler as admin_handler
from common.notifications.service import notify_event, check_payment_email_rate_limit

# --- HELPERS ---

def make_admin_event(role='admin', company_id='tog_and_dogs', body=None, method='POST',
                     path='/admin/requests/req-001/send-payment-email', path_params=None, query_params=None):
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {'request_id': 'req-001'},
        # Default query_params to include clientId so direct get_item mock works by default
        'queryStringParameters': query_params if query_params is not None else {'clientId': 'client-001'},
        'body': json.dumps(body) if body is not None else None,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': 'test-sub-123',
                    'email': 'admin@example.com',
                    'cognito:groups': [role],
                    'custom:company_id': company_id
                }
            }
        }
    }

def make_req_record(company_id='tog_and_dogs', status='PENDING_REVIEW', payment_status='payment_link_sent',
                    stripe_url='https://checkout.stripe.com/pay/cs_123', stripe_id='cs_123', email='client@example.com'):
    return {
        'PK': 'REQ#req-001',
        'SK': 'CLIENT#client-001',
        'entity_type': 'REQUEST',
        'company_id': company_id,
        'request_id': 'req-001',
        'client_id': 'client-001',
        'client_name': 'Jane Doe',
        'client_email': email,
        'status': status,
        'payment_status': payment_status,
        'stripe_payment_url': stripe_url,
        'stripe_checkout_session_id': stripe_id,
        'payment_amount_cents': 15000,
        'workflow_type': 'VISIT_BOOKING',
    }

# --- TESTS ---

class TestAdminPaymentLinkEmail:

    @patch('common.db.get_item')
    @patch('common.db.table')
    @patch('common.notifications.service.check_payment_email_rate_limit')
    @patch('common.notifications.service.notify_event')
    def test_send_payment_email_success(self, mock_notify, mock_rate_limit, mock_table, mock_get):
        """Admin can successfully send a payment email and update DB attributes."""
        mock_get.return_value = make_req_record()
        mock_rate_limit.return_value = False
        mock_notify.return_value = {'success': True, 'message': 'Email sent.'}
        mock_table.update_item = MagicMock()

        event = make_admin_event(role='admin', company_id='tog_and_dogs')

        orig_get = admin_handler.__globals__.get('get_item')
        orig_table = admin_handler.__globals__.get('table')
        try:
            from common.db import get_item as real_get, table as real_table
            admin_handler.__globals__['get_item'] = real_get
            admin_handler.__globals__['table'] = real_table

            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get
            admin_handler.__globals__['table'] = orig_table

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == "Payment email sent successfully"
        assert body['recipient_email'] == "client@example.com"

        # Verify DB updates are made to request attributes
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs['Key'] == {'PK': 'REQ#req-001', 'SK': 'CLIENT#client-001'}
        expr_vals = call_kwargs['ExpressionAttributeValues']
        assert expr_vals[':plr'] == 'client@example.com'
        assert expr_vals[':inc'] == 1
        assert expr_vals[':zero'] == 0
        assert ':pat' in expr_vals

    @patch('common.db.get_item')
    def test_non_admin_forbidden(self, mock_get):
        """Non-admin roles are rejected with 403."""
        mock_get.return_value = make_req_record()

        for role in ['staff', 'client', 'unknown']:
            event = make_admin_event(role=role, company_id='tog_and_dogs')
            response = admin_handler(event, None)
            assert response['statusCode'] == 403

    @patch('common.db.get_item')
    def test_cross_tenant_forbidden(self, mock_get):
        """Cross-tenant payment email requests are rejected with 403."""
        mock_get.return_value = make_req_record(company_id='tenant_b')

        event = make_admin_event(role='admin', company_id='tenant_a')
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 403

    @patch('common.db.get_item')
    def test_missing_payment_link_blocks(self, mock_get):
        """Request missing payment URL or session ID blocks with 400."""
        # Missing URL
        mock_get.return_value = make_req_record(stripe_url=None)
        event = make_admin_event(role='admin')
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 400
        assert "active payment link" in json.loads(response['body'])['error']

        # Missing session ID
        mock_get.return_value = make_req_record(stripe_id=None)
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 400
        assert "active payment link" in json.loads(response['body'])['error']

    @patch('common.db.get_item')
    def test_paid_refunded_waived_blocks(self, mock_get):
        """Requests already paid, refunded, or waived block with 409 Conflict."""
        orig_get = admin_handler.__globals__.get('get_item')
        
        for p_status in ['paid', 'refunded', 'waived']:
            mock_get.return_value = make_req_record(payment_status=p_status)
            event = make_admin_event(role='admin')
            try:
                from common.db import get_item as real_get
                admin_handler.__globals__['get_item'] = real_get
                response = admin_handler(event, None)
            finally:
                admin_handler.__globals__['get_item'] = orig_get

            assert response['statusCode'] == 409
            assert "Conflict" in json.loads(response['body'])['error']

    @patch('common.db.get_item')
    def test_missing_client_email_blocks(self, mock_get):
        """Request missing client email blocks with 400."""
        mock_get.return_value = make_req_record(email=None)
        event = make_admin_event(role='admin')
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 400
        assert "Client email is missing" in json.loads(response['body'])['error']

    @patch('common.db.get_item')
    @patch('common.notifications.service.check_payment_email_rate_limit')
    def test_rate_limit_blocks(self, mock_rate_limit, mock_get):
        """Request exceeding the 3 sends per hour rate limit blocks with 429."""
        mock_get.return_value = make_req_record()
        mock_rate_limit.return_value = True
        event = make_admin_event(role='admin')
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 429
        assert "Rate limit exceeded" in json.loads(response['body'])['error']

    @patch('common.db.get_item')
    @patch('common.db.table')
    @patch('common.notifications.service.check_payment_email_rate_limit')
    @patch('common.notifications.service.notify_event')
    def test_postmark_failure_safe_error(self, mock_notify, mock_rate_limit, mock_table, mock_get):
        """Postmark send failure returns 500 and does NOT update database request email fields."""
        mock_get.return_value = make_req_record()
        mock_rate_limit.return_value = False
        mock_notify.return_value = {'success': False, 'message': 'Postmark server error'}
        mock_table.update_item = MagicMock()

        event = make_admin_event(role='admin')
        
        orig_get = admin_handler.__globals__.get('get_item')
        orig_table = admin_handler.__globals__.get('table')
        try:
            from common.db import get_item as real_get, table as real_table
            admin_handler.__globals__['get_item'] = real_get
            admin_handler.__globals__['table'] = real_table
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get
            admin_handler.__globals__['table'] = orig_table

        assert response['statusCode'] == 500
        assert "delivery failed" in json.loads(response['body'])['error']
        
        # Verify update_item was NOT called
        mock_table.update_item.assert_not_called()

    @patch('common.db.table')
    def test_query_fallback_when_clientId_missing(self, mock_table):
        """If clientId is missing from event, query the DB by PK to resolve request."""
        mock_table.query.return_value = {
            'Items': [make_req_record()]
        }
        mock_table.update_item = MagicMock()
        
        # event has query_params = {}, so client_id is resolved by querying
        event = make_admin_event(role='admin', query_params={})
        
        # Mock rate limit and notify_event
        orig_table = admin_handler.__globals__.get('table')
        try:
            admin_handler.__globals__['table'] = mock_table
            with patch('common.notifications.service.check_payment_email_rate_limit', return_value=False), \
                 patch('common.notifications.service.notify_event', return_value={'success': True, 'message': 'Email sent.'}):
                response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['table'] = orig_table
            
        assert response['statusCode'] == 200
        mock_table.query.assert_called_once()
        body = json.loads(response['body'])
        assert body['message'] == "Payment email sent successfully"

    @patch('common.db.get_item')
    @patch('common.notifications.service.check_payment_email_rate_limit')
    def test_r13b_payment_email_cooldown(self, mock_rate_limit, mock_get):
        """Short cooldown guard blocks sending email within cooldown window and allows it after."""
        mock_rate_limit.return_value = False
        event = make_admin_event(role='admin')

        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get

            # 1. Under cooldown (e.g. sent 30 seconds ago)
            from datetime import datetime, timezone, timedelta
            sent_30s_ago = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            mock_get.return_value = make_req_record(status='PENDING_REVIEW', payment_status='payment_link_sent')
            mock_get.return_value['payment_email_sent_at'] = sent_30s_ago

            response = admin_handler(event, None)
            assert response['statusCode'] == 429
            assert "wait" in json.loads(response['body'])['error'].lower()

            # 2. Past cooldown (e.g. sent 90 seconds ago)
            sent_90s_ago = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
            mock_get.return_value['payment_email_sent_at'] = sent_90s_ago

            with patch('common.notifications.service.notify_event', return_value={'success': True, 'message': 'Email sent.'}), \
                 patch('common.db.table.update_item') as mock_update:
                response = admin_handler(event, None)
                assert response['statusCode'] == 200
                assert json.loads(response['body'])['message'] == "Payment email sent successfully"
        finally:
            admin_handler.__globals__['get_item'] = orig_get


class TestRateLimiterAndLedgerDetails:

    @patch('common.db.table')
    def test_rate_limit_checks_status_index(self, mock_table):
        """check_payment_email_rate_limit queries status index correctly."""
        # Setup mock queries to return 3 entries (rate-limited)
        mock_table.query.return_value = {
            'Items': [
                {'status': 'sent', 'created_at': '2026-06-16T20:00:00Z'},
                {'status': 'sent', 'created_at': '2026-06-16T20:10:00Z'},
                {'status': 'sent', 'created_at': '2026-06-16T20:20:00Z'}
            ]
        }
        
        res = check_payment_email_rate_limit('req-001')
        assert res is True
        
        # Verify query arguments
        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs['IndexName'] == 'StatusIndex'
        
        # Under 3 sends -> not limited
        mock_table.query.return_value = {
            'Items': [
                {'status': 'sent', 'created_at': '2026-06-16T20:00:00Z'}
            ]
        }
        res_ok = check_payment_email_rate_limit('req-001')
        assert res_ok is False

    @patch('common.db.put_item')
    @patch('common.notifications.service.PostmarkClient.send_email')
    def test_notify_payment_link_writes_ledger_with_details(self, mock_send, mock_put):
        """notify_event for PAYMENT_LINK_EMAIL writes correct metadata to notification ledger."""
        mock_send.return_value = {
            "delivered": True,
            "mode": "external_provider",
            "provider": "postmark",
            "message": "Email sent.",
            "message_id": "msg-12345"
        }
        
        record = make_req_record()
        
        with patch('common.notifications.config.NotificationConfig.ENABLED', True), \
             patch('common.notifications.config.NotificationConfig.DRY_RUN', False), \
             patch('common.notifications.config.NotificationConfig.NOTIFICATION_MODE', 'external_provider'):
            res = notify_event("PAYMENT_LINK_EMAIL", record=record)
            
        assert res["success"] is True
        
        # Verify ledger put_item was called
        assert mock_put.call_count >= 1
        called_item = mock_put.call_args[0][0]
        
        assert called_item["PK"] == "NOTIF#msg-12345"
        assert called_item["SK"] == "REQUEST#req-001"
        assert called_item["status"] == "sent"
        assert called_item["recipient_email"] == "client@example.com"
        assert called_item["company_id"] == "tog_and_dogs"
        assert called_item["client_id"] == "client-001"
        assert called_item["stripe_checkout_session_id"] == "cs_123"
        assert called_item["stripe_payment_url"] == "https://checkout.stripe.com/pay/cs_123"
        assert called_item["event_type"] == "PAYMENT_LINK_EMAIL"
