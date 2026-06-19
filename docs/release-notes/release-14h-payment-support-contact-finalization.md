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

## Backend Infrastructure Deployment

* **Deployment Tool**: Terraform v1.14.8
* **Applied Plan File**: `release-14h-support-contact-finalization.tfplan`
* **Plan Summary**: Applied successfully with **`0 added, 12 changed, 0 destroyed`**.
* **Impacted Lambda Handlers**: Updated in-place with the refreshed source code hash of the backend package (`backend.zip` containing the support email template adjustments):
  * `togs-and-dogs-prod-admin`
  * `togs-and-dogs-prod-assign`
  * `togs-and-dogs-prod-cancellation`
  * `togs-and-dogs-prod-device`
  * `togs-and-dogs-prod-google-auth`
  * `togs-and-dogs-prod-intake`
  * `togs-and-dogs-prod-job`
  * `togs-and-dogs-prod-pet`
  * `togs-and-dogs-prod-postmark-webhook`
  * `togs-and-dogs-prod-review`
  * `togs-and-dogs-prod-ses-feedback`
  * `togs-and-dogs-prod-stripe-webhook`
* **Plan Cleanup**: Verified that the temporary `.tfplan` file was deleted immediately after execution.

## Frontend Deployment

* **Build Status**: Frontend compiled successfully via Vite.
* **Target S3 Bucket**: `s3://togs-and-dogs-prod-toganddogs-hosting` (using AWS profile `usmissionhero-website-prod`).
* **S3 Sync Status**: Successfully uploaded the modified CSS and JS index chunks and deleted the obsolete index bundle.
* **CloudFront Invalidation**: Created invalidation **`IA8K63W2FQIV90U5FLOJ1U2SJJ`** for distribution `E35L00QPA2IRCY` to clear global cache.

## Production Smoke Verification Results

A browser subagent completed a comprehensive verification directly on the live production URL. All test targets passed:
1. **Success Page Render**: Checked `https://toganddogs.usmissionhero.com/booking/test-request-14h/success`. Verified the support email is now correctly updated to `support@usmissionhero.com` and old placeholders or emails are completely removed.
2. **Cancel Page Render**: Checked `https://toganddogs.usmissionhero.com/booking/test-request-14h/cancel`. Verified the support email is now correctly updated to `support@usmissionhero.com`.
3. **No sensitive Stripe metadata exposed**: Verified.
4. **Admin Dashboard remains fully functional**: Verified that the admin page loads successfully.
5. **Validation Safety**: Verified that no payment links were generated, no emails were sent, and no checkout sessions/payments were processed during validation.

## Guardrails & Verification Confirmation

* No AWS credentials or manual IAM roles were modified.
* No live Stripe keys were enabled, and `STRIPE_ENV = sandbox` remains fully enforced.
* No live Cognito users, Postmark accounts, DynamoDB application table writes, EAS builds, or second tenants were modified or touched.
