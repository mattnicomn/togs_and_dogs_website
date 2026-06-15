# Release 12H: AWS Secrets and API Gateway Stripe Webhook Route Plan

**Status:** Planning
**Priority:** High (required before sandbox end-to-end testing)
**Risk to Production:** Medium (adds API Gateway routes and Lambda config)
**Terraform Required:** Yes
**Code Changes:** None (code exists from 12D/12G)
**Stripe Changes:** Webhook endpoint creation (after route exists)
**Scope:** Plan Terraform changes for secrets, API routes, Lambda env vars, and IAM

---

## 1. Existing Infrastructure Summary

### Current Architecture (from `infra/prod/main.tf`)

| Component | Pattern |
|-----------|---------|
| API Gateway | REST API (`aws_api_gateway_rest_api.main`) |
| Authorizer | Cognito User Pools (`aws_api_gateway_authorizer.cognito`) |
| Lambda deployment | Single `archive_file` from `src/backend`, shared across all functions |
| Lambda functions | One per handler (intake, admin, review, assign, job, google_auth, pet, cancellation, device, ses_feedback, postmark_webhook) |
| Secrets module | `modules/secrets` (google creds, google tokens, postmark token) |
| IAM module | `modules/iam` (shared Lambda role with DynamoDB, SNS, SFN, Secrets access) |
| Webhook precedent | Postmark webhook: dedicated Lambda, NONE auth, header-based secret verification |

### Key Patterns to Follow

- **Postmark webhook pattern:** Dedicated Lambda function with `NONE` authorization, secret passed as Lambda env var
- **Lambda packaging:** All handlers share same `backend.zip` from `src/backend`
- **IAM:** Shared Lambda role (`module.iam.lambda_role_arn`) — needs new Secrets Manager permissions
- **API module:** Routes defined in `modules/api/main.tf` — new routes added here

---

## 2. New API Gateway Routes

### Route 1: POST /webhooks/stripe

| Field | Value |
|-------|-------|
| Path | `/webhooks/stripe` |
| Method | POST |
| Authorization | NONE (Stripe signature verification in handler) |
| Lambda | New dedicated `stripe-webhook` Lambda function |
| Handler | `handlers.stripe_webhook_handler.handler` |
| Raw body | Required (API Gateway proxy preserves body in `event['body']`) |

### Route 2: POST /admin/payment-session

| Field | Value |
|-------|-------|
| Path | `/admin/payment-session` |
| Method | POST |
| Authorization | COGNITO_USER_POOLS |
| Lambda | Existing `admin` Lambda (handler routes internally based on path) |
| Body | `{"request_id": "...", "amount_cents": 7500, "description": "..."}` |

**Alternative:** `/admin/requests/{request_id}/payment-session` — requires a new path resource under `admin_requests`. Simpler to use flat `/admin/payment-session` with `request_id` in body, matching existing admin handler pattern.

**Recommendation:** Use `POST /admin/payment-session` routed to the admin Lambda. The admin handler already routes by method+path internally. This avoids creating additional API Gateway path resources.

---

## 3. New Lambda Function: Stripe Webhook

### Resource Definition (Proposed)

```hcl
resource "aws_lambda_function" "stripe_webhook" {
  filename         = data.archive_file.backend_zip.output_path
  function_name    = "${local.name_prefix}-stripe-webhook"
  role             = module.iam.lambda_role_arn
  handler          = "handlers.stripe_webhook_handler.handler"
  source_code_hash = data.archive_file.backend_zip.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      DATA_TABLE_NAME                    = module.data.table_name
      STRIPE_WEBHOOK_SECRET              = var.stripe_webhook_secret
      STRIPE_ENVIRONMENT                 = "sandbox"
      STRIPE_PRICE_STARTER_MONTHLY       = var.stripe_price_starter_monthly
      STRIPE_PRICE_PROFESSIONAL_MONTHLY  = var.stripe_price_professional_monthly
      STRIPE_PRICE_PREMIUM_MONTHLY       = var.stripe_price_premium_monthly
      DEFAULT_COMPANY_ID                 = "tog_and_dogs"
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "api_stripe_webhook" {
  statement_id  = "AllowAPIGatewayInvokeStripeWebhook"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stripe_webhook.function_name
  principal     = "apigateway.amazonaws.com"
}
```

### Why Dedicated Lambda (Not Existing Admin Lambda)

- Webhook has NONE auth — must not share a Lambda that also handles Cognito-authenticated routes
- Follows postmark_webhook pattern (dedicated function, unauthenticated route)
- Separate memory/timeout tuning (webhooks should be fast, low memory)
- Cleaner CloudWatch log separation for billing events

---

## 4. Secret Management Strategy

### Decision: Lambda Environment Variables (Not Secrets Manager)

**Rationale:** The project already uses this pattern for the Postmark webhook:
```hcl
POSTMARK_WEBHOOK_SECRET = var.postmark_webhook_secret
```

The secret is passed via `terraform.tfvars` (not committed) → Terraform variable → Lambda env var. This avoids:
- Additional Secrets Manager cost ($0.40/secret/month)
- Additional IAM complexity
- Additional Lambda cold-start latency (Secrets Manager API call)

**For Stripe, follow the same pattern:**

| Secret | Terraform Variable | Lambda Env Var |
|--------|-------------------|----------------|
| Webhook signing secret | `var.stripe_webhook_secret` | `STRIPE_WEBHOOK_SECRET` |
| Stripe secret key | `var.stripe_secret_key` | `STRIPE_SECRET_KEY` |

### Proposed Terraform Variables (in `variables.tf`)

```hcl
# --- Release 12H: Stripe Billing ---

variable "stripe_webhook_secret" {
  type        = string
  description = "Stripe webhook signing secret for verifying webhook requests. Set via terraform.tfvars or TF_VAR."
  sensitive   = true
  default     = ""
}

variable "stripe_secret_key" {
  type        = string
  description = "Stripe secret API key for creating Checkout Sessions. Set via terraform.tfvars or TF_VAR."
  sensitive   = true
  default     = ""
}

variable "stripe_price_starter_monthly" {
  type        = string
  description = "Stripe Price ID for Starter Monthly plan."
  default     = ""
}

variable "stripe_price_professional_monthly" {
  type        = string
  description = "Stripe Price ID for Professional Monthly plan."
  default     = ""
}

variable "stripe_price_premium_monthly" {
  type        = string
  description = "Stripe Price ID for Premium Monthly plan."
  default     = ""
}
```

### Where Secrets Are Stored

| Location | Contains | Committed to Git? |
|----------|----------|-------------------|
| `infra/prod/terraform.tfvars` | Actual secret values | ❌ NO (in .gitignore) |
| `infra/prod/variables.tf` | Variable declarations (no values) | ✅ Yes |
| Lambda env vars | Runtime values | ❌ Not in code |
| Stripe Dashboard | Source of truth | N/A |

### Verify .gitignore Coverage

Confirm `*.tfvars` or `terraform.tfvars` is in `.gitignore`:
```
*.tfvars
*.tfvars.json
```

---

## 5. Lambda Environment Variables (Full List)

### Stripe Webhook Lambda

| Variable | Source | Purpose |
|----------|--------|---------|
| `DATA_TABLE_NAME` | `module.data.table_name` | DynamoDB table |
| `STRIPE_WEBHOOK_SECRET` | `var.stripe_webhook_secret` | Signature verification |
| `STRIPE_ENVIRONMENT` | `"sandbox"` (hardcoded for now) | Prevent cross-env confusion |
| `STRIPE_PRICE_STARTER_MONTHLY` | `var.stripe_price_starter_monthly` | Price-to-tier resolution |
| `STRIPE_PRICE_PROFESSIONAL_MONTHLY` | `var.stripe_price_professional_monthly` | Price-to-tier resolution |
| `STRIPE_PRICE_PREMIUM_MONTHLY` | `var.stripe_price_premium_monthly` | Price-to-tier resolution |
| `DEFAULT_COMPANY_ID` | `"tog_and_dogs"` | Fallback company |

### Admin Lambda (Additional Variables for Payment Session)

| Variable | Source | Purpose |
|----------|--------|---------|
| `STRIPE_SECRET_KEY` | `var.stripe_secret_key` | Checkout Session creation API |
| `STRIPE_PRICE_STARTER_MONTHLY` | `var.stripe_price_starter_monthly` | Price reference |
| `STRIPE_PRICE_PROFESSIONAL_MONTHLY` | `var.stripe_price_professional_monthly` | Price reference |
| `STRIPE_PRICE_PREMIUM_MONTHLY` | `var.stripe_price_premium_monthly` | Price reference |
| `STRIPE_ENVIRONMENT` | `"sandbox"` | Metadata environment field |

---

## 6. IAM Permissions

### Current State

The shared Lambda role (`module.iam.lambda_role_arn`) already has:
- DynamoDB read/write on `togs-and-dogs-prod-data`
- SNS publish
- Step Functions start
- Secrets Manager read (for Google/Postmark secrets)
- Cognito admin actions

### Additional Permissions Needed

**None for this approach.** Since Stripe secrets are passed via Lambda env vars (not Secrets Manager), no new IAM permissions are needed. The existing DynamoDB permissions cover BILLING# and TENANT# key patterns.

If we later switch to Secrets Manager:
```hcl
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod-stripe-*"
}
```

---

## 7. API Gateway Route Configuration (in `modules/api/main.tf`)

### Webhook Route

```hcl
# --- Release 12H: Stripe Webhook ---

resource "aws_api_gateway_resource" "webhooks" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "webhooks"
}

resource "aws_api_gateway_resource" "webhooks_stripe" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.webhooks.id
  path_part   = "stripe"
}

resource "aws_api_gateway_method" "post_webhooks_stripe" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.webhooks_stripe.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "stripe_webhook_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.webhooks_stripe.id
  http_method = aws_api_gateway_method.post_webhooks_stripe.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.stripe_webhook_handler_invoke_arn
}
```

### Payment Session Route

```hcl
# --- Release 12H: Admin Payment Session ---

resource "aws_api_gateway_resource" "admin_payment_session" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "payment-session"
}

resource "aws_api_gateway_method" "post_admin_payment_session" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_payment_session.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_payment_session_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_payment_session.id
  http_method = aws_api_gateway_method.post_admin_payment_session.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}
```

### API Module Variable Addition

```hcl
# In modules/api/variables.tf:
variable "stripe_webhook_handler_invoke_arn" {
  type        = string
  description = "Invoke ARN for the Stripe webhook handler Lambda."
}
```

### Note on `/webhooks` Path

A `/webhooks` resource may already exist (for `/webhooks/postmark`). Check before creating — if it exists, reuse it. If the Postmark webhook uses a different path structure (e.g., root-level `/postmark-webhook`), then `/webhooks` is new.

**From the current API module:** The postmark webhook handler is passed as `postmark_webhook_handler_invoke_arn` but the route path needs verification. If `/webhooks/postmark` already exists, reuse the parent `/webhooks` resource.

---

## 8. Terraform Files to Change

| File | Change |
|------|--------|
| `infra/prod/variables.tf` | Add Stripe variable declarations |
| `infra/prod/main.tf` | Add `stripe_webhook` Lambda function resource + permission |
| `infra/prod/main.tf` | Pass `stripe_webhook_handler_invoke_arn` to API module |
| `infra/prod/main.tf` | Add Stripe env vars to admin Lambda |
| `modules/api/variables.tf` | Add `stripe_webhook_handler_invoke_arn` variable |
| `modules/api/main.tf` | Add webhook route + payment-session route |
| `infra/prod/terraform.tfvars` | Add actual Stripe secret values (NOT committed) |
| `.gitignore` | Verify `*.tfvars` is excluded |

---

## 9. Stripe Dashboard Webhook Setup (After Route Exists)

Once `terraform apply` creates the API Gateway route:

### Get Webhook URL

```
https://{api-id}.execute-api.us-east-1.amazonaws.com/{stage}/webhooks/stripe
```

### Configure in Stripe Dashboard

1. Navigate to: Developers → Webhooks → Add endpoint
2. Endpoint URL: `https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/webhooks/stripe`
3. Events to listen for:
   - `checkout.session.completed`
   - `checkout.session.expired`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Mode: **Test** (sandbox only)
5. Record signing secret (`whsec_...`) → store in `terraform.tfvars`

---

## 10. Safe Deployment Sequence

| Step | Action | Risk |
|------|--------|------|
| 1 | Add variables to `variables.tf` | None (no values) |
| 2 | Add Stripe webhook Lambda to `main.tf` | Low (new resource) |
| 3 | Add routes to API module | Low (new resources) |
| 4 | Add `terraform.tfvars` values locally (empty initially) | None |
| 5 | `terraform plan` — verify only additions, no modifications to existing resources | None |
| 6 | `terraform apply` — requires Matthew's approval | Medium |
| 7 | Verify API Gateway route responds (curl /webhooks/stripe → 401 unsigned) | None |
| 8 | Configure Stripe webhook in dashboard with new URL | Low |
| 9 | Update `terraform.tfvars` with real webhook signing secret | None |
| 10 | `terraform apply` again to set Lambda env var | Low |
| 11 | Test with Stripe CLI: `stripe trigger checkout.session.completed` | None |

### Expected `terraform plan` Output

```
Plan: 5 to add, 1 to change, 0 to destroy.

+ aws_lambda_function.stripe_webhook
+ aws_lambda_permission.api_stripe_webhook
+ aws_api_gateway_resource.webhooks_stripe (or nested)
+ aws_api_gateway_method.post_webhooks_stripe
+ aws_api_gateway_integration.stripe_webhook_lambda
~ aws_lambda_function.admin (env vars added)
```

---

## 11. Validation Strategy

### Pre-Apply

```powershell
# Terraform validate
terraform validate

# Terraform plan (review before apply)
terraform plan -out=release12h-stripe-webhook-route.tfplan
```

### Post-Apply

```powershell
# Verify API route exists
curl -X POST https://{api-url}/webhooks/stripe -d '{}' -H "Content-Type: application/json"
# Expected: 401 (invalid signature — correct behavior)

# Verify Lambda env vars
aws lambda get-function-configuration --function-name togs-and-dogs-prod-stripe-webhook --profile usmissionhero-website-prod --query "Environment.Variables"

# Test with Stripe CLI (after webhook endpoint configured)
stripe listen --forward-to https://{api-url}/webhooks/stripe
stripe trigger checkout.session.completed
```

---

## 12. Rollback Strategy

If issues arise after `terraform apply`:

| Action | Command | Effect |
|--------|---------|--------|
| Remove API route | Remove from `.tf`, re-apply | Route disappears, Stripe webhooks 404 |
| Remove Lambda | Remove from `.tf`, re-apply | Function deleted |
| Remove env vars from admin Lambda | Remove from `.tf`, re-apply | Payment session creation fails gracefully |
| Disable Stripe webhook | Toggle off in Stripe Dashboard | Events stop firing |
| Revert full release | `git revert` + `terraform apply` | All 12H resources removed |

**No data loss risk:** This release only adds infrastructure routes. No data is written during setup.

---

## 13. Recommended Implementation Release

**12I — AWS Secrets and API Gateway Stripe Route Implementation**

Scope:
- Execute the Terraform changes documented above
- Verify API Gateway route responds
- Configure Stripe Dashboard webhook endpoint (sandbox)
- Update `terraform.tfvars` with signing secret
- Run end-to-end sandbox webhook test
- Requires Matthew's explicit `terraform apply` approval

Prerequisites:
- 12E manual Stripe setup complete (product/prices exist)
- Stripe webhook signing secret available
- Stripe secret key available
- Matthew approves Terraform changes

---

## 14. What This Document Does NOT Authorize

- ❌ Modifying Terraform files
- ❌ Running `terraform plan` or `terraform apply`
- ❌ Creating AWS resources
- ❌ Storing secrets in any system
- ❌ Creating Stripe webhook endpoints
- ❌ Deploying Lambda code
- ❌ Modifying DynamoDB
- ❌ Modifying Cognito/Postmark/Google Calendar
- ❌ Going live with Stripe
- ❌ Charging customers
- ❌ EAS/TestFlight changes
- ❌ Any code changes

This is a planning document only. Infrastructure implementation requires separate explicit approval (Release 12I).
