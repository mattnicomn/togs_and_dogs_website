# Release Notes: Release 12Y — End-to-End Sandbox Payment Submission Validation

This release documents the successful end-to-end sandbox payment flow validation from administrative link generation through consumer submission to backend ledger verification.

## Results & Logs

### Pre-payment Checks
* Request `c1b11afe-3cda-45c1-9ada-af91b14234ad` was confirmed in `APPROVED` and `payment_link_sent` state with active checkout session `cs_test_a1gSogQv2TumTRSZaBJ9mbXpEQjRIrSJPcS7el3N84F6cN7RQZIOtAt8lU`.
* Deployed stage `prod` of API Gateway `a022yxuiue` was verified, and the `STRIPE_WEBHOOK_SECRET` environment variable was confirmed to be active on the `togs-and-dogs-prod-stripe-webhook` Lambda function.

### Payment Submission
* Submitted exactly one sandbox payment in the Stripe Sandbox payment interface using test card credentials.
* Verified that the Checkout Session restricted payment methods to Card and Link (ACH/Direct Debit and Klarna were not visible).
* Redirection resolved successfully to the merchant callback success page:
  `https://toganddogs.usmissionhero.com/booking/c1b11afe-3cda-45c1-9ada-af91b14234ad/success?session_id=cs_test_a1gSogQv2TumTRSZaBJ9mbXpEQjRIrSJPcS7el3N84F6cN7RQZIOtAt8lU`

### Webhook & Database Updates
The Stripe webhook successfully received and processed the `checkout.session.completed` event:
* **Payment Status**: Updated from `payment_link_sent` to `paid` in DynamoDB.
* **PaymentIntent ID**: `pi_3TjUAN7vQm58ivsH0xdBF5tK` was successfully recorded.
* **Completion Timestamp**: `2026-06-18T00:50:52Z` (UTC) was saved to `payment_completed_at`.
* **Updated By**: Marked as `system:stripe_webhook` indicating automated processing.

### Billing Ledger Integration
A transaction record was successfully committed to the database under partition `BILLING#tog_and_dogs`:
* **Event SK**: `EVENT#evt_1TjUAO7vQm58ivsH4CJDNo6B`
* **Event Type**: `checkout.session.completed`
* **Processing Status**: `completed`
* **Amount Total**: `100` (cents)

---

## Guardrails Verification
* Only one sandbox transaction was submitted.
* No live mode credentials or real cards were utilized.
* No additional payment email was dispatched.
* No replacement Checkout Sessions were created.
* No Terraform, Cognito, frontend/mobile, or second-tenant modifications occurred.
* No secrets, credentials, or tfvars parameters were exposed.
