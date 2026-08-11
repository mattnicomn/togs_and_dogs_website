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

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tenant-resolution regression | Critical | Production Terraform and all 13 Lambdas use strict `TENANT_RESOLUTION_MODE=multi`, enabled in 18T and monitored in 18U. Missing/invalid tenant claims fail rather than silently using the compatibility fallback. Do not change the mode without explicit Matthew approval. |
| Premature customer-tenant onboarding | High | `test_tenant_alpha` is an internal validation tenant, not a customer onboarding precedent. Require explicit approval plus product, billing, security, and operating readiness for any further tenant. |

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
| 8 | Ryan external testing | ⏸ Paused; requires explicit Matthew approval | Medium |
| 9 | Apple Beta App Review outcome | ❓ UNKNOWN / NOT VERIFIED | Medium |
| 10 | Analytics dashboard | ❌ Not started; lower sequence | Low |
| 11 | AI-assisted onboarding | ❌ Not started; follow deterministic onboarding | Low |
| 12 | Video visit evidence | ❌ Not started | Low |
| 13 | Multi-location support | ❌ Not started | Future |

---

## Current Platform Maturity

| Dimension | Score | Notes |
|-----------|-------|-------|
| Core operations | 9/10 | Booking, scheduling, assignment, completion all working |
| Tenant isolation | 9/10 | Strict multi mode, entitlements, two-tenant isolation, branding, and disabled-tenant enforcement validated |
| Payments | 6/10 | Sandbox-complete; live blocked on EIN |
| Mobile | 8/10 | Corrected iOS Build 6 and Android versionCode 4 internally distributed and revalidated; physical Android remains unconfirmed; Ryan paused |
| Documentation | 8/10 | Ops guides, policies (draft), release notes comprehensive |
| Maintainability | 5/10 | Requires developer/Matthew for many admin tasks |
| Self-service | 3/10 | Web customer password recovery is locally complete but not deployed; onboarding, invites, billing, and settings remain limited |

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
