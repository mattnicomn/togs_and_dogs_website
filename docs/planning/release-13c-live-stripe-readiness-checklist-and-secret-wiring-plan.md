# Release 13C: Live Stripe Readiness Checklist and Secret Wiring Plan

**Status:** Planning
**Priority:** High (gate before any live payment key touches AWS)
**Risk to Production:** None (planning only)
**Terraform Required:** No (planning only — Terraform apply is a future release)
**Code Changes:** None
**Scope:** Define manual Stripe Dashboard readiness checklist + live secret wiring strategy

---

## 1. Stripe Dashboard Live Readiness Checklist

Matthew must verify all items below in the Stripe Dashboard BEFORE live keys are wired into AWS.

### Account Verification

| # | Check | Location in Dashboard | Expected | Result |
|---|-------|----------------------|----------|--------|
| 1 | Business verification complete | Settings → Account details | Green ✓ / "Complete" | ___ |
| 2 | Business type: LLC | Settings → Account details | "usmissionhero LLC" | ___ |
| 3 | Representative identity verified | Settings → Account details → People | Matthew verified | ___ |
| 4 | Tax ID / EIN on file | Settings → Account details → Business details | Present | ___ |
| 5 | Country: United States | Settings → Account details | US | ___ |

### Payout Readiness

| # | Check | Location | Expected | Result |
|---|-------|----------|----------|--------|
| 6 | Bank account connected | Settings → Payouts → Bank accounts | Active bank account linked | ___ |
| 7 | Payout schedule configured | Settings → Payouts | Standard (2-day rolling) or manual | ___ |
| 8 | Test payout received (optional) | Stripe Dashboard → Balance | At least $0.01 test payout history | ___ |

### Live Payment Settings

| # | Check | Location | Expected | Result |
|---|-------|----------|----------|--------|
| 9 | Live mode enabled | Dashboard header (no "restricted" banner) | Active, no restrictions | ___ |
| 10 | Payment methods: Card only | Settings → Payment methods (LIVE toggle) | Card enabled; Link/Klarna/Bank/Afterpay disabled | ___ |
| 11 | Statement descriptor | Settings → Account details → Public details | "TOG AND DOGS" or "TOGS AND DOGS" (≤22 chars) | ___ |
| 12 | Shortened descriptor | Same location | "TOG DOGS" or similar (≤10 chars) | ___ |
| 13 | Support email | Settings → Account details → Public details | `support@usmissionhero.com` | ___ |
| 14 | Support phone (optional) | Same | Business phone or blank | ___ |
| 15 | Support URL | Same | `https://toganddogs.usmissionhero.com` | ___ |

### Customer Communication

| # | Check | Location | Expected | Result |
|---|-------|----------|----------|--------|
| 16 | Successful payment receipt emails | Settings → Customer emails | Enabled | ___ |
| 17 | Refund receipt emails | Settings → Customer emails | Enabled | ___ |
| 18 | Dispute evidence email | Settings → Account emails | Enabled (sent to Matthew) | ___ |

### Security

| # | Check | Location | Expected | Result |
|---|-------|----------|----------|--------|
| 19 | 2FA enabled | Settings → Security | ✅ Active | ___ |
| 20 | Team members | Settings → Team | Only Matthew (no stale invites) | ___ |
| 21 | API key access restricted | Developers → API keys → Restricted keys | No unrestricted keys except standard live/test pair | ___ |

---

## 2. Live Webhook Endpoint Setup

### Recommendation: Separate Live Endpoint

Create a **new** webhook endpoint in Stripe Dashboard specifically for live mode. Keep the existing sandbox endpoint active.

| Field | Value |
|-------|-------|
| Mode | Live (ensure Dashboard is toggled to Live, not Test) |
| Endpoint URL | `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/webhooks/stripe` |
| Description | "Togs & Dogs production webhook — booking payments" |
| API version | Use account default |

### Events to Subscribe

| Event | Required? |
|-------|-----------|
| `checkout.session.completed` | ✅ Yes (payment confirmation) |
| `checkout.session.expired` | ✅ Yes (session timeout) |
| `customer.subscription.created` | ⏳ Defer (future billing) |
| `customer.subscription.updated` | ⏳ Defer (future billing) |
| `customer.subscription.deleted` | ⏳ Defer (future billing) |
| `invoice.payment_succeeded` | ⏳ Defer (future billing) |
| `invoice.payment_failed` | ⏳ Defer (future billing) |

For initial live booking payments, only `checkout.session.completed` and `checkout.session.expired` are needed.

### Signing Secret

After creating the live endpoint:
- Copy the signing secret (`whsec_...`)
- Store in local `terraform.tfvars` (not committed)
- This becomes `STRIPE_WEBHOOK_SECRET` for live mode

---

## 3. Secret Management

### Recommended Approach: Terraform Lambda Env Vars (Consistent with Current Pattern)

| Secret | terraform.tfvars Key | Lambda Env Var |
|--------|---------------------|----------------|
| Live secret key | `stripe_secret_key` | `STRIPE_SECRET_KEY` |
| Live webhook secret | `stripe_webhook_secret` | `STRIPE_WEBHOOK_SECRET` |
| Environment flag | (hardcoded in main.tf) | `STRIPE_ENV = "live"` |
| Price IDs | `stripe_price_*` | `STRIPE_PRICE_*_MONTHLY` |

### Why Not AWS Secrets Manager (Yet)

| Factor | Lambda Env Var | Secrets Manager |
|--------|----------------|-----------------|
| Simplicity | ✅ Same pattern as sandbox | More complex |
| Cost | Free | $0.40/secret/month |
| Cold start | No latency | +50-100ms on cold start |
| Rotation | Manual (update tfvars + apply) | Automated possible |
| Visibility | Visible in Lambda console | Hidden until accessed |
| Current pattern | Matches postmark/google secrets | Would be new pattern |

**Decision:** Use Lambda env vars for initial live cutover. Evaluate Secrets Manager migration after 90 days of live operation if security review requires it.

### Rotation Procedure

1. Generate new key in Stripe Dashboard (Developers → API keys → Roll key)
2. Update `terraform.tfvars` with new key value
3. `terraform plan` → verify only env var change
4. `terraform apply` during low-traffic window
5. Verify webhook still processes (old key becomes invalid)
6. Document rotation date

### What MUST NOT Be Committed

- ❌ `terraform.tfvars` (in .gitignore)
- ❌ Any file containing `sk_live_`, `whsec_`, or `sk_test_`
- ❌ Screenshots showing full API keys
- ❌ Chat messages containing keys
- ❌ CloudWatch log queries that might expose keys

---

## 4. Environment Cutover Strategy

### Current State (Sandbox)

```
STRIPE_SECRET_KEY = sk_test_...
STRIPE_WEBHOOK_SECRET = whsec_sandbox_...
STRIPE_ENV = sandbox
```

### Target State (Live)

```
STRIPE_SECRET_KEY = sk_live_...
STRIPE_WEBHOOK_SECRET = whsec_live_...
STRIPE_ENV = live
```

### Cutover Steps

1. Matthew completes manual readiness checklist (Section 1)
2. Matthew creates live webhook endpoint in Stripe Dashboard
3. Matthew records live signing secret securely
4. Matthew updates local `terraform.tfvars`:
   - `stripe_secret_key = "sk_live_..."`
   - `stripe_webhook_secret = "whsec_..."`
5. Update `STRIPE_ENV` to `"live"` in Terraform main.tf (or variable default)
6. `terraform plan` → expect Lambda env var changes only
7. Matthew approves → `terraform apply`
8. Verify: unsigned webhook request returns 401
9. Verify: sandbox warning no longer appears in admin UI
10. **Do NOT generate payment links for real clients yet** (wait for 13G internal test)

### Keeping Sandbox Available

The sandbox Stripe endpoint remains active in Stripe Dashboard. If rollback is needed, simply revert `terraform.tfvars` to sandbox keys and re-apply.

---

## 5. Validation Sequence (Pre-First-Live-Payment)

| Phase | Release | Gate |
|-------|---------|------|
| Dashboard readiness complete | 13D | Matthew fills checklist |
| Live keys wired to AWS | 13E | Terraform apply approved |
| Live webhook 401 test | 13F | Unsigned request rejected |
| Internal $1 real payment | 13G | Matthew pays with real card |
| Immediate refund | 13G | Refund in Stripe Dashboard |
| Admin UI confirms paid | 13G | Green badge visible |
| First real client payment | 13H | Matthew sends link to real client |

---

## 6. Risk Controls

| Risk | Mitigation |
|------|------------|
| Live keys accidentally committed | .gitignore covers *.tfvars; pre-commit check if available |
| Live email sent with sandbox warning | `STRIPE_ENV = live` suppresses warning (13B code handles this) |
| Live webhook misconfigured | Test 401 before any payment attempt |
| Client charged but webhook fails | Monitor CloudWatch; manual DynamoDB fix as fallback |
| Wrong amount charged | Admin enters amount manually; confirmation modal shows amount |
| Unauthorized live payment | Only owner/admin can generate links; Cognito-gated |
| Stripe account restricted after go-live | Complete all verification items before wiring keys |

---

## 7. Rollback Plan

| Trigger | Action | Time to Restore |
|---------|--------|-----------------|
| Webhook failures after cutover | Revert tfvars to sandbox keys → terraform apply | ~5 minutes |
| Unexpected charges | Disable live webhook in Stripe Dashboard | ~1 minute |
| Email with wrong content sent live | Revert STRIPE_ENV to sandbox → terraform apply → redeploy frontend | ~10 minutes |
| Complete rollback needed | Revert all tfvars + terraform apply + frontend redeploy | ~15 minutes |

**Existing payments remain valid.** Reverting to sandbox keys only affects NEW sessions. Already-paid records stay `paid` in DynamoDB regardless.

---

## 8. Recommended Follow-Up Release Breakdown

| Release | Scope | Approval Gate |
|---------|-------|---------------|
| **13D** | Matthew completes Stripe Dashboard manual readiness checklist | Matthew self-service |
| **13E** | Live Stripe keys wired to Lambda via Terraform apply | Matthew approves terraform apply |
| **13F** | Live webhook 401 validation (no payment) | AG executes |
| **13G** | Internal live $1 payment + immediate refund | Matthew approves + pays |
| **13H** | First real client payment readiness / go-live | Matthew approves |

---

## 9. What This Document Does NOT Authorize

- ❌ Changing Stripe Dashboard settings
- ❌ Creating live webhook endpoints
- ❌ Generating or copying live API keys
- ❌ Updating terraform.tfvars
- ❌ Running terraform plan or apply
- ❌ Deploying anything
- ❌ Creating Checkout Sessions
- ❌ Charging any card (real or test)
- ❌ Sending emails
- ❌ Writing to DynamoDB
- ❌ Modifying code
- ❌ Cognito/Postmark/Google Calendar changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Committing secrets

This is a planning document only. Each follow-up release requires Matthew's separate explicit approval.
