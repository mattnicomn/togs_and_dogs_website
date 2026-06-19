# Release 14I: Payment Track Readiness Checkpoint and EIN Hold

**Status:** On Hold — Blocked by EIN
**Type:** Checkpoint documentation
**Date:** 2026-06-19
**Last Deployment Commit:** `c2a7c21` (14H closeout)

---

## 1. Payment Features Completed

The entire sandbox payment workflow is built, tested, deployed, and validated:

| Feature | Release | Status |
|---------|---------|--------|
| Stripe webhook handler + signature verification | 12D | ✅ Deployed |
| Billing event ledger + idempotency | 12D | ✅ Deployed |
| Entitlement interface (get_tenant_entitlement) | 12D | ✅ Deployed |
| Checkout Session creation endpoint | 12G | ✅ Deployed |
| Card-only payment enforcement | 12M/12N | ✅ Deployed |
| Duplicate payment state guard | 12O/12P | ✅ Deployed |
| Admin payment link UI (CareCard) | 12R | ✅ Deployed |
| Send Payment Email backend endpoint | 12T | ✅ Deployed |
| Send Payment Email frontend button + modal | 12V/12W | ✅ Deployed |
| Payment success page (/booking/:id/success) | 12Z | ✅ Deployed |
| Payment cancel page (/booking/:id/cancel) | 12Z | ✅ Deployed |
| Sandbox end-to-end payment validated | 12Y/12Z | ✅ Verified |
| Payment email received by test recipient | 12X | ✅ Verified |
| Fresh Checkout verified card-only | 12X | ✅ Verified |
| Admin search + payment status filter | 14B | ✅ Deployed |
| CareCard payment helper text + disabled states | 14C | ✅ Deployed |
| Payment operations quick reference | 14D | ✅ Published |
| Success/cancel page copy refinement | 14F | ✅ Deployed |
| Support contact finalized (support@usmissionhero.com) | 14H | ✅ Deployed |
| Payment terms/refund/cancellation policy drafted | 13D.1/13D.2 | ✅ Draft complete |
| Conditional sandbox warning (env-based) | 13B | ✅ Deployed |

---

## 2. Current Production/Sandbox State

| Item | Status |
|------|--------|
| Frontend (web) | ✅ Deployed with all 14H changes |
| Backend (Lambda) | ✅ Deployed with all 14H changes |
| API Gateway routes | ✅ All payment routes active |
| Stripe webhook endpoint (sandbox) | ✅ Active and validated |
| `STRIPE_ENV` | `sandbox` |
| Live Stripe keys wired | ❌ No |
| Live webhook endpoint | ❌ Not created |
| Live payments enabled | ❌ No |
| Real client emails sent | ❌ No (only Matthew-controlled test recipients) |
| CloudFront | ✅ Latest invalidation: `IA8K63W2FQIV90U5FLOJ1U2SJJ` |

---

## 3. Active Blocker

### usmissionhero LLC EIN Unavailable

| Item | Detail |
|------|--------|
| Blocker | Stripe business/tax verification requires EIN |
| Entity | usmissionhero LLC |
| Status | EIN not yet obtained |
| IRS contact | Matthew attempted; high call volume prevented completion |
| Impact | Cannot complete Stripe account verification → cannot enable live charges |
| Documented in | `docs/backlog/stripe-live-activation-blocked-pending-ein.md` |

**Until the EIN is available, no live payment work can proceed.**

---

## 4. Resume Criteria

When the EIN becomes available, resume the live payment track by completing these steps in order:

| # | Step | Release |
|---|------|---------|
| 1 | Obtain EIN confirmation | Matthew (external) |
| 2 | Complete Stripe Tax details in Dashboard | Matthew (manual) |
| 3 | Complete remaining Stripe business verification | Matthew (manual) |
| 4 | Confirm live charges enabled (no restrictions) | Matthew (verify in Dashboard) |
| 5 | Review/complete 13D readiness checklist (all Critical Gates) | Matthew |
| 6 | Wire live Stripe keys via Terraform | 13E (or next numbered release) |
| 7 | Create live webhook endpoint in Stripe Dashboard | 13E/13F |
| 8 | Validate live webhook (401 on unsigned request) | 13F |
| 9 | Internal $1 live payment test + immediate refund | 13G |
| 10 | Publish payment terms/refund policy on website | 13G+ |
| 11 | First real client payment | 13H |

---

## 5. Next Releases After EIN Resolution

| Release | Scope |
|---------|-------|
| 13E (or renumbered) | Live Stripe secret wiring via Terraform apply |
| 13F | Live webhook 401 validation |
| 13G | Internal $1 live payment + refund test |
| 13H | First real client payment readiness |
| 13I | Payment terms/policy published to website |

---

## 6. Recommended Safe Work While Waiting

These tracks have no dependency on the EIN or live Stripe:

| Track | Examples |
|-------|----------|
| Mobile/TestFlight | Ryan onboarding, mobile UX polish, new TestFlight builds |
| Admin UX | Non-payment admin workflow improvements |
| Multi-tenant planning | Architecture roadmap continuation (11-series) |
| Staff/client workflow | Scheduling, assignment, visit notes improvements |
| Policy/legal | Attorney/accountant review of payment terms draft |
| Operations | Additional SOPs, monitoring, documentation |
| Infrastructure | Non-payment Terraform improvements, observability |

---

## 7. What This Document Does NOT Authorize

- ❌ Wiring live Stripe keys
- ❌ Creating live webhook endpoints
- ❌ Enabling live payments
- ❌ Charging real cards
- ❌ Sending payment emails to real clients
- ❌ Code changes
- ❌ Deployments
- ❌ Terraform changes
- ❌ DynamoDB/Cognito/Postmark changes
- ❌ Mobile/EAS/TestFlight changes

This is a checkpoint/status document. All future work requires separate approval.
