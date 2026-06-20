# Backlog: SaaS Maturity and Multi-Business-Owner Readiness

**Status:** Active Backlog
**Owner:** Matthew
**Priority:** Strategic (gates second-tenant onboarding)
**Created:** 2026-06-19
**Source:** Release 16A Repository Readiness Audit

---

## Summary

The platform has strong single-tenant foundations but requires significant work before a second business owner can safely onboard. This backlog tracks all items needed for multi-business-owner SaaS readiness.

---

## Critical Path Items (Must Complete Before Second Tenant)

| # | Item | Status | Effort | Depends On |
|---|------|--------|--------|------------|
| 1 | Entitlement enforcement in handlers | ⚠️ Helpers & tests complete (17B) | High | — |
| 2 | Usage metering per tenant | ❌ Not started | Medium | #1 |
| 3 | Tenant provisioning workflow/tool | ❌ Not started | High | #1 |
| 4 | Cognito `custom:company_id` enforcement | ❌ Not started | Medium | #3 |
| 5 | Stripe subscription Checkout for new tenants | ❌ Not started | High | EIN + #3 |
| 6 | Business owner billing dashboard | ❌ Not started | Medium | #5 |
| 7 | Pricing/signup page | ❌ Not started | Medium | #5 |
| 8 | Per-tenant branding | ❌ Not started | Medium | #3 |
| 9 | "Getting Started" docs for new owners | ❌ Not started | Low | #3 |

---

## Important But Not Blocking Second Tenant

| # | Item | Status | Priority |
|---|------|--------|----------|
| 10 | EIN obtained + Stripe live verification | ❌ Blocked (IRS) | High |
| 11 | Payment terms/refund policy published | ⚠️ Draft exists | Medium |
| 12 | Ryan external TestFlight validated | ⏳ Pending Apple review | Medium |
| 13 | Self-service staff/client invite | ❌ Not started | Low |
| 14 | Video visit evidence | ❌ Not started | Low |
| 15 | Analytics dashboard | ❌ Not started | Low |
| 16 | AI-assisted onboarding | ❌ Not started | Low |
| 17 | Multi-location support | ❌ Not started | Future |

---

## Current Single-Tenant Maturity (tog_and_dogs)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Core operations | 9/10 | Booking, scheduling, assignment, completion all working |
| Tenant isolation | 8/10 | Enforced in all handlers; missing entitlement gating |
| Payments | 6/10 | Sandbox-complete; live blocked on EIN |
| Mobile | 7/10 | Internal TestFlight validated; Ryan not yet testing |
| Documentation | 8/10 | Ops guides, policies (draft), release notes comprehensive |
| Maintainability | 5/10 | Requires developer/Matthew for many admin tasks |
| Self-service | 2/10 | Almost nothing is self-service for a new owner |

---

## Resume Criteria for Multi-Tenant Work

Start multi-tenant implementation (17-series) only when:
1. ✅ Matthew approves starting entitlement enforcement (can proceed without EIN)
2. ⏳ EIN resolved + live payments working (for billing portal integration only)
3. ⏳ Ryan invitation deferred until 19A re-evaluation gate
4. ⏳ Payment terms published
5. ✅ Matthew approves second-tenant timeline

**Updated 2026-06-19 (16B):** Roadmap reprioritized. Entitlement enforcement and tenant provisioning proceed independently of EIN. Ryan remains paused until gates G1–G6 are met. See `release-16b-saas-maturity-roadmap-reprioritization-and-capability-placement-strategy.md` for full revised roadmap.
