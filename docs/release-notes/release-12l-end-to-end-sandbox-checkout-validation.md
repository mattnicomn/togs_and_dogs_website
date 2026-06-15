# Release 12L — End-to-End Sandbox Stripe Checkout Validation

This release validates the complete Stripe Checkout payment flow end-to-end in sandbox mode,
covering session creation, payment completion, webhook delivery, signature verification,
and DynamoDB record updates.

---

## Summary

Release 12L executed a controlled end-to-end sandbox Checkout validation using an approved
archived test request. The core payment flow passed successfully. Two follow-up defects were
identified and are tracked for Release 12M.

---

## Validation Scope

### Test Request (Approved)
| Field | Value |
|---|---|
| `request_id` | `cd211318-aa72-4bfc-829c-f450e6ffe6c2` |
| `client_id` | `client_1697162f` |
| `company_id` | `tog_and_dogs` |
| `is_test_booking` | `true` |
| `status` | `ARCHIVED` |
| `amount` | `$1.00` (100 cents) |

### Safety Boundaries
- **No live Stripe mode.** All operations used Stripe sandbox (test) mode only.
- **No real charges.** The test card `4242 4242 4242 4242` was used — no real payment occurred.
- **No real customer payment card was used.**
- **No unrelated DynamoDB records were changed.**
- **No Cognito changes.**
- **No frontend or mobile deployments.**
- **No second-tenant changes.**
- **No secrets committed.**

---

## Validation Results

### 1. Checkout Session Creation
- **Endpoint**: `POST /admin/requests/{requestId}/payment-session`
- **Lambda**: `togs-and-dogs-prod-admin` (invoked directly to bypass Cognito for headless testing)
- **Result**: Checkout Session created successfully
- **Session ID**: `cs_test_a1bCjlvlR5m0So4g2jMJGCE9yaiUEdbycBLVVLQoY8DqQukTXNTpKnjHXv`
- **Metadata confirmed**: `request_id`, `client_id`, `company_id`, `environment=sandbox`, `payment_type=booking`

### 2. Payment Completion
- **Method**: Stripe Checkout UI — test card `4242 4242 4242 4242`
- **Checkout Session status**: `complete`
- **Payment status (Stripe)**: `paid`
- **PaymentIntent**: `pi_3TigUZ7vQm58ivsH0ge6uaeG`
- **PaymentIntent status**: `succeeded`
- **Amount**: `$1.00` USD
- **Customer email**: `brearockwell@gmail.com`

### 3. Stripe Webhook Delivery
- **Event type**: `checkout.session.completed`
- **Event ID**: `evt_1Tigg17vQm58ivsHyzOMNJvk`
- **Endpoint**: `POST /webhooks/stripe` → `togs-and-dogs-prod-stripe-webhook` Lambda
- **Delivered**: ✅ Yes
- **Signature verification**: ✅ **Passed** — no `SECURITY:` failure logged

### 4. CloudWatch Webhook Lambda Logs
Key log entries confirmed in `/aws/lambda/togs-and-dogs-prod-stripe-webhook`:
```
STRIPE_WEBHOOK_RECEIVED: type=checkout.session.completed, id=evt_1Tigg17vQm58ivsHyzOMNJvk
STRIPE_WEBHOOK_PROCESSED: type=checkout.session.completed, id=evt_1Tigg17vQm58ivsHyzOMNJvk, company=tog_and_dogs
```
- Lambda duration: `3,473 ms` (cold start), billed `3,588 ms`

### 5. DynamoDB — Request Record Updated
- **PK**: `REQ#cd211318-aa72-4bfc-829c-f450e6ffe6c2`
- **SK**: `CLIENT#client_1697162f`
- **`payment_status`**: ✅ `paid` (updated at `2026-06-15T20:00:13Z`)
- **`stripe_checkout_session_id`**: Set ✅
- **`stripe_payment_intent_id`**: `pi_3TigUZ7vQm58ivsH0ge6uaeG` ✅
- **`status`**: `ARCHIVED` (unchanged — expected; only `payment_status` changes on payment)
- **`is_test_booking`**: `true` ✅

### 6. Billing / Idempotency Ledger
- **PK**: `BILLING#tog_and_dogs`
- **SK**: `EVENT#evt_1Tigg17vQm58ivsHyzOMNJvk`
- **`event_type`**: `checkout.session.completed`
- **`processing_status`**: ✅ `completed`
- **`request_id`**: `cd211318-aa72-4bfc-829c-f450e6ffe6c2` ✅
- **`stripe_checkout_session_id`**: Present ✅
- **`amount_total`**: `100` ✅

The idempotency guard is active. Re-delivery of the same event ID will be detected and skipped.

### 7. Unrelated Records Check
No records outside the approved test request and its billing ledger entry were mutated.
No tenant billing rows (`TENANT#...`) were changed — this was a `payment_type=booking` event,
not a SaaS subscription event.

---

## Known Follow-up Defects

### Defect 1 — Wrong Success/Cancel Redirect Domain
**Severity**: Non-blocking (payment succeeds; redirect fails post-payment)

After payment, Stripe redirected the browser to:
```
https://togsanddogs.com/booking/cd211318-aa72-4bfc-829c-f450e6ffe6c2/success?session_id=...
```
Result: `DNS_PROBE_FINISHED_NXDOMAIN` — the domain `togsanddogs.com` does not exist.

**Root cause**: The hardcoded fallback defaults in
`src/backend/common/stripe_client.py` use `togsanddogs.com` instead of the correct
production site `toganddogs.usmissionhero.com`. The `STRIPE_SUCCESS_URL_TEMPLATE` and
`STRIPE_CANCEL_URL_TEMPLATE` environment variables were absent from the live admin Lambda,
causing fallback to these incorrect defaults.

**Expected correct domain**: `https://toganddogs.usmissionhero.com`

### Defect 2 — Klarna / Dynamic Payment Methods Shown
**Severity**: Non-blocking for sandbox validation; must be fixed before production

The Stripe Checkout page displayed Klarna as a payment option alongside the card flow.
Booking payments should be restricted to card-only.

**Fix**: Add `payment_method_types[]=card` to the Stripe Checkout Session creation payload
in `src/backend/common/stripe_client.py`.

### Defect 3 — Terraform Drift on URL Template Env Vars
**Severity**: Minor — safe drift, no production impact

The `STRIPE_SUCCESS_URL_TEMPLATE` and `STRIPE_CANCEL_URL_TEMPLATE` environment variables
are **absent** from the live `togs-and-dogs-prod-admin` Lambda after they were manually
removed during Gate A.2 troubleshooting (to resolve an empty-string error).

Terraform expects them to be present (as empty strings). Running `terraform plan` will
show an in-place update to re-add them. These should be reconciled via Terraform with
correct non-empty values, not restored as empty strings.

---

## Recommended Next Release

### Release 12M — Stripe Checkout Payment UX and Redirect Patch

**Scope**:
1. Fix success/cancel URL defaults in `src/backend/common/stripe_client.py` to use
   `https://toganddogs.usmissionhero.com`
2. Set `STRIPE_SUCCESS_URL_TEMPLATE` and `STRIPE_CANCEL_URL_TEMPLATE` to correct values
   in `infra/prod/terraform.tfvars` and deploy via Terraform
3. Force card-only Checkout for booking payments by adding `payment_method_types[]=card`
   to the Stripe session creation payload
4. Reconcile Terraform drift for the URL template env vars (do not use manual Lambda edits)
5. Run full backend test suite: `py -m pytest tests/backend/ -v`
6. Deploy safely via Terraform plan + apply
7. Validate with a small sandbox payment session or session creation test as appropriate

---

## Safety Confirmation

| Safety Check | Result |
|---|---|
| Live Stripe mode used | ❌ No — sandbox only |
| Real charge occurred | ❌ No — test card only |
| Real customer card used | ❌ No |
| Secrets committed | ❌ No |
| `terraform.tfvars` committed | ❌ No |
| Terraform executed | ❌ No |
| Code changes made | ❌ No |
| Unrelated DynamoDB records mutated | ❌ No |
| Cognito changes | ❌ No |
| Frontend/mobile deployment | ❌ No |
| Second-tenant changes | ❌ No |
| Additional Checkout Sessions created | ❌ No (beyond the Gate B session) |
| Additional payments run | ❌ No |
