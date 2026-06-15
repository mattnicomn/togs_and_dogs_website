"""
Release 12D: Stripe Webhook Handler and Billing Foundation Tests

Covers:
  - Stripe signature verification (valid, invalid, expired, missing)
  - Event routing (known types, unknown types)
  - Idempotency (duplicate event detection)
  - checkout.session.completed → tenant metadata updated
  - customer.subscription.created → tier and status set
  - customer.subscription.updated → tier change, status change
  - customer.subscription.deleted → status = canceled
  - invoice.payment_succeeded → status = active, period updated
  - invoice.payment_failed → status = past_due
  - Missing company_id → fails closed (logged, not processed)
  - Unknown tenant → fails closed
  - Entitlement: active/trialing → allowed
  - Entitlement: past_due within grace → allowed
  - Entitlement: past_due beyond grace → read-only or blocked
  - Entitlement: canceled/paused/disabled → blocked
  - Entitlement: admin override → allowed regardless of status
  - Entitlement: unknown tenant → fail closed (disabled)
  - Entitlement: cache behavior
  - Price-to-tier resolution
"""
import sys
import os
import json
import hashlib
import hmac
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

# Set required env vars before importing modules
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('STRIPE_WEBHOOK_SECRET', 'whsec_test_secret_key')
os.environ.setdefault('STRIPE_PRICE_STARTER_MONTHLY', 'price_starter_monthly')
os.environ.setdefault('STRIPE_PRICE_PROFESSIONAL_MONTHLY', 'price_professional_monthly')
os.environ.setdefault('STRIPE_PRICE_PREMIUM_MONTHLY', 'price_premium_monthly')


# ---------------------------------------------------------------------------
# Signature Helpers
# ---------------------------------------------------------------------------

def _generate_stripe_signature(payload, secret, timestamp=None):
    """Generate a valid Stripe signature header for testing."""
    if timestamp is None:
        timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    sig = hmac.HMAC(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={sig}"


def _make_webhook_event(event_type, event_id, data_object, metadata=None):
    """Build a Stripe event JSON payload."""
    if metadata:
        data_object['metadata'] = metadata
    return json.dumps({
        'id': event_id,
        'type': event_type,
        'data': {'object': data_object},
    })


def _make_api_gateway_event(body, signature):
    """Build an API Gateway proxy event for the webhook handler."""
    return {
        'body': body,
        'isBase64Encoded': False,
        'headers': {
            'stripe-signature': signature,
            'Content-Type': 'application/json',
        },
    }


# ---------------------------------------------------------------------------
# Signature Verification Tests
# ---------------------------------------------------------------------------

class TestStripeSignatureVerification:
    """Tests for verify_stripe_signature in common.billing."""

    def test_valid_signature_parses_event(self):
        from common.billing import verify_stripe_signature

        payload = json.dumps({'id': 'evt_123', 'type': 'test'})
        secret = 'whsec_test123'
        sig = _generate_stripe_signature(payload, secret)

        result = verify_stripe_signature(payload, sig, secret)
        assert result['id'] == 'evt_123'
        assert result['type'] == 'test'

    def test_invalid_signature_raises(self):
        from common.billing import verify_stripe_signature

        payload = json.dumps({'id': 'evt_123', 'type': 'test'})
        secret = 'whsec_test123'
        wrong_secret = 'whsec_wrong'
        sig = _generate_stripe_signature(payload, wrong_secret)

        with pytest.raises(ValueError, match="No matching signature"):
            verify_stripe_signature(payload, sig, secret)

    def test_missing_signature_header_raises(self):
        from common.billing import verify_stripe_signature

        payload = json.dumps({'id': 'evt_123'})
        with pytest.raises(ValueError, match="Missing stripe-signature"):
            verify_stripe_signature(payload, '', 'whsec_test')

    def test_missing_webhook_secret_raises(self):
        from common.billing import verify_stripe_signature

        payload = json.dumps({'id': 'evt_123'})
        sig = 't=123,v1=abc'
        with pytest.raises(ValueError, match="Webhook secret not configured"):
            verify_stripe_signature(payload, sig, '')

    def test_expired_timestamp_raises(self):
        from common.billing import verify_stripe_signature

        payload = json.dumps({'id': 'evt_123', 'type': 'test'})
        secret = 'whsec_test123'
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        sig = _generate_stripe_signature(payload, secret, timestamp=old_timestamp)

        with pytest.raises(ValueError, match="timestamp too old"):
            verify_stripe_signature(payload, sig, secret)

    def test_malformed_signature_header_raises(self):
        from common.billing import verify_stripe_signature

        payload = json.dumps({'id': 'evt_123'})
        with pytest.raises(ValueError, match="Invalid stripe-signature"):
            verify_stripe_signature(payload, 'garbage_header', 'whsec_test')


# ---------------------------------------------------------------------------
# Webhook Handler Tests
# ---------------------------------------------------------------------------

class TestStripeWebhookHandler:
    """Tests for the stripe_webhook_handler.handler function."""

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_checkout_completed_updates_tenant(self, mock_put, mock_get, mock_table):
        """checkout.session.completed → tenant billing fields updated."""
        mock_get.return_value = None  # No existing event (not duplicate)
        mock_put.return_value = True
        mock_table.update_item = MagicMock()

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'checkout.session.completed', 'evt_checkout_1',
            {'customer': 'cus_ABC', 'subscription': 'sub_XYZ'},
            metadata={'company_id': 'tog_and_dogs'}
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'processed'
        # Verify tenant update was called
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs['Key'] == {'PK': 'TENANT#tog_and_dogs', 'SK': 'METADATA'}

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_subscription_deleted_sets_canceled(self, mock_put, mock_get, mock_table):
        """customer.subscription.deleted → status = canceled."""
        mock_get.return_value = None
        mock_put.return_value = True
        mock_table.update_item = MagicMock()

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'customer.subscription.deleted', 'evt_sub_del_1',
            {'id': 'sub_XYZ', 'customer': 'cus_ABC', 'status': 'canceled'},
            metadata={'company_id': 'tog_and_dogs'}
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        # Check that update_item was called with canceled status
        call_kwargs = mock_table.update_item.call_args[1]
        expr_values = call_kwargs['ExpressionAttributeValues']
        # Find the value that is 'canceled'
        assert any(v == 'canceled' for v in expr_values.values())

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_invoice_payment_failed_sets_past_due(self, mock_put, mock_get, mock_table):
        """invoice.payment_failed → status = past_due."""
        mock_get.return_value = None
        mock_put.return_value = True
        mock_table.update_item = MagicMock()

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'invoice.payment_failed', 'evt_inv_fail_1',
            {
                'id': 'in_123', 'customer': 'cus_ABC',
                'amount_due': 7900, 'currency': 'usd',
                'subscription_details': {'metadata': {'company_id': 'tog_and_dogs'}},
            },
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        call_kwargs = mock_table.update_item.call_args[1]
        expr_values = call_kwargs['ExpressionAttributeValues']
        assert any(v == 'past_due' for v in expr_values.values())

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_invoice_payment_succeeded_sets_active(self, mock_put, mock_get, mock_table):
        """invoice.payment_succeeded → status = active."""
        mock_get.return_value = None
        mock_put.return_value = True
        mock_table.update_item = MagicMock()

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'invoice.payment_succeeded', 'evt_inv_ok_1',
            {
                'id': 'in_456', 'customer': 'cus_ABC',
                'amount_paid': 7900, 'currency': 'usd',
                'period_start': 1719792000, 'period_end': 1722470400,
                'subscription_details': {'metadata': {'company_id': 'tog_and_dogs'}},
            },
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        call_kwargs = mock_table.update_item.call_args[1]
        expr_values = call_kwargs['ExpressionAttributeValues']
        assert any(v == 'active' for v in expr_values.values())

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_duplicate_event_skipped(self, mock_put, mock_get, mock_table):
        """Duplicate event_id → returns 200 without processing."""
        # Simulate already-processed event in ledger
        mock_get.return_value = {'processing_status': 'completed'}

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'checkout.session.completed', 'evt_dup_1',
            {'customer': 'cus_ABC', 'subscription': 'sub_XYZ'},
            metadata={'company_id': 'tog_and_dogs'}
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'already_processed'
        # update_item should NOT have been called (no tenant update)
        mock_table.update_item.assert_not_called()

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_unknown_event_type_ignored(self, mock_put, mock_get, mock_table):
        """Unknown event type → returns 200, logged as ignored."""
        mock_get.return_value = None
        mock_put.return_value = True

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'charge.refunded', 'evt_unknown_1',
            {'id': 'ch_123'},
            metadata={'company_id': 'tog_and_dogs'}
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'ignored'

    def test_invalid_signature_returns_401(self):
        """Invalid signature → 401 response."""
        payload = _make_webhook_event(
            'checkout.session.completed', 'evt_bad_sig',
            {'customer': 'cus_ABC'},
            metadata={'company_id': 'tog_and_dogs'}
        )
        bad_sig = 't=123,v1=definitely_not_valid'
        api_event = _make_api_gateway_event(payload, bad_sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 401

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_missing_company_id_returns_200_ignored(self, mock_put, mock_get, mock_table):
        """Event with no company_id in metadata → ignored (200, not retried)."""
        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'checkout.session.completed', 'evt_no_cid',
            {'customer': 'cus_ABC', 'subscription': 'sub_XYZ'},
            metadata={}  # No company_id
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'ignored'
        assert 'cannot_resolve_company_id' in body.get('reason', '')

    def test_empty_body_returns_400(self):
        """Empty body → 400 response."""
        api_event = {
            'body': '',
            'isBase64Encoded': False,
            'headers': {'stripe-signature': 't=123,v1=abc'},
        }

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 400

    @patch('common.db.table')
    @patch('common.db.get_item')
    @patch('common.db.put_item')
    def test_subscription_updated_changes_tier(self, mock_put, mock_get, mock_table):
        """customer.subscription.updated with new price → tier changes."""
        mock_get.return_value = None
        mock_put.return_value = True
        mock_table.update_item = MagicMock()

        secret = 'whsec_test_secret_key'
        payload = _make_webhook_event(
            'customer.subscription.updated', 'evt_sub_upd_1',
            {
                'id': 'sub_XYZ',
                'customer': 'cus_ABC',
                'status': 'active',
                'items': {
                    'data': [{
                        'price': {
                            'id': 'price_premium_monthly',
                            'recurring': {'interval': 'month'}
                        }
                    }]
                },
                'current_period_start': 1719792000,
                'current_period_end': 1722470400,
            },
            metadata={'company_id': 'tog_and_dogs'}
        )
        sig = _generate_stripe_signature(payload, secret)
        api_event = _make_api_gateway_event(payload, sig)

        from handlers.stripe_webhook_handler import handler
        response = handler(api_event, {})

        assert response['statusCode'] == 200
        call_kwargs = mock_table.update_item.call_args[1]
        expr_values = call_kwargs['ExpressionAttributeValues']
        assert any(v == 'premium' for v in expr_values.values())


# ---------------------------------------------------------------------------
# Entitlement Interface Tests
# ---------------------------------------------------------------------------

class TestTenantEntitlement:
    """Tests for get_tenant_entitlement and TenantEntitlement state logic."""

    def setup_method(self):
        """Clear entitlement cache before each test."""
        from common.billing import invalidate_entitlement_cache
        invalidate_entitlement_cache()

    @patch('common.db.get_item')
    def test_active_tenant_is_allowed(self, mock_get):
        """Active subscription → is_access_allowed = True."""
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is True
        assert ent.is_read_only is False
        assert ent.is_blocked is False
        assert ent.subscription_tier == 'professional'

    @patch('common.db.get_item')
    def test_trialing_tenant_is_allowed(self, mock_get):
        """Trialing subscription → is_access_allowed = True."""
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'starter',
            'subscription_status': 'trialing',
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is True
        assert ent.is_blocked is False

    @patch('common.db.get_item')
    def test_past_due_within_grace_is_allowed(self, mock_get):
        """Past_due within 7-day grace → is_access_allowed = True."""
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'past_due',
            'billing_status_changed_at': recent,
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is True
        assert ent.is_read_only is False
        assert ent.is_blocked is False

    @patch('common.db.get_item')
    def test_past_due_beyond_grace_is_read_only(self, mock_get):
        """Past_due beyond 7 days but within 14 days → is_read_only = True."""
        ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'past_due',
            'billing_status_changed_at': ten_days_ago,
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is False
        assert ent.is_read_only is True
        assert ent.is_blocked is False

    @patch('common.db.get_item')
    def test_past_due_beyond_read_only_is_blocked(self, mock_get):
        """Past_due beyond 14 days → is_blocked = True."""
        twenty_days_ago = (datetime.now(timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'past_due',
            'billing_status_changed_at': twenty_days_ago,
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is False
        assert ent.is_read_only is False
        assert ent.is_blocked is True

    @patch('common.db.get_item')
    def test_canceled_is_blocked(self, mock_get):
        """Canceled subscription → is_blocked = True."""
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'canceled',
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is False
        assert ent.is_blocked is True

    @patch('common.db.get_item')
    def test_paused_is_blocked(self, mock_get):
        """Paused subscription → is_blocked = True."""
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'paused',
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is False
        assert ent.is_blocked is True

    @patch('common.db.get_item')
    def test_disabled_is_blocked(self, mock_get):
        """Disabled subscription → is_blocked = True."""
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'disabled',
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is False
        assert ent.is_blocked is True

    @patch('common.db.get_item')
    def test_admin_override_allows_despite_canceled(self, mock_get):
        """Admin override active → access allowed even if canceled."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'canceled',
            'admin_override_until': future,
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is True
        assert ent.is_blocked is False

    @patch('common.db.get_item')
    def test_expired_admin_override_does_not_allow(self, mock_get):
        """Expired admin override → normal status applies."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_get.return_value = {
            'company_id': 'test_co',
            'subscription_tier': 'professional',
            'subscription_status': 'canceled',
            'admin_override_until': past,
        }

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('test_co')

        assert ent.is_access_allowed is False
        assert ent.is_blocked is True

    @patch('common.db.get_item')
    def test_unknown_tenant_fails_closed(self, mock_get):
        """Unknown tenant (None from DynamoDB) → disabled/blocked."""
        mock_get.return_value = None

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('nonexistent_co')

        assert ent.is_access_allowed is False
        assert ent.is_blocked is True
        assert ent.subscription_status == 'disabled'

    @patch('common.db.get_item')
    def test_db_error_fails_closed(self, mock_get):
        """DynamoDB error → fails closed (disabled)."""
        mock_get.side_effect = Exception("DynamoDB timeout")

        from common.billing import get_tenant_entitlement
        ent = get_tenant_entitlement('error_co')

        assert ent.is_access_allowed is False
        assert ent.is_blocked is True

    @patch('common.db.get_item')
    def test_cache_returns_same_object(self, mock_get):
        """Subsequent calls within TTL return cached entitlement."""
        mock_get.return_value = {
            'company_id': 'cached_co',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
        }

        from common.billing import get_tenant_entitlement
        ent1 = get_tenant_entitlement('cached_co')
        ent2 = get_tenant_entitlement('cached_co')

        assert ent1 is ent2
        # get_item should only be called once (cache hit on second call)
        assert mock_get.call_count == 1

    @patch('common.db.get_item')
    def test_invalidate_cache_forces_reload(self, mock_get):
        """invalidate_entitlement_cache → next call reads from DynamoDB."""
        mock_get.return_value = {
            'company_id': 'reload_co',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
        }

        from common.billing import get_tenant_entitlement, invalidate_entitlement_cache
        get_tenant_entitlement('reload_co')
        invalidate_entitlement_cache('reload_co')
        get_tenant_entitlement('reload_co')

        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Price-to-Tier Resolution Tests
# ---------------------------------------------------------------------------

class TestPriceToTier:
    """Tests for price_id_to_tier resolution."""

    def test_known_starter_price(self):
        from common.billing import price_id_to_tier
        assert price_id_to_tier('price_starter_monthly') == 'starter'

    def test_known_professional_price(self):
        from common.billing import price_id_to_tier
        assert price_id_to_tier('price_professional_monthly') == 'professional'

    def test_known_premium_price(self):
        from common.billing import price_id_to_tier
        assert price_id_to_tier('price_premium_monthly') == 'premium'

    def test_unknown_price_defaults_to_starter(self):
        from common.billing import price_id_to_tier
        assert price_id_to_tier('price_unknown_xyz') == 'starter'

    def test_none_price_defaults_to_starter(self):
        from common.billing import price_id_to_tier
        assert price_id_to_tier(None) == 'starter'

    def test_empty_price_defaults_to_starter(self):
        from common.billing import price_id_to_tier
        assert price_id_to_tier('') == 'starter'


# ---------------------------------------------------------------------------
# Billing Event Ledger Tests
# ---------------------------------------------------------------------------

class TestBillingEventLedger:
    """Tests for billing event ledger helpers."""

    @patch('common.db.put_item')
    def test_write_billing_event_success(self, mock_put):
        """write_billing_event → puts item with correct PK/SK."""
        mock_put.return_value = True

        from common.billing import write_billing_event
        result = write_billing_event('test_co', 'evt_123', 'invoice.paid', {'amount': 7900})

        assert result is True
        call_args = mock_put.call_args[0][0]
        assert call_args['PK'] == 'BILLING#test_co'
        assert call_args['SK'] == 'EVENT#evt_123'
        assert call_args['event_type'] == 'invoice.paid'
        assert call_args['amount'] == 7900
        assert call_args['processing_status'] == 'completed'

    @patch('common.db.get_item')
    def test_is_event_already_processed_true(self, mock_get):
        """Existing completed event → returns True."""
        mock_get.return_value = {'processing_status': 'completed'}

        from common.billing import is_event_already_processed
        assert is_event_already_processed('test_co', 'evt_123') is True

    @patch('common.db.get_item')
    def test_is_event_already_processed_false_no_record(self, mock_get):
        """No existing event → returns False."""
        mock_get.return_value = None

        from common.billing import is_event_already_processed
        assert is_event_already_processed('test_co', 'evt_new') is False

    @patch('common.db.get_item')
    def test_is_event_already_processed_false_failed(self, mock_get):
        """Existing failed event → returns False (should retry)."""
        mock_get.return_value = {'processing_status': 'failed'}

        from common.billing import is_event_already_processed
        assert is_event_already_processed('test_co', 'evt_fail') is False

    @patch('common.db.put_item')
    def test_record_failed_event(self, mock_put):
        """record_failed_billing_event → stores error details."""
        mock_put.return_value = True

        from common.billing import record_failed_billing_event
        result = record_failed_billing_event('test_co', 'evt_err', 'invoice.paid', 'Tenant not found')

        assert result is True
        call_args = mock_put.call_args[0][0]
        assert call_args['processing_status'] == 'failed'
        assert call_args['error_message'] == 'Tenant not found'


# ---------------------------------------------------------------------------
# Tenant Metadata Update Tests
# ---------------------------------------------------------------------------

class TestTenantBillingUpdate:
    """Tests for update_tenant_billing."""

    @patch('common.db.table')
    def test_update_tenant_billing_success(self, mock_table):
        """Successful update → returns True."""
        mock_table.update_item = MagicMock()

        from common.billing import update_tenant_billing
        result = update_tenant_billing('test_co', {
            'subscription_status': 'active',
            'subscription_tier': 'professional',
        })

        assert result is True
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs['Key'] == {'PK': 'TENANT#test_co', 'SK': 'METADATA'}
        assert 'ConditionExpression' in call_kwargs

    @patch('common.db.table')
    def test_update_tenant_billing_nonexistent_tenant(self, mock_table):
        """Conditional check fails (tenant doesn't exist) → returns False."""
        from botocore.exceptions import ClientError
        mock_table.update_item = MagicMock(
            side_effect=ClientError(
                {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'condition'}},
                'UpdateItem'
            )
        )

        from common.billing import update_tenant_billing
        result = update_tenant_billing('ghost_co', {'subscription_status': 'active'})

        assert result is False

    @patch('common.db.table')
    def test_update_tenant_billing_empty_fields(self, mock_table):
        """Empty billing_fields → returns True, no DB call."""
        from common.billing import update_tenant_billing
        result = update_tenant_billing('test_co', {})

        assert result is True
        mock_table.update_item.assert_not_called()
