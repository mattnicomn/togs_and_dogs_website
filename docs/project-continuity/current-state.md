# Current Project State

**Last Updated:** 2026-07-23 (Phase 1B.5B-A Staff Pet Editor Production Plan Prepared — Not Deployed)

---

## Production App

| Component | Status |
|-----------|--------|
| Web app (React/Vite) | ✅ Live at `toganddogs.usmissionhero.com` |
| Backend (Python/Lambda) | ✅ Deployed |
| API Gateway | ✅ Active — staff reset-password and set-temp-password routes added (22C) |
| DynamoDB | ✅ Single table, shared-tenant model |
| Google Calendar | ⚠️ Shared business connection — Disconnect button removed from UI (hotfix 2026-07-12); verify status in production (cascade fixed 18P; per-tenant isolation 21H) |
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

- Phase 1B.5A.1: My Pets Hotfix Production Deployment (✅ DEPLOYED — Awaiting Matthew Authenticated Validation — 2026-07-22)
- Phase 1B.5A.1: My Pets List and Status Hotfix (✅ COMPLETE LOCAL & DEPLOYED — 2026-07-22)
- Phase 1B.5A: Authoritative Client Drawer Pet Loading (⏳ DEPLOYED — Awaiting Matthew Authenticated Validation — 2026-07-21)
- Phase 1B.4A–E: Client Drawer Editor Consolidation (✅ PASS — Deployed & Manually Validated — 2026-07-21)
- Phase 1B.3: Client Pet Inventory and Management Detail UX (✅ PASS — Deployed & Hotfix Applied — Awaiting Matthew Authenticated Manual Smoke Validation — 2026-07-21)
- Phase 1B.2A: ClientPetIndex Query Cutover (✅ PASS — Deployed & Manually Validated — 2026-07-20)
- Phase 1B.2A: ClientPetIndex Query Cutover (Local Closeout) (✅ PASS — 2026-07-19)
- Hotfix: Google Calendar Disconnect Safeguard (✅ PASS — Deployed to Production (cumulative: includes 22ZA/22ZB/22ZC) — 2026-07-12)
- Phase 1A: Client/Household Backend Compatibility (✅ PASS — Deployed & Manually Validated — 2026-07-16)
- Phase 1B.1: Client Management Frontend List/Drawer (✅ PASS — Deployed & Production Validated — 2026-07-16)
- 22ZC: Dashboard Cards and Request List Mobile Layout (✅ PASS — Pre-Deploy, deployed via Hotfix — 2026-07-12)
- 22ZB: Profile Editor Mobile Layout (✅ PASS — Pre-Deploy, deployed via Hotfix — 2026-07-12)
- 22ZA: Responsive Foundation and Navigation (✅ PASS — Pre-Deploy, deployed via Hotfix — 2026-07-12)
- 22Z: Mobile Responsive UX Polish Detailed Plan (✅ Planning Complete — 2026-07-12)
- 22Y: Smoke Test Findings: Identity Action State and Google Calendar Disconnect Triage (✅ Planning Complete — 2026-07-11)
- 22X: Controlled Core Workflow Smoke Test Plan (✅ Planning Complete — 2026-07-11)
- 22W: Post-22V Operational Readiness and Core Workflow Validation Plan (✅ Planning Complete — 2026-07-11)
- 22V: Profile Editor Drawer and Client Bookings Display Fix Production Deployment (✅ PASS — Deployed & Validated — 2026-07-11)
- 22U: Client Portal My Bookings Date and Visit Window Display Fix Pre-Deploy (✅ PASS — Pre-Deploy, deployed via 22V — 2026-07-11)
- 22T: Client Portal My Bookings Date and Visit Window Display Integrity Triage (✅ Planning Complete (resolved via 22U/22V) — 2026-07-11)
- 22S: Profile Editor Drawer Portal and Viewport Overflow Fix Pre-Deploy (✅ PASS — Pre-Deploy, deployed via 22V — 2026-07-11)
- 22R: Profile Editor Drawer Stability Fix Production Deployment (❌ FAILED — Manual Validation FAILED — 2026-07-10)
- 22Q: Profile Editor Drawer Stability and Overlay Interaction Fix Pre-Deploy (✅ PASS — Pre-Deploy, deployed via 22R — 2026-07-10)
- 22P: Centralized Profile Editor MVP Production Deployment and Validation (❌ FAILED — Manual Validation FAILED — 2026-07-10)
- 22O: Pending Cancellation Records Review and Cleanup/Processing Plan (✅ Planning Complete — 2026-07-10)
- 22N: Production Release State Reconciliation After 22M Hotfix (✅ Documentation — 2026-07-10)
- 22M: Pending Cancellation Visibility Hotfix Production Deployment (✅ PASS — Deployed & Validated — 2026-07-10)
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

**Production deployment 22P/22R failed manual validation due to drawer stability and viewport scrollbar/overflow issues. Release 22V deployed the combined drawer fixes (22S) and client bookings date/window display fixes (22U) to production. Manual validation passed successfully. No hotfix/main branch divergence remains — production now runs from `main`. Matthew ran a controlled smoke test (Release 22X) and found three findings. Release 22Y completed a read-only triage of these findings, identifying Cognito password reset restrictions and API Gateway DELETE method deployment issues as root causes. Release 22ZA implemented the mobile responsive foundation and accessible slide-out navigation drawer (pre-deploy validated). Release 22ZB implemented the full-screen Profile Editor mobile sheet layout (pre-deploy validated). Release 22ZC added keyboard-accessible stat cards, responsive filter controls stacking, and accessible data-label column labels on mobile request cards (pre-deploy validated). Phase 1B.2A backend-only Lambda package apply completed successfully, deploying the pet creation is_active hardening code to production. Phase 1B.2A ClientPetIndex GSI-only apply completed successfully, creating the global secondary database index in production (index backfilled and status ACTIVE). Phase 1B.2A ClientPetIndex query cutover deployed to production on 2026-07-20 (0 added, 13 changed, 0 destroyed). All 13 Lambda functions verified Active/Successful with expected CodeSha256. Matthew authenticated manual smoke PASSED (admin login, Client Management page, client drawer, admin pet list). Phase 1B.3 frontend deployed to production with /my-pets route, card-click drawer interaction, accessible cards, and mobile bottom-sheet. Hook-order hotfix applied. Matthew confirmed production works. Phase 1B.3 COMPLETE and CLOSED. Phase 1B.4A–E Client Drawer Editor Consolidation deployed to production. Matthew confirmed drawer View/Edit/Create experience works correctly, inline editor retired, Staff Management unaffected. Phase 1B.4A–E COMPLETE and CLOSED. Phase 1B.4F–H remain deferred. Phase 1B.5 (Pet Management and Client–Pet Association) is active. Phase 1B.5A (Authoritative Client Drawer Pet Loading) deployed to production on 2026-07-21. Bundle changed from index-B-lRTVkt.js to index-B9b14KXI.js. CloudFront invalidation I5N3QUSW8OFBB5SU4UA5IJE302 completed. All 178 tests pass. Authenticated validation pending Matthew. Latest completed production release remains Phase 1B.4A–E until validation passes. Phase 1B.5A.1 (My Pets List and Status Hotfix) resolved the raw Missing petId in path error on /my-pets for unlinked/admin users and corrected the Active badge contrast in dark mode. Locally implemented and reviewed. Terraform apply completed (0 added, 13 changed, 0 destroyed) and web/dist synced to S3 with CloudFront invalidated (invalidation Completed). Authenticated validation remains pending Matthew. Phase 1B.5B and later slices have not started.**

**Next options:**
- Phase 1B.5B: Staff Pet Management in Client Management (planning complete, awaiting Matthew implementation policy approval)
- Phase 1B.5C: Customer self-service pet editing (deferred)
- Phase 1B.5D–E: Lifecycle safeguards and booking integration (deferred)
- Address remaining Phase 1B.4F–H staff drawer alignment (deferred, low priority)
- Begin Release 22ZD — Scheduler, Client Management, Platform Admin mobile polish (Phase 4 of 22Z plan)
- Address 22Y remediation items (Cognito password-reset state handling, Google Calendar disconnect API Gateway fix) in a separate release.
- Continue SaaS maturity priorities (blocked on EIN for Stripe live).
