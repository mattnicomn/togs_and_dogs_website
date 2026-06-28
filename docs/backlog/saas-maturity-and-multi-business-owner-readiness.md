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
| 3 | Tenant provisioning workflow/tool | ✅ Second test tenant created (19D) | High | #1 |
| 5 | Cognito `custom:company_id` enforcement | ✅ Verified & isolated in prod (19M) | Medium | #4 |
| 6 | Stripe subscription Checkout for new tenants | ❌ Not started | High | EIN + #4 |
| 7 | Business owner billing dashboard | ❌ Not started | Medium | #6 |
| 8 | Pricing/signup page | ❌ Not started | Medium | #6 |
| 9 | Per-tenant branding | ✅ Dynamic brand name, shell logo, and footer separated by route (19N pre-deploy) | Medium | #4 |
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

**Updated 2026-06-24 (18P):** Implemented defensive Google Calendar cancellation cascade fix to collect, deduplicate, and delete events from parent requests and child jobs. Added detailed error tolerance for HTTP 404/410 and API exceptions, database cleanups, and structured logs. Verified via 9 unit tests.

**Updated 2026-06-26 (18R):** Completed early read-only strict-mode readiness review. Confirmed all 5 Cognito users backfilled with custom:company_id = 'tog_and_dogs'. Confirmed exactly 1 tenant metadata record exists in DynamoDB. Verified all CloudWatch alarms are OK. Analyzed the single fallback event on June 23 and confirmed zero fallbacks/failures occurred in the subsequent 3+ days. Strict mode is recommended for enablement in a separate release.

**Updated 2026-06-26 (18S):** Configured `TENANT_RESOLUTION_MODE = "multi"` across all 13 backend Lambdas in production Terraform config (`locals.tf` and `main.tf`). Generated and saved `release18s-strict-mode.tfplan` showing `0 to add, 13 to change, 0 to destroy` for in-place environment updates only. Ready for approval to apply.

**Updated 2026-06-26 (18T):** Executed Terraform apply using the approved `release18s-strict-mode.tfplan` to enable strict tenant-resolution mode in production. Verified that all 13 backend Lambdas have `TENANT_RESOLUTION_MODE = "multi"`. Confirmed that `/admin` and `/platform-admin` portals load normally, Google Calendar health remains healthy/connected, and all 6 platform alarms remain OK. Matthew completed manual validation (logout, login, verification of `/admin` and `/platform-admin`), confirming no authentication or session errors were encountered. Strict-mode routing is fully operational.

**Updated 2026-06-26 (18U):** Performed post-enable monitoring checkpoint for strict tenant-resolution mode in production. Confirmed all 13 backend Lambdas maintain `TENANT_RESOLUTION_MODE = "multi"`. Verified exactly 1 tenant exists and verified 0.0 fallback/failed metrics and OK alarm states since Release 18T apply.

**Updated 2026-06-26 (19A):** Completed design planning for the second-tenant provisioning dry run, defining parameters and safety verification requirements.

**Updated 2026-06-26 (19B):** Ran `scripts/provision_tenant.py` in dry-run/no-write mode for `test_tenant_alpha`. Confirmed the output correctly builds the metadata record, audit record, Cognito templates, and rollback guidance without making any AWS writes. Resolved Unicode terminal printing encoding bugs. Verified no records were created in Cognito or DynamoDB, and confirmed the tenant count remains exactly 1 (`tog_and_dogs` only).

**Updated 2026-06-26 (19C):** Prepared and documented the final checkpoint and approval plan for the controlled creation of `test_tenant_alpha` (metadata-only) in the production DynamoDB table. Verified the exact CLI apply command parameters, scope of database writes, non-actions (no Cognito, Stripe, calendar, or email writes), and rollback/disable processes. Halted before execution.

**Updated 2026-06-26 (19D):** Executed `scripts/provision_tenant.py` in apply mode to create `test_tenant_alpha` (metadata-only) in production DynamoDB. Verified that the metadata record and audit record were written successfully, tenant count is now 2, and no Cognito, Google Calendar, or Stripe changes occurred. Confirmed `/admin` and `/platform-admin` remain fully operational with alarms in OK state.

**Updated 2026-06-26 (19E):** Performed read-only validation of Platform Admin second-tenant visibility. Verified both `tog_and_dogs` and `test_tenant_alpha` display correctly in the list view, detail view, and audit trails without modifying the existing tenant or triggering user/access changes.

**Updated 2026-06-26 (19F):** Completed Cognito owner user creation design planning, including group mapping rules and message suppression configuration.

**Updated 2026-06-26 (19G):** Prepared the final checkpoint and runbook for creating the Cognito owner user for `test_tenant_alpha`. Confirmed the environment pre-flight status (active tenant, strict resolution mode, group names, zero existing users) and specified the exact CLI commands, placeholders, and approval gates.
**Updated 2026-06-26 (19H):** Executed Cognito owner user creation for `test_tenant_alpha` using Cognito-generated temporary invitations. Manual validation of this user login failed due to tenant isolation defects. Remediation deployed and revalidated as PARTIAL PASS (Data Remediated, Display Pending) in Release 19M.

**Updated 2026-06-27 (19I):** Conducted read-only triage and defect source analysis for the four isolation issues. Identified that Google Calendar credentials, Cognito staff lists, and client lists lack tenant scoping (`custom:company_id` check), and the dashboard branding remains hardcoded on the frontend. Remediation planned and deployed in 19K-19M; data/access remediation verified as PASS, display branding remediation pending.

**Updated 2026-06-27 (19J):** Completed backend and API Gateway planning for tenant isolation remediation. Designed Cognito user list company ID checks and a dedicated `/admin/tenant-info` endpoint.

**Updated 2026-06-27 (19K):** Implemented backend tenant isolation fixes: gated Google Calendar to only allow the default tenant (`tog_and_dogs`); filtered Cognito lists (`/admin/staff` and `/admin/clients`) by the caller's tenant ID under strict mode; and built a safe authenticated `/admin/tenant-info` endpoint. Added 9 unit tests in `tests/backend/test_r19k_tenant_isolation.py` and verified 100% pass rate.

**Updated 2026-06-27 (19L):** Implemented frontend tenant display remediation. Integrated with `/admin/tenant-info` to fetch and render the correct brand names inside the admin header shell and user profile company fields. Replaced all hardcoded references to "Tog and Dogs" in administrative contexts with dynamically resolved values and fallbacks. Ran frontend Vite build and confirmed successful compilation.

**Updated 2026-06-27 (19M):** Deployed tenant isolation fixes to production. Ran Terraform apply to update all 13 Lambdas and API Gateway configurations; synchronized built Vite frontend files to S3; cleared CDN caches via CloudFront cache invalidation. Verified that the DynamoDB tenant configuration has exactly 2 records and all CloudWatch observability alarms remain OK. Matthew completed manual validation, confirming data/access isolation PASS. However, display branding failed manual verification (header and dropdown still show hardcoded Tog and Dogs brand names). Status updated to PARTIAL PASS / PENDING DISPLAY FIX.

**Updated 2026-06-27 (19N):** Implemented frontend tenant branding model cleanup. Replaced the hardcoded `Tog&Dogs` top-left product logo in `App.jsx` with a dynamic value (`<Tenant Display Name>: A Pet Business Platform`) that resolves for authenticated admin/platform routes. Replaced the admin header subtitle `Powered by Tog&Dogs` with `Powered by usmissionhero` in `AdminDashboard.jsx`. Rendered a minimal, tenant-aware admin footer on `/admin` and `/platform-admin` routes, while preserving the full `Tog&Dogs` marketing footer on public routes. Removed duplicate `/admin/tenant-info` fetch from `UserProfile.jsx` and replaced with prop-passing from the parent `AdminDashboard`. Frontend Vite build succeeded (`dist/assets/index-z7VYqP25.js`), deployed to S3 and CloudFront (`E35L00QPA2IRCY`), invalidation completed. Matthew performed manual validation (incognito session) — both `test_tenant_alpha` and `tog_and_dogs` checklists PASS. All tenant isolation and display branding defects from 19H/19I/19M are fully resolved.

**Updated 2026-06-28 (20C):** Executed controlled tenant disable and restore validation for `test_tenant_alpha`. Verified status transitions in DynamoDB, full audit trail logging for both actions, and verified `tog_and_dogs` remains active and unaffected. Documented finding that the `/admin/tenant-info` endpoint is not blocked at the backend level when a tenant is disabled (instead returning 200 with `subscription_status: "disabled"`), which relies on frontend enforcement. Recommended backend-level endpoint gating for future hardening.

**Updated 2026-06-28 (20E):** Implemented centralized backend disabled-tenant access enforcement. Added `require_active_tenant(event)` helper in `common/entitlement.py` and integrated it across 8 tenant-scoped handlers (`admin_handler.py`, `assignment_handler.py`, `cancellation_handler.py`, `device_handler.py`, `google_auth_handler.py`, `intake_handler.py`, `pet_handler.py`, `review_handler.py`). Configured `/admin/tenant-info` to return a safe minimal status (`company_id`, `display_name`, `subscription_status`, `is_access_allowed: false`, `is_blocked: true`) when the tenant is disabled. Created a new backend test suite with 14 tests in `tests/backend/test_r20e_disabled_tenant_enforcement.py` and verified 100% pass rate.


