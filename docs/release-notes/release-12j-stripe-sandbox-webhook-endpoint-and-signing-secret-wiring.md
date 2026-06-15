# Release 12J — Stripe Sandbox Webhook Endpoint and Signing Secret Wiring

This release configures the Stripe webhook signing secret locally and deploys the secret value to the Stripe webhook Lambda function to enable secure HMAC-SHA256 signature verification.

## Summary of Changes

### 1. Configuration (Local & Ignored)
* **`infra/prod/terraform.tfvars`**: Created locally and verified as git-ignored. Added the sandbox webhook signing secret:
  ```hcl
  stripe_webhook_secret = "whsec_..."
  ```

### 2. Infrastructure Updates
* **Lambda Webhook Environment Variable**:
  * Deployed the `stripe_webhook_secret` value to the environment variables of `togs-and-dogs-prod-stripe-webhook` Lambda function under `STRIPE_WEBHOOK_SECRET`.
* **API Gateway Deployment**:
  * Re-deployed API Gateway stage resources (`module.api.aws_api_gateway_deployment.main`) to ensure full synchronization of backend routes.

---

## Safety Checklist Confirmations
* **Sandbox Only**: No live Stripe keys or production secrets have been configured. The Stripe webhook integration remains configured in sandbox/test mode.
* **No Leaks / Secrets Committed**: Checked `git status` and confirmed that `terraform.tfvars` remains untracked and successfully ignored by Git. No credentials or secrets are stored in Git history.
* **No Database / Cognito / Frontend Mutations**: Verified that all tables, Cognito User Pools, and client deployments are untouched.

---

## Verification Results

### 1. Webhook Secret Configuration Check
Inspected `togs-and-dogs-prod-stripe-webhook` Lambda configurations. The `STRIPE_WEBHOOK_SECRET` environment variable is successfully set to the valid sandbox signing secret (`whsec_...`).

### 2. Sandbox Signature Verification Check
Once the webhook secret is wired, signature checks are automatically validated for all incoming webhooks from the Stripe Dashboard. Unsigned requests continue to fail closed with `401 Unauthorized` and logs record:
`SECURITY: Stripe webhook signature verification failed: Missing stripe-signature header`
