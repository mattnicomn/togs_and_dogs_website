# Current Project State

**Last Updated:** 2026-07-30 (Phase 1B.5C-B and 1B.5C-C Production Validation Closed)

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

## Active Local Work / Pending Review

- Phase 1B.5C-A: Customer Pet Editing — Production Deployment (✅ VALIDATED AND CLOSED — 2026-07-30)
  - Applied saved Terraform plan (`phase-1b5c-a-customer-pet-editing.tfplan`, deployment ID `ec4xqi`, 8 added, 14 changed, 1 destroyed).
  - Backend: All 13 Lambda functions updated with CodeSha256 `aUEukME39YjTvpZN/vml1i2QOrP5CxN4Rb+3NiWRuSM=`. `/client/pets/{petId}` (PUT, Cognito auth) active.
  - Frontend: `web/dist` synced to S3 (`togs-and-dogs-prod-toganddogs-hosting`) and CloudFront invalidated (`I4LTEENIVINRH6DDP7URES23EM`).
  - Customer validation PASSED. Admin regression (Phase 1B.5C-A.1) deployed and validated.
  - See: `docs/release-notes/phase-1b5c-a-customer-pet-editing-production-deployment.md`
- Phase 1B.5C-A.1: Admin Pet Care Field Visibility Hotfix (✅ VALIDATED AND CLOSED — 2026-07-30)
  - Resolved admin drawer `UI_RENDERING_GAP`: added `age`, `care_instructions`, and `feeding_notes` rendering.
  - Added abbreviated Pet ID labels for duplicate-name disambiguation.
  - Deployed as part of Phase 1B.5C-B+C frontend deployment (commit `510b063`). Matthew authenticated validation PASSED.
  - See: `docs/release-notes/phase-1b5c-a1-admin-pet-care-field-visibility-hotfix.md`
- Phase 1B.5C-B: Staff Limit Active-Count Entitlement Fix (✅ VALIDATED AND CLOSED — 2026-07-30)
  - Changed `max_staff` entitlement check to count only active staff (`is_active != False`).
  - Deployed as part of Phase 1B.5C-B+C combined deployment (commit `510b063`, backend Terraform apply + S3/CloudFront invalidation `IDDXHEGTSQV9QGXDJX2V03NT4P`).
  - Matthew validated: Staff Users displayed as 4/5, count matched expected active total.
  - See: `docs/release-notes/phase-1b5c-b-staff-limit-active-count-entitlement-fix.md`
- Phase 1B.5C-C: Staff Edit Double-Click Correction (✅ VALIDATED AND CLOSED — 2026-07-30)
  - Fixed staff profile editor requiring a second click to open.
  - Deployed as part of Phase 1B.5C-B+C combined frontend deployment (commit `510b063`).
  - Matthew validated: editor opens with one click, correct staff member opens, existing edit behavior functional.
  - See: `docs/release-notes/phase-1b5c-c-staff-edit-double-click-correction.md`
- Phase 1B.5C-D.1: Platform-Managed Protected Admin Controls (✅ DEPLOYED & SEEDED IN PRODUCTION — 2026-07-29)
  - Data-driven `is_platform_protected` flag, `set-protected`/`unset-protected` actions, frontend toggle.
  - Matthew's profile seeded as Protected Platform Admin.
  - See: `docs/release-notes/phase-1b5c-d1-platform-managed-protected-admin-controls.md`
- Phase 1B.5C-D.2: Remove Legacy Config Protection (🛠️ LOCAL IMPLEMENTATION COMPLETE / READY FOR DEPLOYMENT PREPARATION)
  - Removed `Admin_Root` and `USmissionhero` from legacy fallback defaults and Terraform env vars.
  - Retained `support@usmissionhero.com` as permanent emergency fallback.
  - Awaiting Matthew deployment approval.
  - See: `docs/release-notes/phase-1b5c-d2-remove-legacy-config-protection.md`

## Completed Planning / Evidence Workstreams

- Phase 23A: AWS Tagging Evidence Audit (✅ EVIDENCE AUDIT COMPLETE — No Terraform remediation required — 2026-07-24)
  - All supported Terraform-managed resources carry full nine-key tag set via provider default_tags.
  - Optional deferred items: bootstrap resource tagging, Lambda log-group tagging, SESv2 migration evaluation.
  - Budget filter (`Client=TogAndDogs`) confirmed functioning.
  - Cost-allocation activation status requires payer-account access (linked account cannot query).
  - See `docs/planning/phase-23a-aws-tagging-evidence-audit-and-minimal-remediation.md`
- Phase 23B: AWS Budget Coverage and Cost Visibility Dashboard (✅ STEPS 1–2C COMPLETE — 2026-07-26)
  - Goal: ensure Matthew can see and monitor complete Togs & Dogs cost footprint.
  - Step 1 read-only verification COMPLETE (2026-07-25).
  - Step 2A: All 5 inactive cost-allocation tags activated (Project, Application, CostCenter, Company, BillingModel) on 2026-07-26.
  - Step 2B: Cost Explorer saved report spec complete. Manual console step remains (CLI unsupported). Operating guide written.
  - Step 2C: Budget alerts added — 80% forecasted and 100% actual. Original 80% actual preserved. $20 limit unchanged.
  - Budget coverage: 92–97% of workload-account costs captured by `Client=TogAndDogs` filter.
  - Excluded: CloudWatch alarm monitoring ($0.45/month), Terraform state bucket ($0.01/month).
  - Classification: SUBSTANTIALLY COMPLETE WITH DOCUMENTED EXCLUSIONS.
  - Terraform drift note: two new budget notifications added outside Terraform. Reconciliation deferred.
  - Not blocked by or blocking Phase 1B.5C-A.
  - See `docs/planning/phase-23b-aws-budget-coverage-and-cost-visibility-dashboard.md`
  - See `docs/release-notes/phase-23b-step-1-budget-coverage-verification.md`
  - See `docs/release-notes/phase-23b-cost-visibility-dashboard-and-budget-alerts.md`
  - See `docs/operations/aws-cost-visibility-operating-guide.md`

## Cross-Platform UI Alignment (Planning Only)

- Direction approved: shared design tokens, terminology, validation, API contracts.
- React/Vite remains the web framework. Expo/React Native remains mobile.
- No website rewrite to React Native Web.
- Preferred eventual pilot: My Pets workflow (depends on Phase 1B.5C-A deployment).
- Mobile pet editing depends on the customer pet API being available after the Phase 1B.5C-A deployment decision.
- No EAS, TestFlight, App Store, Google Play, Ryan-testing, or mobile-distribution changes approved.
- Phase 24A planning document complete: `docs/planning/phase-24a-cross-platform-design-system-and-mobile-workflow-alignment.md`
- Phase 24A-1A token contract complete: `shared/tokens/colors.json` defined, validation passes, neither app imports it yet.
- Phase 24A-1B platform adapters complete: generator wired, web and mobile consume generated adapters, no visual change, all tests pass.
- Phase 24A-2 shared constants and contracts complete: request statuses, service types, pet fields, and API paths defined as reference contracts. Not yet consumed by applications. Role-mapping discrepancy documented for separate resolution.
- Phase 24A-3 mobile test foundation complete: jest-expo@54, Jest 29, RNTL v14, test-renderer@1.1. 18 baseline tests passing. All web/mobile/shared regressions validated. Vitest path-casing issue resolved (uppercase drive letter required).
- Recommended sequence: shared architecture (1A ✅) → wiring (1B ✅) → visual alignment (1C) → constants (2 ✅) → mobile tests (3 ✅) → mobile My Pets read (4) → edit (5) → intake (6) → polish (7) → a11y (8) → build/distribution (9, separately approved).
- Mobile test infrastructure must precede new mobile feature screens.
- Web forgot-password is missing (mobile has it complete); not a blocking dependency.

## Latest Completed Releases

- Phase 1B.5C-C: Staff Edit Double-Click Correction (✅ VALIDATED AND CLOSED — 2026-07-30)
- Phase 1B.5C-B: Staff Limit Active-Count Entitlement Fix (✅ VALIDATED AND CLOSED — 2026-07-30)
- Phase 1B.5C-A.1: Admin Pet Care Field Visibility Hotfix (✅ VALIDATED AND CLOSED — 2026-07-30)
- Phase 1B.5C-A: Customer Pet Editing Production Deployment (✅ VALIDATED AND CLOSED — 2026-07-30)
- Phase 1B.5B-A.1: Google Calendar Integration RBAC Production Deployment (✅ VALIDATED AND CLOSED — 2026-07-23)
- Phase 1B.5B-A.1: Google Calendar Integration RBAC Deployment Readiness (✅ PLAN PREPARED — 2026-07-23)
- Phase 1B.5B-A.1: Google Calendar Access Control Remediation (✅ COMPLETE LOCAL — 2026-07-23)
- Phase 1B.5B-A.1: Staff Pet Editor Edit Save Hotfix (✅ VALIDATED AND CLOSED — 2026-07-23)
- Phase 1B.5B-A: Staff Pet Editor Production Deployment (✅ VALIDATED AND CLOSED — 2026-07-23)
- Phase 1B.5B-A: Staff Pet Editor Production Deployment Readiness (✅ PLAN PREPARED — 2026-07-23)
- Phase 1B.5B-A: Pet PUT Validation Order Correction (✅ COMPLETE LOCAL — 2026-07-22)
- Phase 1B.5B-A: Staff Pet Editor Implementation (✅ COMPLETE LOCAL — 2026-07-22)
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

**Production deployment 22P/22R failed manual validation due to drawer stability and viewport scrollbar/overflow issues. Release 22V deployed the combined drawer fixes (22S) and client bookings date/window display fixes (22U) to production. Manual validation passed successfully. No hotfix/main branch divergence remains — production now runs from `main`. Matthew ran a controlled smoke test (Release 22X) and found three findings. Release 22Y completed a read-only triage of these findings, identifying Cognito password reset restrictions and API Gateway DELETE method deployment issues as root causes. Release 22ZA implemented the mobile responsive foundation and accessible slide-out navigation drawer (pre-deploy validated). Release 22ZB implemented the full-screen Profile Editor mobile sheet layout (pre-deploy validated). Release 22ZC added keyboard-accessible stat cards, responsive filter controls stacking, and accessible data-label column labels on mobile request cards (pre-deploy validated). Phase 1B.2A backend-only Lambda package apply completed successfully, deploying the pet creation is_active hardening code to production. Phase 1B.2A ClientPetIndex GSI-only apply completed successfully, creating the global secondary database index in production (index backfilled and status ACTIVE). Phase 1B.2A ClientPetIndex query cutover deployed to production on 2026-07-20 (0 added, 13 changed, 0 destroyed). All 13 Lambda functions verified Active/Successful with expected CodeSha256. Matthew authenticated manual smoke PASSED (admin login, Client Management page, client drawer, admin pet list). Phase 1B.3 frontend deployed to production with /my-pets route, card-click drawer interaction, accessible cards, and mobile bottom-sheet. Hook-order hotfix applied. Matthew confirmed production works. Phase 1B.3 COMPLETE and CLOSED. Phase 1B.4A–E Client Drawer Editor Consolidation deployed to production. Matthew confirmed drawer View/Edit/Create experience works correctly, inline editor retired, Staff Management unaffected. Phase 1B.4A–E COMPLETE and CLOSED. Phase 1B.4F–H remain deferred. Phase 1B.5 (Pet Management and Client–Pet Association) is active. Phase 1B.5A and 1B.5A.1 deployed and validated (2026-07-22). Phase 1B.5B-A Staff Pet Editor and hotfixes deployed and validated (2026-07-23). Phase 1B.5C-A Customer Pet Editing deployed (2026-07-28) and validated (2026-07-30). Phase 1B.5C-A.1 admin pet care field hotfix deployed and validated (2026-07-30). Phase 1B.5C-B (active staff count fix) and 1B.5C-C (staff edit double-click fix) deployed (2026-07-28) and validated (2026-07-30). Phase 1B.5C-D.1 (platform-managed protected admin controls) deployed and seeded (2026-07-29). Phase 1B.5C-D.2 (remove legacy config protection) is local/ready for deployment preparation. Latest completed validated production release is Phase 1B.5C-B+C (2026-07-30).**

**Next options:**
- Phase 1B.5C-D.2: Remove Legacy Config Protection (local complete, awaiting Matthew deployment approval)
- Phase 24A-4: Mobile My Pets Read-Only Screen (requires Matthew approval; depends on 24A-3 ✅ complete and 1B.5C-A ✅ deployed)
- Phase 1B.5D–E: Pet Lifecycle safeguards and booking integration (deferred)
- Address remaining Phase 1B.4F–H staff drawer alignment (deferred, low priority)
- Begin Release 22ZD — Scheduler, Client Management, Platform Admin mobile polish (Phase 4 of 22Z plan)
- Address 22Y remediation items (Cognito password-reset state handling, Google Calendar disconnect API Gateway fix) in a separate release.
- Continue SaaS maturity priorities (blocked on EIN for Stripe live).
