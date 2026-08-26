# Backlog: SaaS Maturity and Multi-Business-Owner Readiness

**Status:** Active Backlog
**Owner:** Matthew
**Priority:** Strategic (future customer-tenant onboarding)
**Created:** 2026-06-19
**Source:** Release 16A Repository Readiness Audit

---

## Summary

The platform has an active primary tenant (`tog_and_dogs`) and an existing internal test tenant (`test_tenant_alpha`). Strict tenant resolution, tenant isolation, entitlement gates, provisioning tooling, branding, and per-tenant Google token isolation are deployed and validated. This backlog now tracks the product, billing, self-service, and operating work required before onboarding a future production/customer tenant. Further tenant provisioning remains approval-gated.

---

## Current Readiness for Future Customer-Tenant Onboarding

| # | Item | Status | Effort | Depends On |
|---|------|--------|--------|------------|
| 1 | Entitlement enforcement in handlers | ✅ Phase 1 active (17D/17I) | Done | — |
| 2 | Usage metering per tenant | ✅ Phase 2 active & validated (18N) | Done | #1 |
| 3 | Tenant provisioning workflow/tool | ✅ Test tenant created and validated (19D/19E); further provisioning approval-gated | Done | #1 |
| 4 | Cognito `custom:company_id` enforcement | ✅ Verified and isolated in production (19M) | Done | #3 |
| 5 | Strict tenant resolution | ✅ `TENANT_RESOLUTION_MODE=multi` active and validated (18T/18U) | Done | #4 |
| 6 | Per-tenant branding and access isolation | ✅ Validated (19M/19N/20F) | Done | #3–#5 |
| 7 | Google Calendar token isolation | ✅ Per-tenant token resolution deployed and validated (21H) | Done | #5 |
| 8 | Stripe subscription Checkout for new tenants | ⛔ Blocked by EIN and product/business approvals | High | EIN + pricing/payment decisions |
| 9 | Business owner billing dashboard | ⏸ Wait for subscription semantics | Medium | #8 |
| 10 | Pricing/signup page | ⛔ Blocked by product/pricing decision and payment direction | Medium | #8 |
| 11 | "Getting Started" guide for business owners | ✅ LOCALLY COMPLETE / `GUIDE_CORRECT` / COMMITTED / PUSHED / NOT PUBLIC | Low | — |
| 12 | Tenant-specific application landing and login-context agreement | 🟡 DOMAIN-1 accepted; B1A route bridge local/validated/not deployed | High | B1A deployment/login review + DOMAIN-2–DOMAIN-4 |

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tenant-resolution regression | Critical | Production Terraform and all 13 Lambdas use strict `TENANT_RESOLUTION_MODE=multi`, enabled in 18T and monitored in 18U. Missing/invalid tenant claims fail rather than silently using the compatibility fallback. Do not change the mode without explicit Matthew approval. |
| Premature customer-tenant onboarding | High | `test_tenant_alpha` is an internal validation tenant, not a customer onboarding precedent. Require explicit approval plus product, billing, security, and operating readiness for any further tenant. |
| Claim-valid identity has no deployed tenant-specific application landing | High | Do not declare the identity broken or bypass the gate through shared `/admin`. The local bridge must receive separate deployment approval and pass login isolation before Gate B1A. |

---

## Remaining Product and Operations Backlog

| # | Item | Status | Priority |
|---|------|--------|----------|
| 1 | EIN obtained + Stripe live verification | ⛔ Blocked (IRS and business approval) | High |
| 2 | Stripe subscription Checkout | ⛔ Blocked by EIN and product/business approvals | High |
| 3 | Business-owner billing dashboard | ⏸ Wait on subscription semantics | Medium |
| 4 | Pricing/signup | ⛔ Blocked by product/pricing decision and payment direction | High |
| 5 | Payment terms/refund policy published | ⚠️ Draft exists | Medium |
| 6 | Business-owner Getting Started guide | ✅ LOCALLY COMPLETE / `GUIDE_CORRECT` / COMMITTED / PUSHED / NOT PUBLIC | High |
| 7 | Self-service staff/client invites | 🧭 Requires product, security, and Cognito design | Medium |
| 8 | Ryan external testing | ✅ Android internal testing resumed; physical install confirmed; operational review completed (2026-08-15). Full historical smoke matrix not re-executed. | Medium |
| 9 | Apple Beta App Review outcome | ❓ UNKNOWN / NOT VERIFIED | Medium |
| 10 | Analytics dashboard | ❌ Not started; lower sequence | Low |
| 11 | AI-assisted onboarding | ❌ Not started; follow deterministic onboarding | Low |
| 12 | Video visit evidence | ❌ Not started | Low |
| 13 | Multi-location support | ❌ Not started | Future |
| 14 | Cross-platform services, scheduling & workflow alignment | ✅ A–C, C1, D1–D2, R1, W1, and O1 committed/pushed/not deployed; E1 implemented/validated/not deployed; D1–D2/W1/O1 not built or distributed; remaining E/F deferred | High |
| 15 | Control-plane / tenant-plane URL architecture | ✅ DOMAIN-1 ADR accepted; canonical infrastructure remains future | P0 |
| 16 | Canonical client onboarding workflow and completion state | ❌ Product/API parity gap documented | P1 |
| 17 | Web Request List / Visit Requests queue correction | ⚠️ Audit found predicate, counter, navigation, and duplicate-fetch risks | P1 |
| 18 | Mobile Dashboard exact destination filters | ⚠️ Five cards are pressable in source but counts/targets need refinement; D1 not in current builds | P3 |
| 19 | Mobile bottom-navigation inset handling | ⚠️ Fixed tab height/padding does not derive from safe-area/system insets | P3 |

---

## Platform Tenant Management Control Plane Backlog (PTM)

**Authoritative Specification:** `docs/planning/platform-tenant-management-control-plane.md`

| Stage | Scope | Status | Priority |
|-------|-------|--------|----------|
| PTM-0 | Control Plane Architecture & Source-of-Truth Reconciliation (Cognito role groups vs `custom:company_id`, lifecycle states, app client policy) | ✅ Specification Approved (2026-08-25) | P0 |
| PTM-1 | Read-Only Tenant Directory Enhancement (`display_name`, `company_id`, `slug`, `lifecycle_state`, `owner_count`, `active_staff`) | Backlog Specification | P0 |
| PTM-2 | Read-Only Tenant Details View (7 sections: Overview, Routing, Owners/Users, Subscriptions, Onboarding, Health, Audit) | Backlog Specification | P0 |
| PTM-3 | Routing & Domain Visibility (Slug mapping, generated subdomain status, custom domain verification) | Backlog Specification | P1 |
| PTM-4 | User & Role Membership Visibility (Cognito `custom:company_id` user listing, identity status, role groups) | Backlog Specification | P1 |
| PTM-5 | Subscription & Entitlement Visibility (Active clients, monthly bookings, staff seats vs. plan limits) | Backlog Specification | P1 |
| PTM-6 | Onboarding Orchestrator Integration (Connect Preview V1 to Directory with approval checklist) | Backlog Specification | P1 |
| PTM-7 | Enhanced Platform Audit History (Target tenant filtering, actor filtering, date range controls) | Backlog Specification | P1 |
| PTM-8 | Controlled Tenant Creation (Approval-gated backend creation handler `POST /platform/tenants`) | Backlog / Approval-Gated | P2 |
| PTM-9 | Controlled Tenant Lifecycle Mutations (`ONBOARDING` -> `ACTIVE` -> `SUSPENDED` -> `ARCHIVED`) | Backlog / Approval-Gated | P2 |
| PTM-10 | Generated Tenant Subdomains (`<tenant-slug>.toganddogs.usmissionhero.com` wildcard routing) | Backlog / Infrastructure Deferred | P2 |
| PTM-11 | Custom Business Domains (Verified custom domain onboarding with ACM SSL/TLS) | Backlog / Infrastructure Deferred | P2 |
| PTM-12 | Enterprise SSO & IdP Extensions (Dedicated Cognito app clients / SAML 2.0 / OIDC integrations) | Backlog / Enterprise Deferred | P2 |

*Note: PTM-0, PTM-1, and PTM-2 represent the minimum required control-plane capabilities before onboarding any real second customer tenant. `test_tenant_alpha` remains an internal validation tenant only.*

---

## SaaS Control-Plane and Tenant-Domain Backlog

**Authoritative design:** `docs/planning/tenant-access-client-onboarding-operational-workflow-alignment.md`

| Stage | Scope | Status | Priority |
|-------|-------|--------|----------|
| DOMAIN-1 | Decide `platform.toganddogs.usmissionhero.com`, `<tenant-slug>.toganddogs.usmissionhero.com`, slug rules, compatibility-host disposition, and threat model | ✅ ADR accepted 2026-08-24 | P0 |
| B1A-ROUTE | Bounded `/t/:tenantSlug/admin` bridge with server registry, active-tenant/claim agreement, and fail-closed Web bootstrap | ✅ Backend & Web v2 Deployed | P0 |
| DOMAIN-2 | Canonical host-derived expected-tenant resolver plus generalized persisted registry/bootstrap | B1A route deployed; canonical host work not implemented | P0 |
| DOMAIN-3 | Wildcard Route53/ACM/CloudFront tenant support | Not implemented; no infrastructure change authorized | P2 |
| DOMAIN-4 | Tenant-specific login, invitation, callback, logout, recovery, and deep-link routing | Not implemented | P2 |
| DOMAIN-5 | Move Platform Admin to the control hostname and remove it from ordinary tenant navigation | Not implemented | P2 |
| DOMAIN-6 | Provision and validate a unique DNS-safe tenant slug during approved onboarding | Not implemented | P4 |
| DOMAIN-7 | Optional verified custom business domains | Deferred | P4 |

Gate B1A does not need to wait for DOMAIN-3 wildcard delivery. The bounded route is deployed to production (Backend v3 and Web v2). ROUTE-GATE-C / B1A-LOGIN isolation validation remains separately blocked and unapproved.

---


## Cross-Platform Services, Scheduling & Workflow Alignment

**Source:** Ryan operational platform review (2026-08-15)
**Status:** Slices A–C, C1, D1–D2, R1 Hardening, W1, and O1 Committed / Pushed / Not Deployed; E1 Implemented / Validated / Not Deployed; D1–D2/W1/O1 Not Built or Distributed; Remaining Slice E and Slice F Deferred

### Target Service Model

| Service | Duration | Visits/Day | Notes |
|---------|----------|-----------|-------|
| 20-Minute Walk | 20 min | — | Exactly one canonical window applies to every selected date; replaces legacy 30-min walk for new bookings |
| Check-In | 30 min | 1, 2, or 3 | Selectable visits per day |
| Overnight | 600 min nominal | — | Fixed local 21:00→07:00 following date; O1 committed/pushed/not deployed; pricing TBD |

### Time Windows

| ID | Label | Hours |
|----|-------|-------|
| MORNING | Morning | 06:30–09:30 |
| MIDDAY | Mid-day | 10:30–15:30 |
| EVENING | Evening | 18:00–21:30 |

### Implementation Slices

| Slice | Scope | Status | Dependencies |
|-------|-------|--------|-------------|
| A | Canonical service/time-window contract update | Committed / Pushed / Not Deployed | — |
| B | Backend booking/job/calendar support | Committed / Pushed / Not Deployed | A |
| C | Web customer intake Check-In parity | Committed / Pushed / Not Deployed | A, B |
| C1 | Web Admin Check-In creation parity | Committed / Pushed / Not Deployed | A, B, C |
| D1 | Mobile dashboard navigation | Committed / Pushed / Not Built / Not Distributed / Not Deployed | A, B |
| D2 | Mobile service-selection/intake parity | Committed / Pushed / Not Built / Not Distributed / Not Deployed | A, B |
| R1 | Scheduler parity + Check-In resiliency hardening | Committed / Pushed / Not Deployed | A–C, C1, D1–D2 |
| W1 | 20-Minute Walk canonical scheduling windows | Committed / Pushed / Not Deployed | A–C1, D2, R1 |
| O1 | Overnight fixed 21:00→07:00 next-day scheduling | Committed / Pushed / Not Deployed | A–C1, D2, R1, W1 |
| E1 | Web Admin guided assignment and Calendar actions | Implemented / Validated / Not Deployed | C, C1, R1 |
| E | Remaining workflow next-action simplification | Partially Complete / Deferred | E1, D1, D2 |
| F | Public website content alignment | Not Started | Ryan pricing decisions |

### Open Business Decisions

1. Price for Check-In 1 visit/day
2. Confirm price for Check-In 2 visits/day ($45/day per public site)
3. Price for Check-In 3 visits/day
4. Whether 60-Minute Walk remains available or is retired
5. Whether Drop-In 1HR/3HR remain available for new bookings
6. Whether $35 deposit is still current
7. In-app pricing automation vs admin-managed Stripe links

---

## Current Platform Maturity

| Dimension | Score | Notes |
|-----------|-------|-------|
| Core operations | 9/10 | Booking, scheduling, assignment, completion all working |
| Tenant isolation | 9/10 | Strict multi mode, entitlements, two-tenant isolation, branding, and disabled-tenant enforcement validated |
| Payments | 6/10 | Sandbox-complete; live blocked on EIN |
| Mobile | 8/10 | Corrected iOS Build 6 and Android versionCode 4 internally distributed and revalidated; Ryan's physical Android install and operational review are confirmed; full historical smoke matrix was not rerun |
| Documentation | 8/10 | Ops guides, policies (draft), release notes comprehensive |
| Maintainability | 5/10 | Requires developer/Matthew for many admin tasks |
| Self-service | 3/10 | Web customer password recovery is production deployed and Cognito E2E validated; onboarding, invites, billing, and settings remain limited |

---

## Future Customer-Tenant Approval Gates

The internal test tenant already exists. Do not provision another tenant or treat `test_tenant_alpha` as a production customer until:

1. ✅ Strict tenant resolution and isolation remain active and healthy (18T/18U/19M/20F).
2. ✅ Platform Admin and provisioning tooling remain validated (17P/17W/19D/19E).
3. ✅ Google Calendar per-tenant token isolation remains deployed and validated (21H).
4. ⛔ Matthew explicitly approves the specific tenant and onboarding scope.
5. ⛔ Product tier, pricing, signup, subscription, support, and rollback semantics are approved.
6. ⛔ Security/Cognito design is approved for any self-service invite path.
7. ⚠️ Billing activation remains blocked by EIN where live subscription/payment behavior is required.
8. ✅ Deterministic Getting Started documentation is locally complete, independently reviewed (`GUIDE_CORRECT`), committed, and pushed as repository documentation; it is not publicly published.
9. ⛔ A normal tenant-specific owner landing and fail-closed expected-tenant/claim agreement are implemented and validated. `test_tenant_alpha` currently lacks this surface, so Gate B1A remains blocked.

The dated update log below is historical chronology. Statements such as “strict mode remains disabled” or “no second tenant exists” were accurate at those checkpoints and are superseded by later entries.

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

**Updated 2026-07-02 (20F):** Deployed centralized backend disabled-tenant access enforcement to production. Successfully ran pre-deploy checks, executed targeted test verification (all 100+ backend tests passed), ran production Terraform plan/apply, validated 403 TenantDisabled blocks, verified minimal tenant-info responses, validated active tenant isolation, confirmed audit logs, and verified CloudWatch alarms remain OK. Controlled disable and restore validation complete.

**Updated 2026-07-02 (21B):** Implemented and deployed frontend-only unconfigured-state calendar UI cleanup for non-default tenants. Modified `AdminDashboard.jsx` to gate the connection handler (early return if `company_id !== 'tog_and_dogs'`), hide the top Google Calendar warning banner, and render a provider-neutral unconfigured settings card (`Calendar Integration` with status `NOT CONFIGURED`) for non-default tenants (e.g. `test_tenant_alpha`), while preserving full Google Calendar integrations for the default tenant. Ran Vite production build and deployed to S3/CloudFront. Smoke validation complete; manual checklist pending.

**Updated 2026-07-02 (21D):** Implemented tenant calendar provider metadata defaults in code. Added `get_tenant_calendar_config` in `calendar_metadata.py` to derive calendar providers, statuses, and capabilities with defaults for `tog_and_dogs` (Google) and other tenants (None). Integrated into `/admin/tenant-info` and Platform Admin detail responses. Updated `AdminDashboard.jsx` to use metadata `calendar_provider` checks rather than hardcoded company ID checks, and updated `PlatformTenantDetail.jsx` to display these metadata attributes. Created 7 new tests under `test_r21d_calendar_metadata_defaults.py` and verified 100% pass across all tests.

**Updated 2026-07-02 (21E):** Deployed tenant calendar provider metadata defaults code and frontend assets to production. Ran Terraform apply to update all 13 backend Lambda function packages with the new metadata helper and endpoint updates. Synced the built Vite frontend assets to S3 and invalidated the CloudFront CDN cache distribution `E35L00QPA2IRCY`. Confirmed live index serves the new 21E bundle. All automated smoke validations passed. Matthew completed manual validation and confirmed checklists pass.

**Updated 2026-07-09 (21G):** Implemented backend per-tenant Google token secret resolution and scoped token storage callback. Resolves token paths dynamically using metadata config or fallback legacy defaults. Restricts callback/initiation endpoints for tenants without Google enabled, and shields the legacy global secret fallback from deletions/mutations on disconnect. Created 8 new unit tests in `test_r21g_google_token_isolation.py` and verified all 110 backend tests pass. Matthew completed manual validation and confirmed checklists pass.

**Updated 2026-07-09 (21H):** Deployed the Google Calendar per-tenant token isolation backend Lambda package updates to production. Ran Terraform plan/apply (13 Lambda resources updated in-place) and completed automated validation of the default tenant compatibility, second tenant token isolation, Google OAuth connection gating, and platform admin detail response mappings. Checked metric alarms (0 active alarms). Matthew completed manual validation (both checklists pass) and closed the per-tenant token isolation release.

**Updated 2026-07-09 (22B):** Implemented backend resend-invite shadowing import fix and added corresponding test coverage. Added the missing staff password reset and set-temporary-password endpoints to API Gateway and CORS mappings in Terraform. Resolved frontend staff card click event bubbling by stopping click propagation on all card action buttons. Polished public care request validation UX on Step 2 to render inline date validation errors and scroll-to-focus on missing inputs instead of browser alerts. All tests and Vite builds compiled successfully.

**Updated 2026-07-09 (22H):** Implemented read-only backend and frontend support to safely detect and display staff login identity states in Staff Management. Derived status fields (`identity_state`, `is_orphaned_identity`, etc.) are returned in `GET /admin/staff` and mapped to dynamic access badges and warning labels on the frontend, with safety disabled actions for orphaned profiles (such as the legacy `USmissionhero` profile). Created 7 new unit tests in `test_r22h_orphaned_identity.py` and confirmed all 22 tests pass.

**Updated 2026-07-10 (22I):** Deployed the orphaned identity detection and frontend warning/action-disabling safeguards to production. Ran pre-deploy tests (all 32 passed, including the new protected orphaned user coverage), executed Terraform apply (13 Lambdas updated, API Gateway deployment replaced), compiled and deployed the React frontend build to S3, and invalidated the CloudFront cache. Verified that the `USmissionhero` profile is dynamically detected and rendered as an "Orphaned Login" with disabled account actions, while other valid staff profiles remain active and unaffected.

**Updated 2026-07-10 (22L):** Implemented the pending cancellation request admin visibility fix pre-deploy. Redefined frontend cancellation helpers and active filter predicates in `AdminDashboard.jsx` to ensure client `CANCELLATION_REQUESTED` bookings appear in "Needs Action" and "All Active" lists, are correctly counted, display as "Cancellation Requested" in an urgent red badge, and expose a dropdown menu option to Approve/Deny reviews. Compiled successfully via Vite. Standalone pytest runs are verified green.

**Updated 2026-07-10 (22P):** Deployed the Centralized Profile Editor MVP (Release 22J) from `main` to production. Staff cards are simplified — direct risky account/security action buttons removed from card surfaces. Each card now has a Manage button that opens a centralized Profile Editor side drawer with structured sections (Profile Details, Login Identity, Tenant & Role, Account Security, Protected Account Guardrails, Danger Zone). Protected platform admin and orphaned login (USmissionhero) guardrails are enforced. The 22M production/main divergence is fully resolved. Matthew manually cleared the 2 pending cancellation records (Joey Rockwell, TestPet_ScenarioB) prior to this deployment.

**Updated 2026-08-11 (Continuity reconciliation):** Removed the duplicated backlog copy and reconciled the live forward-looking state. Strict `multi` mode is active and validated; `test_tenant_alpha` already exists as an internal test tenant; corrected iOS Build 6 and Android versionCode 4 are internally distributed; Ryan remains paused; and Apple Beta App Review outcome remains unknown/not verified. The Getting Started guide is ready now. Stripe Checkout, billing dashboard, pricing/signup, self-service invites, analytics, AI onboarding, and multi-location remain incomplete under the approval and sequencing boundaries above. Web customer password recovery is locally complete, committed, and pushed, but not deployed.

**Updated 2026-08-11 (Business-owner guide closeout):** The authoritative repository-only Business Owner Getting Started guide is locally complete at `docs/operations/business-owner-getting-started.md`, independently reviewed by Kiro (`GUIDE_CORRECT`), committed, and pushed. It documents the current assisted onboarding model, role and workflow boundaries, payment/mobile limitations, self-service gap matrix, and ranked automation opportunities. The guide is not publicly published. This documentation closeout does not authorize tenant/user creation, deployment, live payments, mobile distribution, or self-service onboarding.

**Updated 2026-08-11 (Preview V1 Onboarding Orchestrator):** A preview-only Platform Admin tenant-onboarding orchestrator is committed and pushed (not deployed). It provides deterministic validation, conflict detection, metadata preview, and approval checklist generation through a technically enforced read-only Lambda. No Apply/Create capability exists in V1. Persistent onboarding requests, approval workflow, first-owner provisioning, Calendar onboarding, Stripe subscriptions, and public signup remain deferred and approval-gated. The assisted tenant-onboarding model now has validated preview tooling but remains non-self-service.

**Updated 2026-08-17 (Ryan Slice C Web intake parity):** Web customer intake is aligned to the canonical active/new-booking-eligible service model and generated Check-In visits/day/window metadata. Focused 18/18, full Web 99/99 legacy plus 271/271 Vitest, and the Vite build pass. Independent review returned `RYAN_SLICE_C_IMPLEMENTATION_CORRECT`; Slice C is committed and pushed but not deployed. Admin Check-In booking creation, Walk scheduling, Overnight timing, pricing, workflow simplification, public-site alignment, and all cross-platform deployment/distribution remain separately gated.

**Updated 2026-08-17 (Ryan Slice C1 Admin creation parity):** The existing owner/admin New Visit modal now derives the complete broader admin catalog from generated service metadata and can submit contract-valid Check-In visits/day plus ordered multi-window semantics for existing/offline clients. It preserves immediate `APPROVED` / `VISIT_BOOKING` behavior, client/pet/date/sitter fields, tenant/RBAC boundaries, legacy admin services, notification behavior, and the Slice B jobs/Calendar path. Admin 13/13, combined C1 + Slice C 31/31, full Web 280/280 Vitest plus 99/99 legacy, build, and Slice B backend 31/31 pass. Independent review returned `RYAN_SLICE_C1_IMPLEMENTATION_CORRECT`; C1 is committed and pushed but not deployed. Walk/Overnight policy, pricing, E/F, and deployment remain gated.

**Updated 2026-08-17 (Ryan release-readiness hardening R1):** MasterScheduler filter membership now consumes the complete generated canonical service catalog while retaining operational legacy services and exact filtering. New real-handler tests cover interrupted Check-In batch retry convergence, multi-window cancellation/Calendar-ID deduplication, and six-child assignment with booking-level notification batching. Independent review returned `RYAN_RELEASE_READINESS_HARDENING_R1_IMPLEMENTATION_CORRECT`. Final validation: R1 backend 3/3, Scheduler 16/16, Slice C 18/18, C1 13/13, Web 281/281 plus legacy 99/99 and build, and Mobile typecheck/focused/full regression pass. R1 is committed and pushed but not deployed. W1 subsequently resolved new 20-Minute Walk scheduling; E/F, Overnight, and pricing decisions remain gated.

**Updated 2026-08-17 (Ryan W1 Walk canonical scheduling):** Matthew and Ryan approved exactly one canonical Morning, Mid-day, or Evening window for each new 20-Minute Walk request, applied uniformly to every selected date. The committed and pushed implementation aligns the shared/generated contract, new-write validation, one-child-per-date and 20-minute Calendar semantics, Web customer/Admin, Mobile, and MasterScheduler display while preserving legacy reads and booking-level notifications. Independent review returned `RYAN_W1_WALK_CANONICAL_SCHEDULING_IMPLEMENTATION_CORRECT`. W1 is not deployed, built for Mobile, distributed, or received by Ryan. Overnight, pricing, deposits, legacy retirement, Stripe, E, and F remain gated.

**Updated 2026-08-18 (Ryan O1 Overnight fixed scheduling):** Matthew approved fixed local 21:00 on each selected Overnight start-date through local 07:00 the following date, with 600-minute nominal duration and no scheduling selector. O1 is committed, pushed, and not deployed (commit `46bb6b87`). Independently reviewed (Kiro: `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_IMPLEMENTATION_CORRECT`). The shared/generated contract, backend new-write marker and rejection boundary, one deterministic child per selected date, DST-safe local Calendar event, Web customer/Admin, Mobile, and MasterScheduler are aligned. Unmarked historical records retain legacy 720-minute/all-day or exact-time compatibility. Pricing, deposits, legacy retirement, Stripe, E/F, deployment, and Mobile build/distribution remain gated.

**Updated 2026-08-19 (Ryan Slice E1 Web Admin guided actions):** E1 is implemented and validated locally but not deployed. A pure resolver distinguishes backend status transitions from two UI handoffs: ready-for-staffing `APPROVED`/`BOOKED`/`JOB_CREATED` records open the existing **Assign Sitter** path, while assigned/scheduled records open the existing Scheduler through **View in Calendar**. `ASSIGN` and `VIEW_CALENDAR` cannot enter `reviewRequest`; assignment payload, Complete, Cancel, intake approval, secondary actions, RBAC, notifications, and Calendar behavior are preserved. Remaining Slice E intake Approve & Schedule and Mobile Start Visit → Complete Visit require separate design/approval.

**Updated 2026-08-20 (Ryan Slice E2 intake approval to Scheduler handoff):** E2 is implemented and validated locally but not deployed. Customer-intake **Approve & Open Scheduler** performs exactly one canonical `APPROVED` operation through existing `/admin/review`, never calls `createAdminBooking()`, and never retries approval automatically. It boundedly refetches the same `request_id` immediately plus at most four more times at 500 ms intervals, merges the refreshed parent request, recognizes `job_id` or non-empty `job_ids`, and opens the existing Scheduler. Timeout does not roll back approval and shows a refresh-before-assigning warning; approval failure does not poll or navigate. The handoff does not assign a sitter or complete scheduling, and future-date visibility remains governed by unchanged Scheduler date filters. Focused 24/24, required 86/86, full Web 310/310 plus legacy 99/99, build, baseline-equivalent lint, and diff check pass. Remaining Slice E work is Mobile Start Visit → Complete Visit, which still lacks an approved canonical `IN_PROGRESS` transition.

**Updated 2026-08-20 (Ryan Slice E3A child Start contract and occurrence read model):** E3A is implemented and validated locally but not deployed. Authenticated `POST /admin/job/start` conditionally and atomically records authoritative server Start/actor/update metadata plus one `JOB_STARTED` audit event on one `ASSIGNED` child, while preserving child and parent canonical status and assignment. Replays return the original timestamp; concurrent losers resolve the persisted winner. `IN_PROGRESS` remains non-canonical, and Start has no Calendar or notification side effects. Existing exact-request reads now expose distinct, deterministically ordered Walk, Check-In date×window, and Overnight children with assignment, schedule, Start, and completion metadata; legacy singular `job_id` and missing optional fields remain safe without migration. Complete remains compatible without prior Start. Focused 24/24, affected backend 137/137, exact-checkpoint full-backend comparison adds 24 passes with the same 100 failures, full Web 310/310 plus legacy 99/99/build, and full Mobile 128/128/typecheck pass. Mobile Start UI is not included; E3B and product timing/correction/visibility policy remain future and separately gated.

**Updated 2026-08-20 (Ryan Slice E3B Mobile occurrence-safe workflow):** Mobile now consumes authoritative E3A child occurrences, keeps multi-window Check-In children distinct, starts and completes the exact child, reconciles ambiguous Start by authoritative refetch, and blocks unsafe parent-wide Complete. Singular legacy child identity remains compatible; ambiguous legacy multi-child identity requires refresh. Full Mobile 132/132 and TypeScript pass. E3B is not deployed and is not included in current internal builds; no build or distribution occurred.

**Updated 2026-08-20 (Ryan Slice E3B.1 Mobile visit workflow safety remediation):** E3B.1 is implemented and validated locally but not deployed or included in current internal builds. Start and Complete now share one authoritative child-ID resolver: occurrence identity wins, route/occurrence or parent/occurrence mismatch fails safe, singular legacy identity works without a route ID, and ambiguous multi-child identity remains blocked. A synchronous shared visit-mutation lock prevents duplicate immediate Start and Start/Complete races, while mounted/request-sequence guards prevent stale async results from updating an obsolete screen. Exact-hydration failure now retains safely known parent date/window visibility as distinct refresh-required, non-actionable placeholders with no guessed IDs. Existing E3A/E3B status, Calendar, notification, and Complete semantics are unchanged; 1 + N Mobile hydration remains a future optimization. Focused E3B.1 19/19, full Mobile 148/148, TypeScript, shared validators, and E3A 24/24 pass. No build, distribution, or deployment occurred.
