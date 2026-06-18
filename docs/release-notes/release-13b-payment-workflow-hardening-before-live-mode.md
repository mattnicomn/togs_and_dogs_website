# Release Notes: Release 13B — Payment Workflow Hardening Before Live Mode

This release notes document details the security hardening, amount validation, and resend rate-limiting enhancements implemented and deployed for the payment workflows prior to transition to Live Mode.

## Changes Implemented

### 1. Conditional Sandbox Warning Behavior
- **Stripe Environment Resolver**: Updated the sandbox check in [service.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/notifications/service.py) to inspect both `STRIPE_ENV` and `STRIPE_ENVIRONMENT` environment variables.
- **Conditional Email Context**: If either variable is set to a value other than `sandbox` (e.g. `live`), the `sandbox` boolean resolves to `false`, automatically hiding the sandbox warning banners in checkout/billing emails sent to clients.

### 2. Backend & Frontend Amount Validation
- **Strict Parsing Helper**: Created the `validate_and_parse_amount_cents` validation helper in [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py). It ensures the payment amount is a safe, positive integer > 0 and rejects floats, booleans, strings, NaN, or None.
- **Configurable Maximum Limit**: Enforced a default maximum limit of `$10,000.00` (1,000,000 cents), configurable via the `MAX_PAYMENT_AMOUNT_CENTS` environment variable. Clear validation messages are returned to admins for invalid inputs.
- **Frontend Sync**: Implemented mirrored bounds check validations in [CareCard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/CareCard.jsx) to prevent blank inputs, non-numeric values, values <= $0.00, or values exceeding $10,000.00.

### 3. Cooldown Hardening
- **60-Second Backend Cooldown**: Implemented a 60-second minimum cooldown in [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py) using the timezone-aware `payment_email_sent_at` timestamp. This prevents operator double-click or simultaneous duplicate send attempts.
- **Hour Protection Intact**: Maintained the existing 3 emails per request per hour rate limit block.
- **120-Second Frontend Cooldown**: Added an immediate 120-second local UI lockout upon a successful payment email send in [CareCard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/CareCard.jsx) to disable the resend button and prevent accidental immediate re-clicks.

### 4. Infrastructure (Terraform)
- **Environment Alignment**: Updated the `admin` and `stripe_webhook` Lambda configurations in [main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/infra/prod/main.tf) to explicitly define `STRIPE_ENV = "sandbox"`.

---

## Deployment and Validation Results

### 1. Terraform Infrastructure Apply
- **Action**: Applied the pre-generated plan `release-13b-payment-hardening.tfplan` using Terraform v1.14.8.
- **Result**: Success. Outputs:
  - Resources: **1 added, 13 changed, 1 destroyed**.
  - `STRIPE_ENV = "sandbox"` applied to Lambda environment variables.
  - All 12 Lambda functions updated with the latest codebase package.
  - API Gateway deployment updated and stage main redeployed.

### 2. Frontend Rebuild & Deployment
- **Rebuild**: Rebuilt the production application successfully (`npm run build` in `web/` took 339ms).
- **S3 Sync**: Deployed the compiled production assets to `s3://togs-and-dogs-prod-toganddogs-hosting` using profile `usmissionhero-website-prod`.
- **CloudFront Invalidation**: Created a cache invalidation for distribution `E35L00QPA2IRCY` with invalidation ID: `IBBBXKD2H22J82N0CLLXOZ7WY0`.

### 3. Smoke Validation Results
Post-deploy smoke test was performed successfully using browser subagent execution:
- **Admin Dashboard**: Loaded successfully. 
- **CareCard Status Render**: CareCard details modal loaded correctly. Verified that the paid request `TestPet_ScenarioB` shows a green **Paid** payment status and all details are read-only (un-editable) under the "Pricing & Payment (Stripe Sandbox)" section. Screenshot saved: `paid_carecard_status_1781793642724.png`.
- **Frontend Amount Input Validation**: In an unpaid request CareCard (`TestPet_ScenarioD`), the "Amount to Charge" input validation rules successfully intercepted incorrect values and blocked link generation:
  - **Blank value**: Blocked with `"Amount is required and cannot be blank."` (screenshot: `validation_error_blank_1781793754100.png`)
  - **Negative value (`-50`)**: Blocked with `"Amount must be greater than $0.00."` (screenshot: `validation_error_negative_1781793777952.png`)
  - **Excessive value (`20000`)**: Blocked with `"Amount cannot exceed the maximum limit of $10,000.00."` (screenshot: `validation_error_large_1781793799808.png`)

---

## Guardrail Confirmations
- **No Live Stripe mode** or keys were wired or used.
- **No real payments** or mock payment submissions occurred.
- **No Postmark calls** or emails were sent.
- **No new Checkout Sessions** were generated.
- **No Cognito, mobile, or tenant changes** were made.
- **No secrets, tokens, or credentials** were exposed.
- **No app-triggered DynamoDB writes** occurred outside standard deployment tracking.
