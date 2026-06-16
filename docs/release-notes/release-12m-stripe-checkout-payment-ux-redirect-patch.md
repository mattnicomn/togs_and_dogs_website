# Release 12M — Stripe Checkout Payment UX and Redirect Patch Closeout Notes

This release resolves the checkout redirect domain issue, enforces card-only payments, and reconciles Terraform variables on the production workloads.

## Key Fixes Deployed
1. **Fallback Domain Correction**: Changed the fallback domain for the success and cancel redirect URLs from `togsanddogs.com` to `https://toganddogs.usmissionhero.com`.
2. **Card-Only Checkout Enforcement**: Updated the Stripe Checkout Session payload to include `payment_method_types[0]=card`. This disables dynamic payment methods (like Klarna) for booking payments, ensuring only credit/debit card entries are accepted.
3. **Terraform Variable Reconciliation**: Reconciled the administrative environment variables (`STRIPE_SUCCESS_URL_TEMPLATE` and `STRIPE_CANCEL_URL_TEMPLATE`) in Terraform configuration files to match the updated fallback URLs, successfully deploying them to the `admin` Lambda function.

---

## Technical Details

### Code Integration
* **Commit**: `f99b313`
* **Changes**:
  * [stripe_client.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/stripe_client.py): Modified default URL fallbacks and added card constraint to `payload`.
  * [variables.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/infra/prod/variables.tf): Defined fallback defaults for success/cancel templates.
  * [test_r12g_stripe_checkout.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r12g_stripe_checkout.py): Added direct client tests verifying card payload constraints and domain matches.

### Test Verification
* **Targeted Stripe Checkout Tests**: `12 passed`
  * Command: `py -m pytest tests/backend/test_r12g_stripe_checkout.py -v`
* **Full Backend Suite**: `396 passed`
  * Command: `py -m pytest tests/backend/ -v`

### Infrastructure Verification (Terraform Apply)
* **Execution Plan File**: `release-12m-stripe-checkout-url-card-only.tfplan` (deleted post-apply).
* **Apply Output**: `0 added, 12 changed, 0 destroyed` (Lambdas updated in-place, `admin` Lambda environment reconciled successfully).
* **Configuration Check**: Verified the AWS Lambda environment for the `admin` function using AWS CLI:
  * `STRIPE_SUCCESS_URL_TEMPLATE` -> `"https://toganddogs.usmissionhero.com/booking/{request_id}/success?session_id={{CHECKOUT_SESSION_ID}}"`
  * `STRIPE_CANCEL_URL_TEMPLATE`  -> `"https://toganddogs.usmissionhero.com/booking/{request_id}/cancel"`

---

## Guardrails Compliance
* **No Live Stripe Mode**: Sandbox environment only.
* **No Real Charges / Cards**: No live payment methods or test cards were processed.
* **No Additional Checkout Sessions**: Checked that no extra Stripe Checkout Sessions were requested.
* **No Unrelated mutations**: No DynamoDB mutations outside of Terraform updates.
* **No Cognito Changes**: Cognito configurations were kept completely intact.
* **No Frontend/Mobile Deployments**: Verified no build actions occurred on frontend/mobile branches.
* **No Secrets Committed**: Validated that `terraform.tfvars` remains completely local and git-ignored.
