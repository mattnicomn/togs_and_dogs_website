# Release 12G: Stripe Checkout Session Creation Endpoint and Booking Payment Webhook Extension

**Status:** Complete (code/tests only — not deployed)
**Type:** Code implementation
**Terraform Required:** No (endpoint defined in code, integration with API Gateway deferred to deployment release)
**Deployed:** No
**Dependencies Added:** None (uses stdlib `urllib` for Stripe API calls to keep backend Lambda zip package lightweight)

---

## Summary

Implements booking-specific Stripe Checkout session creation for admin/owners and extends the webhook handler callback logic to support booking payments.

Key design highlights:
- **No Stripe SDK Dependency**: Integrated the Stripe API for Checkout Session creation directly using Python's standard library `urllib.request`. This keeps the deployment package size minimal and portable.
- **Tenant Enforcement**: Secured the new admin endpoint to enforce strict tenant boundary validation on the Request record before session creation.
- **Fail Closed Webhook Handling**: Hardened the webhook processor to fail closed (returning 500/400 errors) if booking payment metadata is missing or if the request/tenant cannot be resolved or matched.

---

## Files Changed

| File | Type | Description |
|------|------|-------------|
| `src/backend/common/stripe_client.py` | New | Custom Stripe API wrapper using standard library `urllib` to create Checkout Sessions in `payment` mode with line items and metadata. |
| `src/backend/handlers/admin_handler.py` | Modified | Added the admin-only route `POST /admin/requests/{request_id}/payment-session` to create Stripe Checkout Sessions, validate tenant ownership, and update Request status to `payment_link_sent`. |
| `src/backend/handlers/stripe_webhook_handler.py` | Modified | Extended `checkout.session.completed` handler to process booking payments, update Request status to `paid`, store Stripe transaction IDs, and write ledger events. |
| `tests/backend/test_r12g_stripe_checkout.py` | New | 10 new unit tests covering positive creation flow, role authorization, tenant boundary protection, validation errors, Stripe API failures, webhook processing, signature mismatches, and idempotency. |
| `docs/release-notes/release-12g-stripe-checkout-session-creation-and-booking-payment-webhook-extension.md` | New | This file. |

---

## Implementation Details

### common/stripe_client.py
- **create_checkout_session(...)**: Assembles nested form-urlencoded payloads (e.g. `line_items[0][price_data][unit_amount]`) required by the Stripe API. Submits POST request to `https://api.stripe.com/v1/checkout/sessions` with the configured `STRIPE_SECRET_KEY` Bearer token.
- **StripeAPIError**: Custom exception class designed to capture and log HTTP status codes and detailed JSON error messages returned from Stripe.

### handlers/admin_handler.py
- **POST /admin/requests/{request_id}/payment-session**:
  - Validates caller role (`owner`/`admin`).
  - Retrieves target Request record using `request_id` and `client_id` (supporting query parameters or request body).
  - Validates tenant boundary using `validate_tenant_ownership` (returns `403` on mismatch).
  - Validates `amount_cents` is a positive integer (returns `400` on invalid or missing amount).
  - Triggers Stripe session creation with specific metadata tags (`company_id`, `request_id`, `client_id`, `payment_type="booking"`, `environment="sandbox"`).
  - Updates the Request record in DynamoDB with:
    - `payment_status` = `"payment_link_sent"`
    - `stripe_checkout_session_id`
    - `stripe_payment_url`
    - `payment_requested_at`
    - `payment_amount_cents`
    - `payment_requested_by` (email of the creator)
  - Logs the event to the system audit trail.

### handlers/stripe_webhook_handler.py
- **checkout.session.completed booking extension**:
  - Checks if `metadata.payment_type` is `"booking"`.
  - Resolves target Request record from DynamoDB.
  - Validates that the request belongs to the webhook event's tenant (`company_id`).
  - Updates the Request record in DynamoDB with:
    - `payment_status` = `"paid"`
    - `stripe_payment_intent_id`
    - `stripe_checkout_session_id`
    - `stripe_customer_id`
    - `payment_completed_at`
  - Writes a ledger entry (PK: `BILLING#{company_id}`, SK: `EVENT#{stripe_event_id}`) containing metadata and transaction IDs to ensure idempotency.
  - Returns `400` or `500` (fails closed) if metadata is missing or mismatched.

---

## Verification Plan

### Automated Unit Tests

Run the backend test suite:
```powershell
py -m pytest tests/backend/ -v
```

10 new test cases added in `tests/backend/test_r12g_stripe_checkout.py`:
- `test_admin_create_session_success`: Admin successfully requests Stripe session, validates inputs, and updates Request record in DynamoDB.
- `test_non_admin_creation_forbidden`: Checks that client/staff/unknown roles are rejected.
- `test_cross_tenant_creation_forbidden`: Confirms that accessing another tenant's Request throws 403.
- `test_invalid_amount_rejected`: Checks validation for non-positive or malformed amount values.
- `test_stripe_creation_failure_handled`: Gracefully handles Stripe API errors and returns 500.
- `test_webhook_booking_payment_completed_success`: Webhook completes a booking payment, updates Request to `paid`, and writes to ledger.
- `test_webhook_missing_company_id_fails_closed`: Returns 400 if company ID is missing from metadata.
- `test_webhook_missing_request_id_fails_closed`: Returns 500 if request ID is missing.
- `test_webhook_mismatched_company_id_fails_closed`: Returns 500 if company ID is mismatched with the Request.
- `test_webhook_duplicate_is_idempotent`: Returns 200 with `already_processed` status for duplicate events.

All 394 backend tests pass successfully.

### Manual Verification
Ensure Python compile checks pass on all modified/new modules:
```powershell
py -m py_compile src/backend/common/stripe_client.py src/backend/handlers/stripe_webhook_handler.py src/backend/handlers/admin_handler.py tests/backend/test_r12g_stripe_checkout.py
```

---

## Guardrails Confirmed

The following constraints have been strictly followed:
- ❌ No AWS infrastructure/Terraform/Lambda deployment.
- ❌ No production deployment or live Stripe API configuration.
- ❌ No live Stripe API keys or secrets stored/committed.
- ❌ No Cognito, Postmark, or Google Calendar changes.
- ❌ No EAS/TestFlight or frontend changes.
