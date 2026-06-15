"""
Release 12D: Stripe Webhook Handler

Receives billing event callbacks from Stripe and updates tenant metadata
and billing event ledger accordingly.

Authentication: Validates Stripe signature (HMAC-SHA256) before processing.
Route: POST /webhooks/stripe
No Cognito authorizer — this is a server-to-server webhook endpoint.

Supported events:
  - checkout.session.completed
  - customer.subscription.created
  - customer.subscription.updated
  - customer.subscription.deleted
  - invoice.payment_succeeded
  - invoice.payment_failed
"""
import json
import os

from common.billing import (
    verify_stripe_signature,
    write_billing_event,
    is_event_already_processed,
    record_failed_billing_event,
    update_tenant_billing,
    price_id_to_tier,
    invalidate_entitlement_cache,
    TIER_LIMITS,
    _now_iso,
)


def handler(event, context):
    """
    POST /webhooks/stripe
    Receives Stripe webhook events and processes billing state changes.
    """
    try:
        # 1. Extract raw body and signature
        raw_body = event.get('body', '')
        if not raw_body:
            return _raw_response(400, {"error": "Empty request body"})

        # Handle base64 encoding if present
        is_base64 = event.get('isBase64Encoded', False)
        if is_base64 and isinstance(raw_body, str):
            try:
                import base64
                raw_body = base64.b64decode(raw_body).decode('utf-8')
            except Exception as e:
                print(f"STRIPE_WEBHOOK_PARSE_FAILED: Failed to decode base64 body: {e}")
                return _raw_response(400, {"error": "Failed to decode request body"})

        headers = event.get('headers', {}) or {}
        signature = (
            headers.get('stripe-signature') or
            headers.get('Stripe-Signature') or
            headers.get('STRIPE-SIGNATURE') or
            ''
        )

        # 2. Verify Stripe signature
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
        try:
            stripe_event = verify_stripe_signature(raw_body, signature, webhook_secret)
        except ValueError as e:
            print(f"SECURITY: Stripe webhook signature verification failed: {e}")
            return _raw_response(401, {"error": "Invalid webhook signature"})

        # 3. Extract event metadata
        event_id = stripe_event.get('id', '')
        event_type = stripe_event.get('type', '')
        event_data = stripe_event.get('data', {}).get('object', {})

        if not event_id or not event_type:
            print("STRIPE_WEBHOOK_PARSE_FAILED: Missing event id or type")
            return _raw_response(400, {"error": "Missing event id or type"})

        print(f"STRIPE_WEBHOOK_RECEIVED: type={event_type}, id={event_id}")

        # 4. Resolve company_id from event
        company_id = _resolve_company_id(event_type, event_data)
        if not company_id:
            print(f"BILLING ERROR: Cannot resolve company_id for event {event_id} type={event_type}")
            return _raw_response(200, {"status": "ignored", "reason": "cannot_resolve_company_id"})

        # 5. Check idempotency
        if is_event_already_processed(company_id, event_id):
            print(f"STRIPE_WEBHOOK_DUPLICATE: event={event_id} already processed for {company_id}")
            return _raw_response(200, {"status": "already_processed"})

        # 6. Route to event-specific handler
        handler_fn = EVENT_HANDLERS.get(event_type)
        if not handler_fn:
            print(f"STRIPE_WEBHOOK_IGNORED: Unhandled event type: {event_type}")
            write_billing_event(company_id, event_id, event_type, {
                'processing_status': 'ignored',
                'ignore_reason': 'unhandled_event_type',
            })
            return _raw_response(200, {"status": "ignored", "reason": f"unhandled_event_type: {event_type}"})

        # 7. Process the event
        try:
            handler_fn(company_id, event_id, event_type, event_data)
            # Invalidate entitlement cache after billing state change
            invalidate_entitlement_cache(company_id)
            print(f"STRIPE_WEBHOOK_PROCESSED: type={event_type}, id={event_id}, company={company_id}")
            return _raw_response(200, {"status": "processed"})
        except Exception as e:
            print(f"BILLING ERROR: Failed to process event {event_id}: {e}")
            record_failed_billing_event(company_id, event_id, event_type, str(e))
            # Return 500 so Stripe retries
            return _raw_response(500, {"error": "Processing failed"})

    except Exception as e:
        print(f"STRIPE_WEBHOOK_ERROR: Unhandled error: {e}")
        return _raw_response(500, {"error": "Internal server error"})


# ---------------------------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------------------------

def _handle_checkout_completed(company_id, event_id, event_type, session):
    """Handle checkout.session.completed — link Stripe customer to tenant."""
    billing_fields = {
        'stripe_customer_id': session.get('customer'),
        'stripe_subscription_id': session.get('subscription'),
        'subscription_status': 'active',
        'billing_provider': 'stripe',
        'billing_status_reason': None,
        'billing_status_changed_at': _now_iso(),
    }

    # Remove None values
    billing_fields = {k: v for k, v in billing_fields.items() if v is not None}

    success = update_tenant_billing(company_id, billing_fields)
    if not success:
        raise RuntimeError(f"Failed to update tenant {company_id} for checkout.session.completed")

    write_billing_event(company_id, event_id, event_type, {
        'stripe_customer_id': session.get('customer'),
        'stripe_subscription_id': session.get('subscription'),
    })


def _handle_subscription_created(company_id, event_id, event_type, subscription):
    """Handle customer.subscription.created — set initial subscription state."""
    tier = _resolve_tier_from_subscription(subscription)
    status = _map_stripe_status(subscription.get('status', 'active'))

    billing_fields = {
        'subscription_status': status,
        'subscription_tier': tier,
        'stripe_subscription_id': subscription.get('id'),
        'stripe_customer_id': subscription.get('customer'),
        'billing_provider': 'stripe',
        'billing_status_reason': None,
        'billing_status_changed_at': _now_iso(),
    }

    # Period dates
    if subscription.get('current_period_start'):
        billing_fields['current_period_start'] = _iso_from_unix(subscription['current_period_start'])
    if subscription.get('current_period_end'):
        billing_fields['current_period_end'] = _iso_from_unix(subscription['current_period_end'])
    if subscription.get('trial_end'):
        billing_fields['trial_ends_at'] = _iso_from_unix(subscription['trial_end'])

    # Update limits based on tier
    if tier in TIER_LIMITS:
        billing_fields['limits'] = TIER_LIMITS[tier]

    success = update_tenant_billing(company_id, billing_fields)
    if not success:
        raise RuntimeError(f"Failed to update tenant {company_id} for subscription.created")

    write_billing_event(company_id, event_id, event_type, {
        'subscription_tier': tier,
        'stripe_subscription_id': subscription.get('id'),
    })


def _handle_subscription_updated(company_id, event_id, event_type, subscription):
    """Handle customer.subscription.updated — update tier, status, period."""
    tier = _resolve_tier_from_subscription(subscription)
    status = _map_stripe_status(subscription.get('status', 'active'))

    billing_fields = {
        'subscription_status': status,
        'subscription_tier': tier,
        'billing_status_changed_at': _now_iso(),
    }

    # Price/interval
    items = subscription.get('items', {}).get('data', [])
    if items:
        price = items[0].get('price', {})
        billing_fields['stripe_price_id'] = price.get('id')
        recurring = price.get('recurring', {})
        if recurring:
            billing_fields['billing_interval'] = recurring.get('interval', 'month')

    # Period dates
    if subscription.get('current_period_start'):
        billing_fields['current_period_start'] = _iso_from_unix(subscription['current_period_start'])
    if subscription.get('current_period_end'):
        billing_fields['current_period_end'] = _iso_from_unix(subscription['current_period_end'])
    if subscription.get('trial_end'):
        billing_fields['trial_ends_at'] = _iso_from_unix(subscription['trial_end'])

    # Update limits based on new tier
    if tier in TIER_LIMITS:
        billing_fields['limits'] = TIER_LIMITS[tier]

    # Clear billing_status_reason if now active
    if status == 'active':
        billing_fields['billing_status_reason'] = None

    success = update_tenant_billing(company_id, billing_fields)
    if not success:
        raise RuntimeError(f"Failed to update tenant {company_id} for subscription.updated")

    write_billing_event(company_id, event_id, event_type, {
        'subscription_tier': tier,
        'subscription_status': status,
    })


def _handle_subscription_deleted(company_id, event_id, event_type, subscription):
    """Handle customer.subscription.deleted — set status to canceled."""
    billing_fields = {
        'subscription_status': 'canceled',
        'billing_status_reason': 'subscription_canceled',
        'billing_status_changed_at': _now_iso(),
    }

    success = update_tenant_billing(company_id, billing_fields)
    if not success:
        raise RuntimeError(f"Failed to update tenant {company_id} for subscription.deleted")

    write_billing_event(company_id, event_id, event_type, {
        'previous_status': _map_stripe_status(subscription.get('status', '')),
    })


def _handle_invoice_paid(company_id, event_id, event_type, invoice):
    """Handle invoice.payment_succeeded — confirm active, update period."""
    billing_fields = {
        'subscription_status': 'active',
        'billing_status_reason': None,
        'billing_status_changed_at': _now_iso(),
    }

    # Update period from invoice lines
    if invoice.get('period_end'):
        billing_fields['current_period_end'] = _iso_from_unix(invoice['period_end'])
    if invoice.get('period_start'):
        billing_fields['current_period_start'] = _iso_from_unix(invoice['period_start'])

    success = update_tenant_billing(company_id, billing_fields)
    if not success:
        raise RuntimeError(f"Failed to update tenant {company_id} for invoice.payment_succeeded")

    write_billing_event(company_id, event_id, event_type, {
        'amount': invoice.get('amount_paid'),
        'currency': invoice.get('currency'),
        'stripe_invoice_id': invoice.get('id'),
    })


def _handle_invoice_failed(company_id, event_id, event_type, invoice):
    """Handle invoice.payment_failed — set status to past_due."""
    billing_fields = {
        'subscription_status': 'past_due',
        'billing_status_reason': 'payment_failed',
        'billing_status_changed_at': _now_iso(),
    }

    success = update_tenant_billing(company_id, billing_fields)
    if not success:
        raise RuntimeError(f"Failed to update tenant {company_id} for invoice.payment_failed")

    write_billing_event(company_id, event_id, event_type, {
        'amount': invoice.get('amount_due'),
        'currency': invoice.get('currency'),
        'stripe_invoice_id': invoice.get('id'),
        'attempt_count': invoice.get('attempt_count'),
    })


# ---------------------------------------------------------------------------
# Event Handler Registry
# ---------------------------------------------------------------------------

EVENT_HANDLERS = {
    'checkout.session.completed': _handle_checkout_completed,
    'customer.subscription.created': _handle_subscription_created,
    'customer.subscription.updated': _handle_subscription_updated,
    'customer.subscription.deleted': _handle_subscription_deleted,
    'invoice.payment_succeeded': _handle_invoice_paid,
    'invoice.payment_failed': _handle_invoice_failed,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_company_id(event_type, event_data):
    """
    Extract company_id from Stripe event data.

    Priority:
    1. metadata.company_id on the object
    2. subscription metadata (for invoice events linked to subscriptions)
    3. None if unresolvable
    """
    # Direct metadata on the event object
    metadata = event_data.get('metadata', {}) or {}
    company_id = metadata.get('company_id')
    if company_id:
        return company_id

    # For subscription events, check subscription metadata
    if 'subscription' in event_type:
        return metadata.get('company_id')

    # For invoice events, try subscription_details or lines metadata
    if 'invoice' in event_type:
        # Check subscription_details
        sub_details = event_data.get('subscription_details', {}) or {}
        sub_metadata = sub_details.get('metadata', {}) or {}
        company_id = sub_metadata.get('company_id')
        if company_id:
            return company_id

        # Check lines data
        lines = event_data.get('lines', {}).get('data', [])
        for line in lines:
            line_metadata = line.get('metadata', {}) or {}
            if line_metadata.get('company_id'):
                return line_metadata['company_id']

    return None


def _resolve_tier_from_subscription(subscription):
    """Extract tier from subscription's price ID."""
    items = subscription.get('items', {}).get('data', [])
    if items:
        price_id = items[0].get('price', {}).get('id')
        if price_id:
            return price_id_to_tier(price_id)
    return 'starter'


def _map_stripe_status(stripe_status):
    """Map Stripe subscription status to our internal status."""
    status_map = {
        'active': 'active',
        'trialing': 'trialing',
        'past_due': 'past_due',
        'canceled': 'canceled',
        'incomplete': 'past_due',
        'incomplete_expired': 'canceled',
        'paused': 'paused',
        'unpaid': 'past_due',
    }
    return status_map.get(stripe_status, 'disabled')


def _iso_from_unix(unix_timestamp):
    """Convert Unix timestamp to ISO string."""
    if not unix_timestamp:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(int(unix_timestamp), tz=timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, TypeError, OSError):
        return None


def _raw_response(status_code, body_dict):
    """Returns a raw API Gateway response (no CORS — webhook is server-to-server)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_dict)
    }
