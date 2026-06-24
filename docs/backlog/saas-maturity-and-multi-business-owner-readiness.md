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
| 2 | Usage metering per tenant | ✅ Phase 2 active & validated (18N) | Done | #1 |
| 3 | Tenant provisioning workflow/tool | ✅ Script implemented (17W) — apply gate pending | High | #1 |
| 5 | Cognito `custom:company_id` enforcement | ⏳ Schema added (18B), backfilled (18C), 7-day observation active (18D/18E) | Medium | #4 |
| 6 | Stripe subscription Checkout for new tenants | ❌ Not started | High | EIN + #4 |
| 7 | Business owner billing dashboard | ❌ Not started | Medium | #6 |
| 8 | Pricing/signup page | ❌ Not started | Medium | #6 |
| 9 | Per-tenant branding | ❌ Not started | Medium | #4 |
| 10 | "Getting Started" docs for new owners | ❌ Not started | Low | #4 |

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `DEFAULT_COMPANY_ID` fallback | Critical | Hardened in 17Y to support strict mode (PermissionError if mode=multi). Single mode remains active for backward compatibility; once Cognito attribute audit (17Z) is complete, strict mode (18A) will be enabled. |

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
1. ✅ Entitlement enforcement active (Phase 1 & 2 gates working — 17D/17I/18L)
2. ✅ Platform Admin UI deployed and validated (17P/17R)
3. ✅ Credential security cleanup complete (shared dev passwords rotated — 17U)
4. ✅ Tenant provisioning tooling exists (creation script — 17W)
5. ❌ Matthew explicitly approves second-tenant creation
6. ⏳ EIN resolved + live payments working (for billing portal only — not required for dry run)
7. ⏳ Ryan invitation deferred until 19A re-evaluation gate

**Updated 2026-06-21 (17W):** Tenant provisioning script (`scripts/provision_tenant.py`) implemented. Dry-run mode is safe. Apply mode requires explicit gate approval. Company ID resolution audit completed — `custom:company_id` claim correctly takes precedence. Known risk documented: a Cognito user without `custom:company_id` set falls through to `DEFAULT_COMPANY_ID` ("tog_and_dogs"). Remediation required before any second-tenant Cognito user is created (post-auth Lambda trigger or strict Cognito user attribute enforcement).

**Updated 2026-06-22 (17Y):** Implemented strict/compatibility tenant resolution modes (`TENANT_RESOLUTION_MODE=single|multi`) and structured logging with CloudWatch observability metrics/alarms. Ready for Cognito audit (17Z) and strict mode enablement (18A).

**Updated 2026-06-23 (18B):** Added `custom:company_id` custom attribute to Cognito user pool schema via Terraform and updated app client read/write attributes (read includes `custom:company_id`, write excludes it) to prevent self-service modification. Ready for manual backfill of users (18C).

**Updated 2026-06-23 (18C):** Completed Cognito user audit and backfilled all production users with `custom:company_id = tog_and_dogs` attribute. Verified admin/platform admin logins.

**Updated 2026-06-23 (18D):** Initiated 7-day observation period for tenant resolution fallback and failure metrics to ensure zero fallback logs before strict mode enablement. Window runs through June 30, 2026.

**Updated 2026-06-23 (18E):** Completed interim checkpoint review of the observation period. Telemetry shows 0 fallback/failure events so far. Strict mode remains disabled; final gate review scheduled on or after June 30, 2026.

**Updated 2026-06-23 (18F):** Completed the Google Calendar connection and scheduler sync reliability review, mapping out degraded state behavior, risks, and post-reconnect validation checklist.

**Updated 2026-06-23 (18G):** Matthew manually completed the Google OAuth consent flow. Verified that the connection status is CONNECTED and healthy. The degraded connection warning on /admin has been cleared.

**Updated 2026-06-23 (18H):** Completed the validation plan for the post-reconnect Google Calendar sync, defining safe test data parameters and notification suppression strategies.

**Updated 2026-06-23 (18I):** Executed the controlled validation run. Confirmed successful test booking and Google Calendar event sync. Cancelled the booking using standard cancellation flow and verified event deletion in Google Calendar. Only the configured admin cancellation email was sent.

**Updated 2026-06-23 (18L):** Implemented Phase 2 entitlement gates (active/disabled client limit gating and monthly booking atomic counter gating). Verified via unit tests and successfully deployed Lambda updates to production.

**Updated 2026-06-23 (18M):** Designed the validation plan for Phase 2 entitlement limits, identifying safe test client profiles and test bookings.

**Updated 2026-06-24 (18N):** Executed the controlled validation run for Phase 2 entitlement gates in production. Verified that client creation increments the active client count, test bookings marked with `is_test_booking = true` are exempt from limits/counter, and normal bookings increment the monthly usage counter by exactly 1. Cancelled all bookings via the cancellation workflow, manually cleaned up Google Calendar events, and disabled/archived the test client profile. Verified zero customer-facing notification impact.
