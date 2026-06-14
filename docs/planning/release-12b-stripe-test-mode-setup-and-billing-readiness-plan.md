# Release 12B: Stripe Test-Mode Setup and Billing Readiness Plan

**Status:** Planning
**Priority:** High (must complete before billing implementation)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Stripe Changes:** None (manual setup checklist only)
**Scope:** Define Stripe account setup, test-mode product/price design, webhook architecture, and billing data model

---

## 1. Stripe Account Prerequisites

### Account Ownership

| Question | Recommendation |
|----------|---------------|
| Who owns the Stripe account? | Matthew (mattnicomn10@gmail.com) — business owner |
| Who has admin access? | Matthew only (initially) |
| Business name on Stripe | Togs & Dogs (or parent company name if different) |
| Country | United States |
| Currency | USD |
| Business type | Software / SaaS |

### Account Security

- Enable 2FA on the Stripe account
- Do not share login credentials
- Use restricted API keys for production (limit permissions per endpoint)
- Store all keys in AWS Secrets Manager or SSM Parameter Store — never in code

### Test Mode vs Live Mode

| Mode | Purpose | When |
|------|---------|------|
| Test mode | Development, integration testing, webhook validation | 12B–12F |
| Live mode | Real charges, real customers | 12G (cutover) — requires Matthew's explicit approval |

**Rule:** All development through Release 12F uses test mode only. Live mode activation is a separate gated release (12G).

---

## 2. Test-Mode Product and Price Design

### Product

| Field | Value |
|-------|-------|
| Product name | Togs & Dogs Platform |
| Product description | Pet care business management platform |
| Product type | Service |
| Billing scheme | Per-unit (1 subscription per tenant) |

### Prices (Monthly — Initial)

| Tier | Price ID Name | Amount | Interval | Currency |
|------|---------------|--------|----------|----------|
| Starter | starter_monthly | $29.00 | monthly | USD |
| Professional | professional_monthly | $79.00 | monthly | USD |
| Premium | premium_monthly | $149.00 | monthly | USD |

### Prices (Annual — Deferred)

Annual pricing will be added in a future release unless Matthew explicitly approves earlier. When added:

| Tier | Price ID Name | Amount | Interval | Currency |
|------|---------------|--------|----------|----------|
| Starter | starter_annual | $290.00 | yearly | USD |
| Professional | professional_annual | $790.00 | yearly | USD |
| Premium | premium_annual | $1,490.00 | yearly | USD |

### Enterprise

- No Stripe product/price created for Enterprise
- Enterprise is handled manually (custom quotes, invoices)
- May use Stripe Invoicing later for Enterprise customers

### Trial Configuration

| Setting | Value |
|---------|-------|
| Trial period | 14 days |
| Trial requires payment method | Yes (reduces friction at conversion) |
| Trial available on | All tiers |

---

## 3. Stripe Metadata Strategy

Every Stripe Customer and Subscription should carry metadata linking back to our system:

### Customer Metadata

```json
{
  "company_id": "tog_and_dogs",
  "tenant_pk": "TENANT#tog_and_dogs",
  "environment": "test",
  "owner_email": "mattnicomn10@gmail.com",
  "owner_cognito_sub": "b4a89428-9071-7063-dcad-983d4305dd8c"
}
```

### Subscription Metadata

```json
{
  "company_id": "tog_and_dogs",
  "subscription_tier": "professional",
  "environment": "test"
}
```

### Why Metadata Matters

- Enables webhook handler to identify which tenant a Stripe event belongs to
- Allows Stripe dashboard searches by company_id
- Enables reconciliation between our DynamoDB records and Stripe records
- `environment` field prevents test events from accidentally updating production data

---

## 4. API Key and Secret Handling

### Key Types Needed

| Key | Purpose | Storage Location |
|-----|---------|------------------|
| `STRIPE_SECRET_KEY` | Server-side API calls (create checkout, read subscriptions) | AWS Secrets Manager |
| `STRIPE_PUBLISHABLE_KEY` | Client-side Stripe.js (if needed for embedded checkout) | SSM Parameter Store (not secret) |
| `STRIPE_WEBHOOK_SECRET` | Verify webhook signatures | AWS Secrets Manager |

### Storage Recommendations

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| AWS Secrets Manager | Rotation support, audit trail, fine-grained IAM | $0.40/secret/month | ✅ Recommended for secret keys |
| SSM Parameter Store (SecureString) | Free, integrated with Lambda | No auto-rotation | ✅ Acceptable alternative |
| Environment variables (Lambda) | Simple, fast access | Visible in console, no rotation | ⚠️ Acceptable for non-secret config |
| `.env` file / code | None | ❌ Never — secrets in code | ❌ Forbidden |

### Proposed Environment Variable Names

```
# Stripe API
STRIPE_SECRET_KEY=sk_test_XXXXXX          # Secrets Manager
STRIPE_PUBLISHABLE_KEY=pk_test_XXXXXX     # SSM or Lambda env var
STRIPE_WEBHOOK_SECRET=whsec_XXXXXX        # Secrets Manager

# Stripe Price IDs (safe to store as env vars — not secrets)
STRIPE_PRICE_STARTER_MONTHLY=price_XXXXXX
STRIPE_PRICE_PROFESSIONAL_MONTHLY=price_XXXXXX
STRIPE_PRICE_PREMIUM_MONTHLY=price_XXXXXX

# Future (annual)
STRIPE_PRICE_STARTER_ANNUAL=price_XXXXXX
STRIPE_PRICE_PROFESSIONAL_ANNUAL=price_XXXXXX
STRIPE_PRICE_PREMIUM_ANNUAL=price_XXXXXX
```

### Key Rotation Plan

- Rotate test keys whenever a team member leaves or access is revoked
- Rotate live keys on a quarterly schedule once in production
- Use Secrets Manager's built-in rotation for automated key rotation (future)

---

## 5. Webhook Architecture Plan

### Endpoint Design

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Endpoint path | `POST /webhooks/stripe` | Clear, standard, separate from business API |
| Handler | New Lambda function or route in existing backend | TBD in 12C |
| Authentication | Stripe signature verification only (no Cognito) | Webhooks are server-to-server |
| Response | 200 on success, 400 on invalid signature | Stripe retries on non-2xx |

### Events to Handle

| Event | Priority | Action |
|-------|----------|--------|
| `checkout.session.completed` | Critical | Create/link tenant billing, set status = active |
| `customer.subscription.created` | Critical | Confirm subscription, update tenant metadata |
| `customer.subscription.updated` | Critical | Update tier, period dates, status |
| `customer.subscription.deleted` | Critical | Set status = canceled |
| `invoice.payment_succeeded` | High | Confirm payment, update current_period_end |
| `invoice.payment_failed` | High | Set status = past_due, trigger admin notification |
| `customer.subscription.paused` | Medium | Set status = paused |
| `customer.subscription.resumed` | Medium | Set status = active |
| `customer.subscription.trial_will_end` | Medium | Send trial-ending notification (3 days before) |

### Events to Ignore (Initially)

| Event | Reason |
|-------|--------|
| `charge.*` | Invoice events are sufficient |
| `payment_intent.*` | Handled via invoice lifecycle |
| `customer.created` | We create customers ourselves during checkout |
| `invoice.created` | Only care about payment outcome |
| `invoice.finalized` | Only care about payment outcome |

### Idempotency Strategy

```python
def handle_stripe_webhook(event_body, stripe_signature):
    # 1. Verify signature
    stripe_event = stripe.Webhook.construct_event(
        event_body, stripe_signature, STRIPE_WEBHOOK_SECRET
    )

    # 2. Check idempotency — skip if already processed
    event_id = stripe_event['id']
    existing = get_item(f"BILLING#{company_id}", f"EVENT#{event_id}")
    if existing:
        return {"statusCode": 200, "body": "Already processed"}

    # 3. Process event
    process_billing_event(stripe_event)

    # 4. Record in ledger (with event_id as dedup key)
    write_billing_event(company_id, stripe_event)

    return {"statusCode": 200, "body": "OK"}
```

### Replay Handling

- Stripe retries failed webhooks for up to 3 days
- Our handler is idempotent (checks event_id before processing)
- Out-of-order events handled by comparing timestamps
- Manual replay available via Stripe dashboard if needed

### Signature Verification

```python
import stripe

def verify_webhook(payload, sig_header, webhook_secret):
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")
```

---

## 6. DynamoDB Billing Data Model

### Tenant Metadata Updates (Existing Record)

New fields to add to `TENANT#{company_id} / METADATA`:

```json
{
  "billing_provider": "stripe",
  "stripe_customer_id": "cus_XXXXXXXXXXXXXX",
  "stripe_subscription_id": "sub_XXXXXXXXXXXXXX",
  "stripe_price_id": "price_XXXXXXXXXXXXXX",
  "billing_interval": "monthly",
  "current_period_start": "2025-07-01T00:00:00Z",
  "current_period_end": "2025-08-01T00:00:00Z",
  "trial_ends_at": null,
  "billing_contact_email": "mattnicomn10@gmail.com",
  "currency": "USD",
  "admin_override_until": null,
  "limits": {
    "max_active_clients": 100,
    "max_staff": 5,
    "max_monthly_notifications": 500,
    "max_monthly_bookings": 250,
    "google_calendar_enabled": true,
    "export_enabled": true,
    "custom_branding_enabled": false,
    "video_evidence_enabled": false
  }
}
```

### Billing Event Ledger (New Records)

```
PK: BILLING#{company_id}
SK: EVENT#{iso_timestamp}#{event_type}

{
  "stripe_event_id": "evt_XXXXXXXXXXXXXX",
  "event_type": "invoice.payment_succeeded",
  "amount": 7900,
  "currency": "usd",
  "period_start": "2025-07-01T00:00:00Z",
  "period_end": "2025-08-01T00:00:00Z",
  "stripe_invoice_id": "in_XXXXXXXXXXXXXX",
  "processed_at": "2025-07-01T00:05:00Z",
  "idempotency_key": "evt_XXXXXXXXXXXXXX"
}
```

### Entitlement Cache (Derived, In-Memory)

Not stored in DynamoDB — derived at runtime from tenant metadata:

```python
class TenantEntitlement:
    company_id: str
    subscription_tier: str        # starter | professional | premium | enterprise
    subscription_status: str      # active | trialing | past_due | canceled | paused | disabled
    limits: dict                  # max_clients, max_staff, etc.
    feature_flags: dict           # google_calendar, export, branding, video
    admin_override_until: str     # ISO timestamp or None
    cached_at: str                # when this was loaded
    ttl_seconds: int = 300        # 5 minutes
```

### Audit Fields

All billing-related writes include:

```json
{
  "updated_at": "ISO timestamp",
  "updated_by": "system:stripe_webhook | admin:sub_id",
  "update_source": "stripe_event_id or manual"
}
```

---

## 7. Manual Setup Checklist

This checklist is for Matthew to complete manually when ready to proceed with 12C implementation:

### Step 1: Stripe Account

- [ ] Create Stripe account at https://dashboard.stripe.com/register (or confirm existing account)
- [ ] Business name: Togs & Dogs (or parent entity)
- [ ] Country: United States
- [ ] Enable 2FA on account
- [ ] Confirm test mode is active (toggle in dashboard header)

### Step 2: Create Test Products

- [ ] Navigate to Products → Add product
- [ ] Product name: "Togs & Dogs Platform"
- [ ] Product description: "Pet care business management platform"

### Step 3: Create Test Prices

- [ ] Add price: Starter Monthly — $29.00/month, recurring
- [ ] Add price: Professional Monthly — $79.00/month, recurring
- [ ] Add price: Premium Monthly — $149.00/month, recurring
- [ ] Record price IDs (format: `price_XXXXXX`) in a secure local note

### Step 4: Record Test API Keys

- [ ] Navigate to Developers → API keys
- [ ] Copy test secret key (`sk_test_XXXXXX`) — store securely, do NOT commit
- [ ] Copy test publishable key (`pk_test_XXXXXX`) — safe to reference in docs
- [ ] Store both in a secure local note for later AWS Secrets Manager setup

### Step 5: Webhook Endpoint (Deferred)

- [ ] Do NOT create webhook endpoint yet (no endpoint exists to receive events)
- [ ] Will be configured in Release 12C after webhook handler is deployed
- [ ] When ready: Developers → Webhooks → Add endpoint
- [ ] Record webhook signing secret (`whsec_XXXXXX`) at that time

### Step 6: Verify Setup

- [ ] Dashboard shows test mode active
- [ ] Product "Togs & Dogs Platform" exists with 3 monthly prices
- [ ] No live mode activity
- [ ] No real customers or charges

---

## 8. App Store / Mobile Payment Policy Research Task

### Future Task (Before Any App Update That Mentions Billing)

Before submitting an app update that references subscription/billing:

1. Review current Apple App Store Review Guidelines (Section 3.1 — Payments)
2. Confirm whether "reader app" or "multiplatform service" exemption applies
3. Verify if external link entitlement is available for our app category
4. Check if B2B SaaS apps with web-only billing require any IAP disclosure
5. Document findings in a separate planning note

### Current Position

- App download is free → no IAP required for download
- Billing is web-only (business owner subscribes via web checkout)
- Staff/clients never see billing UI in the app
- This model aligns with Slack, Salesforce, HubSpot mobile apps
- No mobile billing UI planned unless Apple policy requires disclosure

### Risk

- If Apple requires a disclosure or link during app review, add an informational page
- Do NOT implement IAP unless explicitly required and approved by Matthew
- Monitor Apple Developer News for policy changes quarterly

---

## 9. Data Retention Caution

### Important Policy Note

The "90-day data deletion after cancellation" mentioned in 12A is a **policy placeholder only**.

**Before any automated deletion is implemented:**

1. Review and update Terms of Service to include data retention language
2. Review and update Privacy Policy to include data deletion timeline
3. Implement `disabled` / `archived` states before any `deleted` state
4. Require explicit admin action (not automated timer) for permanent deletion
5. Provide data export option before deletion
6. Send 30-day warning email before any scheduled deletion
7. Matthew must explicitly approve the deletion policy and timeline

**Recommended state progression:**

```
active → past_due → canceled → archived (90 days) → deletion_pending (30-day notice) → deleted
```

**Do NOT implement automated deletion in 12C-12E.** Only implement disabled/archived states initially.

---

## 10. Rollout Strategy

### Current State (No Changes)

| Item | Status |
|------|--------|
| tog_and_dogs tenant | active / professional |
| Stripe connected | ❌ Not yet |
| Ryan charged | ❌ Not during test mode |
| Second tenant | ❌ Not created |

### Planned Progression

| Phase | Releases | What Happens |
|-------|----------|--------------|
| Test setup | 12B (this) | Manual Stripe account + test products |
| Implementation | 12C–12E | Webhook handler, entitlement checks, billing UI |
| Integration test | 12F | End-to-end test with Stripe test mode |
| Live cutover | 12G | Switch to live keys, link Ryan's tenant |
| Second tenant | Future | New business signs up via web checkout |

### Ryan's Billing Transition

- Ryan is NOT charged during 12B–12F (test mode only)
- At 12G (live cutover), Matthew decides:
  - Grandfather pricing? (e.g., free or discounted permanently)
  - Courtesy period? (e.g., 6 months free, then standard pricing)
  - Standard pricing? (Professional at $79/mo)
- This decision is deferred — no action needed now

---

## 11. Recommended Next Release

**12C — Stripe Webhook and Billing Data Model Implementation Plan**

Scope:
- Design the webhook handler Lambda (or route)
- Define exact DynamoDB update logic for each webhook event
- Define the `get_tenant_entitlement()` function interface
- Define error handling and retry logic
- Still planning unless Matthew explicitly approves implementation

Prerequisites:
- Matthew completes manual Stripe setup checklist (Section 7)
- Test product/price IDs are recorded
- Test API keys are stored securely

---

## 12. What This Document Does NOT Authorize

- ❌ Creating a Stripe account (manual checklist provided, not executed)
- ❌ Creating Stripe products or prices
- ❌ Generating or storing API keys
- ❌ Creating webhook endpoints
- ❌ Writing any code
- ❌ Modifying DynamoDB records
- ❌ Deploying to production
- ❌ Modifying Cognito/Postmark/Google Calendar
- ❌ Running Terraform
- ❌ Creating a second tenant
- ❌ Charging any business owner
- ❌ EAS/TestFlight/App Store changes
- ❌ Implementing entitlement checks

This is a planning and readiness document only. Manual Stripe setup and implementation require separate explicit approval.
