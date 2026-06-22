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
| 1 | Entitlement enforcement in handlers | ✅ Phase 1 active (17D/17I) | Done | — |
| 2 | Platform Admin UI | ✅ Deployed and validated (17P/17R) | Done | — |
| 3 | Credential security cleanup | ⏳ Plan ready (17T), awaiting Matthew execution | Low (manual) | — |
| 4 | Tenant provisioning workflow/tool | ❌ Not started | High | #3 |
| 5 | Cognito `custom:company_id` enforcement | ❌ Not started | Medium | #4 |
| 6 | Stripe subscription Checkout for new tenants | ❌ Not started | High | EIN + #4 |
| 7 | Business owner billing dashboard | ❌ Not started | Medium | #6 |
| 8 | Pricing/signup page | ❌ Not started | Medium | #6 |
| 9 | Per-tenant branding | ❌ Not started | Medium | #4 |
| 10 | "Getting Started" docs for new owners | ❌ Not started | Low | #4 |

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

Start second-tenant creation only when:
1. ✅ Entitlement enforcement active (Phase 1 gates working — 17D/17I)
2. ✅ Platform Admin UI deployed and validated (17P/17R)
3. ❌ Credential security cleanup complete (shared dev password rotated — 17T)
4. ❌ Tenant provisioning tooling exists (creation script or API — 17U/17V)
5. ❌ Matthew explicitly approves second-tenant creation
6. ⏳ EIN resolved + live payments working (for billing portal only — not required for dry run)
7. ⏳ Ryan invitation deferred until 19A re-evaluation gate

**Updated 2026-06-21 (17S):** Structural review complete. Three hard blockers remain before second-tenant dry run: no provisioning tool (G1/G2), shared dev password not rotated (G11), Matthew approval not given (G12). Next releases: 17T (credential cleanup) → 17U (provisioning design) → 17V (implementation) → 17W (dry run).
