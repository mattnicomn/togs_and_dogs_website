# Release 12M: Stripe Checkout Payment UX and Redirect Patch Plan

**Status:** Planning
**Priority:** High (fixes broken redirect + unwanted payment methods)
**Risk to Production:** Low (targeted fixes to known defects)
**Terraform Required:** Yes (env var reconciliation)
**Code Changes:** Yes (stripe_client.py + tests)
**Scope:** Fix redirect URLs, restrict to card-only, reconcile Terraform drift

---

## 1. Defects from 12L Validation

| # | Defect | Impact | Root Cause |
|---|--------|--------|------------|
| 1 | Success redirect goes to `togsanddogs.com` (NXDOMAIN) | Client sees DNS error after successful payment | Hardcoded fallback URL in `stripe_client.py` |
| 2 | Klarna/dynamic payment methods shown in Checkout | Clients may use unintended payment flows | No `payment_method_types` specified in session creation |
| 3 | Terraform drift: `STRIPE_SUCCESS_URL_TEMPLATE` and `STRIPE_CANCEL_URL_TEMPLATE` absent from admin Lambda | Env vars were cleaned manually; not in Terraform state | Manual Lambda env edit without corresponding Terraform update |

---

## 2. Fix 1: Redirect URL Correction

### Current Code (`src/backend/common/stripe_client.py`)

```python
default_success = "https://togsanddogs.com/booking/{request_id}/success?session_id={{CHECKOUT_SESSION_ID}}"
default_cancel = "https://togsanddogs.com/booking/{request_id}/cancel"
```

### Problem

- `togsanddogs.com` is not the production domain — the site is at `https://toganddogs.usmissionhero.com`
- Even with the correct domain, no `/booking/{request_id}/success` route exists in the frontend yet

### Proposed Fix

```python
default_success = "https://toganddogs.usmissionhero.com/payment/success?request_id={request_id}&session_id={{CHECKOUT_SESSION_ID}}"
default_cancel = "https://toganddogs.usmissionhero.com/payment/cancel?request_id={request_id}"
```

### Notes

- The frontend does not yet have `/payment/success` or `/payment/cancel` routes
- This is acceptable for now — the redirect will show a 404 or the SPA will catch it
- A future release (12N+) will add actual success/cancel pages
- The important fix is: client lands on the correct domain, not NXDOMAIN
- `{CHECKOUT_SESSION_ID}` uses Stripe's template syntax `{CHECKOUT_SESSION_ID}` (double braces in Python f-string → single braces in output)

### Alternative: Simple Thank-You Page

If a dedicated payment route is not desired yet, redirect to the home page:
```python
default_success = "https://toganddogs.usmissionhero.com/?payment=success&request_id={request_id}"
default_cancel = "https://toganddogs.usmissionhero.com/?payment=cancel&request_id={request_id}"
```

**Recommendation:** Use `/payment/success` and `/payment/cancel` paths. Even if they 404 initially, the URL structure is correct for when the pages are built.

---

## 3. Fix 2: Card-Only Payment Method Types

### Current Code

No `payment_method_types` field is included in the Checkout Session payload. When omitted, Stripe enables all eligible payment methods for the session (including Klarna, Afterpay, etc.).

### Proposed Fix

Add to the payload in `create_checkout_session()`:

```python
payload = {
    'mode': 'payment',
    'payment_method_types[0]': 'card',  # Card only — no Klarna, Afterpay, etc.
    'success_url': success_url,
    'cancel_url': cancel_url,
    ...
}
```

### Why Card-Only

- Booking payments are one-time, known-amount charges
- Klarna/BNPL adds complexity (delayed settlement, dispute risk)
- Ryan's business model is simple: client pays card → service is delivered
- Can be relaxed later if business needs BNPL options

---

## 4. Fix 3: Terraform Drift Reconciliation

### Problem

The admin Lambda's environment variables were manually edited (STRIPE_SUCCESS_URL_TEMPLATE and STRIPE_CANCEL_URL_TEMPLATE removed). This means Terraform state doesn't match reality. Next `terraform apply` may behave unexpectedly.

### Proposed Fix

Add the URL template variables to the admin Lambda in Terraform:

```hcl
# In infra/prod/main.tf, admin Lambda environment block:
environment {
  variables = merge(
    {
      DATA_TABLE_NAME          = module.data.table_name
      ADMIN_USER_POOL_ID       = module.auth.user_pool_id
      DEFAULT_COMPANY_ID       = "tog_and_dogs"
      GOOGLE_CLIENT_CREDS_NAME = module.secrets.google_client_creds_arn
      GOOGLE_USER_TOKENS_NAME  = module.secrets.google_user_tokens_arn
      STRIPE_SECRET_KEY        = var.stripe_secret_key
      STRIPE_ENVIRONMENT       = "sandbox"
      STRIPE_SUCCESS_URL_TEMPLATE = var.stripe_success_url_template
      STRIPE_CANCEL_URL_TEMPLATE  = var.stripe_cancel_url_template
    },
    local.notification_env_vars
  )
}
```

### New Variables in `variables.tf`

```hcl
variable "stripe_success_url_template" {
  type        = string
  description = "Success redirect URL template for Stripe Checkout. Use {request_id} placeholder."
  default     = "https://toganddogs.usmissionhero.com/payment/success?request_id={request_id}&session_id={CHECKOUT_SESSION_ID}"
}

variable "stripe_cancel_url_template" {
  type        = string
  description = "Cancel redirect URL template for Stripe Checkout. Use {request_id} placeholder."
  default     = "https://toganddogs.usmissionhero.com/payment/cancel?request_id={request_id}"
}
```

### Why Defaults in `variables.tf` (Not terraform.tfvars)

- These URLs are not secrets — they're public-facing redirect destinations
- Having them as defaults with override capability is clean
- No need to add them to `.tfvars` unless overriding for a different environment

---

## 5. Files to Change

### Code Changes

| File | Change |
|------|--------|
| `src/backend/common/stripe_client.py` | Fix default URLs to `toganddogs.usmissionhero.com`, add `payment_method_types[0]=card` |

### Test Changes

| File | Change |
|------|--------|
| `tests/backend/test_r12g_stripe_checkout.py` | Add/update test asserting `payment_method_types` includes `card`, verify URL format |

### Terraform Changes

| File | Change |
|------|--------|
| `infra/prod/variables.tf` | Add `stripe_success_url_template` and `stripe_cancel_url_template` variables |
| `infra/prod/main.tf` | Add URL template env vars to admin Lambda |

---

## 6. Test Plan

### New/Updated Unit Tests

| Test | Assertion |
|------|-----------|
| `test_checkout_session_includes_card_payment_type` | Payload sent to Stripe includes `payment_method_types[0]=card` |
| `test_checkout_session_uses_correct_domain` | success_url contains `toganddogs.usmissionhero.com`, not `togsanddogs.com` |
| `test_checkout_session_respects_env_url_override` | When `STRIPE_SUCCESS_URL_TEMPLATE` is set, it's used over default |
| `test_checkout_session_cancel_url_correct_domain` | cancel_url contains `toganddogs.usmissionhero.com` |

### Existing Tests (Must Still Pass)

- All 394 backend tests must pass after changes
- No test should depend on the old `togsanddogs.com` domain

---

## 7. Deployment and Validation Sequence

| Step | Actor | Action | Risk |
|------|-------|--------|------|
| 1 | AG | Implement code fix (stripe_client.py) | None |
| 2 | AG | Update/add tests | None |
| 3 | AG | Run `py -m pytest tests/backend/ -v` — all pass | None |
| 4 | AG | Update Terraform variables.tf + main.tf | None |
| 5 | AG | Commit code + Terraform changes | None |
| 6 | AG | `terraform plan` — expect admin Lambda env var update | Low |
| 7 | Matthew | Approve `terraform apply` | Low |
| 8 | AG | `terraform apply` | Low |
| 9 | AG | Verify admin Lambda env vars are correct | None |
| 10 | AG | Run sandbox Checkout test (same as 12L) | Low |
| 11 | AG | Verify redirect goes to correct domain | None |
| 12 | AG | Verify Klarna/BNPL options are NOT shown | None |
| 13 | AG | Report results | None |

### Expected `terraform plan` Output

```
Plan: 0 to add, 1 to change, 0 to destroy.

~ aws_lambda_function.admin (environment variables updated)
  + STRIPE_SUCCESS_URL_TEMPLATE
  + STRIPE_CANCEL_URL_TEMPLATE
```

---

## 8. Sandbox Re-Validation After Patch

After deployment, repeat the 12L test flow:

1. Create payment session for test record
2. Open Checkout URL
3. **Verify:** Only card payment option shown (no Klarna/Afterpay)
4. Pay with test card `4242 4242 4242 4242`
5. **Verify:** Redirect goes to `https://toganddogs.usmissionhero.com/payment/success?...`
6. **Verify:** Page may 404 (no frontend route yet) but domain is correct
7. **Verify:** Webhook processes successfully (payment_status = paid)
8. **Verify:** No NXDOMAIN or DNS errors

---

## 9. Guardrails

| Guardrail | Enforced |
|-----------|----------|
| No live Stripe mode | ✅ Sandbox only |
| No real payment cards | ✅ Test card only |
| No secrets committed | ✅ URLs are not secrets; keys remain in .tfvars |
| No tfvars committed | ✅ .gitignore covers *.tfvars |
| No TestFlight/EAS/mobile changes | ✅ Backend + Terraform only |
| No second tenant changes | ✅ Single tenant |
| No unrelated DynamoDB mutations | ✅ Only test record |
| No production customer booking mutation | ✅ Only controlled test records |

---

## 10. Non-Goals

| ❌ Item | Reason |
|---------|--------|
| Build frontend payment success/cancel pages | Future release (12N+) |
| Add email notification on payment | Future release |
| Support multiple payment methods | Card-only for now |
| Add refund flow | Future release |
| Add payment amount auto-calculation | Admin enters manually |
| Live mode activation | Sandbox only |

---

## 11. What This Document Does NOT Authorize

- ❌ Implementing the code changes
- ❌ Running `terraform apply`
- ❌ Deploying to production
- ❌ Making DynamoDB writes
- ❌ Activating Stripe live mode
- ❌ Charging real customers
- ❌ Committing secrets
- ❌ Frontend/mobile changes
- ❌ EAS/TestFlight changes

This is a planning document only. Implementation requires separate explicit approval.
