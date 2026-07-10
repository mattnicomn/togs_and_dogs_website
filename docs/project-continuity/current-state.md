# Current Project State

**Last Updated:** 2026-07-10 (Release 22L)

---

## Production App

| Component | Status |
|-----------|--------|
| Web app (React/Vite) | ✅ Live at `toganddogs.usmissionhero.com` |
| Backend (Python/Lambda) | ✅ Deployed |
| API Gateway | ✅ Active — staff reset-password and set-temp-password routes added (22C) |
| DynamoDB | ✅ Single table, shared-tenant model |
| Google Calendar | ✅ Connected (fixed in 18G, cancellation cascade fixed in 18P) |
| Postmark email | ✅ Active (notifications, payment emails) |

## Mobile / TestFlight

| Item | Status |
|------|--------|
| Framework | Expo / React Native |
| Latest build | 1.0.0 (4) — Internal TestFlight |
| Internal tester (Matthew) | ✅ Active |
| External tester (Ryan) | ❌ Paused (deferred to 19-series) |
| Apple Beta App Review | Submitted (15J), outcome pending/unknown |
| Public App Store | ❌ Not submitted, not approved |

## Stripe / Payments

| Item | Status |
|------|--------|
| Sandbox payment workflow | ✅ Fully validated (12L–14I) |
| Live Stripe mode | ❌ Blocked (usmissionhero LLC EIN pending) |
| Admin payment link UX | ✅ Deployed |
| Payment email sending | ✅ Deployed |
| Payment terms draft | ✅ Written (not published to website) |

## Tenant / Multi-Business Readiness

| Item | Status |
|------|--------|
| Tenant isolation (company_id enforcement) | ✅ Active in all handlers (11E) |
| Entitlement enforcement Phase 1 | ✅ Active (export, calendar, staff limit) |
| Entitlement enforcement Phase 2 | ✅ Deployed (client limit, monthly booking counter) — 18L |
| Platform Admin UI | ✅ Deployed (/platform-admin) |
| Platform audit trail | ✅ Working |
| Cognito custom:company_id | ✅ Deployed & verified in production (19M) |
| TENANT_RESOLUTION_MODE | ✅ Enabled (strict `multi` mode active — 18T validated) |
| Strict-mode observation | ✅ Post-enable monitoring complete (18U — PASS) |
| Second tenant | ✅ Created & Validated in Platform Admin (19E) |
| Tenant provisioning script | ✅ Dry run validated (19B) |
| Tenant display branding | ✅ Dynamic brand name, shell logo, and footer separated by route (19N pre-deploy) |
| Tenant disable & restore | ✅ Gated & Validated in Production (20F — PASS) |
| Google Calendar Per-Tenant Token Isolation | ✅ Deployed & Validated (21H — PASS) |

## Current Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| EIN unavailable | Live Stripe payments blocked | Matthew (IRS) |
| Ryan testing paused | Cannot validate real staff workflow externally | Decision (19-series) |

## Latest Completed Releases

- 22L: Pending Cancellation Request Admin Visibility Fix Pre-Deploy (✅ PASS — Pre-Deploy — 2026-07-10)
- 22J: Centralized Profile Editor MVP Pre-Deploy (✅ PASS — Pre-Deploy — 2026-07-10)
- 22I: Orphaned Identity Detection Production Deployment and Validation (✅ PASS — Deployed & Validated — 2026-07-10)
- 22H: Orphaned Identity Detection Backend/Frontend Pre-Deploy (✅ PASS — Pre-Deploy — 2026-07-09)
- 22E: Care Request Validation UX Polish Production Deployment (✅ PASS — Manually Validated — 2026-07-09)
- 22D: Care Request Date Validation Copy and Auto-Fill UX Polish (✅ PASS — Manually Validated — 2026-07-09)
- 22C: Immediate Identity Action and Care Request Validation Fixes Production Deployment (⚠️ PARTIALLY VALIDATED — 2026-07-09)
- 22B: Immediate Identity Action and Care Request Validation Fixes (✅ PASS — Pre-Deploy / Deployed via 22C 2026-07-09)
- 22A: Identity/Profile Management and Care Request Validation Defect Triage (✅ PASS — 2026-07-09)
- 21H: Google Per-Tenant Token Isolation Production Deployment and Validation (✅ PASS — Manually Validated 2026-07-09)
- 21G: Google Per-Tenant Token Isolation Implementation (✅ PASS — 2026-07-02)
- 21E: Calendar Metadata Defaults Production Deployment and Validation (✅ PASS — Manually Validated 2026-07-02)
- 21D: Tenant Calendar Provider Metadata Defaults Implementation (✅ PASS — 2026-07-02)
- 21B: Calendar UI Unconfigured-State Cleanup (✅ PASS — Manually Validated 2026-07-02)
- 20F: Disabled Tenant Backend Access Enforcement Production Deployment and Validation (✅ PASS — Manually Validated 2026-07-02)
- 20E: Disabled Tenant Backend Access Enforcement Implementation (✅ PASS — 2026-06-28)
- 20C: Controlled Tenant Disable and Restore Validation (✅ PASS — 2026-06-28)
- 19N: Tenant Branding Model Cleanup (✅ PASS — Manually Validated 2026-06-27)
- 19M: Production Deployment and Tenant Isolation Revalidation (✅ PASS — display defect resolved by Release 19N)
- 19L: Frontend Tenant Display Remediation (Pre-Deploy Complete)
- 19K: Backend Tenant Isolation Remediation Plan (Pre-Deploy Complete)
- 19J: Second-Tenant Owner Login Isolation Remediation Planning
- 19I: Second-tenant owner login isolation defect triage (PARTIAL PASS - Data Remediated)
- 19H: Controlled second-tenant owner Cognito user creation (PARTIAL PASS - Data Remediated)
- 19G: Second-tenant owner Cognito user creation approval runbook
- 19E: Platform Admin second-tenant visibility validation
- 19D: Controlled second-tenant metadata creation
- 19B: Tenant provisioning script dry run
- 18U: Post-enable strict-mode monitoring checkpoint (PASS)

## Next Recommended Action
 
 **Next: Release 22M — Centralized Profile Editor MVP and Cancellation Visibility Production Deployment and Validation** — Build and deploy the Release 22J centralized staff Profile Editor and Release 22L pending cancellation visibility fix to production, execute S3 sync and CDN cache invalidations, and validate.
