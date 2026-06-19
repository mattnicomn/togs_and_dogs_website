# Release Notes — Release 14F — Payment Success Cancel Page and Email Copy Refinement

## Implementation Summary

This release refines client-facing copy on the payment success page, payment cancel page, and the payment link email template to clarify the billing and scheduling expectations for clients before live payments are enabled.

All changes are restricted to copy updates across the frontend components and backend notification templates. No changes were made to API routes, database models, Stripe settings, or Cognito groups.

## Copy Refinements

1. **Payment Success Page (`web/src/components/PaymentSuccess.jsx`)**:
   * **Stripe Receipt Mention**: Explicitly mentions that a confirmation receipt from Stripe has been sent to their email.
   * **Scheduling & Visit Updates**: Clarifies that the client will receive scheduling and visit updates as they are finalized.
   * **Service Guarantee Caveat**: Added a note stating that payment confirms the booking request, but visits and staff assignments are officially scheduled once confirmed by administration.
   * **Placeholder Contact Info**: Directs clients to contact `[billing/support email to be confirmed]` for any questions.
   * **Subtle Request ID Reference**: Replaced the prominent gray box containing the raw Request ID UUID with a smaller, muted `Request Reference: {requestId}` at the bottom of the card, while retaining the clean "Paid" status badge inside the card.
   * **Sensitive Stripe Details**: Ensured no sensitive Stripe session IDs, checkout secrets, or customer keys are exposed.

2. **Payment Cancel Page (`web/src/components/PaymentCancel.jsx`)**:
   * **Heading Update**: Changed the heading from "Payment Cancelled" to "Payment Not Completed" to be less alarming.
   * **Reassurance of Active Status**: Added clear reassurance that no charges were made and the client's booking request remains active.
   * **Actionable Next Steps**: Instructs the client to use the payment link from their email or contact support to request a new one.
   * **Placeholder Contact Info**: Changed the hardcoded support email to `[billing/support email to be confirmed]`.
   * **Subtle Request ID Reference**: Shortened and muted the request reference display to match the success page.

3. **Payment Link Email Template (`src/backend/common/notifications/templates.py` & `service.py`)**:
   * **Expiry Note Update**: Updated the link expiry warning to reflect Stripe Checkout's actual behavior:
     > For security, Stripe Checkout links may expire after a short period once opened. If the link no longer works, contact us and we can send a new one.
   * **Post-Payment Expectations**: Added a clear expectation block in both plaintext and HTML versions of the email:
     > After payment, you'll see a confirmation page and receive a receipt from Stripe.
   * **Sandbox Environment Warning**: Kept the sandbox/test warning conditional logic intact from Release 13B.

## Backend Infrastructure Deployment

* **Deployment Tool**: Terraform v1.14.8
* **Applied Plan File**: `release-14f-payment-copy-refinement.tfplan`
* **Plan Summary**: Applied successfully with **`0 added, 12 changed, 0 destroyed`**.
* **Impacted Lambda Handlers**: Updated in-place with the refreshed source code hash of the backend package (`backend.zip` containing the copy refined email template and service functions):
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
* **CloudFront Invalidation**: Created invalidation **`I171FMCKDXGT4SKAER593O3TJS`** for distribution `E35L00QPA2IRCY` to clear global cache.

## Production Smoke Verification Results

A browser subagent completed a comprehensive verification directly on the live production URL. All test targets passed:
1. **Success Page Render**: Checked `https://toganddogs.usmissionhero.com/booking/test-request-14f/success`. Verified the new Stripe receipt details, next-steps warning copy, support placeholder, and the subtle Request Reference display.
2. **Cancel Page Render**: Checked `https://toganddogs.usmissionhero.com/booking/test-request-14f/cancel`. Verified the title renamed to "Payment Not Completed", reassurance text, Next Steps email link guidance, support placeholder, and subtle Request Reference display.
3. **No sensitive Stripe metadata exposed**: Verified.
4. **Admin Dashboard remains fully functional**: Verified.
5. **Validation Safety**: Verified that no payment links were generated, no emails were sent, and no checkout sessions/payments were processed during validation.

## Guardrails & Verification Confirmation

* No AWS credentials or manual IAM roles were modified.
* No live Stripe keys were enabled, and `STRIPE_ENV = sandbox` remains fully enforced.
* No live Cognito users, Postmark accounts, DynamoDB application table writes, EAS builds, or second tenants were modified or touched.
