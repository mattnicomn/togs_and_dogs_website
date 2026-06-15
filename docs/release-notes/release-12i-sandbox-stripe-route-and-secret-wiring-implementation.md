# Release 12I — Sandbox Stripe Route and Secret Wiring Implementation

This release deploys the AWS infrastructure and API Gateway routes supporting the Togs & Dogs Stripe checkout session creation and Stripe webhook processing in sandbox/test mode.

## Summary of Changes

### 1. Infrastructure (Terraform)
* **API Gateway Routing**:
  * Exposed a public, unauthenticated webhook endpoint: `POST /webhooks/stripe`.
  * Exposed a Cognito-authorized payment session creation endpoint: `POST /admin/requests/{requestId}/payment-session` (with CORS configuration for browser integration).
* **Lambda Orchestration**:
  * Provisioned a new dedicated `togs-and-dogs-prod-stripe-webhook` Lambda function mapped to `handlers.stripe_webhook_handler.handler`.
  * Wired Stripe environment variables (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_ENVIRONMENT`, price IDs, and success/cancel URLs) into both the existing `admin` Lambda and the new `stripe_webhook` Lambda.
  * Replaced the API Gateway deployment resource to trigger routing deployment.
* **Shared Backend Code Archive**:
  * All existing Lambda functions were updated in-place to use the new `backend.zip` code archive containing Stripe client integration code from Release 12G.

### 2. Git Security Policy
* **`.gitignore`** was updated to explicitly exclude any local `*.tfvars` or `*.tfvars.json` files to prevent credentials/secrets from being committed.

---

## Safety Checklist Confirmations
* **Sandbox Only**: All Stripe configurations are hardcoded to `sandbox` mode. No live Stripe API keys or credentials were used or committed.
* **No Database Mutations**: The DynamoDB tables, schemas, and historical records remain unchanged (no-op).
* **Cognito Unaffected**: The Cognito User Pool configuration and user metadata remain unchanged (no-op).
* **Fail-Closed Verification**:
  * `POST /webhooks/stripe` fails with `401 Unauthorized` (Invalid signature error) when called without a valid `stripe-signature` header.
  * `POST /admin/requests/{requestId}/payment-session` is blocked by Cognito Authorizer when called unauthenticated.

---

## Verification Results

### 1. Backend Pytest Suite
```powershell
py -m pytest tests/backend/ -v
```
* **Result**: **`394 / 394` unit tests passed successfully**.

### 2. Regression Smoke Validation (Real Production Database Invocation)
Executed all core API Gateway regression checks (requests list, request details, client bookings, staff schedule, and pet counters) using Cognito claims context:
* **Result**: **All 8 regression checks passed successfully**.

### 3. Webhook Execution Verification (CloudWatch Logs)
Attempted an unsigned POST request to the live webhook endpoint. The invocation was captured and verified in `/aws/lambda/togs-and-dogs-prod-stripe-webhook`:
* **Log entry**: `SECURITY: Stripe webhook signature verification failed: Missing stripe-signature header`
* **Status**: Clean failure, no crashes or runtime exceptions.
