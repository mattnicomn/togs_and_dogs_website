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
| 2 | Usage metering per tenant | ❌ Not started | Medium | #1 |
| 3 | Tenant provisioning workflow/tool | ✅ Script implemented (17W) — apply gate pending | High | #1 |
| 5 | Cognito `custom:company_id` enforcement | ⏳ Design complete (17X), implementation pending (17Y/17Z) | Medium | #4 |
| 6 | Stripe subscription Checkout for new tenants | ❌ Not started | High | EIN + #4 |
| 7 | Business owner billing dashboard | ❌ Not started | Medium | #6 |
| 8 | Pricing/signup page | ❌ Not started | Medium | #6 |
| 9 | Per-tenant branding | ❌ Not started | Medium | #4 |
| 10 | "Getting Started" docs for new owners | ❌ Not started | Low | #4 |

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `DEFAULT_COMPANY_ID` fallback | Critical | Any Cognito user created without a `custom:company_id` will default to "tog_and_dogs". Must implement post-auth Lambda trigger or strict attribute enforcement before the first secondary tenant is onboarded. |

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

**Updated 2026-06-21 (17W):** Tenant provisioning script (`scripts/provision_tenant.py`) implemented. Dry-run mode is safe. Apply mode requires explicit gate approval. Company ID resolution audit completed — `custom:company_id` claim correctly takes precedence. Known risk documented: a Cognito user without `custom:company_id` set falls through to `DEFAULT_COMPANY_ID` ("tog_and_dogs"). Remediation required before any second-tenant Cognito user is created (post-auth Lambda trigger or strict Cognito user attribute enforcement).
