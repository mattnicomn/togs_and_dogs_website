# Release 20A: SaaS Maturity Next-Phase Plan

**Status:** Planning
**Date:** 2026-06-27
**Priority:** Strategic (defines next 2–4 months of work)
**Scope:** Define work lanes, sequencing, and approval gates after tenant isolation is validated

---

## 1. Where We Are

### Completed (19-Series Closeout)

- ✅ Strict tenant-resolution mode active and validated
- ✅ Second tenant (test_tenant_alpha) created, owner user exists, isolation validated
- ✅ Google Calendar, staff/client lists, bookings, branding — all isolated
- ✅ Platform Admin UI shows both tenants
- ✅ Phase 1 + Phase 2 entitlement enforcement active
- ✅ Sandbox payment workflow fully validated (12-series)
- ✅ Payment admin UX complete (14-series)
- ✅ Credential security cleanup complete (17T/17U)
- ✅ Calendar cancellation race condition fixed (18P)

### Remaining Work Lanes

| Lane | Status | Next Step |
|------|--------|-----------|
| **Stripe payments** | Sandbox-validated; live blocked on EIN | Architecture decision: booking payments vs SaaS subscriptions |
| **Tenant lifecycle** | Create/isolate works; no disable/archive/cleanup flow | Runbook + Platform Admin disable workflow |
| **Owner onboarding** | Manual script + Cognito CLI | UX/backoffice simplification |
| **Subscription/tier enforcement** | Entitlement gates active; no Stripe-linked subscriptions | Connect entitlement to Stripe subscription lifecycle |
| **External testing** | Ryan paused; Apple Beta Review submitted | Readiness gates before reintroduction |
| **Mobile/App Store** | Internal TestFlight validated; not public | Publish gates |
| **Operational monitoring** | Alarms exist; manual runbooks | Expand coverage |

---

## 2. Stripe Payment Strategy (Sandbox Only)

### Current Stripe State

| Item | Status |
|------|--------|
| Stripe account | Exists (mbn@usmissionhero.com) |
| Mode | **Sandbox/test only** |
| Live mode | ❌ Blocked (EIN pending) |
| Legal entity | usmissionhero LLC |
| Model | Direct charges (not Stripe Connect) |

### Two Payment Tracks (Separate)

| Track | Purpose | Payer | When |
|-------|---------|-------|------|
| **A: Booking payments** | Client pays for pet-care service | Client (one-time per booking) | Ready in sandbox (12-series) |
| **B: SaaS subscriptions** | Business owner pays for platform access | Tenant owner (monthly/annual) | Not implemented |

### Recommendation: Keep Tracks Separate

- **Track A (booking payments)** is fully built and sandbox-validated
- **Track B (SaaS subscriptions)** requires Stripe Billing + Checkout for subscriptions + webhook lifecycle management + tier upgrade/downgrade
- Implement Track B only when a paying second business owner is expected
- Both tracks use the same Stripe account but different Stripe products/modes

### What NOT to Do Yet

- ❌ No Stripe live mode activation
- ❌ No real customer charges
- ❌ No Stripe Connect / marketplace payouts
- ❌ No EIN/bank/tax details in docs
- ❌ No subscription product creation until design is approved

---

## 3. Tenant Lifecycle Management

### Current Capabilities

| Action | Method | Status |
|--------|--------|--------|
| Create tenant | `scripts/provision_tenant.py --mode=apply` | ✅ Tested |
| Create owner user | Manual Cognito CLI | ✅ Tested |
| View tenants | Platform Admin UI | ✅ Working |
| Edit tenant metadata | Platform Admin PATCH | ✅ Working |
| Disable tenant | Set `subscription_status = disabled` | ✅ Designed, not formally tested |
| Delete tenant | Not implemented | ❌ Deferred |
| Archive tenant data | Not implemented | ❌ Deferred |

### Next Steps

| Release | Scope |
|---------|-------|
| 20D | Tenant disable/cleanup runbook (documented steps, Platform Admin flow) |
| 20E | Formal disable validation (set test_tenant_alpha to disabled, verify login blocked) |
| Future | Automated archive/data-retention (requires policy/legal review) |

---

## 4. Owner Onboarding Flow

### Current (Manual/Developer-Driven)

1. Matthew runs provisioning script
2. Matthew creates Cognito user via CLI
3. Matthew communicates credentials privately
4. Owner logs in, changes password

### Future (Simplified)

| Level | Approach | Effort |
|-------|----------|--------|
| Near-term | Platform Admin "Create Tenant" button → guided form | Medium |
| Mid-term | Invite-by-email workflow (owner gets link, sets own password) | Medium-High |
| Long-term | Public self-service signup with Stripe subscription Checkout | High |

### Recommendation

Start with Platform Admin "Create Tenant" button (20E) — Matthew/usmissionhero operators can onboard new businesses without running scripts. Self-service is a much later milestone.

---

## 5. External Tester / Ryan Gate

### Current Status

- Ryan is NOT invited to TestFlight
- Apple Beta App Review was submitted (15J)
- Ryan testing deferred until SaaS maturity gates pass (16B decision)

### Prerequisites Before Ryan Invitation

| # | Prerequisite | Status |
|---|-------------|--------|
| 1 | Tenant isolation validated | ✅ Done (19N) |
| 2 | Branding shows correct tenant info | ✅ Done (19L/19N) |
| 3 | Entitlement enforcement active | ✅ Done (17I/18L) |
| 4 | Strict tenant-resolution active | ✅ Done (18T) |
| 5 | No cross-tenant data leaks | ✅ Done (19N) |
| 6 | Ryan's intended role/tenant defined | ⏳ Matthew decision |
| 7 | Test data prepared for Ryan's tenant | ⏳ Not started |
| 8 | Matthew explicitly approves Ryan invite | ⏳ Pending |
| 9 | Fresh mobile build (if needed) | ⏳ May need update |
| 10 | Apple Beta Review approved | ⏳ Status unknown |

### Recommendation

Ryan reintroduction can be planned (20F) but not executed until Matthew explicitly approves. Most prerequisites are now met. The remaining gates are Matthew's decisions about Ryan's role, tenant, and test data.

---

## 6. Recommended Release 20 Sequence

| Release | Scope | Priority | Owner |
|---------|-------|----------|-------|
| **20A** | SaaS maturity next-phase plan (this document) | ✅ Done | Kiro |
| **20B** | Stripe sandbox payment architecture decision (booking vs subscription tracks) | Medium | Kiro |
| **20C** | Tenant lifecycle: disable/cleanup runbook + Platform Admin flow | Medium | Kiro → AG |
| **20D** | Tenant disable controlled validation (test_tenant_alpha → disabled → verify) | Medium | AG + Matthew |
| **20E** | Owner onboarding simplification plan (Platform Admin "Create Tenant" wizard) | Medium | Kiro |
| **20F** | External tester readiness checklist (Ryan gates, mobile build, approval) | Low-Medium | Kiro |
| **20G** | SaaS subscription billing design (Stripe Billing Track B) — if/when needed | Low | Kiro |

---

## 7. Approval Gates (Ongoing)

| Action | Requires |
|--------|----------|
| Stripe live mode activation | Matthew explicit approval + EIN resolved |
| New tenant creation | Matthew explicit approval per tenant |
| Cognito user creation | Matthew explicit approval |
| Ryan/external tester invitation | Matthew explicit approval |
| App Store public submission | Matthew explicit approval |
| Production test data (bookings/clients) | Matthew explicit approval of exact data |
| Terraform apply | Matthew reviews plan first |
| Frontend/mobile deployment | Build passes + Matthew approval |
| Disable/archive a tenant | Matthew explicit approval |

---

## 8. What This Document Does NOT Authorize

- ❌ Creating tenants/users
- ❌ Stripe live mode or charges
- ❌ Code changes or deployment
- ❌ Terraform/AWS changes
- ❌ Ryan/tester invitation
- ❌ App Store submission
- ❌ DynamoDB writes
- ❌ Cognito changes
- ❌ Google Calendar/Postmark/payment actions
- ❌ Mobile builds
- ❌ Changing TENANT_RESOLUTION_MODE
- ❌ Production data creation

This is a strategic planning document. Each 20-series release requires separate approval.
