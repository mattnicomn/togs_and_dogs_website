"""
Release 12G: Stripe Checkout Session Creation and Webhook Handler Booking Extension Tests
"""
import sys
import os
import json
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

# Set required environment variables
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('STRIPE_WEBHOOK_SECRET', 'whsec_test_secret_key')
os.environ.setdefault('STRIPE_SECRET_KEY', 'sk_test_key')

from handlers.admin_handler import handler as admin_handler
from handlers.stripe_webhook_handler import handler as webhook_handler
from common.stripe_client import StripeAPIError

# --- HELPERS ---

def make_admin_event(role='admin', company_id='tog_and_dogs', body=None, method='POST',
                     path='/admin/requests/req-001/payment-session', path_params=None, query_params=None):
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {'request_id': 'req-001'},
        'queryStringParameters': query_params or {},
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

def make_req_record(company_id='tog_and_dogs', status='PENDING_REVIEW'):
    return {
        'PK': 'REQ#req-001',
        'SK': 'CLIENT#client-001',
        'entity_type': 'REQUEST',
        'company_id': company_id,
        'request_id': 'req-001',
        'client_id': 'client-001',
        'client_name': 'Jane Doe',
        'client_email': 'jane@example.com',
        'status': status,
        'workflow_type': 'VISIT_BOOKING',
    }

# --- TESTS ---

class TestAdminStripeCheckoutCreation:

    @patch('common.db.get_item')
    @patch('common.db.table')
    @patch('common.stripe_client.create_checkout_session')
    def test_admin_create_session_success(self, mock_create, mock_table, mock_get):
        """Admin can create checkout session for request in same tenant."""
        mock_get.return_value = make_req_record(company_id='tog_and_dogs')
        mock_create.return_value = {
            'id': 'cs_test_123',
            'url': 'https://checkout.stripe.com/c/pay/cs_test_123'
        }
        mock_table.update_item = MagicMock()

        event = make_admin_event(
            role='admin',
            company_id='tog_and_dogs',
            body={'amount_cents': 15000, 'client_id': 'client-001'}
        )
        
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
        assert body['stripe_checkout_session_id'] == 'cs_test_123'
        assert body['stripe_payment_url'] == 'https://checkout.stripe.com/c/pay/cs_test_123'
        assert body['payment_status'] == 'payment_link_sent'

        # Verify correct metadata was passed to Stripe creator
        mock_create.assert_called_once_with(
            company_id='tog_and_dogs',
            request_id='req-001',
            client_id='client-001',
            amount_cents=15000,
            environment='sandbox'
        )

        # Verify DynamoDB update contains correct attributes
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs['Key'] == {'PK': 'REQ#req-001', 'SK': 'CLIENT#client-001'}
        expr_vals = call_kwargs['ExpressionAttributeValues']
        assert expr_vals[':ps'] == 'payment_link_sent'
        assert expr_vals[':sid'] == 'cs_test_123'
        assert expr_vals[':surl'] == 'https://checkout.stripe.com/c/pay/cs_test_123'
        assert expr_vals[':pac'] == 15000

    @patch('common.db.get_item')
    def test_non_admin_creation_forbidden(self, mock_get):
        """Non-admin roles are rejected with 403."""
        mock_get.return_value = make_req_record(company_id='tog_and_dogs')

        for role in ['staff', 'client', 'unknown']:
            event = make_admin_event(
                role=role,
                company_id='tog_and_dogs',
                body={'amount_cents': 15000, 'client_id': 'client-001'}
            )
            response = admin_handler(event, None)
            assert response['statusCode'] == 403

    @patch('common.db.get_item')
    def test_cross_tenant_creation_forbidden(self, mock_get):
        """Cross-tenant payment session creation returns 403."""
        mock_get.return_value = make_req_record(company_id='tenant_b')

        # Admin belongs to tenant_a, trying to access request in tenant_b
        event = make_admin_event(
            role='admin',
            company_id='tenant_a',
            body={'amount_cents': 15000, 'client_id': 'client-001'}
        )
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 403

    @patch('common.db.get_item')
    def test_invalid_amount_rejected(self, mock_get):
        """Missing or non-positive integer amounts are rejected with 400."""
        mock_get.return_value = make_req_record(company_id='tog_and_dogs')

        invalid_amounts = [None, -500, 0, 10.5, "1000", True, False]
        for amt in invalid_amounts:
            body = {'client_id': 'client-001'}
            if amt is not None:
                body['amount_cents'] = amt
                
            event = make_admin_event(
                role='admin',
                company_id='tog_and_dogs',
                body=body
            )
            response = admin_handler(event, None)
            assert response['statusCode'] == 400
            resp_body = json.loads(response['body'])
            assert "amount_cents" in resp_body["error"]

    @patch('common.db.get_item')
    @patch('common.stripe_client.create_checkout_session')
    def test_stripe_creation_failure_handled(self, mock_create, mock_get):
        """Stripe creation failure returns 500."""
        mock_get.return_value = make_req_record(company_id='tog_and_dogs')
        mock_create.side_effect = StripeAPIError("Stripe API is down", status_code=502)

        event = make_admin_event(
            role='admin',
            company_id='tog_and_dogs',
            body={'amount_cents': 15000, 'client_id': 'client-001'}
        )
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 500
        resp_body = json.loads(response['body'])
        assert "Stripe session creation failed" in resp_body["error"]

    @patch('common.db.get_item')
    @patch('common.stripe_client.create_checkout_session')
    def test_payment_status_guards_blocked(self, mock_create, mock_get):
        """Requests with status paid, refunded, or waived return 409 Conflict and do not call Stripe."""
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get

            for status in ['paid', 'refunded', 'waived', ' PAID ', 'refunded ']:
                record = make_req_record(company_id='tog_and_dogs')
                record['payment_status'] = status
                mock_get.return_value = record
                mock_create.reset_mock()

                event = make_admin_event(
                    role='admin',
                    company_id='tog_and_dogs',
                    body={'amount_cents': 15000, 'client_id': 'client-001'}
                )
                response = admin_handler(event, None)
                assert response['statusCode'] == 409
                resp_body = json.loads(response['body'])
                assert "Conflict" in resp_body["error"]
                mock_create.assert_not_called()
        finally:
            admin_handler.__globals__['get_item'] = orig_get

    @patch('common.db.get_item')
    @patch('common.db.table')
    @patch('common.stripe_client.create_checkout_session')
    def test_payment_status_guards_allowed(self, mock_create, mock_table, mock_get):
        """Requests with absent, null, payment_failed, or expired status allow session creation (returns 200)."""
        mock_create.return_value = {
            'id': 'cs_new_123',
            'url': 'https://checkout.stripe.com/pay/cs_new_123'
        }
        mock_table.update_item = MagicMock()
        
        orig_get = admin_handler.__globals__.get('get_item')
        orig_table = admin_handler.__globals__.get('table')
        try:
            from common.db import get_item as real_get, table as real_table
            admin_handler.__globals__['get_item'] = real_get
            admin_handler.__globals__['table'] = real_table

            # Test scenarios for allowed statuses
            # None (absent), '', 'payment_failed', 'expired'
            for status in [None, '', 'payment_failed', 'expired', 'payment_failed ', ' EXPIRED']:
                record = make_req_record(company_id='tog_and_dogs')
                if status is not None:
                    record['payment_status'] = status
                else:
                    record.pop('payment_status', None)
                    
                mock_get.return_value = record
                mock_create.reset_mock()
                mock_table.update_item.reset_mock()

                event = make_admin_event(
                    role='admin',
                    company_id='tog_and_dogs',
                    body={'amount_cents': 15000, 'client_id': 'client-001'}
                )
                response = admin_handler(event, None)
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert body['stripe_checkout_session_id'] == 'cs_new_123'
                mock_create.assert_called_once()
                mock_table.update_item.assert_called_once()
        finally:
            admin_handler.__globals__['get_item'] = orig_get
            admin_handler.__globals__['table'] = orig_table

    @patch('common.db.get_item')
    @patch('common.stripe_client.create_checkout_session')
    def test_payment_link_sent_existing_url_resends(self, mock_create, mock_get):
        """Requests with payment_link_sent status and existing URL return 200 with the URL without calling Stripe."""
        record = make_req_record(company_id='tog_and_dogs')
        record['payment_status'] = 'payment_link_sent'
        record['stripe_payment_url'] = 'https://checkout.stripe.com/pay/cs_existing_456'
        record['stripe_checkout_session_id'] = 'cs_existing_456'
        mock_get.return_value = record

        event = make_admin_event(
            role='admin',
            company_id='tog_and_dogs',
            body={'amount_cents': 15000, 'client_id': 'client-001'}
        )
        
        orig_get = admin_handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            admin_handler.__globals__['get_item'] = real_get
            response = admin_handler(event, None)
        finally:
            admin_handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['stripe_checkout_session_id'] == 'cs_existing_456'
        assert body['stripe_payment_url'] == 'https://checkout.stripe.com/pay/cs_existing_456'
        assert body['payment_status'] == 'payment_link_sent'
        mock_create.assert_not_called()

    @patch('common.db.get_item')
    @patch('common.db.table')
    @patch('common.stripe_client.create_checkout_session')
    def test_payment_link_sent_missing_url_creates_new(self, mock_create, mock_table, mock_get):
        """Requests with payment_link_sent status but missing URL fall back to creating a new Stripe session."""
        record = make_req_record(company_id='tog_and_dogs')
        record['payment_status'] = 'payment_link_sent'
        # missing stripe_payment_url and stripe_checkout_session_id
        mock_get.return_value = record
        
        mock_create.return_value = {
            'id': 'cs_fallback_789',
            'url': 'https://checkout.stripe.com/pay/cs_fallback_789'
        }
        mock_table.update_item = MagicMock()

        event = make_admin_event(
            role='admin',
            company_id='tog_and_dogs',
            body={'amount_cents': 15000, 'client_id': 'client-001'}
        )
        
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
        assert body['stripe_checkout_session_id'] == 'cs_fallback_789'
        mock_create.assert_called_once()
        mock_table.update_item.assert_called_once()

    @patch('common.db.get_item')
    def test_r13b_amount_validation_extended(self, mock_get):
        """Extended amount validations cover NaN, Infinity, and huge/max amounts."""
        mock_get.return_value = make_req_record(company_id='tog_and_dogs')

        # 1. NaN and Infinity
        for bad_val in [float('nan'), float('inf'), float('-inf')]:
            event = make_admin_event(
                role='admin',
                company_id='tog_and_dogs',
                body={'amount_cents': bad_val, 'client_id': 'client-001'}
            )
            response = admin_handler(event, None)
            assert response['statusCode'] == 400
            assert "amount_cents" in json.loads(response['body'])['error']

        # 2. Exceeding default limit ($10,000 / 1,000,000 cents)
        event = make_admin_event(
            role='admin',
            company_id='tog_and_dogs',
            body={'amount_cents': 1000001, 'client_id': 'client-001'}
        )
        response = admin_handler(event, None)
        assert response['statusCode'] == 400
        assert "exceeds the maximum limit" in json.loads(response['body'])['error']

        # 3. Configurable max amount limit via environment variable
        with patch.dict(os.environ, {'MAX_PAYMENT_AMOUNT_CENTS': '50000'}):
            # 50,001 cents is over the 50,000 limit
            event = make_admin_event(
                role='admin',
                company_id='tog_and_dogs',
                body={'amount_cents': 50001, 'client_id': 'client-001'}
            )
            response = admin_handler(event, None)
            assert response['statusCode'] == 400
            assert "exceeds the maximum limit of $500.00" in json.loads(response['body'])['error']


class TestStripeWebhookBookingPaymentExtension:

    def _generate_stripe_signature(self, payload, secret, timestamp=None):
        import hmac
        import hashlib
        if timestamp is None:
            timestamp = int(time.time())
        signed_payload = f"{timestamp}.{payload}"
        sig = hmac.HMAC(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={sig}"

    def _make_webhook_event(self, event_type, event_id, data_object, metadata=None):
        if metadata:
            data_object['metadata'] = metadata
        return json.dumps({
            'id': event_id,
            'type': event_type,
            'data': {'object': data_object},
        })

    def _make_api_gateway_event(self, body, signature):
        return {
            'body': body,
            'isBase64Encoded': False,
            'headers': {
                'stripe-signature': signature,
                'Content-Type': 'application/json',
            },
        }

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_webhook_booking_payment_completed_success(self, mock_put, mock_get, mock_table):
        """checkout.session.completed webhook for booking payment updates Request status to paid."""
        mock_get.side_effect = [
            None,  # Event not processed yet
            make_req_record(company_id='tog_and_dogs')  # The request record
        ]
        mock_put.return_value = True
        mock_table.update_item = MagicMock()

        secret = 'whsec_test_secret_key'
        session_obj = {
            'id': 'cs_test_123',
            'customer': 'cus_ABC',
            'payment_intent': 'pi_123',
            'amount_total': 15000,
        }
        metadata = {
            'company_id': 'tog_and_dogs',
            'request_id': 'req-001',
            'client_id': 'client-001',
            'payment_type': 'booking'
        }
        
        payload = self._make_webhook_event('checkout.session.completed', 'evt_booking_1', session_obj, metadata)
        sig = self._generate_stripe_signature(payload, secret)
        api_event = self._make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        
        orig_get = handler.__globals__.get('get_item')
        orig_table = handler.__globals__.get('table')
        orig_put = handler.__globals__.get('put_item')
        try:
            from common.db import get_item as real_get, table as real_table, put_item as real_put
            handler.__globals__['get_item'] = real_get
            handler.__globals__['table'] = real_table
            handler.__globals__['put_item'] = real_put
            
            response = handler(api_event, {})
        finally:
            handler.__globals__['get_item'] = orig_get
            handler.__globals__['table'] = orig_table
            handler.__globals__['put_item'] = orig_put

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'processed'

        # Verify request update was performed
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs['Key'] == {'PK': 'REQ#req-001', 'SK': 'CLIENT#client-001'}
        expr_vals = call_kwargs['ExpressionAttributeValues']
        assert expr_vals[':b0'] == 'paid'
        assert expr_vals[':b1'] == 'pi_123'
        assert expr_vals[':b2'] == 'cs_test_123'
        assert expr_vals[':b3'] == 'cus_ABC'

        # Verify billing event ledger was written
        assert mock_put.call_count > 0

    @patch('common.db.get_item')
    def test_webhook_missing_company_id_fails_closed(self, mock_get):
        """Webhook missing company_id fails closed (returns 400)."""
        mock_get.return_value = None  # Idempotency check

        secret = 'whsec_test_secret_key'
        session_obj = {
            'id': 'cs_test_123',
            'customer': 'cus_ABC',
            'payment_intent': 'pi_123',
            'amount_total': 15000,
        }
        metadata = {
            'request_id': 'req-001',
            'client_id': 'client-001',
            'payment_type': 'booking'
        }
        
        payload = self._make_webhook_event('checkout.session.completed', 'evt_booking_no_cid', session_obj, metadata)
        sig = self._generate_stripe_signature(payload, secret)
        api_event = self._make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert "Missing company_id for booking event" in body['error']

    @patch('common.db.get_item')
    def test_webhook_missing_request_id_fails_closed(self, mock_get):
        """Webhook missing request_id for booking payment fails closed (returns 500)."""
        mock_get.return_value = None  # Idempotency check

        secret = 'whsec_test_secret_key'
        session_obj = {
            'id': 'cs_test_123',
            'customer': 'cus_ABC',
            'payment_intent': 'pi_123',
            'amount_total': 15000,
        }
        metadata = {
            'company_id': 'tog_and_dogs',
            'client_id': 'client-001',
            'payment_type': 'booking'
        }
        
        payload = self._make_webhook_event('checkout.session.completed', 'evt_booking_no_req', session_obj, metadata)
        sig = self._generate_stripe_signature(payload, secret)
        api_event = self._make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        
        orig_get = handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            handler.__globals__['get_item'] = real_get
            response = handler(api_event, {})
        finally:
            handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'Processing failed'

    @patch('common.db.get_item')
    def test_webhook_mismatched_company_id_fails_closed(self, mock_get):
        """Webhook with company_id mismatched with Request company_id fails closed (returns 500)."""
        mock_get.side_effect = [
            None,  # Idempotency
            make_req_record(company_id='tenant_b')  # Request belongs to tenant_b
        ]

        secret = 'whsec_test_secret_key'
        session_obj = {
            'id': 'cs_test_123',
            'customer': 'cus_ABC',
            'payment_intent': 'pi_123',
            'amount_total': 15000,
        }
        metadata = {
            'company_id': 'tenant_a',  # Webhook is for tenant_a!
            'request_id': 'req-001',
            'client_id': 'client-001',
            'payment_type': 'booking'
        }
        
        payload = self._make_webhook_event('checkout.session.completed', 'evt_booking_cross_tenant', session_obj, metadata)
        sig = self._generate_stripe_signature(payload, secret)
        api_event = self._make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        
        orig_get = handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            handler.__globals__['get_item'] = real_get
            response = handler(api_event, {})
        finally:
            handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'Processing failed'

    @patch('common.db.table')
    @patch('common.db.get_item')
    def test_webhook_duplicate_is_idempotent(self, mock_get, mock_table):
        """Duplicate webhook event is skipped (idempotency)."""
        mock_get.return_value = {'processing_status': 'completed'}  # Already processed

        secret = 'whsec_test_secret_key'
        session_obj = {
            'id': 'cs_test_123',
            'customer': 'cus_ABC',
            'payment_intent': 'pi_123',
            'amount_total': 15000,
        }
        metadata = {
            'company_id': 'tog_and_dogs',
            'request_id': 'req-001',
            'client_id': 'client-001',
            'payment_type': 'booking'
        }
        
        payload = self._make_webhook_event('checkout.session.completed', 'evt_dup_123', session_obj, metadata)
        sig = self._generate_stripe_signature(payload, secret)
        api_event = self._make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        
        orig_get = handler.__globals__.get('get_item')
        try:
            from common.db import get_item as real_get
            handler.__globals__['get_item'] = real_get
            response = handler(api_event, {})
        finally:
            handler.__globals__['get_item'] = orig_get

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'already_processed'
        mock_table.update_item.assert_not_called()


class TestStripeClientCheckoutSessionDirect:

    @patch('urllib.request.urlopen')
    def test_stripe_client_payload_details(self, mock_urlopen):
        # Mock Stripe response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "cs_test_999", "url": "https://checkout.stripe.com/c/pay/cs_test_999"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Call function
        from common.stripe_client import create_checkout_session
        res = create_checkout_session(
            company_id='tog_and_dogs',
            request_id='req-001',
            client_id='client-001',
            amount_cents=15000,
            environment='sandbox'
        )

        assert res['id'] == 'cs_test_999'

        # Verify urllib.request.urlopen was called with a Request object
        mock_urlopen.assert_called_once()
        req_arg = mock_urlopen.call_args[0][0]
        
        # Verify headers and URL
        assert req_arg.full_url == "https://api.stripe.com/v1/checkout/sessions"
        assert req_arg.get_header("Authorization") == "Bearer sk_test_key"
        
        # Verify POST payload parameters
        post_data_bytes = req_arg.data
        post_data_str = post_data_bytes.decode('utf-8')
        from urllib.parse import parse_qs
        parsed_payload = parse_qs(post_data_str)

        # 1. Proving Checkout payload includes payment_method_types[0]=card
        assert parsed_payload.get('payment_method_types[0]') == ['card']

        # 2. Proving success/cancel URLs use correct domain
        success_url = parsed_payload.get('success_url')[0]
        cancel_url = parsed_payload.get('cancel_url')[0]
        assert success_url.startswith("https://toganddogs.usmissionhero.com")
        assert cancel_url.startswith("https://toganddogs.usmissionhero.com")

        # 3. Ensure existing booking metadata still passes
        assert parsed_payload.get('metadata[company_id]') == ['tog_and_dogs']
        assert parsed_payload.get('metadata[request_id]') == ['req-001']
        assert parsed_payload.get('metadata[client_id]') == ['client-001']
        assert parsed_payload.get('metadata[payment_type]') == ['booking']
        assert parsed_payload.get('metadata[environment]') == ['sandbox']

    @patch('urllib.request.urlopen')
    def test_stripe_client_custom_templates(self, mock_urlopen):
        # Mock Stripe response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "cs_test_999"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Set environment variables for templates
        from common.stripe_client import create_checkout_session
        with patch.dict(os.environ, {
            'STRIPE_SUCCESS_URL_TEMPLATE': 'https://custom-domain.com/{request_id}/success?id={{CHECKOUT_SESSION_ID}}',
            'STRIPE_CANCEL_URL_TEMPLATE': 'https://custom-domain.com/{request_id}/cancel'
        }):
            create_checkout_session(
                company_id='tog_and_dogs',
                request_id='req-123',
                client_id='client-001',
                amount_cents=1000,
                environment='sandbox'
            )

        req_arg = mock_urlopen.call_args[0][0]
        post_data_str = req_arg.data.decode('utf-8')
        from urllib.parse import parse_qs
        parsed_payload = parse_qs(post_data_str)

        assert parsed_payload.get('success_url')[0] == 'https://custom-domain.com/req-123/success?id={CHECKOUT_SESSION_ID}'
        assert parsed_payload.get('cancel_url')[0] == 'https://custom-domain.com/req-123/cancel'

