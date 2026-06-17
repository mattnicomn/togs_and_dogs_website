# Release 12X: Fresh Checkout Card-Only and First Email Send Validation Plan

**Status:** Planning
**Priority:** High (blocker for real client payments and email workflow)
**Risk to Production:** Low (controlled test actions with stop gates)
**Terraform Required:** No
**Code Changes:** None (validation only; code fix if card-only is broken)
**Scope:** Verify card-only Checkout enforcement + first controlled payment email send

---

## 1. Problem Statement

During 12W production smoke, Matthew opened an existing Stripe Test Payment Page and observed:
- Link (Stripe wallet)
- Card
- Bank
- Klarna

Releases 12M/12N added `payment_method_types[0]=card` to the Checkout Session creation payload, which should restrict the page to card-only.

**Possible explanations:**
1. The session Matthew opened was created **before** the 12M/12N patch deployed (old session = old config)
2. The `payment_method_types` parameter is not being sent correctly in production code
3. Stripe Dashboard settings or account-level payment method configuration overrides the API parameter
4. Stripe ignores `payment_method_types` in test mode under certain conditions

**Resolution requires:** Creating a fresh Checkout Session and verifying the payment page shows card-only.

---

## 2. Candidate Test Request Selection

### Requirements

| Requirement | Reason |
|-------------|--------|
| Request belongs to `company_id = tog_and_dogs` | Tenant ownership check |
| Request has `is_test_booking: true` or is clearly test data | Safety |
| Client email is Matthew-controlled | No real client contact |
| Status allows payment link generation | `payment_status` must not be `paid`/`refunded`/`waived` |

### Preferred Candidates

1. **Existing test request from 12K/12L** — `test_payment_validation_12k`
   - Already has `payment_status = paid` from earlier testing
   - Would need to be reset to `null`/`payment_failed` to allow new session (requires DynamoDB write — needs approval)

2. **New test request via admin portal**
   - Matthew creates a manual booking for a test client (Matthew-controlled email)
   - Marks as test booking
   - Approves it → status allows payment link generation
   - Safest option — no existing data mutation

3. **Any unpaid archived/test request**
   - Check if one already exists with `payment_status = null`

### Recommendation

**Option 2 (new test request via admin portal)** is safest if no suitable unpaid test request exists. Requires no DynamoDB write from AG.

---

## 3. Validation Sequence

### Gate A: Fresh Checkout Session (Card-Only Verification)

**Purpose:** Confirm that a newly created Checkout Session restricts to card-only payment methods.

| Step | Actor | Action | Stop? |
|------|-------|--------|-------|
| A1 | Matthew | Identify or create a suitable test request (unpaid, test, Matthew-controlled email) | — |
| A2 | Matthew | Approve: "Generate a fresh payment link for this test request" | ⛔ STOP until approved |
| A3 | Matthew | In admin CareCard, click "Generate Payment Link" with a test amount (e.g., $1.00) | — |
| A4 | Matthew | Click "Test Payment Page" to open the fresh Stripe Checkout URL | — |
| A5 | Matthew | **Observe:** What payment methods are shown? | — |
| A6 | Matthew | **Report:** Card only? Or Link/Bank/Klarna visible? | — |
| A7 | Matthew | Close the Stripe page **without submitting payment** | — |

### Expected Result (Pass)

- Only "Card" payment option is shown
- No Link, Bank, Klarna, or other methods visible

### If Card-Only Fails (Link/Bank/Klarna Still Shown)

Proceed to investigation steps (Section 5 below).

---

### Gate B: Confirmation Modal Validation

**Purpose:** Verify the "Send Payment Email" confirmation modal opens and Cancel works.

| Step | Actor | Action | Stop? |
|------|-------|--------|-------|
| B1 | Matthew | On the same test request (now `payment_link_sent`), click "Send Payment Email" | — |
| B2 | Matthew | **Observe:** Does the confirmation modal appear? | — |
| B3 | Matthew | **Verify:** Modal shows recipient email, amount, service, sandbox warning | — |
| B4 | Matthew | Click **"Cancel"** in the modal | — |
| B5 | Matthew | **Verify:** Modal closes, no email sent, no error | — |

### Expected Result

- Modal appears with correct details
- Cancel dismisses without side effects

---

### Gate C: First Real Payment Email Send

**Purpose:** Send a real email to a Matthew-controlled address and verify delivery.

| Step | Actor | Action | Stop? |
|------|-------|--------|-------|
| C1 | Matthew | Approve: "Send first real payment email to my own address" | ⛔ STOP until approved |
| C2 | Matthew | Verify recipient will be Matthew-controlled (e.g., `mattnicomn10@gmail.com`) | — |
| C3 | Matthew | Click "Send Payment Email" → confirm modal → click **"Send Email"** | — |
| C4 | Matthew | **Observe:** Success banner in admin UI | — |
| C5 | Matthew | Check inbox for payment request email | — |
| C6 | Matthew | **Verify email contents:** | — |
| | | - Subject line correct | |
| | | - Client name / pet / service details correct | |
| | | - Amount shown correctly | |
| | | - "Pay Now" link present and clickable | |
| | | - Sandbox warning banner present | |
| | | - Business name/contact info present | |
| C7 | AG | Verify DynamoDB: `payment_email_sent_at` set on request record | ⛔ Read-only check only |
| C8 | AG | Verify notification ledger entry exists | ⛔ Read-only check only |

### Expected Result

- Email arrives at Matthew's inbox
- Contents match template specification from 12S/12T
- Sandbox warning is visible
- Payment link works (opens Stripe Checkout)
- No email sent to any real client

---

## 4. Stop Points (Explicit Approval Required)

| Gate | Requires | Before |
|------|----------|--------|
| Gate A (step A2) | Matthew says "approved" or "generate" | Creating fresh Checkout Session |
| Gate C (step C1) | Matthew says "approved" or "send email" | Sending first real email |
| Payment submission | Matthew says "approved" or "submit payment" | Completing any Stripe payment |

**Default:** If Matthew does not explicitly approve a gate, do NOT proceed past it.

---

## 5. Stripe Payment Method Investigation (If Card-Only Fails)

If Gate A reveals Link/Bank/Klarna on a fresh session:

### Investigation Steps

| # | Check | How |
|---|-------|-----|
| 1 | Verify `payment_method_types` in code | Read `src/backend/common/stripe_client.py` — confirm `payment_method_types[0]=card` is in payload |
| 2 | Verify Lambda has latest code | Check `source_code_hash` on admin Lambda matches current build |
| 3 | Check Stripe Dashboard payment method settings | Stripe Dashboard → Settings → Payment methods — are additional methods enabled at account level? |
| 4 | Check if Stripe ignores `payment_method_types` with `mode=payment` | Review Stripe docs for any test-mode or account-setting override behavior |
| 5 | Test with Stripe CLI | `stripe checkout sessions create --payment-method-types=card ...` and inspect resulting page |

### Likely Fixes

| Cause | Fix |
|-------|-----|
| Account-level payment methods enabled in Stripe Dashboard | Disable Link/Klarna/Bank in Dashboard payment method settings |
| Code sends parameter but Stripe ignores in test mode | Disable in Dashboard (overrides API in some configurations) |
| Code is NOT sending the parameter | Code fix needed (verify payload construction) |
| Old Lambda deployed (pre-12M code) | Redeploy Lambda via Terraform |

### Recommendation

Check Stripe Dashboard payment method settings FIRST. Stripe's newer "automatic payment methods" feature can override `payment_method_types` unless explicitly disabled. The simplest fix may be toggling off unwanted methods in Dashboard → Settings → Payment methods.

---

## 6. Rollback / Safety

| Scenario | Action |
|----------|--------|
| Fresh session still shows Klarna | Investigate (Section 5); do not send client emails until resolved |
| Email send fails with 500 | Check CloudWatch logs; do not retry without investigation |
| Email arrives with wrong content | Review Postmark template; block further sends |
| Email sent to wrong recipient | Immediately investigate; should be impossible if using test request with Matthew email |
| Payment accidentally submitted | Document; no real charges in sandbox — test money only |

---

## 7. Success Criteria

12X validation is complete when:

1. ✅ Fresh Checkout Session shows card-only (or Dashboard fix applied and confirmed)
2. ✅ Confirmation modal opens correctly with all expected fields
3. ✅ Cancel in modal works without side effects
4. ✅ First payment email sent to Matthew-controlled address
5. ✅ Email arrives with correct content and sandbox warning
6. ✅ Payment link in email works (opens Stripe Checkout)
7. ✅ Notification ledger entry written
8. ✅ Request record has `payment_email_sent_at`
9. ✅ No real client received any communication
10. ✅ No real payment submitted

---

## 8. Recommended Next Steps After 12X

| If card-only passes + email passes | Next Release |
|-------------------------------------|--------------|
| Both pass | 12Y — End-to-end payment + email closeout (submit test payment after email) |
| Card-only fails | 12X.1 — Stripe payment method enforcement fix (code or Dashboard) |
| Email fails | Debug and retry within 12X |

---

## 9. What This Document Does NOT Authorize

- ❌ Creating Checkout Sessions (requires Gate A approval)
- ❌ Sending emails (requires Gate C approval)
- ❌ Submitting payments (requires separate approval)
- ❌ Writing code
- ❌ Deploying anything
- ❌ Terraform/AWS changes
- ❌ DynamoDB writes
- ❌ Cognito changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets
- ❌ Contacting real clients

This is a planning document only. Each validation gate requires Matthew's explicit approval before execution.
