# Release 12J: Stripe Sandbox Webhook Endpoint and Signing Secret Wiring Checklist

**Status:** Awaiting Matthew's Manual Setup
**Type:** Manual setup checklist (docs only)
**Risk to Production:** None (sandbox only)
**Terraform Required:** Yes (env var update only — after Matthew provides signing secret)
**Code Changes:** None
**Scope:** Configure Stripe sandbox webhook endpoint, wire signing secret into Lambda

---

## 1. Prerequisites

| Prerequisite | Status |
|-------------|--------|
| 12I AWS route deployment complete | ✅ `0c3797f` |
| Webhook route live: POST /webhooks/stripe | ✅ Returns 401 on unsigned request |
| Payment-session route live: POST /admin/payment-session | ✅ Cognito-gated |
| Stripe account exists (sandbox mode) | ✅ mbn@usmissionhero.com |
| Test product/prices created | ✅ (from 12E) |
| No live Stripe mode activated | ✅ |

---

## 2. Manual Checklist for Matthew

### Step 1: Confirm Sandbox Mode

- [ ] Open Stripe Dashboard: https://dashboard.stripe.com
- [ ] Confirm orange **"TEST"** banner is visible in the header
- [ ] If not in test mode, toggle to test mode before proceeding

### Step 2: Create Sandbox Webhook Endpoint

- [ ] Navigate to: **Developers → Webhooks → Add endpoint**
- [ ] Endpoint URL: `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/webhooks/stripe`
- [ ] Description (optional): "Togs & Dogs sandbox webhook - booking payments"

### Step 3: Select Events to Listen For

**Required events (booking payment flow):**
- [ ] `checkout.session.completed`
- [ ] `checkout.session.expired`

**Optional events (subscription billing — existing 12D handler supports these):**
- [ ] `customer.subscription.created`
- [ ] `customer.subscription.updated`
- [ ] `customer.subscription.deleted`
- [ ] `invoice.payment_succeeded`
- [ ] `invoice.payment_failed`

**Decision:** Include all events above if convenient. The handler already routes unknown events to a safe "ignored" path, so extra events are harmless.

### Step 4: Save and Record Signing Secret

- [ ] Click **"Add endpoint"** to save
- [ ] Stripe shows the webhook signing secret: `whsec_...`
- [ ] **Copy the signing secret immediately** (it's only shown once, or accessible via "Reveal" later)
- [ ] Store securely in a password manager or secure local note

⚠️ **DO NOT** paste the signing secret into any committed file, chat message, or shared document.

### Step 5: Provide Signing Secret for Terraform

After recording the signing secret:
- [ ] Add it to the local (ignored) `infra/prod/terraform.tfvars` file:
  ```
  stripe_webhook_secret = "whsec_XXXXXXXXXXXXXXXXXXXXXX"
  ```
- [ ] Confirm `terraform.tfvars` is in `.gitignore` (it should already be)
- [ ] Do NOT commit this file

### Step 6: Confirm What Was NOT Done

- [ ] Live mode was NOT activated
- [ ] No live webhook endpoint was created
- [ ] No real customers or charges exist
- [ ] No signing secret was committed to the repository
- [ ] No `terraform apply` was run yet

---

## 3. AG Implementation Steps (After Matthew Completes Step 1–5)

Once Matthew provides confirmation that the sandbox webhook endpoint exists and the signing secret is in `terraform.tfvars`:

### Step A: Terraform Plan

```powershell
C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe plan -out=release12j-webhook-secret.tfplan
```

**Expected output:**
- 0 to add, 1 to change, 0 to destroy
- Change: `aws_lambda_function.stripe_webhook` (environment variable `STRIPE_WEBHOOK_SECRET` updated from empty to real value)

**If plan shows unexpected changes:** STOP and report to Matthew.

### Step B: Terraform Apply (Requires Matthew's Approval)

```powershell
C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe apply release12j-webhook-secret.tfplan
```

### Step C: Verify Lambda Environment Variable

```powershell
aws lambda get-function-configuration --function-name togs-and-dogs-prod-stripe-webhook --profile usmissionhero-website-prod --query "Environment.Variables.STRIPE_WEBHOOK_SECRET" --output text
```

**Expected:** Returns a non-empty string (masked — do not log full value). Confirm it starts with `whsec_`.

### Step D: Sandbox Webhook Test

**Option 1: Stripe Dashboard Test Event**
1. In Stripe Dashboard → Webhooks → select the sandbox endpoint
2. Click **"Send test webhook"**
3. Select `checkout.session.completed`
4. Click **"Send test webhook"**

**Option 2: Stripe CLI (if installed)**
```powershell
stripe trigger checkout.session.completed
```

### Step E: Verify CloudWatch Logs

```powershell
aws logs filter-log-events --log-group-name /aws/lambda/togs-and-dogs-prod-stripe-webhook --profile usmissionhero-website-prod --start-time <unix_ms> --filter-pattern "STRIPE_WEBHOOK"
```

**Expected log patterns:**
- `STRIPE_WEBHOOK_RECEIVED: type=checkout.session.completed, id=evt_...` → signature verified, event parsed
- OR `SECURITY: Stripe webhook signature verification failed` → if test event doesn't include proper signing (Dashboard test events may not sign correctly — this is acceptable)

### Step F: Validation Checklist

| Check | Expected | Result |
|-------|----------|--------|
| Stripe Dashboard shows endpoint as "Active" | ✅ | ___ |
| Endpoint URL matches our API Gateway | ✅ | ___ |
| Events list includes checkout.session.completed | ✅ | ___ |
| Lambda env var STRIPE_WEBHOOK_SECRET is non-empty | ✅ | ___ |
| Unsigned request still returns 401 | ✅ | ___ |
| Signed test event processes or logs correctly | ✅ | ___ |
| CloudWatch shows no ERROR-level exceptions | ✅ | ___ |
| No live mode charges or customers | ✅ | ___ |

---

## 4. Setup Results (Fill in After Completing)

| Item | Result |
|------|--------|
| Stripe Dashboard in test mode | ___ yes / no |
| Webhook endpoint created | ___ yes / no |
| Endpoint URL correct | ___ yes / no |
| Events subscribed | ___ list |
| Signing secret recorded securely | ___ yes / no |
| Signing secret added to terraform.tfvars | ___ yes / no |
| terraform.tfvars NOT committed | ___ yes / no |
| Terraform plan shows expected change | ___ yes / no |
| Terraform apply executed | ___ yes / no |
| Lambda env var confirmed | ___ yes / no |
| Test webhook sent | ___ yes / no |
| Test result | ___ success / expected failure / error |
| Live mode touched | ___ no |
| Real charges made | ___ no |

---

## 5. Troubleshooting

### Webhook endpoint shows "Disabled" in Stripe

- Check that the URL is correct (no trailing slash)
- Confirm API Gateway stage is `prod`
- Ensure the endpoint was created in TEST mode, not live

### Test webhook returns error in Stripe Dashboard

- "Connection failed" → API Gateway route may not be deployed; verify with `curl`
- "Timed out" → Lambda cold start may exceed Stripe's timeout; check Lambda timeout setting (should be 30s)
- "Invalid response" → Lambda may be returning non-JSON; check CloudWatch logs

### Lambda shows "SECURITY: Invalid signature"

- **For Dashboard "Send test webhook" button:** This is expected — Stripe's test button may not sign the payload with the endpoint's signing secret
- **For real events triggered by test checkout:** This indicates a secret mismatch — verify `terraform.tfvars` value matches Stripe Dashboard "Reveal signing secret"

### No CloudWatch logs appearing

- Verify Lambda function name: `togs-and-dogs-prod-stripe-webhook`
- Check that the API Gateway integration points to the correct Lambda ARN
- Confirm Lambda permission `AllowAPIGatewayInvokeStripeWebhook` exists

---

## 6. What This Document Does NOT Authorize

- ❌ Running `terraform apply` (separate approval needed)
- ❌ Creating live Stripe webhook endpoints
- ❌ Activating live Stripe mode
- ❌ Charging real customers
- ❌ Committing secrets
- ❌ Modifying code
- ❌ DynamoDB writes
- ❌ Cognito/Postmark/Google Calendar changes
- ❌ Frontend/mobile/EAS/TestFlight changes
- ❌ Creating a second tenant

This is a setup checklist. Terraform apply and sandbox testing require separate explicit approval.

---

## 7. Recommended Next Release

**12K — Sandbox End-to-End Checkout and Webhook Validation**

After 12J is complete (webhook wired, signing secret active):
- Create a test Checkout Session via API or Stripe CLI
- Complete test payment using Stripe test card
- Verify webhook fires → Lambda processes → DynamoDB updated
- Full happy-path sandbox validation
- Still sandbox only — no live mode
