# Release 12A: Billing and Entitlement Architecture Plan

**Status:** Planning
**Priority:** High (must complete before second tenant onboarding)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Stripe Changes:** None
**Scope:** Define the billing model, entitlement enforcement, and Stripe integration architecture

---

## 1. Billing Model Overview

### Core Principle

**Business owners pay for platform access. The app download is free.**

| Actor | Pays? | Access Method |
|-------|-------|---------------|
| Business owner (tenant admin) | ✅ Yes — monthly/annual subscription | Web admin portal + mobile admin |
| Staff members | ❌ No — access granted by business owner | Mobile app (free download) |
| Clients (pet owners) | ❌ No — access granted by business owner | Mobile app (free download) + client portal |

### Revenue Model

- Subscription-based SaaS (recurring monthly or annual)
- Tenant admin purchases a plan → unlocks platform access for their business
- Staff and clients are covered by the business subscription
- No per-seat charges for staff or clients (included in tier limits)
- No in-app purchases or paid app downloads

### Why Backend Entitlement Over App Store Purchase Gating

1. Business owners are the paying customer, not individual staff/clients
2. App Store purchase model doesn't map to B2B SaaS subscriptions
3. Backend gating allows flexible plan changes without app updates
4. Avoids Apple's 30% commission on subscriptions managed through IAP
5. Web-first checkout keeps billing under our control
6. Standard SaaS pattern: free app → backend checks subscription status

---

## 2. Subscription Tiers

### Tier Definitions

| Tier | Monthly | Annual | Target Customer |
|------|---------|--------|-----------------|
| **Starter** | $29/mo | $290/yr | Solo operators, 1 staff, ≤20 active clients |
| **Professional** | $79/mo | $790/yr | Small teams, ≤5 staff, ≤100 active clients |
| **Premium** | $149/mo | $1,490/yr | Growing businesses, ≤15 staff, ≤500 active clients |
| **Enterprise** | Custom | Custom | Large operations, unlimited, dedicated support |

### Tier Capabilities

| Feature | Starter | Professional | Premium | Enterprise |
|---------|---------|--------------|---------|------------|
| Active clients | 20 | 100 | 500 | Unlimited |
| Staff accounts | 1 | 5 | 15 | Unlimited |
| Monthly notifications | 100 | 500 | 2,000 | Unlimited |
| Booking requests/month | 50 | 250 | 1,000 | Unlimited |
| Google Calendar sync | ❌ | ✅ | ✅ | ✅ |
| Export data | ❌ | ✅ | ✅ | ✅ |
| Custom branding | ❌ | ❌ | ✅ | ✅ |
| Video evidence storage | ❌ | ❌ | ✅ | ✅ |
| Multi-day bookings | ✅ | ✅ | ✅ | ✅ |
| Visit notes | ✅ | ✅ | ✅ | ✅ |
| Priority support | ❌ | ❌ | ✅ | ✅ |
| Dedicated account manager | ❌ | ❌ | ❌ | ✅ |
| API access | ❌ | ❌ | ❌ | ✅ |
| White-label option | ❌ | ❌ | ❌ | ✅ |

### Pricing Notes

- Annual pricing = ~2 months free (incentivizes commitment)
- All tiers include 14-day free trial
- Enterprise is quote-based / custom agreement
- Prices are initial targets — validate with market research before launch

---

## 3. Tenant Entitlement Data Model

### Proposed Fields on Tenant Metadata Record

```json
{
  "PK": "TENANT#tog_and_dogs",
  "SK": "METADATA",
  "company_id": "tog_and_dogs",
  "display_name": "Togs & Dogs",
  "owner_email": "mattnicomn10@gmail.com",
  "owner_cognito_sub": "b4a89428-9071-7063-dcad-983d4305dd8c",

  "subscription_tier": "professional",
  "subscription_status": "active",
  "trial_ends_at": null,
  "current_period_start": "2025-06-01T00:00:00Z",
  "current_period_end": "2025-07-01T00:00:00Z",

  "billing_provider": "stripe",
  "stripe_customer_id": "cus_XXXXXXXXXXXXXX",
  "stripe_subscription_id": "sub_XXXXXXXXXXXXXX",
  "stripe_price_id": "price_XXXXXXXXXXXXXX",
  "billing_interval": "monthly",

  "limits": {
    "max_active_clients": 100,
    "max_staff": 5,
    "max_monthly_notifications": 500,
    "max_monthly_bookings": 250,
    "google_calendar_enabled": true,
    "export_enabled": true,
    "custom_branding_enabled": false,
    "video_evidence_enabled": false
  },

  "feature_flags": {
    "multi_day_bookings": true,
    "visit_notes": true,
    "staff_assignment": true,
    "client_cancellation": true
  },

  "billing_contact_email": "mattnicomn10@gmail.com",
  "tax_id": null,
  "currency": "USD",

  "created_at": "2025-05-06T17:49:19Z",
  "updated_at": "2025-06-14T00:00:00Z",
  "created_by": "b4a89428-9071-7063-dcad-983d4305dd8c"
}
```

### Billing Event Ledger

Separate DynamoDB records to track billing lifecycle events:

```
PK: BILLING#tog_and_dogs
SK: EVENT#2025-06-14T00:00:00Z#invoice.paid

{
  "event_type": "invoice.paid",
  "stripe_event_id": "evt_XXXXXXXXXXXXXX",
  "amount": 7900,
  "currency": "usd",
  "period_start": "2025-06-01T00:00:00Z",
  "period_end": "2025-07-01T00:00:00Z",
  "processed_at": "2025-06-14T00:00:00Z"
}
```

### Entitlement Derived Status

The system derives access from `subscription_status`:

| Status | Access | Behavior |
|--------|--------|----------|
| `active` | ✅ Full access | Normal operation |
| `trialing` | ✅ Full access | Trial period, no charge yet |
| `past_due` | ⚠️ Degraded | Grace period (7 days), read-only after |
| `canceled` | ❌ Denied | Redirect to resubscribe page |
| `paused` | ❌ Denied | Redirect to resume page |
| `disabled` | ❌ Denied | Admin manually disabled (break-glass) |

---

## 4. Entitlement Enforcement Points

### Where to Check Entitlement

| Enforcement Point | Check Type | Behavior on Failure |
|-------------------|-----------|---------------------|
| Login / session bootstrap | Status check | Block login, show "subscription inactive" |
| Admin dashboard load | Status + tier | Show upgrade prompt if limits exceeded |
| Staff mobile login | Status check | Block login, show "business subscription inactive" |
| Client portal login | Status check | Block login, show "service unavailable" |
| Booking creation | Status + limit | Reject if monthly booking limit reached |
| Notification send | Status + limit | Skip send if monthly notification limit reached |
| Staff account creation | Tier limit | Reject if max_staff exceeded |
| Client registration | Tier limit | Reject if max_active_clients exceeded |
| Export data | Feature flag | Return 403 if export_enabled = false |
| Google Calendar sync | Feature flag | Skip sync if google_calendar_enabled = false |
| Video evidence upload | Feature flag | Return 403 if video_evidence_enabled = false |
| Custom branding | Feature flag | Ignore branding config if custom_branding_enabled = false |

### Enforcement Architecture

```
Request → API Gateway → Lambda Handler
                          ↓
                   get_current_company_id(event)
                          ↓
                   get_tenant_entitlement(company_id)  ← NEW
                          ↓
                   check_entitlement(entitlement, action)  ← NEW
                          ↓
                   [proceed or return 403/402]
```

### Caching Strategy

- Cache tenant entitlement in-memory for Lambda execution duration (reuse across warm invocations)
- TTL: 5 minutes (balance between freshness and DynamoDB reads)
- Force-refresh on subscription webhook events
- Fallback: if cache miss and DynamoDB read fails, deny access (fail closed)

---

## 5. Stripe Integration Architecture

### Architecture Overview

```
Business Owner (Web)
       ↓
   Stripe Checkout (hosted)
       ↓
   Stripe creates subscription
       ↓
   Webhook → API Gateway → Lambda (webhook handler)
       ↓
   Update TENANT#{company_id} / METADATA
       ↓
   Write BILLING#{company_id} / EVENT#{timestamp}#{type}
```

### Stripe Resources Mapping

| Stripe Concept | Our Concept | Notes |
|----------------|-------------|-------|
| Customer | Tenant admin (business owner) | 1:1 with tenant |
| Product | "Togs & Dogs Platform" | Single product |
| Price | Tier + interval | e.g., Professional Monthly = $79/mo |
| Subscription | Tenant subscription | 1:1 with tenant |
| Invoice | Monthly/annual charge | Auto-generated by Stripe |
| Checkout Session | Signup/upgrade flow | Hosted by Stripe |
| Customer Portal | Self-service billing management | Hosted by Stripe |
| Webhook | Event notifications | Drives our status updates |

### Stripe Products and Prices

```
Product: "Togs & Dogs Platform"
  ├── Price: Starter Monthly     ($29/mo)
  ├── Price: Starter Annual      ($290/yr)
  ├── Price: Professional Monthly ($79/mo)
  ├── Price: Professional Annual  ($790/yr)
  ├── Price: Premium Monthly     ($149/mo)
  ├── Price: Premium Annual      ($1,490/yr)
  └── Enterprise: Custom (manual setup)
```

### Critical Webhooks to Handle

| Webhook Event | Action |
|---------------|--------|
| `checkout.session.completed` | Link Stripe customer to tenant, set status = active |
| `invoice.paid` | Confirm active, update current_period_end |
| `invoice.payment_failed` | Set status = past_due, notify admin |
| `customer.subscription.updated` | Update tier, interval, period dates |
| `customer.subscription.deleted` | Set status = canceled |
| `customer.subscription.paused` | Set status = paused |
| `customer.subscription.resumed` | Set status = active |
| `customer.subscription.trial_will_end` | Notify admin (3 days before trial end) |

### Webhook Security

- Verify Stripe signature on every webhook (`stripe-signature` header)
- Use webhook signing secret from environment variable
- Reject requests without valid signature
- Idempotency: store `stripe_event_id` in ledger, skip duplicates
- Replay safety: process events in order by timestamp, ignore stale events

### Test Mode First

- All initial development uses Stripe test mode
- Test API keys in Lambda environment variables
- Test webhook endpoint separate from production
- Switch to live mode only after full validation with Matthew's approval

---

## 6. Checkout and Customer Portal Flow

### New Tenant Signup

```
1. Business owner visits pricing page (web)
2. Selects tier → redirected to Stripe Checkout
3. Stripe collects payment → creates subscription
4. Webhook fires → our Lambda:
   a. Creates TENANT#{new_company_id} / METADATA record
   b. Sets subscription_tier, subscription_status = active
   c. Links stripe_customer_id, stripe_subscription_id
   d. Creates Cognito user with custom:company_id = new_company_id
   e. Sends welcome email via Postmark
5. Business owner redirected to admin dashboard
```

### Existing Tenant Upgrade/Downgrade

```
1. Admin clicks "Manage Subscription" → Stripe Customer Portal
2. Owner changes plan in Stripe-hosted UI
3. Webhook fires (customer.subscription.updated)
4. Lambda updates tenant metadata: tier, limits, feature_flags
5. Changes take effect immediately (next entitlement check)
```

### Cancellation

```
1. Admin clicks "Cancel" in Stripe Customer Portal
2. Stripe sets subscription to cancel at period end
3. Webhook fires (customer.subscription.deleted) at period end
4. Lambda sets subscription_status = canceled
5. Next login → blocked with "subscription inactive" message
6. Data retained for 90 days (re-subscribe to restore)
```

---

## 7. App Store / Mobile Payment Considerations

### Research Task (Before Implementation)

Before implementing any billing, verify the following against current Apple App Store Review Guidelines:

1. **Reader app exemption:** Does our model qualify? Business owner pays via web, staff/clients access via free app.
2. **IAP requirement:** Are we required to offer IAP for the subscription if it's initiated from within the app?
3. **External link entitlement:** Can we link to our web checkout from within the app?
4. **Multiplatform service exemption:** Does our web-first billing qualify under the "multiplatform services" rule?
5. **Business/Enterprise exception:** Are B2B SaaS apps exempt from IAP requirements?

### Current Recommendation

- **Do NOT implement paid app download.** The app is free.
- **Do NOT implement in-app purchase for subscriptions.** Business owners subscribe via web.
- **DO use backend entitlement gating.** The app checks tenant status server-side.
- **DO keep the app functional without payment UI.** Staff/clients never see billing.
- This model aligns with how other B2B SaaS apps (Slack, Salesforce, HubSpot) handle mobile access.

### Risk Mitigation

- If Apple rejects during App Store review, we can add an informational message directing to web
- The "reader app" or "multiplatform service" classification likely applies
- Enterprise distribution (if needed) avoids App Store rules entirely
- Monitor Apple policy changes quarterly

---

## 8. Failure Modes and Recovery

### Payment Failure (invoice.payment_failed)

```
Day 0: Payment fails → status = past_due → notify admin via email
Day 1-7: Grace period — full access continues, daily reminder emails
Day 7: Access degraded — read-only mode (can view but not create)
Day 14: Access denied — login blocked, "update payment" redirect
Day 90: Data eligible for deletion (with 30-day warning email)
```

### Subscription Canceled

```
Immediate: subscription_status = canceled
Effect: login blocked for all tenant users (admin, staff, clients)
Data: retained 90 days
Recovery: re-subscribe via web → access restored immediately
```

### Trial Expired (No Payment Method)

```
Day -3: Email warning "trial ending soon"
Day 0: trial_ends_at passed → status = canceled (if no payment method)
Effect: login blocked, "subscribe to continue" page shown
```

### Webhook Missed/Delayed

- Stripe retries webhooks for up to 3 days
- Our handler is idempotent (checks `stripe_event_id` before processing)
- If webhook never arrives: manual reconciliation via Stripe dashboard
- Admin override available: manually set `subscription_status` in DynamoDB (break-glass)

### Stripe Outage

- Checkout unavailable → new signups blocked temporarily
- Existing subscriptions unaffected (we cache entitlement status)
- Webhook backlog processes when Stripe recovers
- No action needed unless outage exceeds entitlement cache TTL (5 min)

### Manual Admin Override (Break-Glass)

For exceptional cases (refund disputes, courtesy extensions, etc.):
- Matthew can manually update `subscription_status` on TENANT record
- Override field: `admin_override_until` (ISO timestamp)
- While override active, entitlement check returns `active` regardless of Stripe status
- Audit: all manual overrides logged in billing event ledger

---

## 9. Initial Rollout Plan

### Current State (tog_and_dogs)

| Field | Current Value | Notes |
|-------|---------------|-------|
| subscription_tier | professional | Already set in 11C metadata record |
| subscription_status | active | Already set |
| stripe_customer_id | null | Not yet connected to Stripe |
| billing_provider | null | Not yet configured |

### Rollout Sequence

1. **Phase 1 (12B-12E):** Build billing infrastructure in test mode
2. **Phase 2:** Connect Ryan's existing tenant to Stripe (test mode) — verify webhooks
3. **Phase 3:** Switch to Stripe live mode — Ryan's tenant gets real subscription
4. **Phase 4:** Open second-tenant onboarding (new businesses can sign up)

### Ryan's Billing Transition

- **Do NOT charge Ryan** during development/testing phases unless Matthew explicitly approves
- Ryan's tenant remains `subscription_status = active` throughout
- When ready to go live: Matthew decides whether Ryan gets grandfathered pricing, a courtesy period, or standard pricing
- The system must support manual `admin_override_until` for courtesy extensions

---

## 10. Implementation Sequence

| Release | Scope | Dependencies |
|---------|-------|--------------|
| **12A** | Billing and entitlement architecture plan (this document) | 11G complete |
| **12B** | Stripe test-mode setup plan | 12A approved |
| **12C** | Billing data model and webhook implementation plan | 12B complete |
| **12D** | Entitlement enforcement implementation plan | 12C complete |
| **12E** | Billing UI / owner portal plan | 12D complete |
| **12F** | End-to-end billing integration test plan | 12E complete |
| **12G** | Live mode cutover plan | 12F validated |
| **Future** | Second-tenant onboarding | 12G complete + Matthew approval |

### What Each Release Covers

- **12B:** Create Stripe account (test mode), configure products/prices, set up webhook endpoint, store test API keys
- **12C:** Add billing fields to tenant metadata, create webhook handler Lambda, implement event ledger, handle all critical webhook events
- **12D:** Add `get_tenant_entitlement()` function, add `check_entitlement()` checks at enforcement points, implement grace periods, implement limit checks
- **12E:** Build pricing page, integrate Stripe Checkout, add "Manage Subscription" link to admin portal, show current plan/usage
- **12F:** Full end-to-end test: signup → checkout → webhook → entitlement active → upgrade → downgrade → cancel → resubscribe
- **12G:** Switch from test keys to live keys, verify webhook endpoint, confirm Ryan's tenant linked

---

## 11. Risks and Open Questions

| Risk / Question | Impact | Recommended Resolution |
|-----------------|--------|------------------------|
| Pricing not validated with market | Medium | Research competitors before public launch |
| Apple App Store IAP policy | Medium | Research current guidelines before app update |
| Tax/accounting handling | Medium | Use Stripe Tax or defer to accountant |
| Refund policy | Low | Define before public launch |
| Stripe vs alternative processor | Low | Stripe recommended (best developer experience, webhook support) |
| Currency support (USD only vs multi) | Low | Start USD only, add multi-currency later |
| Annual billing proration on tier change | Low | Use Stripe's built-in proration |
| Admin override abuse | Low | Audit log + time-limited overrides |
| Webhook endpoint security | High | Stripe signature verification mandatory |
| Grace period duration | Medium | 7 days recommended, configurable per tenant |
| Data retention after cancellation | Medium | 90 days, then notify + delete |
| Grandfather pricing for Ryan | Low | Matthew decides at go-live time |

---

## 12. What This Document Does NOT Authorize

- ❌ Creating a Stripe account
- ❌ Configuring Stripe products/prices
- ❌ Writing webhook handlers
- ❌ Modifying DynamoDB records
- ❌ Adding entitlement checks to handlers
- ❌ Building pricing pages or billing UI
- ❌ Deploying any code
- ❌ Creating a second tenant
- ❌ Charging Ryan or any business owner
- ❌ Modifying Cognito/Postmark/Google Calendar
- ❌ EAS/TestFlight/App Store changes
- ❌ Terraform/AWS infrastructure changes

This is a planning and architecture document only. Implementation requires separate explicit approval per release (12B onward).
