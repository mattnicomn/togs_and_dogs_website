# Release 12Y: End-to-End Sandbox Payment Submission Validation Plan

**Status:** Planning
**Priority:** High (final sandbox payment validation before live-mode consideration)
**Risk to Production:** Low (sandbox Stripe, test card, controlled test request)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Submit one controlled sandbox payment and verify full backend lifecycle

---

## 1. Objective

Complete the final piece of the payment workflow: client submits payment via Stripe Checkout → webhook fires → backend updates request to `paid` → admin sees paid status.

This has been partially validated in 12L but with a different test record and before the 12M/12N/12O/12R patches. This validation confirms the full patched workflow end-to-end.

---

## 2. Test Request

| Field | Value |
|-------|-------|
| Request ID | `c1b11afe-3cda-45c1-9ada-af91b14234ad` |
| Client ID | `client_1697162f` |
| Client Name | TestClient_ScenarioB |
| Pet Name | TestPet_ScenarioB |
| Amount | $1.00 (100 cents) |
| Recipient | `brearockwell@gmail.com` |
| Checkout Session | `cs_test_a1gSogQv2TumTRSZaBJ9mbXpEQjRIrSJPcS7el3N84F6cN7RQZIOtAt8lU` |
| Expected current status | `payment_link_sent` |
| Company | `tog_and_dogs` |

---

## 3. Pre-Payment Checks

Before submitting payment, verify:

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Request exists in DynamoDB | AG read-only query | Record present |
| 2 | `payment_status = payment_link_sent` | Field check | Not already `paid` |
| 3 | `stripe_payment_url` exists | Field check | Non-empty URL |
| 4 | Checkout session not expired | Open URL in browser | Stripe page loads (not "expired" message) |
| 5 | Webhook endpoint active | Stripe Dashboard → Webhooks | Status: Active |
| 6 | Not already paid/refunded/waived | Status check | Blocked statuses absent |

### If Checkout Session Is Expired

If the existing session has expired (30-min default):
1. Generate a fresh $1.00 payment link from admin CareCard
2. Use the new session URL instead
3. Document the new session ID

---

## 4. Stripe Test Card Details

| Field | Value |
|-------|-------|
| Card number | `4242 4242 4242 4242` |
| Expiration | Any future date (e.g., `12/30`) |
| CVC | Any 3 digits (e.g., `123`) |
| Name | `Test User` |
| ZIP/Postal | Any valid format (e.g., `12345`) |

**This is Stripe's standard test card.** No real charge occurs. Sandbox mode only.

---

## 5. Payment Submission Steps

| Step | Actor | Action | Stop? |
|------|-------|--------|-------|
| 1 | AG/Matthew | Open the payment link URL in a browser | — |
| 2 | AG/Matthew | Verify: page shows card-only input (no Bank/Klarna) | ⛔ Stop if Bank/Klarna shown |
| 3 | AG/Matthew | Verify: amount shows $1.00 | — |
| 4 | Matthew | Approve: "Submit sandbox test payment" | ⛔ STOP until approved |
| 5 | AG/Matthew | Enter test card: `4242 4242 4242 4242`, exp `12/30`, CVC `123`, ZIP `12345` | — |
| 6 | AG/Matthew | Click "Pay" / submit button | — |
| 7 | AG/Matthew | Observe: redirect to success URL (may 404 — that's fine, domain should be `toganddogs.usmissionhero.com`) | — |
| 8 | AG | Wait 10–30 seconds for webhook delivery | — |
| 9 | AG | Verify backend state (Section 6 below) | — |

---

## 6. Expected Backend Results After Payment

### DynamoDB Request Record

| Field | Expected Value |
|-------|----------------|
| `payment_status` | `paid` |
| `stripe_payment_intent_id` | `pi_...` (set by webhook) |
| `stripe_checkout_session_id` | `cs_test_a1gSogQv...` (unchanged) |
| `payment_completed_at` | ISO timestamp (set by webhook) |
| `payment_amount_cents` | `100` |

### Billing Event Ledger

| Field | Expected |
|-------|----------|
| `PK` | `BILLING#tog_and_dogs` |
| `SK` | `EVENT#evt_...` (new Stripe event ID) |
| `event_type` | `checkout.session.completed` |
| `payment_type` | `booking` |
| `request_id` | `c1b11afe-3cda-45c1-9ada-af91b14234ad` |
| `processing_status` | `completed` |

### Webhook Delivery

| Check | Expected |
|-------|----------|
| Stripe Dashboard → Webhooks → Recent deliveries | `checkout.session.completed` delivered with 200 response |
| CloudWatch logs | `STRIPE_WEBHOOK_PROCESSED: type=checkout.session.completed` |
| No errors | Zero `BILLING ERROR` or `SECURITY` entries |

### Admin UI

| Check | Expected |
|-------|----------|
| CareCard payment section | 🟢 "Paid" badge with "$1.00" |
| "Generate Payment Link" button | Hidden (paid status blocks) |
| "Send Payment Email" button | Hidden (paid status) |

---

## 7. Validation Checklist

| # | Check | Method | Expected | Result |
|---|-------|--------|----------|--------|
| 1 | Stripe Checkout completed | Browser redirect | Success URL loaded | ___ |
| 2 | Stripe Dashboard: PaymentIntent succeeded | Stripe Dashboard | Status: succeeded | ___ |
| 3 | Stripe Dashboard: webhook delivered 200 | Stripe Dashboard → Webhooks | 200 response | ___ |
| 4 | CloudWatch: webhook processed | AWS CloudWatch logs | `STRIPE_WEBHOOK_PROCESSED` log | ___ |
| 5 | DynamoDB: payment_status = paid | Read-only query | `paid` | ___ |
| 6 | DynamoDB: stripe_payment_intent_id set | Read-only query | `pi_...` present | ___ |
| 7 | DynamoDB: payment_completed_at set | Read-only query | ISO timestamp present | ___ |
| 8 | DynamoDB: billing ledger event written | Read-only query | Record exists | ___ |
| 9 | Admin UI: paid badge visible | Browser check | 🟢 Paid | ___ |
| 10 | Admin UI: Generate button hidden | Browser check | Not visible | ___ |
| 11 | No duplicate payment session created | DynamoDB check | Only original session | ___ |
| 12 | No additional email sent | Brea inbox check | No new email | ___ |
| 13 | No real charge | Stripe Dashboard | $0 real balance | ___ |

---

## 8. Stop Points (Explicit Approval Required)

| Gate | Trigger | Action If Not Approved |
|------|---------|------------------------|
| Payment submission (step 4) | Matthew must say "approved" or "submit payment" | Do NOT enter card details |
| Bank/Klarna shown (step 2) | Unexpected payment methods on Checkout page | Stop, investigate, do NOT proceed |
| Webhook failure | `payment_status` does not become `paid` within 60s | Stop, check CloudWatch, report |

---

## 9. Failure Handling

| Failure | Action |
|---------|--------|
| Checkout session expired | Generate fresh session, retry with new URL |
| Stripe page shows error | Screenshot/describe error, do not retry blindly |
| Payment fails (card declined) | Should not happen with test card — investigate |
| Webhook not delivered | Check Stripe Dashboard delivery log, check endpoint health |
| Webhook delivered but DynamoDB not updated | Check CloudWatch for processing errors |
| payment_status remains payment_link_sent | Wait up to 60s, then check CloudWatch |
| Duplicate webhook delivery | Expected to be handled by idempotency — verify only one ledger entry |

---

## 10. What Happens After Success

If all 13 validation checks pass:

1. Document results in this file
2. Mark 12Y as complete
3. The full sandbox payment lifecycle is validated:
   - Admin generates link ✅
   - Email sent to client ✅
   - Client pays via card-only Checkout ✅
   - Webhook processes payment ✅
   - Request status updated to paid ✅
   - Admin sees paid state ✅
   - Duplicate payment blocked by guard ✅

4. **Recommended next steps:**
   - 12Z — Sandbox payment workflow closeout and live-mode readiness assessment
   - Or shift to real client workflow planning (pricing, live mode, first real payment)

---

## 11. Cleanup After Validation

The test request will have `payment_status = paid` after successful validation.

**Recommendation:** Leave as-is. The request is clearly test data (`TestClient_ScenarioB`). No cleanup needed unless it causes admin UI clutter.

---

## 12. What This Document Does NOT Authorize

- ❌ Submitting payment (requires Gate approval)
- ❌ Creating new Checkout Sessions (use existing or generate fresh only if expired)
- ❌ Sending emails
- ❌ Writing code
- ❌ Deploying anything
- ❌ Terraform/AWS changes
- ❌ Cognito changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Live Stripe mode
- ❌ Real customer payments
- ❌ Committing secrets

This is a planning document only. Payment submission requires Matthew's explicit approval at the designated stop point.
