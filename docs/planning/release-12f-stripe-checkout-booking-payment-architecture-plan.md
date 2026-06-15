# Release 12F: Stripe Checkout Booking Payment Architecture Plan

**Status:** Planning
**Priority:** High (first integrated payment workflow)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Stripe Changes:** None
**Scope:** Define the architecture for approved booking payment via Stripe Checkout

---

## 1. Payment Model Overview

### Combined Payment Strategy

| Payment Type | Method | Timeline |
|--------------|--------|----------|
| One-time booking payment | Stripe Checkout (session-based) | This release series (12F–12I) |
| Recurring SaaS subscription | Stripe Billing | Future (separate release track) |
| Manual/emergency fallback | Stripe Payment Links (manual) | Available anytime as MVP tool |

### Legal and Financial Structure

| Field | Value |
|-------|-------|
| Legal entity | usmissionhero LLC |
| Stripe account email | mbn@usmissionhero.com |
| Product/service | Togs & Dogs (operated by usmissionhero LLC) |
| Payment recipient | usmissionhero LLC (direct) |
| Payment model | Direct charges (not Stripe Connect / marketplace) |
| Currency | USD |

### Why Stripe Checkout (Not Payment Links as Primary)

- Checkout Sessions are API-driven → fully integrated with our backend
- Metadata ties payments to specific requests/tenants automatically
- Webhook events confirm payment without polling
- Supports success/cancel redirect URLs for client UX
- Payment Links are manual (admin copies link) → acceptable as fallback only

---

## 2. Booking Payment Flow

### Happy Path

```
1. Client submits booking request → status: PENDING
2. Admin reviews and approves → status: APPROVED
3. Admin clicks "Send Payment Request" on approved booking
4. Backend creates Stripe Checkout Session with:
   - amount from booking/service pricing
   - metadata: company_id, request_id, client_id, payment_type
   - success_url, cancel_url
5. Backend stores checkout_session_id on the request record
6. Backend updates request: payment_status = PAYMENT_LINK_SENT
7. System emails payment link to client (via Postmark)
8. Client clicks link → Stripe Checkout hosted page
9. Client pays
10. Stripe fires webhook: checkout.session.completed
11. Backend verifies metadata, updates request: payment_status = PAID
12. Admin sees "Paid" badge on request
13. Normal scheduling/assignment flow continues
```

### Failure Path

```
Client abandons checkout → no webhook fires
  → payment_status remains PAYMENT_LINK_SENT
  → Admin can resend or follow up

Payment method fails → Stripe handles retry on hosted page
  → If ultimately fails: checkout.session.expired webhook (30 min)
  → payment_status remains PAYMENT_LINK_SENT (admin can resend)
```

### Manual Fallback (Payment Links)

If the integrated flow is unavailable:
1. Admin creates a Payment Link in Stripe Dashboard manually
2. Admin copies link and emails/texts to client
3. Admin manually updates payment status after confirming in Stripe Dashboard
4. No webhook automation — fully manual

---

## 3. Booking Payment Status Model

### New Field: `payment_status`

Added to the existing request record (does NOT replace the booking `status` field):

| payment_status | Meaning | Trigger |
|----------------|---------|---------|
| `null` / not set | No payment required or not yet initiated | Default |
| `pending` | Payment expected but not yet requested | Admin approves booking |
| `payment_link_sent` | Checkout session created, link sent to client | POST /admin/requests/{id}/payment-session |
| `paid` | Payment confirmed by Stripe | checkout.session.completed webhook |
| `payment_failed` | Payment attempt failed (session expired) | checkout.session.expired webhook |
| `refunded` | Payment was refunded | Future: refund webhook |
| `waived` | Admin waived payment for this booking | Admin manual action |

### Relationship to Existing `status` Field

The booking `status` field (PENDING, APPROVED, ASSIGNED, COMPLETED, CANCELLED, etc.) remains unchanged. `payment_status` is an independent field that tracks financial state:

```
status: APPROVED + payment_status: null         → approved, no payment needed
status: APPROVED + payment_status: pending      → approved, awaiting payment request
status: APPROVED + payment_status: payment_link_sent → link sent, waiting for client
status: APPROVED + payment_status: paid         → paid, ready for scheduling
status: ASSIGNED + payment_status: paid         → staff assigned, paid
status: COMPLETED + payment_status: paid        → done and paid
status: CANCELLED + payment_status: refunded    → cancelled and refunded
```

### Decision: Do NOT Block Scheduling on Payment

For the initial release, payment and scheduling are independent. Admin can assign/schedule before payment is received (Ryan's current workflow doesn't gate on payment). Future release can add a "require payment before assignment" toggle per tenant.

---

## 4. Stripe Checkout Session Creation

### Proposed Endpoint

```
POST /admin/requests/{request_id}/payment-session
```

### Authorization

- Owner or Admin role only
- Tenant ownership validated (request must belong to caller's company)

### Request Body

```json
{
  "amount_cents": 7500,
  "description": "Dog walking - 5 visits (Nov 1-5)"
}
```

- `amount_cents`: payment amount in cents (e.g., 7500 = $75.00)
- `description`: optional line item description for the checkout page

If `amount_cents` is omitted, derive from the request's pricing fields (if available).

### Backend Logic

```python
def create_payment_session(request_id, amount_cents, description, event):
    # 1. Load request record
    request = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not request:
        return not_found(...)

    # 2. Validate tenant ownership
    validate_tenant_ownership(request, event)

    # 3. Check request is in valid state for payment
    if request.get('payment_status') == 'paid':
        return error(409, "Payment already received for this request")

    # 4. Create Stripe Checkout Session
    session = stripe.checkout.Session.create(
        mode='payment',
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': description or 'Pet Care Service'},
                'unit_amount': amount_cents,
            },
            'quantity': 1,
        }],
        metadata={
            'company_id': get_current_company_id(event),
            'request_id': request_id,
            'client_id': request.get('client_id'),
            'payment_type': 'booking',
            'environment': os.environ.get('STRIPE_ENV', 'sandbox'),
        },
        success_url=f"{FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/payment/cancelled?request_id={request_id}",
        customer_email=request.get('client_email'),
        expires_after=1800,  # 30 minutes
    )

    # 5. Update request record
    update_item(request_pk, request_sk, {
        'payment_status': 'payment_link_sent',
        'stripe_checkout_session_id': session.id,
        'payment_amount_cents': amount_cents,
        'payment_requested_at': now_iso(),
        'payment_requested_by': get_claims(event).get('email'),
    })

    # 6. Send payment email to client
    send_payment_email(request, session.url)

    # 7. Return session URL
    return success({
        'checkout_url': session.url,
        'session_id': session.id,
        'expires_at': session.expires_at,
    })
```

### Response

```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_...",
  "expires_at": 1719793800
}
```

---

## 5. Stripe Checkout Metadata Strategy

### On Checkout Session

```json
{
  "company_id": "tog_and_dogs",
  "request_id": "abc123",
  "client_id": "client_xyz",
  "payment_type": "booking",
  "environment": "sandbox"
}
```

### Why Each Field

| Field | Purpose |
|-------|---------|
| `company_id` | Tenant resolution in webhook handler |
| `request_id` | Link payment back to specific booking request |
| `client_id` | Audit trail + client payment history |
| `payment_type` | Distinguish booking payments from future subscription payments |
| `environment` | Prevent sandbox webhooks from updating production data |

---

## 6. DynamoDB Payment Record Model

### Option A: Fields on Existing Request Record (Recommended)

Add payment fields directly to the existing `REQ#{request_id}` record:

```json
{
  "PK": "REQ#abc123",
  "SK": "CLIENT#client_xyz",
  "status": "approved",
  "payment_status": "paid",
  "payment_amount_cents": 7500,
  "payment_currency": "usd",
  "stripe_checkout_session_id": "cs_test_...",
  "stripe_payment_intent_id": "pi_...",
  "payment_requested_at": "2025-07-01T10:00:00Z",
  "payment_requested_by": "mattnicomn10@gmail.com",
  "payment_completed_at": "2025-07-01T10:15:00Z",
  "payment_receipt_url": "https://pay.stripe.com/receipts/..."
}
```

**Why Option A:** Avoids a separate payment table/record. Payment is 1:1 with booking request. Simplifies queries (load request = load payment state). Consistent with existing single-record-per-request pattern.

### Option B: Separate Payment Record (Deferred)

```
PK: PAYMENT#{request_id}
SK: ATTEMPT#{checkout_session_id}
```

Only needed if we support multiple payment attempts per request or partial payments. Deferred unless explicitly required.

### Payment Audit Ledger

Reuse the existing billing event ledger pattern from 12D:

```
PK: BILLING#{company_id}
SK: EVENT#{stripe_event_id}

{
  "event_type": "checkout.session.completed",
  "payment_type": "booking",
  "request_id": "abc123",
  "amount": 7500,
  "currency": "usd",
  ...
}
```

### Idempotency

- Webhook handler checks `stripe_event_id` in billing ledger (existing 12D pattern)
- If `checkout.session.completed` fires twice for same session, second is skipped
- Request's `payment_status` only transitions forward (pending → sent → paid)

---

## 7. Webhook Handling for Booking Payments

### Events to Handle

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Set `payment_status = paid`, store payment_intent_id, receipt_url |
| `checkout.session.expired` | Set `payment_status = payment_failed` (admin can resend) |
| `charge.refunded` | Set `payment_status = refunded` (future) |
| `charge.dispute.created` | Alert admin (future) |

### checkout.session.completed Handler (Booking)

```python
def handle_checkout_completed_booking(company_id, event_id, event_type, session):
    """Handle completed checkout for a booking payment."""
    metadata = session.get('metadata', {})
    request_id = metadata.get('request_id')
    payment_type = metadata.get('payment_type')

    if payment_type != 'booking':
        # Not a booking payment — defer to subscription handler
        return handle_checkout_completed(company_id, event_id, event_type, session)

    if not request_id:
        raise ValueError("Missing request_id in checkout session metadata")

    # Update request record with payment confirmation
    # (Need to resolve request PK/SK from request_id)
    update_request_payment_status(company_id, request_id, {
        'payment_status': 'paid',
        'stripe_payment_intent_id': session.get('payment_intent'),
        'payment_completed_at': _now_iso(),
        'payment_receipt_url': _extract_receipt_url(session),
    })

    # Write billing ledger
    write_billing_event(company_id, event_id, event_type, {
        'payment_type': 'booking',
        'request_id': request_id,
        'amount': session.get('amount_total'),
        'currency': session.get('currency'),
    })
```

### Differentiating Booking vs Subscription Payments

The `payment_type` metadata field distinguishes:
- `payment_type = "booking"` → update request record
- `payment_type = "subscription"` → update tenant metadata (existing 12D logic)

---

## 8. Client UX

### Payment Email

When admin creates a checkout session, system sends email to client:

```
Subject: Payment Required — Your Booking with Togs & Dogs

Hi {client_name},

Your booking has been approved! Please complete payment to confirm.

Service: {service_description}
Amount: ${amount}
Due: Within 30 minutes of opening the link

[Pay Now] → {checkout_url}

If you have questions, contact us at {business_email}.

Thanks,
Togs & Dogs
```

### Success Page

After payment, Stripe redirects to:
```
{FRONTEND_URL}/payment/success?session_id={CHECKOUT_SESSION_ID}
```

Page shows: "Payment received! Your booking is confirmed."

### Cancel Page

If client abandons checkout:
```
{FRONTEND_URL}/payment/cancelled?request_id={request_id}
```

Page shows: "Payment not completed. Contact us if you need help."

### Future: Dashboard Payment Button

Later release can add a "Pay Now" button in the client portal for unpaid bookings. For now, email link is sufficient.

---

## 9. Admin UX

### Payment Request Action

On an approved booking in the admin dashboard:
- Button: "Send Payment Request"
- Prompts for amount (pre-filled from service pricing if available)
- Creates checkout session + sends email
- Shows confirmation: "Payment link sent to {client_email}"

### Payment Status Visibility

Admin request list/detail shows payment badge:
- No badge: no payment required
- 🟡 "Payment Pending": link sent, waiting
- 🟢 "Paid": payment confirmed
- 🔴 "Payment Failed": session expired, can resend
- ⚪ "Waived": admin waived payment

### Resend Payment Request

If payment_status is `payment_link_sent` or `payment_failed`:
- Admin can click "Resend Payment Request"
- Creates a new checkout session (old one may have expired)
- Sends new email to client

---

## 10. Security

### Tenant Ownership Validation

- Before creating a checkout session: validate request belongs to caller's company
- On webhook: verify `company_id` metadata matches a real tenant
- Fail closed if metadata is missing or tenant unknown

### Metadata Verification on Webhook

```python
def verify_booking_payment_webhook(session):
    metadata = session.get('metadata', {})
    company_id = metadata.get('company_id')
    request_id = metadata.get('request_id')
    environment = metadata.get('environment')

    if not company_id or not request_id:
        raise ValueError("Missing required metadata on checkout session")

    # Prevent sandbox webhooks from hitting production
    expected_env = os.environ.get('STRIPE_ENV', 'sandbox')
    if environment != expected_env:
        raise ValueError(f"Environment mismatch: got {environment}, expected {expected_env}")

    return company_id, request_id
```

### No Card Data Stored

- All card handling is on Stripe's hosted checkout page
- Our system never sees card numbers, CVVs, or raw payment details
- We store only: payment_intent_id, amount, status, receipt_url

---

## 11. Non-Goals (This Release)

| ❌ Item | Reason |
|---------|--------|
| Stripe Connect / marketplace payouts | Direct charges only |
| Recurring subscriptions | Separate release track |
| Live payments | Test mode only |
| Automatic refunds | Future release |
| Payment gating before scheduling | Admin flexibility preserved |
| In-app payments (mobile) | Web checkout only |
| Partial payments | Full amount per session |
| Multi-currency | USD only |
| Tax calculation | Deferred (use Stripe Tax later) |
| Invoicing | Deferred |
| Payment Links as primary | API-driven Checkout is primary |
| App Store payments | Not applicable |

---

## 12. Stripe SDK Dependency Decision

### Current State (12D)

The 12D implementation uses stdlib HMAC for signature verification — no Stripe SDK.

### For Checkout Session Creation (12G)

Creating a Checkout Session **requires** the Stripe Python SDK (`stripe` package) because:
- The `stripe.checkout.Session.create()` API is complex
- It handles authentication, request formatting, error handling
- Reimplementing it from scratch would be error-prone

### Recommendation

Add `stripe` package to the Lambda deployment in Release 12G:
- Install via pip into the Lambda layer or deployment package
- Pin version (e.g., `stripe==7.x.x`)
- Only used server-side (Lambda) — no client/mobile dependency
- Test mode API key loaded from environment variable

---

## 13. Implementation Sequence (Updated)

| Release | Scope | Type |
|---------|-------|------|
| **12F** | Booking payment architecture plan (this document) | Planning |
| **12G** | Checkout Session creation endpoint + webhook extension (code/tests) | Code |
| **12H** | AWS secrets, API Gateway route, Lambda env vars (Terraform) | Infrastructure |
| **12I** | Sandbox end-to-end: create session → pay → webhook → status update | Integration test |
| **12J** | Admin UI: payment request button, status badges | Frontend |
| **12K** | Client email: payment link template | Notification |
| **Future** | Live mode cutover, recurring billing | Production |

---

## 14. Risks and Open Questions

| Risk / Question | Impact | Resolution |
|-----------------|--------|------------|
| Amount source: manual entry vs service pricing? | Medium | Start with manual admin entry; add auto-calculation later |
| Checkout session expiry (30 min default) | Low | Admin can resend; consider longer expiry |
| Client without email? | Low | Payment link requires email; profile-only clients can't pay online |
| Multiple services on one request? | Medium | Single line item for now; itemized checkout later |
| Refund workflow? | Medium | Deferred — admin processes via Stripe Dashboard initially |
| Dispute/chargeback handling? | Low | Alert admin; handle manually via Stripe |
| Receipt delivery? | Low | Stripe sends receipt automatically if configured |
| Payment amount mismatch? | Low | Admin enters amount; no auto-calculation yet |

---

## 15. What This Document Does NOT Authorize

- ❌ Writing any code
- ❌ Adding the Stripe SDK dependency
- ❌ Creating API Gateway routes
- ❌ Storing secrets in AWS
- ❌ Deploying to production
- ❌ Creating live Stripe resources
- ❌ Charging customers
- ❌ Writing to DynamoDB
- ❌ Modifying Cognito/Postmark/Google Calendar
- ❌ EAS/TestFlight/App Store changes
- ❌ Implementing Stripe Connect

This is a planning and architecture document only. Implementation requires separate explicit approval (Release 12G).
