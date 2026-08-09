# Current Project State

**Last Updated:** 2026-08-09 (Phase 24A-7 Mobile Visual Consistency Polish Locally Complete)

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

| Feature | Status |
|---------|--------|
| Tenant Resolution Engine | ✅ Deployed (header, query param, sub-domain, path, fallback) |
| Tenant Resolution Mode | ⚠️ Currently `off` in production (`DEFAULT_COMPANY_ID` fallback) |
| Tenant Isolation | ✅ Enforced across all primary database helpers (11E, 18V, 19K) |
| Entitlement Framework | ✅ Active with 8 enforced metrics (17A–17W) |
| Platform Admin Panel | ✅ Deployed (`/platform-admin/metrics`, `/platform-admin/tenants`) |
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

- Phase 24A-7: Visual Consistency Polish (🔗 LOCALLY COMPLETE / MOBILE VISUAL CONSISTENCY POLISHED / 8PX ACTION BUTTON RADII & 12PX CARD SURFACE RADII NORMALIZED / COLOR TOKEN LITERALS REPLACED WITH `COLORS.white` / INDEPENDENTLY REVIEWED (KIRO: IMPLEMENTATION_CORRECT) / COMMITTED AND PUSHED / NOT DEPLOYED — 2026-08-09)
  - Standardized mobile action button radii to `8px` (`BookingsScreen.tsx` header CTA, `IntakeScreen.tsx` step navigation and submit buttons) and card surface radii to `12px` (`IntakeScreen.tsx` service options grid).
  - Replaced raw `#ffffff` string literals with generated token `COLORS.white`. Assessed `MyPetsScreen.tsx` and `RequestCard.tsx` and confirmed they were already fully aligned.
  - Preserved all status badge pill shapes (`borderRadius: 99`), selection chips (`borderRadius: 20`), navigation, forms, validation, status display semantics, and business logic.
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 28 focused tests, 89 full mobile tests across 10 suites.
  - Kiro independent review: `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_7_COMMIT_DECISION`).
  - Committed (`b34f0460c50fdf5033c4155b9e07ca4ea30e3868`) and pushed to `origin/main`. NOT DEPLOYED; production baseline remains Phase 1B.5C-D.2. Zero EAS or Expo distribution builds occurred.
  - See: `docs/release-notes/phase-24a-7-visual-consistency-polish.md`

- Phase 24A-6: Mobile Care-Request Intake Flow (🔗 LOCALLY COMPLETE / MOBILE CARE-REQUEST INTAKE FLOW IMPLEMENTED / 3-STEP INTAKE WIZARD INTEGRATED / CONTRACT-DERIVED CANONICAL SERVICES / READ-ONLY CLIENT PETS LOADED / INDEPENDENTLY REVIEWED (KIRO: IMPLEMENTATION_CORRECT) / COMMITTED AND PUSHED / NOT DEPLOYED — 2026-08-09)
  - Implemented complete 3-step mobile care request intake wizard (`IntakeScreen.tsx`), integrated navigation route (`AppNavigator.tsx`), added `+ Book Care` and `+ Book Pet Care` buttons (`BookingsScreen.tsx`), added API helper `submitClientRequest` (`client.ts`), and created a 10-test unit suite (`IntakeScreen.test.tsx`).
  - Derived service options from `SERVICE_TYPES` contract metadata, excluded `MEET_GREET`, enforced client terms/privacy policy agreement (`accepted_terms: true`, `accepted_privacy: true`, `terms_version: "1.0"`, `privacy_version: "1.0"`), and submitted booking requests to backend (`POST /client/request`) without client-assigned status.
  - Loaded existing read-only client pets via `getClientPets()` (`GET /client/pets`, Phase 24A-4 contract) without invoking pet modification or creation endpoints, preserving Phase 24A-5 as deferred.
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 14 focused tests, 89 full mobile tests across 10 suites.
  - Kiro independent review: `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_6_COMMIT_DECISION`).
  - Committed (`2831205a092ab94b774ac7bcdaada27bea19976e`) and pushed to `origin/main`. NOT DEPLOYED; production baseline remains Phase 1B.5C-D.2. Zero EAS or Expo distribution builds occurred.
  - See: `docs/release-notes/phase-24a-6-mobile-care-request-intake-flow.md`

- Phase 24A Roadmap & Continuity Reconciliation (🔗 LOCALLY COMPLETE / COMBINED PHASE 2C CONTRACT STREAM 2C.1 & 2C.2 LOCALLY CLOSED / PHASE 24A-6 IDENTIFIED AS NEXT UNFINISHED FEATURE TASK / PHASE 24A-5 & 24A-9 DEFERRED AND GATED / COMMITTED AND PUSHED / NOT DEPLOYED — 2026-08-07)
  - Reconciled Phase 24A roadmap and project continuity state across repository documentation.
  - Confirmed the combined Phase 2C contract workstream (2C.1 request statuses and 2C.2 service types) is 100% locally complete, validated, independently reviewed by Kiro, committed, and pushed.
  - Re-established Phase 24A-6 (Mobile Care-Request Intake Flow) as the true next unfinished feature task (`PLANNED_NOT_STARTED`).
  - Confirmed Phase 24A-5 (Mobile My Pets Editing) remains deferred/gated on Phase 1B.5C-A deployment, Phase 24A-9 remains distribution-gated on explicit Matthew approval, and Phase 24A remains NOT DEPLOYED (latest validated production baseline remains Phase 1B.5C-D.2).
  - See: `docs/release-notes/phase-24a-roadmap-continuity-reconciliation.md`

- Phase 24A-2C.1C: Mobile Request-Status Display Compatibility Wiring (🔗 LOCALLY COMPLETE / MOBILE REQUEST-STATUS DISPLAY WIRING IMPLEMENTED / CONTEXTUAL & WORKFLOW LABELS PRESERVED / DEDICATED COMPATIBILITY SUITE ADDED / INDEPENDENTLY REVIEWED (KIRO: IMPLEMENTATION_CORRECT) / COMMITTED AND PUSHED / NOT DEPLOYED — 2026-08-07)
  - Wired generated `REQUEST_STATUSES` from `mobile/src/contracts/generatedContracts.ts` into mobile status badge (`StatusBadge.tsx`) for upper-cased contract-backed badge labels and customer appointments screen (`BookingsScreen.tsx`) for exact-match entries.
  - Preserved customer contextual overrides (`ASSIGNED` → `"Scheduled"`, `JOB_CREATED` → `"Scheduled"`), staff navigation filter tabs (`RequestListScreen.tsx`), staff dashboard metrics counter (`DashboardScreen.tsx`), badge styling, colors, borders, typography, layout, padding, and accessibility properties.
  - Added 10 dedicated compatibility unit tests in `mobile/__tests__/RequestStatusDisplayCompatibility.test.tsx`. Validation: 18 constants, 9 adapters, 79 full mobile Jest tests across 9 suites.
  - Kiro independent review classified candidate as `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_2C_1C_COMMIT_DECISION`).
  - Committed (`83225b6800b3ed16eb825f61f06e1027347a2e52`) and pushed to `origin/main`. NOT DEPLOYED; production baseline remains Phase 1B.5C-D.2. Zero EAS or Expo distribution builds occurred.
  - See: `docs/planning/phase-24a-2c1-request-status-contract-display-wiring.md`
  - See: `docs/release-notes/phase-24a-2c1c-mobile-request-status-display-compatibility-wiring.md`

- Phase 24A-2C.1B: Web Request-Status Display Compatibility Wiring (🔗 LOCALLY COMPLETE / WEB REQUEST-STATUS DISPLAY WIRING IMPLEMENTED / CONTEXTUAL & WORKFLOW LABELS PRESERVED / DEDICATED COMPATIBILITY SUITE ADDED / INDEPENDENTLY REVIEWED (KIRO: IMPLEMENTATION_CORRECT) / COMMITTED AND PUSHED / NOT DEPLOYED — 2026-08-07)
  - Wired generated `REQUEST_STATUSES` from `web/src/generated/contracts.js` into customer portal (`ClientPortal.jsx`) for exact-match entries and Intake Queue status pills (`MasterScheduler.jsx`).
  - Preserved client-facing contextual overrides (`MG_SCHEDULED` → `"M&G Scheduled"`, `ASSIGNED` → `"Scheduled"`, `CANCELLATION_REQUESTED` → `"Cancellation Pending"`), MasterScheduler status filter dropdown options (`ALL`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` single-"l", `RESCHEDULED`), CareCard status transition options, AdminDashboard workflow-sensitive labels, descriptions, colors, backgrounds, and fallbacks.
  - Added 7 focused unit tests in `web/tests/RequestStatusDisplayCompatibility.test.jsx`. Validation: 18 constants, 9 adapters, 13 backend parity, 238 full web Vitest across 20 test files.
  - Kiro independent review classified the candidate as `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_2C_1B_COMMIT_DECISION`).
  - Committed (`2a7959e06367681527cc784f448663521ae030a8`) and pushed to `origin/main`. NOT DEPLOYED; production baseline remains Phase 1B.5C-D.2.
  - See: `docs/planning/phase-24a-2c1-request-status-contract-display-wiring.md`
  - See: `docs/release-notes/phase-24a-2c1b-web-request-status-display-compatibility-wiring.md`

- Phase 24A-2C.1A: Request-Status Label Metadata & Parity Hardening (🔗 LOCALLY COMPLETE / 17 REQUEST-STATUS LABELS ADDED / REQUEST-STATUS CONTRACT AND ADAPTER PARITY HARDENED / DEDICATED CHARACTERIZATION TESTS ADDED / DOCUMENTED, COMMITTED, AND PUSHED / NO RUNTIME CONSUMER WIRING / NOT DEPLOYED — 2026-08-06)
  - Implemented the bounded six-file metadata and parity hardening candidate: added non-empty `label` strings to all 17 canonical entries in `shared/constants/request-statuses.json`, hardened `validate-constants.mjs` and `validate-contract-adapters.mjs`, deterministically regenerated `web/src/generated/contracts.js` and `mobile/src/contracts/generatedContracts.ts` via unchanged generator command (`node shared/generate-contract-adapters.mjs`), and added dedicated backend characterization suite `tests/backend/test_phase24a_request_status_contract_parity.py` (13 tests).
  - All existing keys, exact key order, categories, booleans, synonyms, and prior values were preserved byte-for-byte. Documented backend enum synonyms (`NEEDS_REVIEW`, `NEEDS_MG`, `NEW_REQUEST`, `QUOTED`, `BOOKED`), JobStatus enum (6 members), pseudo-actions (`VERIFY_MEET_GREET`), and UI filter options (`IN_PROGRESS`, `RESCHEDULED`) are characterized separately and excluded from canonical contract keys.
  - Validation: 18/18 constants, 9/9 adapters, 13/13 parity, and 172/172 AG combined backend regression tests passed. Kiro independent review classified the candidate as `IMPLEMENTATION_CORRECT` and returned `READY_FOR_PHASE_24A_2C_1A_DOCUMENTATION_AND_LOCAL_CLOSEOUT`.
  - Committed and pushed to `origin/main` at commit `5f27b282b1a638ffd641fbef598623351cb9da42` (`feat: add request status labels and parity validation`). Generator source (`generate-contract-adapters.mjs`) remained unchanged. No application code, UI components, backend handlers, persistence, calendar behavior, notifications, infrastructure, dependencies, production data, or production systems were modified. Future consumer wiring (2C.1B/2C.1C) remains unapproved.
  - See: `docs/planning/phase-24a-2c1-request-status-contract-display-wiring.md`
  - See: `docs/release-notes/phase-24a-2c1a-request-status-label-metadata-parity-hardening.md`

- Release 22Y Finding 2: Staff Password-Reset State Awareness (🔗 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / STAFF PASSWORD RESET STATE AWARENESS COMPLETE / NOT DEPLOYED — 2026-08-04)
  - The real AdminDashboard staff drawer now preserves protected, self, and orphaned reset guards while also disabling normal password reset for the existing direct `cognito_status: FORCE_CHANGE_PASSWORD` and backend-derived `identity_state: linked_invited` invitation states. `linked_invited` covers enabled Cognito users whose status is not `CONFIRMED`, including `FORCE_CHANGE_PASSWORD`, `UNCONFIRMED`, and `RESET_REQUIRED`; `invitation_sent` is not a staff response value and no frontend or backend contract was invented.
  - Eligible confirmed staff retain the unchanged confirmation and `resetStaffPassword(staff_id)` path. Explanation precedence remains protected → self → orphaned → initial login; invitation-state copy names only alternatives whose existing controls remain available. Resend Invite and Set Temporary Password behavior is unchanged.
  - Validation: 7 focused rendered tests, 38 existing drawer tests, 165 complete Vitest tests across 16 files, 99 legacy tests / 264 unique web tests, and successful Vite build with 108 modules transformed (`index-D53dI4qG.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The new test is lint-clean; AdminDashboard retains its exact pre-change 18-error/5-warning baseline, with zero candidate-introduced lint findings.
  - Independent Kiro review returned `READY_FOR_LOCAL_RELEASE_22Y_FINDING_2_CLOSEOUT` and classified the tests as `STRONG_RENDERED_BEHAVIORAL_COVERAGE`; no correction was required.
  - No backend exception handling, API client, Cognito, Terraform, API Gateway, production-data, deployment, mobile, tester, Ryan, Stripe, tenant, or Google Calendar action occurred. Findings 1 and 3 remain outside this closeout. Passing local validation and local closeout do not authorize deployment.
  - See: `docs/planning/release-22y-smoke-test-identity-actions-and-google-calendar-disconnect-triage.md`

- Phase 24A-2A: Shared Contract Adapter Foundation & API Path Wiring (🔗 LOCALLY VALIDATED AND REVIEWED / API PATHS WIRED / NOT DEPLOYED OR DISTRIBUTED — 2026-07-30)
  - Created deterministic generator `shared/generate-contract-adapters.mjs`, generated `web/src/generated/contracts.js` and `mobile/src/contracts/generatedContracts.ts`.
  - Wired canonical `API_PATHS` and safe `buildPath` parameter encoder into `web/src/api/client.js` and `mobile/src/api/client.ts`.
  - Added mocked behavioral tests in `web/tests/contracts.test.jsx` (9 tests) and `mobile/__tests__/generatedContracts.test.ts` (6 tests) asserting actual `fetch()` invocation URLs, HTTP methods, headers, and payloads.
  - Deferred pet fields, request statuses, service types, and UI labels to Phase 24A-2B and 24A-2C.
  - Validation: 17 contract tests, 5 adapter tests, 242 web tests, Vite production build, 42 mobile Jest tests, and `tsc --noEmit` clean. Changed files lint cleanly; full web lint retains 51 errors and 9 warnings in pre-existing unrelated files.
  - See: `docs/release-notes/phase-24a-2a-api-path-wiring.md`

- Phase 24A-2B: Shared Pet-Field & Validation-Limit Wiring (🔗 LOCALLY VALIDATED AND REVIEWED / ALL PLANNED PHASE 24A-2B CUSTOMER PET FIELD AND VALIDATION WIRING COMPLETE / NOT DEPLOYED OR DISTRIBUTED — 2026-08-03)
  - Detailed contract field matrix and safety rules for client read/write allowlists and validation limits.
  - Documented health nested structure (`vet_name`, `vet_phone`).
  - Completed subphases: 24A-2B.1 read-helper wiring, 24A-2B.2A top-level customer validation-limit wiring, and 24A-2B.2B customer veterinarian-field contract limits and web wiring.
  - Independent review passed implementation, contract design, deterministic generation, validators, component wiring, tests, backend parity, and security scope.
  - Separately deferred scopes—not unfinished Phase 24A-2B work—are staff pet-contract work, mobile pet editing or creation, and Phase 24A-2C request-status/service-type wiring.
  - See: `docs/planning/phase-24a-2b-pet-field-and-validation-wiring.md`

- Phase 24A-2B.1: Web Customer Pet Read-Allowlist Helper Wiring (🔗 LOCALLY VALIDATED AND REVIEWED / WEB CUSTOMER PET READ ALLOWLIST WIRED / NOT DEPLOYED OR DISTRIBUTED — 2026-07-30)

  - Wired `PET_FIELDS.clientReadFields` and `PET_FIELDS.clientWriteHealthSubfields` from generated contract adapter (`web/src/generated/contracts.js`) into `web/src/utils/petHelpers.js`.
  - Preserved `health.vet_name` and `health.vet_phone` via explicit helper logic while stripping internal fields and unknown health attributes.
  - Added 4 characterization unit test cases to `web/tests/phase1b3.test.js`.
  - Validation: 17 contract tests, 5 adapter tests, 20 focused helper tests, 242 web tests, Vite production build, 42 mobile Jest tests, `tsc --noEmit` clean. Changed files lint cleanly (`0 errors, 0 warnings`).
  - See: `docs/release-notes/phase-24a-2b1-web-pet-read-allowlist.md`

- Phase 24A-2B.2A: Web Customer Top-Level Validation-Limit Wiring (🔗 LOCALLY VALIDATED AND REVIEWED / WEB CUSTOMER TOP-LEVEL PET LIMITS WIRED / NOT DEPLOYED OR DISTRIBUTED — 2026-08-03)
  - The eight existing customer controls previously had no frontend `maxLength` attributes. Applied `PET_FIELDS.fieldLimits` directly from the generated contract adapter (`web/src/generated/contracts.js`) as `maxLength` attributes to those top-level fields in `web/src/components/MyPets.jsx`.
  - At the historical 2B.2A checkpoint, frontend limits for nested health fields (`health.vet_name`, `health.vet_phone`) were deferred to the separately approved 2B.2B shared-contract enhancement; 2B.2B subsequently completed that wiring.
  - Strengthened existing MyPets tests to use `PET_FIELDS.fieldLimits` and assert the exact unchanged update payload for all eight top-level fields plus nested veterinarian values; the suite remains 24 tests.
  - Independent review: `EXACT_BOUNDED_LIMIT_WIRING`; `STRONG_COMPONENT_AND_PAYLOAD_PARITY_COVERAGE`; `READY_FOR_LOCAL_PHASE_CLOSEOUT_WITH_KNOWN_PREEXISTING_LINT`.
  - Validation: 17 contract tests, 5 adapter tests, 24 focused MyPets tests, 20 phase1b3 tests, 96 legacy tests, 147 Vitest tests, 243 unique web tests, Vite production build, 6 mobile suites / 42 mobile tests, and `tsc --noEmit` clean. A subsequent independent recount confirmed 96 legacy tests rather than the originally recorded 99, correcting the unique total from 246 to 243. Phase 24A-2B.2A changed files lint cleanly; full web lint remains 51 errors and 9 warnings in unrelated pre-existing files. These findings were not introduced, modified, or remediated by this phase. No mobile lint script is configured.
  - See: `docs/release-notes/phase-24a-2b2a-web-pet-top-level-limits.md`

- Phase 24A-2B.2B: Customer Veterinarian-Field Contract Limits and Web Wiring (🔗 LOCALLY VALIDATED AND REVIEWED / CUSTOMER VETERINARIAN FIELD LIMIT CONTRACT AND WEB WIRING COMPLETE / NOT DEPLOYED OR DISTRIBUTED — 2026-08-03)
  - Added customer-write-specific `PET_FIELDS.clientWriteHealthFieldLimits` with exact `vet_name: 100` and `vet_phone: 100` values matching unchanged backend customer PUT validation.
  - Regenerated web and mobile adapters deterministically without changing generator source; added exact canonical/adaptor validator coverage.
  - Wired the two existing MyPets veterinarian inputs to the generated limits using `maxLength` only; payload, health nesting, API behavior, messages, staff behavior, mobile application behavior, and backend behavior remain unchanged.
  - Validation: 18 shared constants, 6 adapter checks, 13 focused web contracts, 24 focused MyPets, 20 phase1b3, 96 legacy, 147 Vitest across 13 files / 243 unique web, successful Vite build, 10 focused mobile contracts, 6 mobile suites / 42 tests, 0 TypeScript errors, and 16 focused backend tests with 0 failed and 0 skipped. Changed Phase 24A-2B.2B web files lint cleanly; full web lint remains 51 errors and 9 warnings in unrelated pre-existing files. These findings were not introduced, modified, or remediated by this phase. No mobile lint script is configured.
  - See: `docs/release-notes/phase-24a-2b2b-veterinarian-field-limits.md`

- Phase 24A-2C.2: Cross-Platform Service-Type Contract Wiring (🔗 PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D LOCALLY COMPLETE / NOT DEPLOYED OR DISTRIBUTED — 2026-08-05)
  - Phase 24A-2C.2A imported the generated `SERVICE_TYPES` contract into `AdminDashboard.jsx`, replaced duplicated long/short label maps, and sourced the seven explicit selector text nodes from `labelLong` without changing values, order, membership, or the `PET_SITTING` default.
  - Focused behavioral coverage preserves canonical labels, long case-sensitive fallbacks, short case-normalized recognition/original-value fallback, search, raw export, dispatch output, and the exact raw new-visit payload.
  - Independent review confirmed the exact six-file candidate, bounded scope, label/fallback parity, and selector parity with no correction required. Validation: 18 shared constants, 6 adapter checks, 4 focused tests, 99 legacy, 151 Vitest across 14 files / 250 unique web, successful Vite build (`index-D7UoV5fJ.js`, `index-bVFIMo3n.css`), 6 mobile suites / 42 tests, 0 TypeScript errors, and 30 focused backend calendar tests. Phase 2C.2A introduced no lint findings; the new test is lint-clean, `AdminDashboard.jsx` retains its pre-existing 18 errors/5 warnings, and full web lint retains 51 errors/9 warnings in unrelated pre-existing code.
  - At the Phase 2C.2B planning checkpoint, `DOG_WALKING`, `WALKING`, and `OTHER` were active frontend option values. Phase 2C.2B.2A removed `DOG_WALKING` from new customer intake without mapping or rewriting it. The separately approved Phase 2C.2B.2B CareCard Option 2 correction removes the ignored `WALKING`/`OTHER` PET-field selector without mapping or rewriting historical values. Request creation still has no canonical fixed allowlist. Current production presence was not verified; no production-data inspection or migration occurred.
  - Phase 2C.2A is locally validated and reviewed. With Matthew's explicit approval, Phase 2C.2C added one type-safe shared mobile display helper and migrated BookingsScreen, ScheduleScreen, RequestDetailScreen, and RequestCard. Exact canonical identifiers now use generated short `label` values; noncanonical, unknown, case-variant, nullish, and blank values preserve exact legacy output.
  - Phase 2C.2C validation: 18 shared constants, 6 adapter checks, 23 focused helper tests, 8 focused owner tests, 8 complete mobile suites / 69 tests, and 0 TypeScript errors. All four render paths use the real helper; API inputs and raw navigation values remain unchanged. No mobile lint script is configured.
  - Independent review confirmed the exact 12-file candidate, type-safe own-property guard, exact legacy fallback parity, all four real render paths, 4 BookingsScreen tests, 4 ServiceTypeLabelOwners tests, no final successful-run console or React `act()` warnings, no open handles or asynchronous leaks, and accurate documentation with no correction required.
  - Phase 2C.2C is locally validated and reviewed. Mobile service-type display labels are wired, the intentional canonical label improvements are complete, and exact legacy fallback behavior is preserved. No EAS build, APK/AAB/IPA generation, distribution, tester change, deployment, or production-data action occurred or is approved.
  - Phase 2C.2B planning is complete. Phase 2C.2B.2A is locally validated and reviewed, with customer IntakeForm canonical service selection complete locally and not deployed: IntakeForm derives the six exact `availableInIntake: true` canonical options from generated `SERVICE_TYPES`, preserves contract order plus the controlled `PET_SITTING` initial/default and reset behavior, adds no placeholder, and submits selected identifiers unchanged without mapping, aliasing, trimming, or normalization.
  - New customer intake no longer emits `DOG_WALKING`; it offers explicit `WALK_30MIN` and `WALK_60MIN` plus `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, and `PET_SITTING`. `MEET_GREET`, `WALKING`, and service identifier `OTHER` remain excluded. Legacy identifiers remain readable elsewhere; no mapping, normalization, backend enforcement, production-data assessment, or migration occurred.
  - Independent review confirmed the exact expected eight-file candidate with no correction required. Phase 2C.2B.2A validation: 18 shared constants, 6 adapter checks, 7 focused IntakeForm, 99 legacy, 158 Vitest across 15 files / 257 unique web, and successful Vite build with 108 modules transformed (`index-aRRxk0NM.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The focused test is lint-clean; IntakeForm retains 2 pre-existing lint errors and 0 warnings, and complete lint remains the known 51-error/9-warning baseline with zero candidate-introduced findings. Existing jsdom navigation, Vite `optimizeDeps` deprecation, and large-chunk notices remain; no open handles or asynchronous leaks were found. Backend and mobile classifications are `NO_BACKEND_REGRESSION_REQUIRED_FOR_FRONTEND_SELECTOR_ONLY_SCOPE` and `NO_MOBILE_REGRESSION_REQUIRED_FOR_WEB_INTAKE_SELECTOR_ONLY_SCOPE`.
  - Phase 2C.2B.1 is locally validated and independently reviewed, with web display compatibility complete and not deployed. One exact-known-label resolver supplies canonical `labelLong` plus exact `DOG_WALKING` → `Daily Dog Walking`, `WALKING` → `Dog Walking`, and `OTHER` → `Other` displays to ClientPortal, MasterScheduler desktop service-only visit cards, and MasterScheduler pending-intake cards. Raw `window_type`, owner-specific unknown/nullish/blank fallbacks, exact filters, callbacks, object identity, navigation, payloads, persistence, exports, scheduling, backend behavior, and mobile behavior remain unchanged.
  - Phase 2C.2B.1 validation: 37/37 new helper/real-owner tests, 11/11 existing AdminDashboard/IntakeForm exclusion regressions, 202/202 complete Vitest across 18 files, 99/99 legacy / 301 unique web, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build (`index-mPUri6lj.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). New files lint cleanly; ClientPortal and MasterScheduler retain exact pre-change lint baselines, complete web lint remains 51 errors/9 warnings, and candidate-introduced lint is zero. Kiro returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_1_CLOSEOUT` with no correction required. No pre-existing focused ClientPortal suite exists beyond the new real-owner coverage.
  - Phase 2C.2B.2B CareCard Option 2 is locally validated and independently reviewed, with the CareCard service-type correction complete and not deployed. The editable Service Type selector is removed; Visit Details remains read-only with request `_originItem.service_type` precedence and historical `pet.service_type` fallback. The existing helper supplies canonical `labelLong` and exact `DOG_WALKING`, `WALKING`, and `OTHER` aliases; unknown values remain raw and untrimmed; missing/blank values display `Not Specified`. Top-level `service_type` is explicitly omitted from PET update payloads while all other fields, identifiers, callbacks, status behavior, multi-pet behavior, and new/fallback flow remain exact. No request editor or PET-level service preference was added.
  - Phase 2C.2B.2B final validation: 22/22 focused CareCard, 37/37 service-label/owner regressions, 11/11 AdminDashboard/IntakeForm regressions, 224/224 complete Vitest across 19 files, 99/99 legacy / 323 unique web, 23/23 staff/admin PET backend tests, 18/18 customer PET backend tests, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build (`index-C-Rflmrt.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The new test is lint-clean; CareCard retains its exact pre-change 6-error/1-warning baseline, complete web lint remains 51 errors/9 warnings, and candidate-introduced lint is zero. Backend source was unchanged; tests only characterize existing staff/admin ignore/preserve and client rejection/sanitization behavior. Kiro independently confirmed the exact 10-file candidate and returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_2B_CLOSEOUT` with no blocking correction.
  - Phase 2C.2B.2C is locally validated and independently reviewed, with documentation prepared, a commit decision pending, and no deployment. MasterScheduler retains the static `ALL` / `All Services` default and adds `WALK_60MIN` / `60m Walk`, `PET_SITTING` / `Pet Sitting`, and `MEET_GREET` / `Meet & Greet` to the exact ordered canonical filter. Filtering remains exact case-sensitive `service_type` equality; `window_type` is not a filter input, pending intake remains independent, and desktop/mobile continue to use the same filtered collection. No legacy, unknown, blank, null, or undefined options were added.
  - Phase 2C.2B.2C final validation: 15/15 focused ServiceTypeDisplayOwners, 29/29 service-label helper, 22/22 CareCard, 11/11 AdminDashboard/IntakeForm, 231/231 complete Vitest across 19 files, 99/99 legacy / 330 unique web, 18/18 shared constants, 6/6 deterministic adapter checks, and a successful 109-module Vite build (`index-C5FqHoe-.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png`). The changed test is lint-clean; MasterScheduler retains its one pre-existing unused `onAssign` error; complete web lint remains 51 errors/9 warnings; candidate-introduced lint is zero. Kiro verified the exact two-file implementation candidate and returned `READY_FOR_PHASE_24A_2C_2B_2C_DOCUMENTATION_AND_LOCAL_CLOSEOUT` with no blocking correction.
  - Phase 2C.2B is locally complete for approved frontend scope: 2B.1 display compatibility, 2B.2A IntakeForm canonical selection, 2B.2B CareCard read-only correction/PET payload exclusion, and 2B.2C MasterScheduler canonical filter correction are complete at their stated review gates. Backend accepted-identifier allowlisting or rejection, legacy normalization, production assessment, migration/deprecation, scheduler-specific contract metadata, additional product/service availability changes, deployment, and unrelated lint remediation remain separate future decisions and are deferred and unapproved.
  - Repository evidence does not establish current production presence of noncanonical identifiers. No production data was inspected and migration is not presumed necessary.
  - Phase 2C.2D.1 is locally validated and independently reviewed. It hardens canonical service validation and complete canonical/web/mobile `SERVICE_TYPES` equality, and adds 48 focused backend parity/fallback tests against real canonical JSON and real `_build_event_body()` behavior using synthetic records only. No contract value, generator, generated adapter, runtime calendar logic, handler, request/job persistence, scheduling behavior, web, mobile, notification, infrastructure, production-data, or production-system behavior changed.
  - Canonical parity is characterized as `WALK_30MIN` 30 / `30-Min Walk`; `WALK_60MIN` 60 / `60-Min Walk`; `DROPIN_1HR` 60 / `1-Hour Drop-in`; `DROPIN_3HR` 180 / `3-Hour Drop-in`; `OVERNIGHT` 720 / `Overnight Care`; `PET_SITTING` 60 / `Pet Sitting`; and `MEET_GREET` 45 / `Meet & Greet`. Existing override precedence, exact case-sensitive unresolved 60-minute/color-`8` fallback, canonical colors, exclusive-next-day all-day shape, and 08:00/11:00/14:00/17:00 visit-window starts are characterized without mapping or normalization.
  - Validation and independent review: 18/18 shared constants, 7/7 adapter checks with deterministic zero diff, 48/48 focused parity tests, and 100/100 combined affected backend tests. Kiro verified the exact three-file candidate and returned `READY_FOR_PHASE_24A_2C_2D_1_DOCUMENTATION_AND_LOCAL_CLOSEOUT`; no blocking correction was identified.
  - Phase 2C.2D.2 is locally validated and independently reviewed with no runtime consumption. The existing shared generator now emits the commit-ready plain-dictionary `src/backend/common/generated_service_types.py` from cleaned canonical `SERVICE_TYPES`, preserving the root `services` wrapper, identifier/field order, camelCase names, exact values, and types without imports, functions, helpers, derived maps, aliases, normalization, timestamps, or side effects. Web and mobile generated bytes remain unchanged.
  - Phase 2C.2D.2 adapter validation safely uses a Python standard-library subprocess with `ast.parse`, a strict direct `SERVICE_TYPES` assignment check, `ast.literal_eval`, and JSON serialization; no `eval`, arbitrary execution, or generated-module import occurs. Complete canonical/web/mobile/backend equality and three-target deterministic zero diff are proved. Three focused tests prove real backend import, exact equality/order/types, module location, and no static or literal dynamic runtime consumer. Final validation: 18/18 constants, 8/8 adapters, 3/3 generated-backend tests, 48/48 parity, 18/18 calendar hardening, 12/12 all-day, 22/22 multi-day, and 103/103 combined affected backend tests. Kiro reproduced the candidate and returned `READY_FOR_PHASE_24A_2C_2D_2_DOCUMENTATION_AND_LOCAL_CLOSEOUT`; no blocking correction was identified.
  - Phase 2C.2D.3 is locally validated and independently reviewed. `google_calendar.py` imports `SERVICE_TYPES` from `common.generated_service_types` and derives `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` (`label`) directly from generated contract metadata. Exact symbol names, `_build_event_body()`, handwritten `SERVICE_COLORS`, and fallback logic are preserved. 11 new edge characterization tests in `test_phase24a_service_duration_contract_parity.py` preserve existing `scheduled_duration` edge handling. AST inspection proves `google_calendar.py` is the exactly-one runtime consumer of generated metadata in backend source. Validation: 18/18 constants, 8/8 adapters, 6/6 generated metadata tests, 59/59 duration parity tests, 18/18 calendar hardening, 12/12 all-day, 22/22 multi-day, and 117/117 combined affected backend tests. Kiro independently verified the candidate and returned `READY_FOR_PHASE_24A_2C_2D_3_DOCUMENTATION_AND_LOCAL_CLOSEOUT`. No deployment or production-data access occurred.
  - Phase 2C.2D.4 is locally complete as an assessed no-implementation closeout. Google Calendar color IDs (`"9"`, `"7"`, `"6"`, etc.) are provider-specific presentation keys unconsumed by web or mobile UIs. Adding color IDs to shared `service-types.json` would pollute cross-platform contracts and bloat platform adapters, while generator-injected backend-only metadata would create un-sourced authority and break adapter validator symmetry. Recommended decision: keep `SERVICE_COLORS` handwritten and isolated inside `src/backend/common/google_calendar.py`. Planned Phase 2C.2D backend service-metadata workstream is locally complete across all four subphases (2D.1, 2D.2, 2D.3, 2D.4). Backend identifier policy, production assessment, legacy normalization, migration/deprecation, deployment review, and existing-event resynchronization remain deferred.
  - See: `docs/planning/phase-24a-2c2b-selector-normalization-design.md`
  - See: `docs/release-notes/phase-24a-2c2b1-web-display-compatibility.md`
  - See: `docs/release-notes/phase-24a-2c2b2a-intake-canonical-service-options.md`
  - See: `docs/release-notes/phase-24a-2c2b2b-carecard-service-type-correction.md`
  - See: `docs/release-notes/phase-24a-2c2b2c-masterscheduler-canonical-service-filter.md`
  - See: `docs/planning/phase-24a-2c2c-mobile-service-label-wiring.md`
  - See: `docs/release-notes/phase-24a-2c2c-mobile-service-labels.md`
  - See: `docs/release-notes/phase-24a-2c2a-web-admin-service-labels.md`
  - See: `docs/release-notes/phase-24a-2c2d1-service-duration-parity-validator-hardening.md`
  - See: `docs/release-notes/phase-24a-2c2d2-generated-backend-service-metadata-adapter.md`
  - See: `docs/release-notes/phase-24a-2c2d3-generated-calendar-duration-friendly-name-wiring.md`
  - See: `docs/release-notes/phase-24a-2c2d4-calendar-color-metadata-assessment.md`

### Phase 24A Completion Boundaries

- Latest completed validated production release: **Phase 1B.5C-D.2**.
- Latest completed locally validated shared-contract phase: **Phase 24A-2C.2D.4** (assessed no-implementation closeout; Phase 2D stream locally complete).
- Completed Phase 24A-2B subphases: **Phase 24A-2B.1**, **Phase 24A-2B.2A**, and **Phase 24A-2B.2B**.
- Phase 24A-2B overall: **LOCALLY VALIDATED AND REVIEWED / ALL PLANNED PHASE 24A-2B CUSTOMER PET FIELD AND VALIDATION WIRING COMPLETE / NOT DEPLOYED OR DISTRIBUTED**.
- Phase 24A-2C.2 service-type work: **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D LOCALLY COMPLETE / NOT DEPLOYED OR DISTRIBUTED**. Phases 2C.2A and 2C.2C are locally validated and reviewed. Phase 2C.2B planning, 2B.1 web display compatibility, 2B.2A customer IntakeForm canonical selection, 2B.2B CareCard correction, and 2B.2C MasterScheduler canonical filter correction are locally complete at their review gates. Phase 2D.1 parity/validator hardening, Phase 2D.2 generated backend metadata, Phase 2D.3 duration/friendly-name calendar wiring, and Phase 2D.4 optional color-metadata assessment closeout are locally complete with exact behavior preserved. Backend accepted-identifier policy, production assessment, normalization, migration/deprecation, scheduler-specific metadata, additional availability changes, tenant-configurable color policy, existing-event resynchronization, and deployment remain deferred and unapproved.
- Phase 24A-2C.1 request-status work: **PLANNING COMPLETE / REQUEST AND JOB STATUS DOMAINS DOCUMENTED / FIRST METADATA AND PARITY SLICE DEFINED / NO IMPLEMENTATION AUTHORIZED / NOT DEPLOYED**.
- Phase 24A-2C request-status wiring remains outside this implementation and has not started.
- Separate deferred scopes: staff pet-contract work, mobile pet creation and editing, production deployment, mobile distribution, and Ryan testing.
  - Aligned 6 remaining color tokens per Matthew's explicit approval: `primaryHover` (`#a37213`), `textMuted` (`#6a6a66`), `border` (`#e2dfd9`), `borderSoft` (`#edf2ee`), `success` (`#4a7c59`), `danger` (`#d64933`).
  - Contract `shared/tokens/colors.json` updated to 100% aligned (`"aligned": true` across all 13 tokens).
  - Regenerated `web/src/generated/color-tokens.css` and `mobile/src/theme/generatedColors.ts`.
  - Cleaned up duplicate manual CSS declarations in `web/src/index.css` so `@import` is authoritative.
  - Validation: 9 contract tests, 7 adapter tests, 229 web tests, Vite production build, 31 mobile Jest tests, and `tsc --noEmit` all passed.
  - See: `docs/release-notes/phase-24a-1c-visual-token-alignment.md`
- Phase 24A-4.1: Mobile My Pets Session-Expiration Test Hardening (🛡️ LOCALLY VALIDATED AND REVIEWED / NOT BUILT OR DISTRIBUTED — 2026-07-30)
  - Added behavioral unit test to `mobile/__tests__/MyPetsScreen.test.tsx` verifying session-expiration logout invocation and error UI suppression.
  - Validation: 14 focused tests pass (+1 test), 32 complete mobile suite tests pass, `tsc --noEmit` clean (0 errors). Zero application source changed.
  - See: `docs/release-notes/phase-24a-41-mobile-my-pets-session-expiration-test-hardening.md`
- Phase 24A-4: Mobile My Pets Read-Only Screen (✅ LOCALLY VALIDATED AND REVIEWED / NOT BUILT OR DISTRIBUTED — 2026-07-30)
  - Original implementation at commit `33e579c` (2026-07-25). Phase 24A-4 was reconciliation and validation only — no mobile source changes.
  - Customer-facing read-only screen using authenticated `GET /client/pets`.
  - Independent Kiro re-review PASSED: navigation access, API integration, read-model fields, strict read-only, UI states, accessibility all confirmed.
  - Tests: 13 focused + 31 complete suite passed, TypeScript 0 errors. No build or distribution.
  - See: `docs/release-notes/phase-24a-4-mobile-my-pets-read-only-screen.md`
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
- Phase 1B.5C-D.1: Platform-Managed Protected Admin Controls (✅ VALIDATED AND CLOSED — 2026-07-30)
  - Data-driven `is_platform_protected` flag, `set-protected`/`unset-protected` actions, frontend toggle.
  - Matthew's profile seeded as Protected Platform Admin.
  - Matthew validated: profile shows Access: Protected, self-unprotect blocked, destructive actions disabled, other profiles unaffected.
  - See: `docs/release-notes/phase-1b5c-d1-platform-managed-protected-admin-controls.md`
- Phase 1B.5C-D.2: Remove Legacy Config Protection (✅ VALIDATED AND CLOSED — 2026-07-30)
  - Removed `Admin_Root` and `USmissionhero` from legacy fallback defaults and Terraform env vars.
  - Retained `support@usmissionhero.com` as permanent emergency fallback.
  - Production convergence confirmed via fresh Terraform refresh (zero pending Lambda changes).
  - D.2 was included in the earlier D.1 Lambda deployment; no separate D.2 apply was required.
  - Matthew validated protected-admin behavior in production.
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

- Phase 1B.5C-D.2: Remove Legacy Config Protection (✅ VALIDATED AND CLOSED — 2026-07-30)
- Phase 1B.5C-D.1: Platform-Managed Protected Admin Controls (✅ VALIDATED AND CLOSED — 2026-07-30)
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

**Production deployment 22P/22R failed manual validation due to drawer stability and viewport scrollbar/overflow issues. Release 22V deployed the combined drawer fixes (22S) and client bookings date/window display fixes (22U) to production. Manual validation passed successfully. No hotfix/main branch divergence remains — production now runs from `main`. Matthew ran a controlled smoke test (Release 22X) and found three findings. Release 22Y completed a read-only triage of these findings, identifying Cognito password reset restrictions and API Gateway DELETE method deployment issues as root causes. Release 22ZA implemented the mobile responsive foundation and accessible slide-out navigation drawer (pre-deploy validated). Release 22ZB implemented the full-screen Profile Editor mobile sheet layout (pre-deploy validated). Release 22ZC added keyboard-accessible stat cards, responsive filter controls stacking, and accessible data-label column labels on mobile request cards (pre-deploy validated). Phase 1B.2A backend-only Lambda package apply completed successfully, deploying the pet creation is_active hardening code to production. Phase 1B.2A ClientPetIndex GSI-only apply completed successfully, creating the global secondary database index in production (index backfilled and status ACTIVE). Phase 1B.2A ClientPetIndex query cutover deployed to production on 2026-07-20 (0 added, 13 changed, 0 destroyed). All 13 Lambda functions verified Active/Successful with expected CodeSha256. Matthew authenticated manual smoke PASSED (admin login, Client Management page, client drawer, admin pet list). Phase 1B.3 frontend deployed to production with /my-pets route, card-click drawer interaction, accessible cards, and mobile bottom-sheet. Hook-order hotfix applied. Matthew confirmed production works. Phase 1B.3 COMPLETE and CLOSED. Phase 1B.4A–E Client Drawer Editor Consolidation deployed to production. Matthew confirmed drawer View/Edit/Create experience works correctly, inline editor retired, Staff Management unaffected. Phase 1B.4A–E COMPLETE and CLOSED. Phase 1B.4F–H remain deferred. Phase 1B.5 (Pet Management and Client–Pet Association) is active. Phase 1B.5A and 1B.5A.1 deployed and validated (2026-07-22). Phase 1B.5B-A Staff Pet Editor and hotfixes deployed and validated (2026-07-23). Phase 1B.5C-A Customer Pet Editing deployed (2026-07-28) and validated (2026-07-30). Phase 1B.5C-A.1 admin pet care field hotfix deployed and validated (2026-07-30). Phase 1B.5C-B (active staff count fix) and 1B.5C-C (staff edit double-click fix) deployed (2026-07-28) and validated (2026-07-30). Phase 1B.5C-D.1 (platform-managed protected admin controls) deployed, seeded, and validated (2026-07-30). Phase 1B.5C-D.2 (remove legacy config protection) converged via D.1 deployment and validated (2026-07-30). Latest completed validated production release is Phase 1B.5C-D.2 (2026-07-30).**

**Next options:**
- Phase 24A-4: Mobile My Pets Read-Only Screen (requires Matthew approval; depends on 24A-3 ✅ complete and 1B.5C-A ✅ deployed)
- Phase 1B.5D–E: Pet Lifecycle safeguards and booking integration (deferred)
- Address remaining Phase 1B.4F–H staff drawer alignment (deferred, low priority)
- Begin Release 22ZD — Scheduler, Client Management, Platform Admin mobile polish (Phase 4 of 22Z plan)
- A later explicit deployment decision is required for the independently reviewed Release 22Y Finding 2 frontend fix; Google Calendar disconnect/API Gateway remediation remains separate and unapproved.
- Budget notification Terraform drift reconciliation (deferred, requires separate review and Matthew approval)
- Continue SaaS maturity priorities (blocked on EIN for Stripe live).
