# Release Notes — Release 14H — Payment Support Contact Finalization

## Implementation Summary

This release replaces the payment-related placeholder and old support email references with the confirmed monitored business support email address:
`support@usmissionhero.com`

This ensures that clients have a direct, correct way to contact support if they have questions about their payment or experience issues during checkout.

## Replacements Made

1. **Payment Success Page (`web/src/components/PaymentSuccess.jsx`)**:
   * Replaced the placeholder `[billing/support email to be confirmed]` with the verified contact link `support@usmissionhero.com`.

2. **Payment Cancel Page (`web/src/components/PaymentCancel.jsx`)**:
   * Replaced the placeholder `[billing/support email to be confirmed]` with the verified contact link `support@usmissionhero.com`.

3. **Payment Link Email Template (`src/backend/common/notifications/templates.py`)**:
   * Updated the default/fallback business email inside the `payment_link_email` template to use `support@usmissionhero.com` instead of the old `support@toganddogs.com`.

4. **Draft Payment Policy (`docs/policies/payment-terms-refund-cancellation-draft.md`)**:
   * Replaced all billing/support email decision placeholders (e.g. `[PENDING MATTHEW: billing/support email to be confirmed]`) with `support@usmissionhero.com`.

## Validation Outcomes

* **Frontend Build**: The frontend production build (`npm run build` in the `web` folder) compiled successfully:
  ```
  vite v8.0.8 building client environment for production...
  transforming...✓ 96 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                         1.47 kB │ gzip:   0.67 kB
  dist/assets/usmh-logo-CrRnxp7-.png  2,583.40 kB
  dist/assets/index-Dhj_nyZO.css         59.93 kB │ gzip:  11.05 kB
  dist/assets/index-CmFmTpMG.js         898.04 kB │ gzip: 264.77 kB
  ✓ built in 336ms
  ```
* **Backend Tests**: The payment email unit test suite (`pytest tests/backend/test_r12t_payment_email.py`) passed successfully (12/12 tests passing).
* **Placeholder Auditing**: Verified that all active code files are free from billing/support email placeholders. Remaining `[PENDING MATTHEW]` decision tags in the draft policy document are reserved for non-email business policies (such as effective dates and payment options).

## Deployment Instructions

To promote these changes to production, the following steps are required in a future deployment cycle:
1. **Backend Deployment**: Run a Terraform plan/apply to package the updated backend code into `backend.zip` and deploy the updated Lambdas in-place.
2. **Frontend Deployment**: Sync the compiled `dist/` directory to the hosting S3 bucket (`s3://togs-and-dogs-prod-toganddogs-hosting`) and perform a CloudFront invalidation for `E35L00QPA2IRCY`.

## Guardrails & Verification Confirmation

* No AWS infrastructure modifications or Terraform apply operations occurred.
* No Stripe Dashboard settings, API keys, or checkout sessions were modified or used.
* No Postmark email transmissions, SMS messages, DynamoDB writes, Cognito updates, or mobile builds occurred.
