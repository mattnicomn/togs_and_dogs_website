# Release Notes: Release 13B — Payment Workflow Hardening Before Live Mode

This release notes document details the security hardening, amount validation, and resend rate-limiting enhancements implemented for the payment workflows prior to transition to Live Mode.

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

## Validation and Test Results

### Backend Unit & Integration Tests
- **All 413 Backend Tests Passed** successfully:
  - `pytest tests/backend/test_r12g_stripe_checkout.py` passed.
  - `pytest tests/backend/test_r12t_payment_email.py` passed.
  - Full suite `pytest tests/backend` executed and passed cleanly.
- **New Tests**:
  - `test_r13b_amount_validation_extended` (bounds, NaN/Infinity, custom env limits).
  - `test_r13b_payment_email_cooldown` (60-second resend enforcement).

### Frontend Production Build
- **Build Command**: `npm run build` executed inside `web` directory.
- **Result**: Success. Vite compiled all assets successfully in 398ms.

---

## Guardrail Confirmations
- **No Live Stripe mode** or keys were wired or used.
- **No real payments** or mock payment submissions occurred.
- **No Postmark calls** or emails were sent.
- **No Terraform apply** was run (only planning was attempted, which failed cleanly due to expired AWS SSO credentials).
- **No production deployment** has occurred.
- **No Cognito, mobile, or tenant changes** were made.
- **No secrets, tokens, or credentials** were exposed.
