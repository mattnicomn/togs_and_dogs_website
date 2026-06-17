# Release 12T — Backend Payment Link Email Endpoint and Notification Ledger Closeout Note

## Release Information
* **Release Name**: `12T — Backend Payment Link Email Endpoint and Notification Ledger`
* **Implementation Commit**: `777d383`
* **Targeted Tests**: `11 passed` (`tests/backend/test_r12t_payment_email.py`)
* **Full Backend Suite**: `411 passed` (`tests/backend`)
* **Terraform Apply Result**: Successful (`8 added, 13 changed, 1 destroyed`)

---

## Endpoint Behavior & Integration

### New Endpoint
* **Path**: `POST /admin/requests/{requestId}/send-payment-email`
* **Authentication**: Cognito User Pools protected (`COGNITO_USER_POOLS` authorizer).
* **Authorization**: Restricts access to `owner` and `admin` roles only.
* **Scope**: Tenant-scoped validation. Enforces that request `company_id` matches user's `company_id` claims.

### Security Guards & Validations
The endpoint requires that:
1. The request exists in DynamoDB.
2. The request is not yet paid, refunded, or waived (otherwise blocks with 409 Conflict).
3. The request has an active payment session, containing `stripe_payment_url` and `stripe_checkout_session_id` (otherwise blocks with 400 Bad Request).
4. The request has a valid client email (otherwise blocks with 400 Bad Request).
5. The request does not exceed the rate limit of **3 sends per request per hour** (otherwise blocks with 429 Too Many Requests).

---

### Postmark / Template / Ledger Approach
* **Email Rendering**: Built localized templates in `templates.py` containing text and HTML bodies. Includes a conditional Stripe sandbox warning banner when `STRIPE_ENV == 'sandbox'`.
* **Dispatch Helper**: Uses the offline `notify_event()` helper routing the `PAYMENT_LINK_EMAIL` event to dispatch.
* **Notification Ledger**: Records all dispatch attempts. Saves detailed audit records containing `client_id`, `stripe_checkout_session_id`, and `stripe_payment_url` fields to the DynamoDB notification ledger.
* **Rate Limiting**: Checks `StatusIndex` looking for `status = 'sent'` payment email notification ledger entries in the past hour.

---

## Verification & Validation
* **Unauthenticated Smoke Validation**: Verified via curl that unauthenticated requests to the endpoint are successfully intercepted by API Gateway, producing a `403 Forbidden` response:
  ```json
  {"message":"Missing Authentication Token"}
  ```
* **Offline Mock Verification**: Verified through offline pytest suites that rate-limiter, database updates, and Postmark client mocks run successfully without hitting the real network.

---

## Guardrails Compliance
* **No real emails** or SMS notifications were sent.
* **No Stripe/Checkout API calls** or payments were made.
* **No production DynamoDB writes** occurred (except deployment stage metadata managed by Terraform).
* **No frontend, mobile, EAS, or TestFlight deployments** were executed.
* **No Cognito changes** were made.
* **No second tenant changes** were made.
* **No secrets or credentials** were printed or committed.
