# Release 13A: Payments Production Readiness and Live Mode Cutover Plan

**Status:** Planning
**Priority:** High (gate before real client payments)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Define all requirements for transitioning from sandbox to live Stripe payments

---

## 1. Current State Summary

### What's Validated in Sandbox

| Capability | Status | Release |
|------------|--------|---------|
| Admin generates payment link | ✅ | 12R |
| Checkout is card-only | ✅ | 12M/12N/12X |
| Duplicate payment guard | ✅ | 12O/12P |
| Admin sends payment email | ✅ | 12T/12V/12X |
| Client receives email with link | ✅ | 12X |
| Client pays via Stripe Checkout | ✅ | 12Y/12Z |
| Webhook processes payment | ✅ | 12D/12L/12Z |
| DynamoDB request → paid | ✅ | 12L/12Z |
| Billing ledger records event | ✅ | 12D/12Z |
| Admin sees paid badge/read-only | ✅ | 12Z |
| Success/cancel redirect pages | ✅ | 12Z |

### What Does NOT Exist Yet

| Gap | Impact |
|-----|--------|
| Live Stripe API keys | Cannot charge real cards |
| Live webhook endpoint | Cannot receive live events |
| Refund workflow | Cannot process refunds |
| Dispute/chargeback handling | No automated response |
| Payment terms/receipts | Customer-facing policy missing |
| Environment toggle (sandbox→live) | Manual Terraform change needed |

---

## 2. Live Stripe Readiness

### Account Verification

Before enabling live mode, Stripe requires:

| Requirement | Status | Action Needed |
|-------------|--------|---------------|
| Business verification | ⏳ Check | Verify usmissionhero LLC is fully verified in Stripe Dashboard |
| Bank account linked | ⏳ Check | Confirm payout destination is connected |
| Identity verification | ⏳ Check | Matthew's identity verified as account representative |
| Tax information | ⏳ Check | W-9 or equivalent on file |
| Statement descriptor | ⏳ Configure | Set to "TOG AND DOGS" or "USMISSIONHERO" (max 22 chars) |

**Matthew must check:** Stripe Dashboard → Settings → Account details → verify all sections are green/complete.

### Live API Keys

| Key | Source | Storage |
|-----|--------|---------|
| Live secret key (`sk_live_...`) | Stripe Dashboard → Developers → API keys (live toggle) | `terraform.tfvars` (not committed) |
| Live publishable key (`pk_live_...`) | Same location | Lambda env var or frontend config |
| Live webhook signing secret (`whsec_...`) | Created when live endpoint is added | `terraform.tfvars` (not committed) |

### Live Webhook Endpoint

| Field | Value |
|-------|-------|
| URL | `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/webhooks/stripe` |
| Mode | Live |
| Events | Same as sandbox: `checkout.session.completed`, `checkout.session.expired`, `customer.subscription.*`, `invoice.*` |

**Important:** The same API Gateway URL can receive both sandbox and live webhooks. The handler differentiates by checking the `environment` metadata field. However, using separate webhook endpoints (sandbox + live) is cleaner and prevents cross-contamination.

**Recommendation:** Create a SEPARATE live webhook endpoint in Stripe Dashboard. Keep the existing sandbox endpoint active for testing.

### Payment Method Settings (Live Mode)

In Stripe Dashboard → Settings → Payment methods (live mode):
- Enable: Card
- Disable: Link, Klarna, Afterpay, Bank transfers, all others
- This ensures card-only even if API parameter is somehow bypassed

---

## 3. Secret/Config Management

### Current Pattern (Sandbox)

```
terraform.tfvars (not committed):
  stripe_secret_key = "sk_test_..."
  stripe_webhook_secret = "whsec_..."

Lambda env vars (via Terraform):
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  STRIPE_ENVIRONMENT = "sandbox"
  STRIPE_PRICE_*_MONTHLY
```

### Live Mode Decision

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| Keep in terraform.tfvars + Lambda env vars | Simple, consistent, proven pattern | Visible in Lambda console, no rotation | ✅ For initial go-live |
| Move to AWS Secrets Manager | Rotation, audit trail, not visible in console | Cost, IAM complexity, cold-start latency | Later (post-go-live hardening) |

**Recommendation:** Keep the terraform.tfvars + Lambda env var pattern for initial live cutover. Migrate to Secrets Manager in a hardening release if needed.

### Environment Toggle

To switch from sandbox to live:

```hcl
# In terraform.tfvars:
stripe_secret_key       = "sk_live_..."        # was sk_test_...
stripe_webhook_secret   = "whsec_live_..."     # new live signing secret
```

```hcl
# In main.tf or variables.tf:
STRIPE_ENVIRONMENT = "production"              # was "sandbox"
```

Then `terraform apply` updates the Lambda env vars.

### Rotation Procedure

- Rotate live keys quarterly (or immediately if compromised)
- Generate new key in Stripe Dashboard → update terraform.tfvars → terraform apply
- Old key becomes invalid immediately — coordinate timing with low-traffic window

---

## 4. Postmark/Email Readiness

### Template Review

| Item | Current State | Action Before Live |
|------|--------------|-------------------|
| Subject line | "Payment Link for {pet}'s Care - Tog & Dogs" | ✅ Good |
| From address | `support@usmissionhero.com` | ✅ Good |
| Sandbox warning banner | Present | ❌ Must be removed/hidden for live |
| Amount formatting | $X.XX | ✅ Good |
| Payment link button | "Pay Secure Now" | ✅ Good |
| Reply-to | Not explicitly set | Consider setting to Ryan's business email |

### Environment-Specific Template Behavior

The sandbox warning (`⚠️ Stripe Sandbox Mode: Test Payment Only`) should be conditionally shown based on `STRIPE_ENVIRONMENT`:

```python
# In email template rendering:
if environment == 'sandbox':
    include_sandbox_warning = True
else:
    include_sandbox_warning = False
```

**Code change needed:** Add environment check to payment email template rendering (Release 13B or 13C).

### From/Reply-To Finalization

| Field | Recommended Value | Rationale |
|-------|-------------------|-----------|
| From | `support@usmissionhero.com` | Matches existing notification sender |
| Reply-To | Ryan's business email (or `support@toganddogs.com` if configured) | Client replies go to business |
| Business name in email | "Tog & Dogs" | Client-facing brand |

---

## 5. Operational Guardrails

### Already Implemented

| Guard | Release | Status |
|-------|---------|--------|
| Duplicate payment session blocked for paid/refunded/waived | 12O/12P | ✅ |
| Card-only Checkout | 12M/12N | ✅ |
| Tenant ownership validation | 11E | ✅ |
| Webhook signature verification | 12D | ✅ |
| Idempotent webhook processing | 12D | ✅ |
| Send email confirmation modal | 12V | ✅ |

### Needed Before Live

| Guard | Priority | Release |
|-------|----------|---------|
| Remove sandbox warning from live emails | High | 13B/13C |
| Rate limit on payment email sends (already in backend) | ✅ Done | 12T |
| Admin UI sandbox label removal for live mode | Medium | 13C |
| Payment amount min/max validation ($1–$10,000) | Low | 13B |

---

## 6. Payment Lifecycle Gaps

### Refunds

| Aspect | Current State | Needed Before Live? |
|--------|--------------|---------------------|
| Automatic refund on cancellation | Not implemented | No — manual via Stripe Dashboard for now |
| Refund webhook handling | Not implemented | Low priority — admin checks Stripe Dashboard |
| payment_status = refunded state | Defined in guard | ✅ Guard respects it |
| Admin refund button | Not implemented | No — use Stripe Dashboard initially |

**Recommendation:** For v1 live launch, refunds are processed manually in Stripe Dashboard. Admin updates payment_status manually if needed. Automated refund handling is a future enhancement.

### Cancellations + Payments

| Scenario | Current Behavior | Acceptable for Live? |
|----------|-----------------|----------------------|
| Client cancels after paying | Cancellation flow doesn't touch payment | ✅ (refund manual) |
| Admin cancels after payment link sent | No automatic session expiry | ✅ (session expires in 30 min anyway) |
| Client never pays | payment_status stays `payment_link_sent` | ✅ (admin can follow up) |

### Disputes/Chargebacks

- Stripe handles dispute notifications
- Admin receives email from Stripe for disputes
- No automated response in our system
- **Acceptable for v1 launch** — volume is too low to justify automation

### Failed/Expired Payment Links

- Checkout sessions expire after 30 minutes by default
- Admin can generate a new link (existing flow handles this)
- `checkout.session.expired` webhook could set `payment_status = expired` (partially implemented)
- **Acceptable for v1** — admin resends if client reports expired

---

## 7. Admin/Business Workflow Decisions

### When to Generate Payment Link

| Trigger | Recommendation |
|---------|---------------|
| After request approved | Admin generates link at their discretion |
| Automatic on approval | NOT recommended for v1 (admin controls timing) |
| Before scheduling/assignment | NOT required (payment doesn't gate scheduling) |

### When to Send Payment Email

| Trigger | Recommendation |
|---------|---------------|
| After generating link | Admin sends at their discretion (separate action) |
| Automatic after link generation | NOT recommended for v1 |

### Payment Required Before Service?

**Decision for Matthew:** Does Ryan require payment before confirming/scheduling service?

| Option | Behavior |
|--------|----------|
| A: Payment NOT required | Schedule anytime, collect payment separately (current behavior) |
| B: Payment required | Block assignment until `payment_status = paid` (requires code change) |

**Recommendation:** Option A for v1. Payment and scheduling are independent. Ryan can choose to wait for payment or proceed at her discretion.

---

## 8. Legal/Compliance/Customer Messaging

### Before First Real Client Payment

| Item | Status | Action |
|------|--------|--------|
| Payment terms on website/portal | ❌ Missing | Add a brief payment terms section |
| Refund/cancellation policy | ❌ Missing | Define and publish |
| Receipt delivery | ✅ Stripe handles | Configure Stripe to send receipt emails |
| Business contact for payment issues | ✅ In email template | `support@usmissionhero.com` |
| Privacy policy covers payment data | ⚠️ Review needed | Confirm existing privacy policy mentions payment processing |

### Stripe Receipt Configuration

Stripe can automatically email receipts after successful payment:
- Enable in Dashboard → Settings → Customer emails → Successful payments
- Receipt shows: amount, date, business name, card last 4
- No code change needed — Stripe handles this

---

## 9. Validation Phases (Live Cutover)

### Phase 1: Live Key Wiring (13C)

- Add live Stripe keys to terraform.tfvars
- Set `STRIPE_ENVIRONMENT = "production"`
- Create live webhook endpoint in Stripe Dashboard
- `terraform apply` to update Lambda env vars
- Verify: unsigned request to webhook returns 401
- **No real payment yet**

### Phase 2: Internal Live $1 Test (13E)

- Matthew (or controlled test account) generates a payment link
- Matthew pays $1.00 with a REAL card
- Verify: real charge appears in Stripe Dashboard (live)
- Verify: webhook delivers, DynamoDB updates to `paid`
- Verify: $1.00 appears in Stripe balance (will settle in 2 days)
- **Refund the $1.00 immediately via Stripe Dashboard**

### Phase 3: First Real Client Payment (13F)

- Select one real client with an upcoming approved booking
- Generate payment link with real amount
- Send payment email
- Client pays
- Verify full lifecycle
- Monitor for 24-48 hours

---

## 10. Rollback Plan

If live payments cause issues:

| Action | Method | Effect |
|--------|--------|--------|
| Revert to sandbox keys | Update terraform.tfvars → terraform apply | All new sessions use test mode |
| Disable "Send Payment Email" button | Frontend flag or quick hide | Admin can't trigger emails |
| Disable webhook endpoint in Stripe | Toggle off in Stripe Dashboard | Events stop firing |
| Admin falls back to manual links | Copy Stripe Payment Link from Dashboard | Business continues manually |

**Data safety:** Reverting to sandbox does not affect existing `paid` records. Already-completed payments remain valid in Stripe regardless of key change.

---

## 11. Recommended Release Breakdown After 13A

| Release | Scope | Priority |
|---------|-------|----------|
| **13B** | Hardening: sandbox warning conditional on env, amount min/max, email send dedup guard review | Medium |
| **13C** | Live Stripe secret wiring + Terraform apply + live webhook endpoint | High |
| **13D** | Live webhook validation (unsigned request test, no payment) | High |
| **13E** | Internal live $1 real-card test + immediate refund | High |
| **13F** | First real client payment readiness checklist | High |
| **13G** | Payment terms / refund policy content update | Medium |
| **Future** | Automated refund handling, dispute response, payment gating | Low |

---

## 12. Highest Risks and Blockers

| Risk | Impact | Mitigation |
|------|--------|------------|
| Stripe account not fully verified for live payouts | Cannot receive real money | Matthew checks Dashboard verification status |
| Sandbox warning sent to real client | Confusing/unprofessional | Must remove before live (13B) |
| Live webhook secret misconfigured | Payments succeed but DynamoDB not updated | Test webhook delivery before first real payment (13D) |
| Refund request with no automated process | Manual Stripe Dashboard work | Acceptable for low volume; document SOP |
| Duplicate email sends (process deviation) | Client receives 2 copies | Already documented; admin UI has cooldown |
| Client card charged but webhook fails | payment_status stays payment_link_sent | Monitor CloudWatch; manual DynamoDB update as fallback |
| Payment terms not published | Potential dispute risk | Publish before first real client charge (13G) |

---

## 13. What This Document Does NOT Authorize

- ❌ Enabling Stripe live mode
- ❌ Adding live API keys anywhere
- ❌ Creating live webhook endpoints
- ❌ Charging real cards
- ❌ Sending emails to real clients
- ❌ Writing code
- ❌ Deploying anything
- ❌ Terraform changes
- ❌ DynamoDB writes
- ❌ Cognito/Postmark/Google Calendar changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Creating a second tenant
- ❌ Committing secrets

This is a planning document only. Each subsequent release (13B–13F) requires separate explicit approval.
