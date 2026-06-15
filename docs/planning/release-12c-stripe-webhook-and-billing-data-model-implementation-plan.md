# Release 12C: Stripe Webhook and Billing Data Model Implementation Plan

**Status:** Planning
**Priority:** High (must complete before billing implementation)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Stripe Changes:** None
**Scope:** Define webhook handler architecture, billing event ledger, tenant metadata update flow, and entitlement interface

---

## 1. Webhook Endpoint Architecture

### Route Design

| Field | Value |
|-------|-------|
| Route | `POST /webhooks/stripe` |
| Authentication | Stripe signature verification only (no Cognito) |
| Lambda | Existing backend Lambda (new handler module) |
| Raw body required | Yes — signature verification needs unmodified payload |
| Response | 200 on success, 400 on invalid signature, 500 on processing error |

### Why Existing Lambda (Not a New Function)

- Reuses existing DynamoDB table connection and common utilities
- Shares `get_item`, `put_item`, `update_item` helpers
- Keeps deployment atomic (one backend.zip, one Lambda)
- Avoids Terraform complexity of a second function + API Gateway route
- Handler isolation achieved via separate module file (`stripe_webhook_handler.py`)

### API Gateway Configuration

```
POST /webhooks/stripe → Lambda (existing backend)
  - No Cognito authorizer (webhook is server-to-server)
  - Binary media types: application/json (raw body passthrough)
  - Integration: Lambda proxy (event contains raw body)
```

### Request Flow

```
Stripe → API Gateway (POST /webhooks/stripe)
       → Lambda handler (stripe_webhook_handler.py)
       → Verify signature (stripe-signature header + STRIPE_WEBHOOK_SECRET)
       → Parse event
       → Check idempotency (BILLING#{company_id} / EVENT#{stripe_event_id})
       → Route to event-specific handler
       → Update TENANT#{company_id} / METADATA
       → Write BILLING#{company_id} / EVENT#{timestamp}#{event_type}
       → Return 200
```

### Raw Body Requirement

Stripe signature verification requires the exact raw request body (no parsing, no whitespace changes). The Lambda proxy integration provides this via `event['body']`. The handler must NOT parse the body before signature verification.

```python
# Correct order:
raw_body = event['body']                    # raw string
signature = event['headers']['stripe-signature']
stripe_event = stripe.Webhook.construct_event(raw_body, signature, webhook_secret)
# NOW safe to use stripe_event as parsed object
```

---

## 2. Handler Module Structure

### Proposed File

```
src/backend/handlers/stripe_webhook_handler.py
```

### Module Interface

```python
def handle_stripe_webhook(event, context):
    """
    Entry point for POST /webhooks/stripe.
    
    1. Extract raw body and signature header
    2. Verify Stripe signature
    3. Parse event type and metadata
    4. Check idempotency
    5. Route to event-specific processor
    6. Return response
    """
```

### Event Router Pattern

```python
EVENT_HANDLERS = {
    'checkout.session.completed': handle_checkout_completed,
    'customer.subscription.created': handle_subscription_created,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_succeeded': handle_invoice_paid,
    'invoice.payment_failed': handle_invoice_failed,
}

def route_event(stripe_event):
    event_type = stripe_event['type']
    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        return handler(stripe_event)
    else:
        # Log unknown event type, return 200 (don't retry unknown events)
        print(f"BILLING: Ignoring unhandled event type: {event_type}")
        return success_response()
```

---

## 3. Stripe Events — Initial Support

### Event-to-State Mapping

| Stripe Event | Tenant Field Updates | Ledger Entry |
|--------------|---------------------|--------------|
| `checkout.session.completed` | `stripe_customer_id`, `stripe_subscription_id`, `subscription_status = active`, `billing_provider = stripe` | ✅ |
| `customer.subscription.created` | `subscription_status = active`, `subscription_tier` (from price metadata), `current_period_start`, `current_period_end`, `trial_ends_at` | ✅ |
| `customer.subscription.updated` | `subscription_tier`, `subscription_status`, `current_period_start`, `current_period_end`, `stripe_price_id`, `billing_interval` | ✅ |
| `customer.subscription.deleted` | `subscription_status = canceled`, `billing_status_reason = subscription_canceled` | ✅ |
| `invoice.payment_succeeded` | `subscription_status = active`, `current_period_end`, `billing_status_reason = null` | ✅ |
| `invoice.payment_failed` | `subscription_status = past_due`, `billing_status_reason = payment_failed` | ✅ |

### Detailed State Transitions

#### checkout.session.completed

```python
def handle_checkout_completed(stripe_event):
    session = stripe_event['data']['object']
    company_id = session['metadata']['company_id']
    
    update_tenant_metadata(company_id, {
        'stripe_customer_id': session['customer'],
        'stripe_subscription_id': session['subscription'],
        'subscription_status': 'active',
        'billing_provider': 'stripe',
        'updated_at': now_iso(),
        'updated_by': 'system:stripe_webhook',
        'update_source': stripe_event['id']
    })
```

#### customer.subscription.updated

```python
def handle_subscription_updated(stripe_event):
    subscription = stripe_event['data']['object']
    company_id = subscription['metadata']['company_id']
    
    # Derive tier from price ID
    tier = price_id_to_tier(subscription['items']['data'][0]['price']['id'])
    
    # Derive status
    status = map_stripe_status(subscription['status'])
    # stripe statuses: active, past_due, canceled, incomplete, incomplete_expired, trialing, paused
    
    update_tenant_metadata(company_id, {
        'subscription_tier': tier,
        'subscription_status': status,
        'stripe_price_id': subscription['items']['data'][0]['price']['id'],
        'billing_interval': subscription['items']['data'][0]['price']['recurring']['interval'],
        'current_period_start': iso_from_unix(subscription['current_period_start']),
        'current_period_end': iso_from_unix(subscription['current_period_end']),
        'trial_ends_at': iso_from_unix(subscription.get('trial_end')),
        'updated_at': now_iso(),
        'updated_by': 'system:stripe_webhook',
        'update_source': stripe_event['id']
    })
```

#### customer.subscription.deleted

```python
def handle_subscription_deleted(stripe_event):
    subscription = stripe_event['data']['object']
    company_id = subscription['metadata']['company_id']
    
    update_tenant_metadata(company_id, {
        'subscription_status': 'canceled',
        'billing_status_reason': 'subscription_canceled',
        'updated_at': now_iso(),
        'updated_by': 'system:stripe_webhook',
        'update_source': stripe_event['id']
    })
```

#### invoice.payment_failed

```python
def handle_invoice_failed(stripe_event):
    invoice = stripe_event['data']['object']
    # Resolve company_id via stripe_customer_id lookup
    company_id = resolve_company_from_customer(invoice['customer'])
    
    update_tenant_metadata(company_id, {
        'subscription_status': 'past_due',
        'billing_status_reason': 'payment_failed',
        'updated_at': now_iso(),
        'updated_by': 'system:stripe_webhook',
        'update_source': stripe_event['id']
    })
    
    # Trigger admin notification
    send_payment_failed_notification(company_id)
```

### Stripe Status to Our Status Mapping

| Stripe `subscription.status` | Our `subscription_status` |
|-------------------------------|---------------------------|
| `active` | `active` |
| `trialing` | `trialing` |
| `past_due` | `past_due` |
| `canceled` | `canceled` |
| `incomplete` | `past_due` |
| `incomplete_expired` | `canceled` |
| `paused` | `paused` |
| `unpaid` | `past_due` |

---

## 4. Billing Event Ledger

### DynamoDB Key Pattern

```
PK: BILLING#{company_id}
SK: EVENT#{stripe_event_id}
```

**Why `stripe_event_id` in SK (not timestamp)?**
- Guarantees uniqueness (Stripe event IDs are globally unique)
- Enables O(1) idempotency check (`get_item` by exact PK+SK)
- Avoids timestamp collision if two events arrive in the same millisecond

### Ledger Record Shape

```json
{
  "PK": "BILLING#tog_and_dogs",
  "SK": "EVENT#evt_1234567890abcdef",
  "company_id": "tog_and_dogs",
  "stripe_event_id": "evt_1234567890abcdef",
  "event_type": "invoice.payment_succeeded",
  "event_timestamp": "2025-07-01T00:00:00Z",
  "amount": 7900,
  "currency": "usd",
  "stripe_customer_id": "cus_XXXXXXXXXXXXXX",
  "stripe_subscription_id": "sub_XXXXXXXXXXXXXX",
  "stripe_invoice_id": "in_XXXXXXXXXXXXXX",
  "period_start": "2025-07-01T00:00:00Z",
  "period_end": "2025-08-01T00:00:00Z",
  "subscription_tier": "professional",
  "processing_status": "completed",
  "processed_at": "2025-07-01T00:00:05Z",
  "error_message": null,
  "retry_count": 0
}
```

### Idempotency Check

```python
def is_already_processed(company_id, stripe_event_id):
    """Check if this event has already been processed."""
    existing = get_item(f"BILLING#{company_id}", f"EVENT#{stripe_event_id}")
    return existing is not None and existing.get('processing_status') == 'completed'
```

### Error Recording

If processing fails after signature verification:

```python
def record_failed_event(company_id, stripe_event_id, event_type, error_message):
    put_item({
        'PK': f'BILLING#{company_id}',
        'SK': f'EVENT#{stripe_event_id}',
        'company_id': company_id,
        'stripe_event_id': stripe_event_id,
        'event_type': event_type,
        'processing_status': 'failed',
        'error_message': str(error_message),
        'processed_at': now_iso(),
        'retry_count': 0
    })
```

### Querying the Ledger

For audit/reporting, query by company:

```python
# Get all billing events for a tenant (most recent first)
events = query(
    PK=f"BILLING#{company_id}",
    ScanIndexForward=False
)
```

---

## 5. Tenant Metadata Update Strategy

### Update Target

```
PK: TENANT#{company_id}
SK: METADATA
```

### Conditional Update Pattern

```python
def update_tenant_metadata(company_id, updates):
    """
    Update tenant metadata with billing fields.
    Uses conditional expression to ensure tenant exists.
    """
    update_expression_parts = []
    expression_values = {}
    
    for key, value in updates.items():
        update_expression_parts.append(f"#{key} = :{key}")
        expression_values[f":{key}"] = value
    
    table.update_item(
        Key={'PK': f'TENANT#{company_id}', 'SK': 'METADATA'},
        UpdateExpression="SET " + ", ".join(update_expression_parts),
        ExpressionAttributeValues=expression_values,
        ConditionExpression="attribute_exists(PK)",  # Fail if tenant doesn't exist
    )
```

### Fail-Closed: Unknown Tenant

If the webhook references a `company_id` that doesn't have a TENANT record:

1. Log error: `"BILLING ERROR: No tenant record found for company_id={company_id}"`
2. Record failed event in ledger with `processing_status = failed`
3. Return 200 to Stripe (don't trigger retries for data issues)
4. Alert via CloudWatch alarm for manual investigation

### Company ID Resolution

Stripe events carry `company_id` in different locations:

| Event | Where to Find company_id |
|-------|--------------------------|
| `checkout.session.completed` | `session.metadata.company_id` |
| `customer.subscription.*` | `subscription.metadata.company_id` |
| `invoice.*` | Must resolve via `customer_id` → tenant lookup |

### Customer-to-Tenant Resolution (for invoice events)

Invoice events don't always carry metadata. Resolution path:

```python
def resolve_company_from_customer(stripe_customer_id):
    """
    Find company_id by scanning tenant records for matching stripe_customer_id.
    Uses GSI or scan with filter (prefer GSI if available).
    """
    # Option A: GSI on stripe_customer_id (recommended if volume grows)
    # Option B: Scan TENANT# records with filter (acceptable for <100 tenants)
    results = query_by_begins_with("TENANT#", filter={"stripe_customer_id": stripe_customer_id})
    if not results:
        raise ValueError(f"No tenant found for Stripe customer {stripe_customer_id}")
    return results[0]['company_id']
```

**Decision:** Start with scan+filter (Option B). Add GSI if tenant count exceeds 50.

---

## 6. Entitlement Interface Design

### Function Signature

```python
def get_tenant_entitlement(company_id: str) -> TenantEntitlement:
    """
    Load and cache tenant entitlement status.
    
    Returns a TenantEntitlement object with subscription status,
    tier limits, and feature flags.
    
    Fail-closed: returns DENIED if tenant cannot be resolved.
    """
```

### Return Object

```python
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class TenantEntitlement:
    company_id: str
    subscription_tier: str          # starter | professional | premium | enterprise
    subscription_status: str        # active | trialing | past_due | canceled | paused | disabled
    is_access_allowed: bool         # derived: True if active/trialing/grace period
    is_read_only: bool              # derived: True if past_due and past grace period
    limits: Dict[str, int]          # max_clients, max_staff, max_notifications, max_bookings
    feature_flags: Dict[str, bool]  # google_calendar, export, branding, video
    admin_override_until: Optional[str]  # ISO timestamp or None
    grace_period_ends_at: Optional[str]  # calculated from status change + 7 days
    cached_at: str                  # ISO timestamp
```

### Access Decision Logic

```python
def is_access_allowed(entitlement: TenantEntitlement) -> bool:
    """Determine if tenant has active access."""
    
    # Admin override takes precedence
    if entitlement.admin_override_until:
        if now() < parse_iso(entitlement.admin_override_until):
            return True
    
    # Active statuses
    if entitlement.subscription_status in ('active', 'trialing'):
        return True
    
    # Grace period for past_due (7 days)
    if entitlement.subscription_status == 'past_due':
        if entitlement.grace_period_ends_at and now() < parse_iso(entitlement.grace_period_ends_at):
            return True  # Within grace period
        return False  # Grace period expired
    
    # All other statuses: denied
    return False
```

### Status Categories

| Category | Statuses | Behavior |
|----------|----------|----------|
| Allowed | `active`, `trialing` | Full access |
| Grace | `past_due` (within 7 days) | Full access + warning banner |
| Read-only | `past_due` (after 7 days, before 14 days) | View only, no create/update |
| Blocked | `canceled`, `paused`, `disabled` | Login denied, redirect to billing |

### Cache Strategy

```python
# Module-level cache (persists across warm Lambda invocations)
_entitlement_cache: Dict[str, TenantEntitlement] = {}
_cache_ttl_seconds = 300  # 5 minutes

def get_tenant_entitlement(company_id: str) -> TenantEntitlement:
    cached = _entitlement_cache.get(company_id)
    if cached and not _is_expired(cached):
        return cached
    
    # Cache miss or expired — read from DynamoDB
    tenant = get_item(f"TENANT#{company_id}", "METADATA")
    if not tenant:
        # FAIL CLOSED — deny access for unknown tenants
        return TenantEntitlement(
            company_id=company_id,
            subscription_status='disabled',
            is_access_allowed=False,
            ...
        )
    
    entitlement = build_entitlement(tenant)
    _entitlement_cache[company_id] = entitlement
    return entitlement
```

### Fail-Closed vs Fail-Open Decision

| Scenario | Decision | Rationale |
|----------|----------|-----------|
| Tenant not found in DynamoDB | **Fail closed** (deny) | Unknown tenant should never have access |
| DynamoDB read error (timeout/throttle) | **Fail closed** (deny) | Security over availability |
| Cache expired + DynamoDB unavailable | **Fail closed** (deny) | Don't serve stale entitlement |
| Stripe webhook delayed | **No change** | Keep last-known status until updated |
| Admin override active | **Allow** | Explicit admin decision overrides billing |

---

## 7. Secret and Environment Variable Design

### Secrets (AWS Secrets Manager)

| Secret Name | Value Pattern | Purpose |
|-------------|---------------|---------|
| `togs-and-dogs/stripe/secret-key` | `sk_test_XXXXXX` | Server-side Stripe API calls |
| `togs-and-dogs/stripe/webhook-secret` | `whsec_XXXXXX` | Webhook signature verification |

### Environment Variables (Lambda)

| Variable | Value Pattern | Purpose |
|----------|---------------|---------|
| `STRIPE_PRICE_STARTER_MONTHLY` | `price_XXXXXX` | Checkout session creation |
| `STRIPE_PRICE_PROFESSIONAL_MONTHLY` | `price_XXXXXX` | Checkout session creation |
| `STRIPE_PRICE_PREMIUM_MONTHLY` | `price_XXXXXX` | Checkout session creation |
| `STRIPE_SECRETS_ARN` | `arn:aws:secretsmanager:...` | Reference to Secrets Manager |

### Secret Access Pattern

```python
import boto3
import json

_secrets_client = boto3.client('secretsmanager')
_stripe_secrets_cache = None

def get_stripe_secret(key_name):
    """Load Stripe secrets from Secrets Manager (cached per Lambda instance)."""
    global _stripe_secrets_cache
    if _stripe_secrets_cache is None:
        response = _secrets_client.get_secret_value(SecretId=os.environ['STRIPE_SECRETS_ARN'])
        _stripe_secrets_cache = json.loads(response['SecretString'])
    return _stripe_secrets_cache[key_name]

# Usage:
stripe.api_key = get_stripe_secret('secret_key')
webhook_secret = get_stripe_secret('webhook_secret')
```

### What Is NOT Committed to Code

- ❌ API keys (test or live)
- ❌ Webhook signing secrets
- ❌ Customer/subscription IDs
- ❌ Price IDs (stored in env vars, not code)
- ❌ Secrets Manager ARN (in Terraform config only)

---

## 8. Security Design

### Signature Verification

```python
import stripe
import hmac

def verify_stripe_signature(raw_body: str, signature_header: str) -> dict:
    """
    Verify Stripe webhook signature.
    Raises ValueError on invalid signature.
    """
    webhook_secret = get_stripe_secret('webhook_secret')
    try:
        event = stripe.Webhook.construct_event(
            raw_body, signature_header, webhook_secret
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        print(f"SECURITY: Invalid Stripe webhook signature: {e}")
        raise ValueError("Invalid webhook signature")
    except ValueError as e:
        print(f"SECURITY: Invalid Stripe webhook payload: {e}")
        raise
```

### Replay Protection

- Stripe includes a timestamp in the signature header
- `construct_event` rejects events older than `tolerance` (default: 300 seconds)
- Combined with idempotency check, replayed events are harmless

### Logging Rules

| Log | Level | What |
|-----|-------|------|
| Event received | INFO | Event type, event ID, company_id |
| Event processed | INFO | Event type, company_id, new status |
| Duplicate event | INFO | Event ID, "already processed" |
| Invalid signature | ERROR | "SECURITY: Invalid signature" (no payload details) |
| Unknown tenant | ERROR | "BILLING ERROR: No tenant for company_id" |
| Processing error | ERROR | Event type, company_id, error message |

**Never log:**
- Full Stripe event payload
- API keys or secrets
- Payment card details
- Customer email addresses in ERROR logs

### IAM Permissions (Least Privilege)

The Lambda execution role needs:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:Query"
  ],
  "Resource": "arn:aws:dynamodb:*:*:table/togs-and-dogs-prod-data",
  "Condition": {
    "ForAllValues:StringLike": {
      "dynamodb:LeadingKeys": ["TENANT#*", "BILLING#*"]
    }
  }
}
```

Plus Secrets Manager read:

```json
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:*:*:secret:togs-and-dogs/stripe/*"
}
```

---

## 9. Testing Strategy

### Unit Tests

| Test | Category | Expected |
|------|----------|----------|
| Valid signature → event parsed | Signature | ✅ Returns parsed event |
| Invalid signature → rejected | Signature | ❌ Raises ValueError |
| Missing signature header → rejected | Signature | ❌ Returns 400 |
| Expired timestamp → rejected | Signature | ❌ Raises ValueError |
| `checkout.session.completed` → tenant updated | State | ✅ Status = active, stripe fields set |
| `subscription.updated` (tier change) → tenant tier updated | State | ✅ Tier changed |
| `subscription.deleted` → status = canceled | State | ✅ Status = canceled |
| `invoice.payment_succeeded` → status = active | State | ✅ Status = active, period_end updated |
| `invoice.payment_failed` → status = past_due | State | ✅ Status = past_due |
| Duplicate event ID → skipped | Idempotency | ✅ Returns 200, no update |
| Unknown event type → 200 (ignored) | Routing | ✅ Returns 200, logged |
| Missing company_id in metadata → error logged | Resolution | ❌ Logged, 200 returned |
| Unknown company_id → error logged | Resolution | ❌ Logged, 200 returned |
| DynamoDB write failure → error recorded | Error | ❌ Logged, 500 returned (Stripe retries) |

### Integration Tests (Test Mode)

| Test | Method | Expected |
|------|--------|----------|
| Create test checkout session | Stripe test API | Session URL returned |
| Simulate webhook delivery | Stripe CLI (`stripe trigger`) | Handler processes event |
| End-to-end: checkout → webhook → tenant updated | Stripe test mode | Tenant status = active |
| End-to-end: payment failure → past_due | Stripe test clock | Tenant status = past_due |

### Test Tooling

- `stripe` Python SDK for test API calls
- `stripe listen --forward-to` (Stripe CLI) for local webhook testing
- `pytest` with mocked DynamoDB for unit tests
- Stripe test clocks for simulating subscription lifecycle

---

## 10. Price-to-Tier Resolution

### Mapping Strategy

```python
# Environment variable based mapping
PRICE_TO_TIER = {
    os.environ.get('STRIPE_PRICE_STARTER_MONTHLY'): 'starter',
    os.environ.get('STRIPE_PRICE_PROFESSIONAL_MONTHLY'): 'professional',
    os.environ.get('STRIPE_PRICE_PREMIUM_MONTHLY'): 'premium',
    # Future annual prices
    os.environ.get('STRIPE_PRICE_STARTER_ANNUAL'): 'starter',
    os.environ.get('STRIPE_PRICE_PROFESSIONAL_ANNUAL'): 'professional',
    os.environ.get('STRIPE_PRICE_PREMIUM_ANNUAL'): 'premium',
}

def price_id_to_tier(price_id: str) -> str:
    tier = PRICE_TO_TIER.get(price_id)
    if not tier:
        print(f"BILLING WARNING: Unknown price_id {price_id}, defaulting to starter")
        return 'starter'  # Fail safe — lowest tier
    return tier
```

### Tier-to-Limits Resolution

```python
TIER_LIMITS = {
    'starter': {
        'max_active_clients': 20,
        'max_staff': 1,
        'max_monthly_notifications': 100,
        'max_monthly_bookings': 50,
        'google_calendar_enabled': False,
        'export_enabled': False,
        'custom_branding_enabled': False,
        'video_evidence_enabled': False,
    },
    'professional': {
        'max_active_clients': 100,
        'max_staff': 5,
        'max_monthly_notifications': 500,
        'max_monthly_bookings': 250,
        'google_calendar_enabled': True,
        'export_enabled': True,
        'custom_branding_enabled': False,
        'video_evidence_enabled': False,
    },
    'premium': {
        'max_active_clients': 500,
        'max_staff': 15,
        'max_monthly_notifications': 2000,
        'max_monthly_bookings': 1000,
        'google_calendar_enabled': True,
        'export_enabled': True,
        'custom_branding_enabled': True,
        'video_evidence_enabled': True,
    },
    'enterprise': {
        'max_active_clients': 999999,
        'max_staff': 999999,
        'max_monthly_notifications': 999999,
        'max_monthly_bookings': 999999,
        'google_calendar_enabled': True,
        'export_enabled': True,
        'custom_branding_enabled': True,
        'video_evidence_enabled': True,
    },
}
```

---

## 11. Deployment Sequence (Revised)

| Release | Scope | Type |
|---------|-------|------|
| **12C** | Webhook + billing data model implementation plan (this document) | Planning |
| **12D** | Implement webhook handler + billing ledger + entitlement interface in code | Code (no live Stripe) |
| **12E** | AWS secrets setup + Terraform for API Gateway route + IAM | Infrastructure |
| **12F** | Matthew completes Stripe manual setup (products, prices, keys) | Manual |
| **12G** | Stripe test-mode end-to-end validation (webhook → tenant update) | Integration test |
| **12H** | Entitlement enforcement implementation (gate handlers) | Code |
| **12I** | Live mode cutover planning | Planning |
| **Future** | Live mode activation + Ryan linking | Production (requires approval) |

### Dependency Chain

```
12C (plan) → 12D (code) → 12E (infra) → 12F (Stripe setup) → 12G (test validation)
                                                                        ↓
                                                                  12H (enforcement)
                                                                        ↓
                                                                  12I (live cutover)
```

---

## 12. Data Retention Caution

### Repeat from 12B (Remains in Effect)

- Do NOT implement automatic deletion for unpaid/canceled tenants
- Use disabled → read-only → archived states only
- Require Terms of Service and Privacy Policy review before any deletion automation
- "90-day deletion" from 12A is a policy placeholder, not an implementation target
- Any deletion feature requires Matthew's explicit approval AND legal review

### Tenant State Machine (No Deletion)

```
active → past_due → canceled → archived
                                    ↑
                              (manual only, admin action)
```

---

## 13. Explicit Non-Goals (This Release)

| ❌ Item | Reason |
|---------|--------|
| Live Stripe mode | Test mode only through 12G |
| Real charges | No billing until live cutover |
| Second tenant creation | Single-tenant until billing validated |
| Billing UI / pricing page | Release 12H+ |
| Mobile in-app purchases | Web-first billing only |
| App Store submission changes | No billing UI in app |
| Automated tenant deletion | Requires legal/policy review |
| Entitlement enforcement in handlers | Release 12H |
| Annual pricing implementation | Deferred unless approved |

---

## 14. What This Document Does NOT Authorize

- ❌ Writing any code
- ❌ Creating Stripe account/products/prices
- ❌ Generating or storing API keys
- ❌ Creating webhook endpoints
- ❌ Modifying DynamoDB records
- ❌ Deploying to production
- ❌ Modifying Terraform/IAM/API Gateway
- ❌ Modifying Cognito/Postmark/Google Calendar
- ❌ Creating a second tenant
- ❌ Charging any business owner
- ❌ EAS/TestFlight/App Store changes

This is a planning and architecture document only. Implementation requires separate explicit approval (Release 12D).
