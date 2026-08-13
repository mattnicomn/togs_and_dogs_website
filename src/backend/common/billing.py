"""
Release 12D: Billing and Entitlement Foundation

Provides:
  - TenantEntitlement dataclass for structured entitlement state
  - get_tenant_entitlement(company_id) with in-memory cache
  - Tier limits and feature flag resolution
  - Billing event ledger helpers
  - Tenant metadata billing update helpers
  - Stripe signature verification (without requiring stripe SDK)

No external dependencies beyond stdlib + boto3 (already available in Lambda).
Stripe signature verification uses HMAC-SHA256 directly.
"""
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

from common.tenant_catalog import (
    ALLOWED_STATUSES as CATALOG_ALLOWED_STATUSES,
    BLOCKED_STATUSES as CATALOG_BLOCKED_STATUSES,
    get_all_tier_limits,
)


# ---------------------------------------------------------------------------
# Tier Limits Configuration
# ---------------------------------------------------------------------------

# Preserve the long-standing public symbol while sourcing it from the canonical
# catalog. The accessor returns a deep copy, so callers cannot mutate catalog
# state through billing.TIER_LIMITS.
TIER_LIMITS = get_all_tier_limits()

# Statuses that allow full access
ALLOWED_STATUSES = tuple(
    status for status in ('active', 'trialing')
    if status in CATALOG_ALLOWED_STATUSES
)

# Statuses that block access entirely
BLOCKED_STATUSES = tuple(
    status for status in ('canceled', 'paused', 'disabled')
    if status in CATALOG_BLOCKED_STATUSES
)

# Grace period duration in seconds (7 days)
GRACE_PERIOD_SECONDS = 7 * 24 * 60 * 60

# Read-only period after grace (7 more days = 14 total)
READ_ONLY_PERIOD_SECONDS = 14 * 24 * 60 * 60

# Entitlement cache TTL in seconds
CACHE_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# TenantEntitlement
# ---------------------------------------------------------------------------

class TenantEntitlement:
    """Structured representation of a tenant's billing/entitlement state."""

    def __init__(self, company_id, subscription_tier='starter',
                 subscription_status='disabled', limits=None,
                 feature_flags=None, admin_override_until=None,
                 status_changed_at=None, cached_at=None):
        self.company_id = company_id
        self.subscription_tier = subscription_tier
        self.subscription_status = subscription_status
        self.limits = limits or TIER_LIMITS.get(subscription_tier, TIER_LIMITS['starter'])
        self.feature_flags = feature_flags or {}
        self.admin_override_until = admin_override_until
        self.status_changed_at = status_changed_at
        self.cached_at = cached_at or _now_iso()

    @property
    def is_access_allowed(self):
        """Determine if tenant has active access (full or grace)."""
        # Admin override takes precedence
        if self._is_override_active():
            return True

        if self.subscription_status in ALLOWED_STATUSES:
            return True

        # Grace period for past_due
        if self.subscription_status == 'past_due':
            return self._is_within_grace_period()

        return False

    @property
    def is_read_only(self):
        """True if past_due and beyond grace period but within read-only window."""
        if self.subscription_status != 'past_due':
            return False
        if self._is_override_active():
            return False
        if self._is_within_grace_period():
            return False
        return self._is_within_read_only_period()

    @property
    def is_blocked(self):
        """True if access is completely denied."""
        if self._is_override_active():
            return False
        if self.subscription_status in BLOCKED_STATUSES:
            return True
        if self.subscription_status == 'past_due':
            return not self._is_within_grace_period() and not self._is_within_read_only_period()
        return False

    def _is_override_active(self):
        if not self.admin_override_until:
            return False
        try:
            override_dt = datetime.fromisoformat(self.admin_override_until.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) < override_dt
        except (ValueError, AttributeError):
            return False

    def _is_within_grace_period(self):
        if not self.status_changed_at:
            return True  # If we don't know when status changed, assume grace
        try:
            changed_dt = datetime.fromisoformat(self.status_changed_at.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - changed_dt).total_seconds()
            return elapsed <= GRACE_PERIOD_SECONDS
        except (ValueError, AttributeError):
            return True

    def _is_within_read_only_period(self):
        if not self.status_changed_at:
            return True
        try:
            changed_dt = datetime.fromisoformat(self.status_changed_at.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - changed_dt).total_seconds()
            return elapsed <= READ_ONLY_PERIOD_SECONDS
        except (ValueError, AttributeError):
            return True

    def to_dict(self):
        return {
            'company_id': self.company_id,
            'subscription_tier': self.subscription_tier,
            'subscription_status': self.subscription_status,
            'is_access_allowed': self.is_access_allowed,
            'is_read_only': self.is_read_only,
            'is_blocked': self.is_blocked,
            'limits': self.limits,
            'feature_flags': self.feature_flags,
            'admin_override_until': self.admin_override_until,
            'cached_at': self.cached_at,
        }


# ---------------------------------------------------------------------------
# Entitlement Cache
# ---------------------------------------------------------------------------

_entitlement_cache = {}


def get_tenant_entitlement(company_id):
    """
    Load tenant entitlement with in-memory caching.

    Fail-closed: returns a BLOCKED entitlement if tenant cannot be resolved.
    Cache TTL: 5 minutes.
    """
    cached = _entitlement_cache.get(company_id)
    if cached and not _is_cache_expired(cached):
        return cached

    # Attempt to load from DynamoDB
    try:
        from common.db import get_item
        tenant = get_item(f"TENANT#{company_id}", "METADATA")
    except Exception as e:
        print(f"BILLING ERROR: Failed to load tenant {company_id}: {e}")
        tenant = None

    if not tenant:
        # FAIL CLOSED — deny access for unknown/unresolvable tenants
        blocked = TenantEntitlement(
            company_id=company_id,
            subscription_tier='starter',
            subscription_status='disabled',
        )
        return blocked

    entitlement = _build_entitlement(tenant)
    _entitlement_cache[company_id] = entitlement
    return entitlement


def invalidate_entitlement_cache(company_id=None):
    """Clear cached entitlement. If company_id is None, clears all."""
    if company_id:
        _entitlement_cache.pop(company_id, None)
    else:
        _entitlement_cache.clear()


def _build_entitlement(tenant):
    """Build a TenantEntitlement from a raw DynamoDB tenant metadata record."""
    tier = tenant.get('subscription_tier', 'starter')
    status = tenant.get('subscription_status', 'disabled')
    limits = tenant.get('limits') or TIER_LIMITS.get(tier, TIER_LIMITS['starter'])
    feature_flags = tenant.get('feature_flags', {})
    admin_override = tenant.get('admin_override_until')
    status_changed = tenant.get('billing_status_changed_at')

    return TenantEntitlement(
        company_id=tenant.get('company_id', ''),
        subscription_tier=tier,
        subscription_status=status,
        limits=limits,
        feature_flags=feature_flags,
        admin_override_until=admin_override,
        status_changed_at=status_changed,
    )


def _is_cache_expired(entitlement):
    """Check if cached entitlement is older than TTL."""
    try:
        cached_dt = datetime.fromisoformat(entitlement.cached_at.replace('Z', '+00:00'))
        elapsed = (datetime.now(timezone.utc) - cached_dt).total_seconds()
        return elapsed > CACHE_TTL_SECONDS
    except (ValueError, AttributeError, TypeError):
        return True


# ---------------------------------------------------------------------------
# Stripe Signature Verification (No SDK Required)
# ---------------------------------------------------------------------------

STRIPE_SIGNATURE_TOLERANCE = 300  # 5 minutes


def verify_stripe_signature(payload, signature_header, webhook_secret):
    """
    Verify a Stripe webhook signature without the stripe SDK.

    Uses HMAC-SHA256 as per Stripe's webhook verification spec.
    Raises ValueError if signature is invalid or timestamp is too old.

    Args:
        payload: raw request body string
        signature_header: value of the stripe-signature header
        webhook_secret: the webhook signing secret (whsec_...)

    Returns:
        The parsed event dict on success.
    """
    if not signature_header:
        raise ValueError("Missing stripe-signature header")
    if not webhook_secret:
        raise ValueError("Webhook secret not configured")

    # Parse signature header: t=timestamp,v1=signature[,v1=signature...]
    elements = {}
    for item in signature_header.split(','):
        parts = item.strip().split('=', 1)
        if len(parts) == 2:
            key, value = parts
            if key not in elements:
                elements[key] = []
            elements[key].append(value)

    timestamp_str = (elements.get('t') or [None])[0]
    signatures = elements.get('v1', [])

    if not timestamp_str or not signatures:
        raise ValueError("Invalid stripe-signature header format")

    # Check timestamp tolerance
    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        raise ValueError("Invalid timestamp in stripe-signature header")

    current_time = int(time.time())
    if abs(current_time - timestamp) > STRIPE_SIGNATURE_TOLERANCE:
        raise ValueError("Webhook timestamp too old — possible replay attack")

    # Compute expected signature
    signed_payload = f"{timestamp_str}.{payload}"
    expected_sig = hmac.HMAC(
        webhook_secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Compare against provided signatures
    for sig in signatures:
        if hmac.compare_digest(expected_sig, sig):
            # Signature valid — parse and return event
            try:
                event = json.loads(payload)
                return event
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(f"Valid signature but invalid JSON payload: {e}")

    raise ValueError("No matching signature found — webhook signature verification failed")


# ---------------------------------------------------------------------------
# Billing Event Ledger Helpers
# ---------------------------------------------------------------------------

def write_billing_event(company_id, stripe_event_id, event_type, extra_fields=None):
    """
    Write a billing event to the ledger.

    PK: BILLING#{company_id}
    SK: EVENT#{stripe_event_id}

    Returns True on success, False on error.
    """
    from common.db import put_item

    item = {
        'PK': f'BILLING#{company_id}',
        'SK': f'EVENT#{stripe_event_id}',
        'company_id': company_id,
        'stripe_event_id': stripe_event_id,
        'event_type': event_type,
        'processing_status': 'completed',
        'processed_at': _now_iso(),
    }

    if extra_fields and isinstance(extra_fields, dict):
        item.update(extra_fields)

    return put_item(item)


def is_event_already_processed(company_id, stripe_event_id):
    """
    Check idempotency — has this Stripe event already been processed?

    Returns True if already processed, False otherwise.
    """
    from common.db import get_item

    existing = get_item(f'BILLING#{company_id}', f'EVENT#{stripe_event_id}')
    return existing is not None and existing.get('processing_status') == 'completed'


def record_failed_billing_event(company_id, stripe_event_id, event_type, error_message):
    """Record a failed billing event for audit/debugging."""
    from common.db import put_item

    item = {
        'PK': f'BILLING#{company_id}',
        'SK': f'EVENT#{stripe_event_id}',
        'company_id': company_id,
        'stripe_event_id': stripe_event_id,
        'event_type': event_type,
        'processing_status': 'failed',
        'error_message': str(error_message)[:500],
        'processed_at': _now_iso(),
    }

    return put_item(item)


# ---------------------------------------------------------------------------
# Tenant Metadata Billing Updates
# ---------------------------------------------------------------------------

def update_tenant_billing(company_id, billing_fields):
    """
    Update billing-related fields on the tenant metadata record.

    Uses conditional expression to ensure tenant exists (fail-closed).
    Always sets updated_at.

    Args:
        company_id: the tenant company_id
        billing_fields: dict of fields to update

    Returns True on success, False on error.
    """
    from common.db import table as _table
    from botocore.exceptions import ClientError

    if not billing_fields:
        return True

    billing_fields['updated_at'] = _now_iso()
    billing_fields['updated_by'] = 'system:stripe_webhook'

    update_parts = []
    expr_names = {}
    expr_values = {}

    for i, (key, value) in enumerate(billing_fields.items()):
        name_key = f"#b{i}"
        val_key = f":b{i}"
        update_parts.append(f"{name_key} = {val_key}")
        expr_names[name_key] = key
        expr_values[val_key] = value

    try:
        _table.update_item(
            Key={'PK': f'TENANT#{company_id}', 'SK': 'METADATA'},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ConditionExpression="attribute_exists(PK)",
        )
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ConditionalCheckFailedException':
            print(f"BILLING ERROR: Tenant {company_id} does not exist — cannot update billing fields")
        else:
            print(f"BILLING ERROR: Failed to update tenant {company_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Price-to-Tier Resolution
# ---------------------------------------------------------------------------

def price_id_to_tier(price_id):
    """
    Resolve a Stripe price_id to a subscription tier.
    Uses environment variables for mapping.
    Returns 'starter' as safe default for unknown price IDs.
    """
    if not price_id:
        return 'starter'

    price_map = {
        os.environ.get('STRIPE_PRICE_STARTER_MONTHLY'): 'starter',
        os.environ.get('STRIPE_PRICE_PROFESSIONAL_MONTHLY'): 'professional',
        os.environ.get('STRIPE_PRICE_PREMIUM_MONTHLY'): 'premium',
        os.environ.get('STRIPE_PRICE_STARTER_ANNUAL'): 'starter',
        os.environ.get('STRIPE_PRICE_PROFESSIONAL_ANNUAL'): 'professional',
        os.environ.get('STRIPE_PRICE_PREMIUM_ANNUAL'): 'premium',
    }

    # Remove None keys
    price_map = {k: v for k, v in price_map.items() if k is not None}

    tier = price_map.get(price_id)
    if not tier:
        print(f"BILLING WARNING: Unknown price_id {price_id}, defaulting to starter")
        return 'starter'
    return tier


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now_iso():
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
