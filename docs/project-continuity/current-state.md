# Current Project State

**Last Updated:** 2026-08-25 (ROUTE-GATE-A and ROUTE-GATE-B complete / DOMAIN-1 backend and Web route deployed / ROUTE-GATE-C and B1A login not approved)

---

## Production App

| Component | Status |
|-----------|--------|
| Web app (React/Vite) | ✅ DOMAIN-1 tenant-route Web v2 artifact from runtime source `440cab2` deployed to the shared compatibility host; direct tenant deep links and fail-closed unauthenticated boundary verified |
| Backend (Python/Lambda) | ✅ Deployed — DOMAIN-1 expected-tenant route bridge is active across the shared Lambda package; all 13 functions Active/Successful |
| API Gateway | ✅ Active — E3A authenticated Start and exact-request GET routes deployed; no Start/data-write Gate-B validation approved |
| DynamoDB | ✅ Single table, shared-tenant model |
| Google Calendar | ✅ One configured Google provider connection for `tog_and_dogs`; token storage/resolution is tenant-scoped (21H). `test_tenant_alpha` remains provider `none` / `not_configured`; independent providers for multiple tenants are not claimed. |
| Postmark email | ✅ Active (notifications, payment emails); approved production transactional email provider |

## Mobile / TestFlight

| Item | Status |
|------|--------|
| Framework | Expo / React Native |
| Latest build | iOS 1.0.0 (6) — TestFlight; Android 1.0.0 versionCode 4 — Google Play Internal Testing |
| Internal tester (Matthew) | ✅ Active |
| External tester (Ryan) | ✅ Android internal testing resumed (2026-08-15); physical Android install confirmed; operational review completed. Full historical remediation smoke matrix on Ryan's phone is NOT claimed. |
| Apple Beta App Review | ❓ Submitted (15J); outcome `UNKNOWN / NOT VERIFIED` |
| Public stores | ❌ No Apple App Store or Google Play Production release approved |

## Stripe / Payments

| Item | Status |
|------|--------|
| Sandbox payment workflow | ✅ Fully validated (12L–14I) |
| Live Stripe mode | ❌ Blocked (usmissionhero LLC EIN pending) |
| Admin payment link UX | ✅ Deployed |
| Payment email sending | ✅ Deployed |
| Payment terms draft | ✅ Written (not published to website) |
| Test credential exposure | ⚠️ Stripe test API and test webhook-signing credential exposure identified; rotation not performed and separately approval-gated; sandbox/test-mode only |

## Tenant / Multi-Business Readiness

| Feature | Status |
|---------|--------|
| Tenant Resolution Engine | ✅ Deployed (header, query parameter, subdomain, and path sources); active strict `multi` mode rejects unresolved tenants instead of using the compatibility fallback |
| Tenant Resolution Mode | ✅ Strict `TENANT_RESOLUTION_MODE=multi` active in production and validated (18T/18U); do not change without explicit Matthew approval |
| Tenant Isolation | ✅ Enforced across all primary database helpers (11E, 18V, 19K) |
| Entitlement Framework | ✅ Active with 8 enforced metrics (17A–17W) |
| Platform Admin Panel | ✅ Deployed (`/platform-admin/metrics`, `/platform-admin/tenants`) |
| Platform Tenant Management Control Plane | ✅ Specification Approved (2026-08-25); PTM-0 through PTM-13 defined (including PTM-3B read-only branding, PTM-3C mobile presentation, PTM-3D Web presentation, & PTM-3E cross-platform validation); Tier-1 PTM-0..2+4+5 required for admin provisioning; Tier-2 PTM-3B+3D+3E required for Web launch; Tier-3 Tier-2+PTM-3C+3E for Mobile launch; `docs/planning/platform-tenant-management-control-plane.md` |
| Control-plane / tenant-plane URL separation | 🟡 DOMAIN-1 backend bridge and `/t/:tenantSlug/admin` Web route are deployed; canonical tenant host/DNS separation remains unimplemented and unapproved |
| Strict-mode observation | ✅ Post-enable monitoring complete (18U — PASS) |
| Second tenant | ✅ Internal test tenant `test_tenant_alpha` created and validated (19D/19E); future customer/additional tenant provisioning remains approval-gated |
| Second-tenant application landing | 🟡 `/t/test-tenant-alpha/admin` is deployed and verified unauthenticated; authenticated tenant isolation remains separately approval-gated, so B1A remains blocked |
| Tenant provisioning script | ✅ Dry run and controlled test-tenant apply validated (19B/19D) |
| Tenant display branding | ✅ Single shared React application and single shared Expo app preserve runtime presentation (`docs/planning/tenant-aware-mobile-presentation-architecture.md`); PTM-3B/3C/3D/3E specified; PTM-10 subdomains require DNS-safe slug `test-tenant-alpha` |
| Tenant disable & restore | ✅ Gated & Validated in Production (20F — PASS) |
| Google Calendar Per-Tenant Token Isolation | ✅ Deployed & Validated (21H — PASS) |

## Current Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| EIN unavailable | Live Stripe payments blocked | Matthew (IRS) |
| Credential recovery pending execution | ROUTE-GATE-C/B1A-LOGIN remains blocked until approved credential recovery execution completes | Matthew / Antigravity |

## Current Work and Latest Closeouts

The Phase 24A entries below preserve their local-closeout wording at the time each phase was committed. The authoritative current mobile distribution state is the corrected internal pair: iOS `1.0.0 (6)` on TestFlight and Android `1.0.0` versionCode `4` on Google Play Internal Testing. Phase 24A mobile work is internally distributed and revalidated, but not publicly released.

- API Gateway Semantic Deployment Fingerprint (✅ INFRA-GATE-A V2 COMPLETE / DOMAIN-1 RC REBUILD PLANNING READY — 2026-08-24)
  - Reviewed commit `8d6e38b4488cf8eb4a39d8f4b069aa0d5367875d` was fast-forwarded unchanged into `main`. The original `route-gate-a-b1a-route-20260824.tfplan` remains permanently rejected and must never be applied; DOMAIN-1 requires a rebuilt RC and fresh plan after this completed infrastructure migration.
  - Replaced the 81-whole-provider-object `jsonencode` trigger with an explicit semantic manifest and provider-independent typed canonicalizer. Optional maps become `{}`, sets/lists become sorted `[]`, strings become `""`, and booleans/numeric defaults are explicit.
  - Fingerprinted behavior covers 53 resources, 54 non-CORS methods, 54 integrations, 47 CORS resources, the Cognito authorizer reference, response behavior, and both gateway responses. Provider-generated IDs and Lambda package metadata are excluded.
  - E3A `POST /admin/job/start` and `GET /admin/requests/{requestId}` remain semantically covered. DOMAIN-1 application/runtime files were not changed.
  - INFRA-GATE-A used the explicitly approved saved plan, then Terraform stopped before any managed AWS resource changed because `jsondecode(file(...))` had recorded LF raw input at plan time and saw semantically identical CRLF raw input at apply time. Production API deployment and stage remain `886zij`; API, authorizer, and all 13 Lambda fingerprints are unchanged.
  - State serial advanced 508 → 509 with unchanged lineage and canonically identical 250 managed resources/outputs. Serial 509 is authoritative; no decrement or manual state edit is appropriate. Failed plan SHA-256 `9629B084680E0E519B9C7F0CEE153514F99F68BA89961DA9CBEBDA6C105D99FA` is permanently invalid and must never be retried.
  - The remediation moves the object into native `deployment-semantics.tf.json`, eliminating the external raw `file()` result while retaining parsed semantic canonicalization. A narrow manifest-only LF attribute is defense in depth.
  - Validation: Terraform tests 10/10; Windows provider-free LF/CRLF/compact saved-plan stability pass; static source/config coverage and raw-byte audit pass; format and validate pass; tenant-route plus E3A 38/38; disabled-tenant/Platform boundaries 34/34; shared constants/API 24/24 and adapters 9/9 in an LF-neutral clone; Python compile and diff check pass.
  - A prior inspection identified Stripe test API and test webhook-signing credential exposure. No values were reused or recorded. Rotation was not performed and requires separate approval; Stripe remains sandbox/test-mode only.
  - Independent review returned `LINE-ENDING FIX APPROVED FOR MIGRATION-RC PLANNING`. Fresh branch `release/api-semantic-fingerprint-migration-v2-rc` starts from deployed baseline `732e48b`, excludes DOMAIN-1/unrelated main, and has zero `src/`, Web, Mobile, or shared-contract differences.
  - Production-scoped manifest validates at 50 resources, 52 methods, 52 integrations, 44 CORS resources, and two gateway responses. Plan-source `6f130fb4ba6d07b457a0466d8ee1f301dd6ba2da`; final pushed RC `02e5bfda9310e7c80884b34f9c2d61ebf0d9b8bb`.
  - Fresh locked, refresh-enabled state-509 plan `infra/prod/api-semantic-fingerprint-migration-v2-20260824.tfplan`, SHA-256 `519E3EE19BE40A9EE790D00736DD08857B312FE6B83EF7D5D6B265F3AAD86004`, is exactly 1 add, 1 change, 1 destroy: triggers-only API deployment replacement plus stage `deployment_id` only. Complete plan review found exactly two meaningful addresses and zero Lambda/API-topology/IAM/data/auth/DNS/Web/Mobile drift.
  - Matthew explicitly approved and the exact verified saved plan applied once from `2026-08-25T00:27:41.3307060Z` to `2026-08-25T00:27:46.9727543Z`. Terraform exited 0 with exactly 1 added, 1 changed, 1 destroyed. State advanced 509 → 510 on the unchanged lineage.
  - Production stage `prod` moved from deployment `886zij` to new immutable deployment `atxpw3`; the old deployment was removed after the stage transition. Live inventory remains 51 paths, 96 methods, 96 integrations, one authorizer, and 48 authorizer assignments. Topology, authorizer, and stage-config fingerprints are unchanged.
  - All 13 Lambda code/config fingerprints remain exactly equal to the pre-apply aggregate `0240C7A1...B011D4`, and every function remains Active/Successful. Non-write smoke returned expected 401/200/200; the observed API metric window contained one expected 4xx and zero 5xx, with no Lambda import/init error evidence.
  - INFRA-GATE-A v2 is complete. DOMAIN-1 subsequently used a fresh separately reviewed state-510 plan that proved and applied 0 add, 13 change, 0 destroy with zero API deployment/stage churn. B1A and Stripe test-secret rotation remain separately blocked and approval-gated.
  - See: `docs/release-notes/api-gateway-semantic-deployment-fingerprint-infrastructure-rc.md`, `docs/release-notes/api-gateway-semantic-fingerprint-migration-plan.md`, `docs/release-notes/api-gateway-semantic-fingerprint-line-ending-remediation.md`, `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-plan.md`, and `docs/release-notes/api-gateway-semantic-fingerprint-migration-v2-deployment.md`

- DOMAIN-1 + B1A-ROUTE (✅ ROUTE-GATE-A + ROUTE-GATE-B COMPLETE / BACKEND + WEB ROUTE DEPLOYED / ROUTE-GATE-C NOT APPROVED — 2026-08-25)
  - Accepted `platform.toganddogs.usmissionhero.com` as the control plane, `<tenant-slug>.toganddogs.usmissionhero.com` as the tenant plane, and the current host as a temporary compatibility surface.
  - The server-owned backend bridge registry is deployed and maps only `test-tenant-alpha` to canonical `test_tenant_alpha`. The `/t/:tenantSlug/admin` Web route is now deployed on the compatibility host; no production tenant record or schema changed.
  - Strict multi mode, active tenant metadata, and exact Cognito `custom:company_id` agreement are required before operational Web data loading. Unknown, inactive, missing, wrong, or lookup-failed context denies generically with no primary fallback.
  - Tenant routes suppress Platform Admin navigation; existing compatibility-host Platform Admin behavior remains intact. Direct Cognito login, refresh, new-password completion, and logout retain the path; hosted/Google callback work remains future.
  - Validation: focused backend 14/14; related tenant/Platform regressions 41/41; focused Web 7/7; full Web 317/317 plus legacy 99/99; Vite build 112 modules; shared validators 24/24, 7/7, 9/9, and 9/9; Python compile pass. Full lint retains the existing 50-error/9-warning repository baseline with zero findings in the new tenant utility/test files.
  - All three v2 failures were classified A/A/A after identical failure on deployed E3A. The test-only correction explicitly models active tenant metadata and `admin_override_until=None`; it changes no production/runtime source. Corrected validation passed 3/3, tenant isolation 51/51, DOMAIN-1 14/14, E3A 24/24, disabled-tenant/Platform 26/26, and explicit negative boundaries 11/11.
  - Fresh v3 branch `release/domain1-b1a-route-backend-v3-rc` composes deployed E3A `732e48b`, deployed semantic infrastructure `6f130fb4`, reviewed DOMAIN-1 replay `f3d48f1`, and test-only correction `3a04476`. Plan-source `46ab287` and evidence head `5de430c` are pushed.
  - Repository-native package SHA-256 `5BD46E19...AC558` / Base64 `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` contains exactly 40 eligible backend files and no caches/bytecode. Fresh locked, refreshed state-510 plan `domain1-b1a-route-backend-v3-20260825.tfplan`, SHA-256 `871EF0EA...97D00`, is exactly 0 add / 13 change / 0 destroy: the 13 shared-package Lambdas only, with package hash plus computed `last_modified`; all 336 API records, including deployment and stage, are no-op.
  - Matthew approved the exact saved plan. It applied once from `2026-08-25T16:13:06.8599655Z` to `16:14:28.0494479Z`, exit 0, with exactly 0 added / 13 changed / 0 destroyed. State advanced 510 -> 513 on the unchanged lineage; exact state comparison found only the 13 Lambda code metadata changes and unchanged outputs.
  - All 13 Lambdas are Active/Successful on CodeSha256 `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=` with every configuration fingerprint unchanged. API remained `prod -> atxpw3`, with unchanged 51 paths / 96 methods / 96 integrations / one authorizer / 48 assignments and identical topology/authorizer/stage fingerprints. Deployment-window metrics recorded four deliberate 4xx and zero 5xx.
  - ROUTE-GATE-A completed as a backend-only deployment. At that checkpoint, ROUTE-GATE-B and ROUTE-GATE-C/B1A-LOGIN were still independent and unapproved, and no Web, DNS, Cognito, or data action occurred.
  - Fresh Web branch `release/domain1-b1a-route-web-v2-rc` starts from independently proven deployed Web source `4c7975d`, replays only the reviewed tenant-route/bootstrap delta, and adds test-only stale-state and failure-boundary coverage. Exact runtime/build source is `440cab2`; pushed evidence head is `154731c`.
  - Live `index.html`, `index-BtB1oa0E.js`, and `index-BroXJAxV.css` matched a production build of `4c7975d` byte-for-byte. CloudFront still maps 403/404 to `/index.html` with 200, and both tenant deep links returned the deployed index without mutation.
  - Web validation passed 255/255 total tests (96 legacy plus 159 Vitest), including tenant routing 13/13; Vite production build passed. Candidate JS is `index-BpY_nxft.js`, SHA-256 `F0BEFB80...AEB782`; CSS remains `index-BroXJAxV.css`, SHA-256 `69A7D7BC...616990`.
  - The fresh RC review concluded ROUTE-GATE-B was ready for Matthew's approval. During the later approved pre-deploy check, three reviewed text/PWA objects were proven semantically identical but CRLF-deployed versus LF-reviewed; the exact approved artifact normalized those bytes as expressly covered by the full 11-file sync approval.
  - Matthew approved only the exact Web artifact from runtime source `440cab2` / evidence head `154731c`. The 11-file artifact synced successfully to the established production bucket from `2026-08-26T00:31:06.934Z` to `00:31:09.661Z`; new `index-BpY_nxft.js` and `index.html` were deployed and retired `index-BtB1oa0E.js` was deleted.
  - Post-sync S3 verification matched all 11 approved hashes. CloudFront invalidation `I4G5JQMQZFA5GRB4L1Z3M3P17T` for `/*` completed. Edge HTML/JS/CSS hashes matched, both tenant deep links loaded, malformed/unknown routes exposed no operational content, and `/about` rendered normally without authentication.
  - API remained `prod -> atxpw3`; all 13 Lambdas remained Active/Successful on `W9RuGay6...axVg=`. Available deployment-window CloudFront metrics were 0% 4xx and 0% 5xx, and browser console review was clean.
  - ROUTE-GATE-B is **COMPLETE**. ROUTE-GATE-C/B1A-LOGIN remains **NOT APPROVED**; no login, Cognito, DNS, data, Stripe, Calendar, notification, Mobile, E1/E2/O1, assignment, Start, Complete, or B1A/B1B/B2/B3 action occurred.
  - See: `docs/planning/adr-domain-1-tenant-access-routing.md`
  - See: `docs/release-notes/domain-1-b1a-route-local-implementation.md`
  - See: `docs/release-notes/domain-1-b1a-route-backend-v2-rc.md`
  - See: `docs/release-notes/domain-1-b1a-route-test-harness-triage.md`
  - See: `docs/release-notes/domain-1-b1a-route-backend-v3-rc.md`
  - See: `docs/release-notes/domain-1-b1a-route-backend-v3-deployment.md`
  - See: `docs/release-notes/domain-1-b1a-route-web-v2-rc.md`
  - See: `docs/release-notes/domain-1-b1a-route-web-v2-deployment.md`

- Ryan Slice E3B.1 Mobile Visit Workflow Safety Remediation (✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED / NOT IN CURRENT INTERNAL BUILDS — 2026-08-20)
  - One resolver now supplies authoritative child identity to both Start and Complete. Occurrence identity wins; route/occurrence or parent/occurrence disagreement fails safe with no mutation. Singular legacy identity works without a route ID; ambiguous multi-child identity remains blocked.
  - A synchronous shared visit-mutation ref lock prevents duplicate immediate Start calls and Start/Complete races. Mounted/request-sequence guards reject stale async results. Start uses server/refetched metadata only and adds no `IN_PROGRESS`; Complete remains exact-child, passes notes, and never invokes parent review `COMPLETED`.
  - Failed exact hydration retains safely known parent dates/windows as distinct refresh-required, non-actionable placeholders with no guessed child IDs. The unchanged 1 + N Mobile hydration remains a future optimization.
  - Validation: focused E3B.1 19/19; related Mobile integration 23/23; Mobile contracts/colors 15/15; full Mobile 148/148 across 16 suites; TypeScript; shared 24/24, 7/7, and 9/9; unchanged E3A 24/24; diff check pass. No Mobile lint script is configured. No build/distribution occurred.
  - See: `docs/release-notes/ryan-slice-e3b1-mobile-visit-workflow-safety-remediation.md`

- Ryan Slice E3B Mobile Occurrence Selection and Start → Complete (✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED / NOT IN CURRENT INTERNAL BUILDS — 2026-08-20)
  - Mobile consumes E3A exact child occurrences; Check-In date × window children remain distinct and exact `job_id` reaches Start/Complete.
  - Start uses server metadata, blocks duplicate taps, and reconciles ambiguous failure by exact refetch. No `IN_PROGRESS` exists.
  - Singular legacy identity remains compatible; ambiguous multi-child identity blocks instead of invoking parent-wide Complete. Full Mobile 132/132 and TypeScript pass. No build/distribution occurred.

- Ryan Slice E3A Child Start Contract and Occurrence Read Model (✅ DEPLOYED TO PRODUCTION / GATE B0 COMPLETE / B1A–B3 NOT APPROVED — 2026-08-23)
  - Authenticated `POST /admin/job/start` targets exactly one canonical `ASSIGNED` child JOB. A conditional atomic update writes authoritative server UTC `started_at`, authenticated actor metadata, update metadata, and exactly one `JOB_STARTED` child audit entry.
  - Child and parent canonical statuses and assignment remain unchanged; `IN_PROGRESS` was not added. Start creates no job/request, Calendar mutation, or notification.
  - Owner/admin authorization follows existing per-job conventions; staff must match the child `worker_id`. Tenant ownership is enforced. Replays return the original timestamp without writing, and concurrent losers use a strongly consistent read to resolve the persisted winner.
  - Existing exact-request reads now expose distinct, deterministic child occurrences—including multi-date Walk, Check-In date×window, and fixed Overnight—with parent relationship, schedule, assignment, Start, and completion metadata. Legacy singular `job_id` and missing optional metadata remain compatible without migration.
  - Complete is unchanged and remains valid with or without prior Start. E3A itself includes no Mobile Start UI; E3B and E3B.1 remain not built, distributed, or deployed.
  - Validation: focused 24/24; affected backend 137/137; full backend 977 passed / same 100 exact-checkpoint failures versus 953 / 100; shared/adapters pass; full Web 310/310 plus legacy 99/99/build; full Mobile 128/128/typecheck; diff check pass.
  - Matthew-approved Gate A deployed RC `732e48b930f6fd9aac958351c4ac7823c14cf3e0` using only saved plan SHA-256 `01DA5C94E022420A0E3456ED888F9800DDD972FACA32BF61106FFE801B696854` and backend ZIP SHA-256 `C7E407664A170CA1C2077029E6750BDEBE736E648E505666DE3DED091C66635A` (`14 added, 14 changed, 1 destroyed`).
  - All 13 Lambdas are Active/Successful with the approved code hash and unchanged configuration fingerprints. API Gateway deployment `886zij`, Cognito authorization, Lambda proxy integrations, CORS, all 50 baseline paths, and eight critical legacy routes passed.
  - Non-write checks: unauthenticated Start and exact GET returned 401 before integration; both OPTIONS routes returned 200. Authenticated malformed Start and authenticated exact-record GET were skipped because no approved auth context or preapproved internal record was available.
  - Matthew-approved Gate B0 completed on 2026-08-23: exactly one `AdminEnableUser` enabled the sole existing `test_tenant_alpha` identity. It remains `CONFIRMED`, mapped to `test_tenant_alpha`, and in `client,owner`; no password, invitation, group, role, or tenant-mapping change occurred.
  - No safe existing authenticated session/credentials were available, so login was not attempted. Read-only validation found only tenant metadata and zero client, staff, pet, request, or job records. No notification, Calendar/Stripe action, Start, Complete, or production data creation occurred.
  - Subsequent manual UI review confirmed that `test_tenant_alpha` has no normal tenant-specific application landing URL. The identity remains enabled and is not declared broken. B1A is now explicitly **BLOCKED** until a fail-closed expected-tenant route/host agrees with the existing authenticated company claim and login isolation is validated. B1B, B2, B3, Mobile build/distribution, tester changes, and Ryan testing remain unapproved.
  - The canonical decision is `platform.toganddogs.usmissionhero.com` for the control plane and `<tenant-slug>.toganddogs.usmissionhero.com` for tenant applications. A bounded claim-matched route now exists only in local source; deployment and independent login validation still require separate approval.
  - See: `docs/planning/tenant-access-client-onboarding-operational-workflow-alignment.md`
  - See: `docs/release-notes/ryan-slice-e3a-child-start-contract-occurrence-read-model.md`

- Ryan Slice E2 Intake Approval to Scheduler Handoff (✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED — 2026-08-20)
  - Customer-intake approval exposes **Approve & Open Scheduler** as a distinct approval-to-Scheduler semantic while still submitting exactly one canonical `APPROVED` operation through existing `/admin/review`.
  - No second booking is created: E2 never calls `createAdminBooking()`, adds no synthetic status, and never automatically retries approval.
  - After success, five bounded existing-request reads at most (immediate, then 500 ms intervals; 2 seconds maximum) match the same `request_id`, merge refreshed data, and accept `job_id` or non-empty `job_ids` as ready.
  - Readiness or timeout opens the existing Scheduler. Timeout does not roll back approval and shows a refresh-before-assigning warning. The handoff does not assign a sitter or complete scheduling, and Scheduler date visibility remains unchanged.
  - Approval failure performs no readiness polling and no navigation; an in-flight guard prevents duplicate submissions.
  - Validation: focused 24/24; required combined suites 86/86; full Web 310/310 plus legacy 99/99; Vite build 111 modules; exact 17-error/5-warning AdminDashboard lint baseline preserved; diff check pass.
  - Remaining Slice E decision: Mobile **Start Visit → Complete Visit**; no approved canonical `IN_PROGRESS` transition exists for this workstream.
  - See: `docs/release-notes/ryan-slice-e2-intake-approval-scheduler-handoff.md`

- Ryan Slice E1 Web Admin Guided Assignment and Calendar Actions (✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED — 2026-08-19)
  - A pure workflow-action resolver now distinguishes status transitions from assignment UI handoff and local Calendar navigation.
  - `APPROVED`, `BOOKED`, and `JOB_CREATED` visit bookings expose **Assign Sitter**, which opens the existing staff selector and retains the existing `assignWorker` payload. `ASSIGN` cannot enter the `reviewRequest` status-transition path.
  - `ASSIGNED` and `SCHEDULED` records with a worker expose **View in Calendar**, which switches locally to the existing Scheduler without a status mutation, Calendar mutation, or navigation-only API request.
  - Complete, Cancel, intake approval, Archive, Edit, secondary actions, confirmations, RBAC, notifications, Calendar behavior, and service/status contracts remain unchanged.
  - Validation: E1 focused 16/16; required combined suites 58/58; full Web 302/302 plus legacy 99/99; Vite build 111 modules; zero E1-introduced lint findings; diff check pass.
  - Slice E2 now resolves the intake approval handoff without a second booking. Mobile **Start Visit → Complete Visit** remains deferred because no approved canonical `IN_PROGRESS` transition exists.
  - See: `docs/release-notes/ryan-slice-e1-web-admin-guided-actions.md`

- Ryan O1 Overnight Fixed 9PM–7AM Scheduling (✅ COMMITTED / PUSHED / NOT DEPLOYED — 2026-08-18)
  - Matthew approved fixed `OVERNIGHT` service from local 21:00 on each selected start-date through local 07:00 on the following calendar date. Nominal duration is 600 minutes / 10 hours; there is no visits/day, selectable window, custom time, custom range, or pricing behavior.
  - The generic shared contract now represents fixed schedules and retains `legacyDurationMinutes: 720`. Generated Web, Mobile, and Backend adapters are deterministic. Backend-derived `canonical_schedule_mode: fixed` is the persisted new/history boundary; unmarked historical records retain their legacy 720-minute/all-day or exact-time Calendar interpretation without migration.
  - New customer/Admin writes reject client-supplied scheduling fields and derive contract values. Job creation emits one stable UUIDv5 child per selected start-date, with selected-date 21:00, next-date 07:00, stable Calendar identity, and replay convergence. Calendar builds the two local wall clocks independently, preserving 21:00→07:00 across ordinary, spring-forward, and fall-back nights.
  - Web customer, Admin New Visit, Mobile Intake, and MasterScheduler show the fixed schedule and following-morning meaning without a selector. Existing client/pet/date/sitter/notes, immediate Admin `APPROVED`/`VISIT_BOOKING`, assignment, cancellation, and booking-level notification behavior remain intact.
  - Independent review returned `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_IMPLEMENTATION_CORRECT`. Validation: shared 23/23; adapters 9/9; O1 backend 22/22; combined O1/W1/Slice A/Slice B/R1 backend 90/90; focused Web 52/52; full Web 286/286 plus legacy 99/99 and 110-module build; Mobile typecheck, focused Intake 28/28, combined Intake/D1 34/34, and full Mobile 128/128.
  - No deployment, Mobile build/distribution, production write, Calendar mutation, notification send, infrastructure, Cognito, tenant, Stripe, or public-site action occurred. Pricing, deposit, legacy retirement, Stripe automation, Slice E, Slice F, deployment, and Mobile build/distribution remain gated.
  - See: `docs/release-notes/ryan-o1-overnight-fixed-scheduling.md`

- Ryan W1 20-Minute Walk Canonical Scheduling (✅ COMMITTED / PUSHED / NOT DEPLOYED — 2026-08-17)
  - Matthew and Ryan approved exactly one canonical Morning (06:30–09:30), Mid-day (10:30–15:30), or Evening (18:00–21:30) window for each new `WALK_20MIN` request. The selected window applies to every selected date; no per-date model was introduced.
  - The shared contract uses `windowSelectionMode: exactly_one`; generated Web, Mobile, and Backend adapters were regenerated deterministically. New writes require one canonical `visit_windows` entry and reject `visits_per_day`, missing/multiple/duplicate windows, legacy IDs, and unknown IDs.
  - One deterministic child job is created per selected date with the same occurrence window, canonical 06:30/10:30/18:00 start, exactly 20-minute Calendar duration, stable job/Calendar identity, and replay-safe behavior.
  - Web customer, Web Admin New Visit, and Mobile intake have contract-derived exactly-one controls, clean cross-service resets, preserved surrounding payload/workflow fields, and no pricing. MasterScheduler shows canonical Walk label, occurrence window, and child start while preserving existing item handoff/actions.
  - Historical Walk services and `AFTERNOON`/`ANYTIME`/legacy `visit_window` records remain readable. Assignment remains booking/batch level with one `STAFF_ASSIGNED` and one `VISIT_SCHEDULED` notification pair per batch.
  - Independent review returned `RYAN_W1_WALK_CANONICAL_SCHEDULING_IMPLEMENTATION_CORRECT`. Validation: shared 23/23; adapters 9/9; focused W1 backend 20/20; Slice B 31/31; R1 3/3; combined affected backend 68/68; focused Web customer/Admin/Scheduler 50/50; full Web 284/284 plus legacy 99/99 and 110-module build; Mobile typecheck, focused Intake 27/27, combined Intake/D1 33/33, and full Mobile 127/127.
  - No deployment, Mobile build/distribution, production write, Calendar mutation, notification send, infrastructure, Cognito, tenant, Stripe, or public-site action occurred. Overnight, pricing, deposit, legacy retirement, Stripe automation, Slice E, and Slice F remain gated.
  - See: `docs/release-notes/ryan-w1-walk-canonical-scheduling-windows.md`

- Ryan Cross-Platform Release Readiness Hardening R1 (✅ COMMITTED / PUSHED / NOT DEPLOYED — 2026-08-17)
  - MasterScheduler service filtering now derives the complete nine-service operational/history catalog from generated `SERVICE_TYPES`, including `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT`, while preserving `All Services`, legacy service options, canonical labels, exact case-sensitive equality, and existing actions.
  - New real-handler backend tests prove a simulated mid-batch interruption across 3 dates × 2 Check-In windows retries to exactly six deterministic children with stable identities and no duplicates; cancellation reaches all six children, deduplicates Calendar IDs, and tolerates already-gone results; assignment reaches all six children and emits one `STAFF_ASSIGNED` plus one `VISIT_SCHEDULED` for the batch.
  - Independent review returned `RYAN_RELEASE_READINESS_HARDENING_R1_IMPLEMENTATION_CORRECT`. Final validation: R1 backend 3/3; Scheduler focused 16/16; Slice C 18/18; C1 13/13; full Web 281/281 plus 99/99 legacy; Web build 110 modules; Mobile typecheck, focused D1/D2 29/29, and full Mobile 123/123; diff checks pass.
  - No Walk timing, Overnight duration/hours, pricing, deposit, or legacy-retirement policy was chosen. No deployment, Mobile build/distribution, production validation/write, Calendar mutation, notification, or infrastructure action occurred.
  - See: `docs/release-notes/ryan-release-readiness-hardening-r1.md`

- Cognito Custom Email Sender + Postmark (✅ LOCAL IMPLEMENTATION COMPLETE / NOT DEPLOYED — 2026-08-15)
  - Added an isolated dedicated Lambda package, pinned AWS Encryption SDK dependencies, customer-managed symmetric KMS key/alias, least-privilege role, scoped Cognito invoke permission, and auth-module Custom Email Sender configuration.
  - Supports only `CustomEmailSender_ForgotPassword`; all other triggers fail closed without delivery. Branded Postmark delivery uses `Togs & Dogs <support@usmissionhero.com>`, reply-to `support@usmissionhero.com`, and message stream `outbound`.
  - Validation: 27/27 focused, 216/216 stable notification regression, and 862 passed / 97 unchanged baseline failures in the full backend suite versus 835 passed / the same 97 failures at archived clean HEAD. Two package builds were byte-identical; Terraform format and validate pass.
  - No Terraform plan/apply, Cognito change, KMS grant, Postmark email, password reset, deployment, or production write occurred. Existing generic Cognito email remains active until a separately reviewed and explicitly approved deployment.
  - See: `docs/release-notes/release-cognito-custom-email-sender-postmark.md`

- Ryan Cross-Platform Services, Scheduling & Workflow Alignment Slices A–C + C1 + D1–D2 (✅ COMMITTED / PUSHED / NOT DEPLOYED; D1–D2 NOT BUILT OR DISTRIBUTED — 2026-08-17)
  - Ryan completed an operational platform review confirming target service model: 20-Minute Walk, Check-In (30 min, 1–3 visits/day selectable), and Overnight.
  - Slice A (`53818bc`) extends the canonical service contract with `WALK_20MIN`, `CHECK_IN`, lifecycle/new-booking metadata, visits/day options, allowed windows, and window-selection mode; generated Web, Mobile, and Backend adapters agree deterministically. Independently reviewed (Kiro: IMPLEMENTATION_CORRECT).
  - Slice B (`37bb806`) validates new CHECK_IN writes, persists `visits_per_day` + canonical ordered `visit_windows`, expands selected dates × windows into deterministic child jobs with stable UUIDv5 identities, one Calendar event per child at canonical 06:30/10:30/18:00 starts for 30 minutes, idempotent replay, and 409-conflict handling. Independently reviewed (Kiro: IMPLEMENTATION_CORRECT).
  - Ryan's physical Android internal-testing install confirmed and operational review completed (2026-08-15).
  - Slice D1 makes the five existing admin/owner dashboard statistic cards accessible touch targets. Pending Review and Needs Sitter open Requests with transient canonical `PENDING_REVIEW`/`APPROVED` filters; Scheduled, Today's Visits, and This Week's Visits open the existing Schedule. The current Schedule has no admin date/range route parameter, so no unsupported today/week focus was invented.
  - D1 validation: focused dashboard/request/schedule/navigator 10/10, TypeScript pass, and full mobile 115/115 across 13 suites. It has not been built, distributed, deployed, or received by Ryan.
  - Slice D2 locally wires customer Mobile intake to active/mobile-supported/new-booking-eligible service metadata and contract-derived Check-In visits/day/windows. It submits canonical ordered `visit_windows` plus `visits_per_day` for Check-In and omits both for Walk/Overnight. State resets, review copy, and accessibility are covered.
  - D2 validation: focused Intake 23/23, TypeScript pass, and full mobile 123/123 across 13 suites. Independent review returned `RYAN_SLICE_D2_IMPLEMENTATION_CORRECT`; D2 is committed and pushed but has not been built, distributed, deployed, or received by Ryan. The current Android versionCode 4 contains neither D1 nor D2.
  - Slice C locally wires Web customer intake to canonical active/new-booking-eligible service metadata: `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT`. The generated contract supplies Check-In visits/day, active windows, labels, times, exact count rules, canonical ordering, confirmed duration, review display, and accessibility semantics. Check-In payloads carry `visits_per_day` plus ordered `visit_windows`; Walk/Overnight omit Check-In-only fields.
  - Slice C validation: focused IntakeForm 18/18, full Web 99/99 legacy plus 271/271 Vitest across 22 files, and Vite build success with 110 modules transformed. Independent review returned `RYAN_SLICE_C_IMPLEMENTATION_CORRECT`; Slice C is committed and pushed but not deployed. No shared/generated, backend, Mobile, production, public-site, or distribution change occurred.
  - Slice C1 locally closes the staff/admin creation gap in the existing owner/admin New Visit modal. The modal derives all nine canonical admin options from generated `SERVICE_TYPES`, preserves the seven prior options and `PET_SITTING` default, and adds contract-driven Check-In visits/day plus canonical structured windows. Check-In payloads preserve client, pets, dates, sitter preference, and notes while adding numeric `visits_per_day` and ordered `visit_windows`; Walk/Overnight omit all Check-In-only fields.
  - The actual admin path remains authenticated `POST /client/requests` with `source: admin_created`, producing an immediate `APPROVED` `VISIT_BOOKING` for a tenant-scoped existing/offline client. Slice B already handles validation, date×window jobs, Calendar child events, and replay safety; backend change was not required. Notification and assignment semantics remain unchanged.
  - C1 validation: AdminDashboard 13/13, combined C1 + Slice C 31/31, full Web 280/280 Vitest plus 99/99 legacy, successful 110-module build, and focused Slice B backend 31/31. Independent review returned `RYAN_SLICE_C1_IMPLEMENTATION_CORRECT`; C1 is committed and pushed but not deployed.
  - Legacy service/window compatibility is preserved. W1 resolves new `WALK_20MIN` window scheduling, and committed/pushed O1 resolves new `OVERNIGHT` fixed 21:00→07:00 scheduling while preserving unmarked history.
  - Slice C/C1 deployment remains separately gated before cross-platform release. Slice E1–E2 Web Admin handoffs are implemented and validated locally but not deployed; the remaining Mobile Slice E decision and Slice F public-site/pricing remain separately gated.
  - No production deployment, booking, job, Calendar mutation, or pricing change occurred.
  - See: `docs/release-notes/ryan-slice-a-canonical-service-time-window-contract.md`
  - See: `docs/release-notes/ryan-slice-b-check-in-booking-job-calendar-semantics.md`
  - See: `docs/release-notes/ryan-slice-c-web-check-in-intake-parity.md`
  - See: `docs/release-notes/ryan-slice-c1-admin-check-in-creation-parity.md`
  - See: `docs/release-notes/ryan-slice-d1-mobile-dashboard-navigation.md`
  - See: `docs/release-notes/ryan-slice-d2-mobile-check-in-intake-parity.md`

- Preview-Only V1 Platform Admin Tenant-Onboarding Orchestrator (✅ COMMITTED AND PUSHED / NOT DEPLOYED — 2026-08-11)
  - Platform Admin validation and preview APIs with technically enforced read-only Lambda IAM.
  - Provides tenant-input validation, existence/conflict checks, metadata preview, tier-limit preview, audit preview, hash/expiry, and downstream checklist.
  - No Apply, Create Tenant, or approval-persistence capability exists in V1.
  - Feature is NOT available in production until a separately approved deployment occurs.
  - See: `docs/release-notes/release-platform-admin-tenant-onboarding-preview-v1.md`

- Business Owner Getting Started Guide (✅ LOCALLY COMPLETE / KIRO `GUIDE_CORRECT` / COMMITTED / PUSHED / NOT PUBLIC — 2026-08-11)
  - Added the repository-only onboarding and operations guide at `docs/operations/business-owner-getting-started.md` for a nondeveloper business owner, with a secondary platform-admin audience.
  - Documents the current assisted onboarding model, tenant/role boundaries, first login, branding, staff/client/pet workflows, request/booking/job lifecycle, Calendar, notifications, sandbox-only payments, internal-only mobile distribution, practical checklists, support boundaries, and known limitations.
  - Includes an internal self-service gap matrix and ranked top-five automation opportunities. No tenant, user, application, integration, infrastructure, production, payment, or distribution change occurred.
  - Kiro independently reviewed the five-file documentation candidate and returned `GUIDE_CORRECT` / `READY_FOR_BUSINESS_OWNER_GUIDE_COMMIT_DECISION`. The guide is committed and pushed as repository documentation; no public publication or release is claimed.

- Web Customer Self-Service Password Recovery (✅ PRODUCTION FRONTEND DEPLOYED / SAFE SMOKE PASS / COGNITO E2E PASS — 2026-08-15)
  - Deployed isolated V2 RC `4c7975d` onto production baseline `ed7a01f`.
  - Frontend-only: S3 sync + CloudFront invalidation `I3RWSM6SQK81OWOK1SR22J3PDE` (Completed).
  - Live assets: `index-BtB1oa0E.js`, `index-BroXJAxV.css`.
  - No backend, Lambda, Terraform, or API Gateway deployment.
  - Safe production smoke: login loads, Forgot Password visible, recovery UI opens, local validation works, Back to Sign In works. No browser errors.
  - Matthew manually validated end-to-end Cognito recovery: forgot-password request succeeded, verification email arrived, code accepted, password changed, subsequent login succeeded. Disposition: PASSWORD_RECOVERY_COGNITO_E2E_PASS.
  - Remaining production UX improvement: Cognito default verification email remains generic and unbranded. The branded Postmark Custom Email Sender is locally implemented but not deployed.
  - See: `docs/release-notes/release-web-customer-self-service-password-recovery.md`

- Phase 24A-9C.2 / Phase 24A-9C: Paired Remediation Builds and Revalidation (✅ PAIRED REMEDIATION BUILDS COMPLETE / REMEDIATION REVALIDATION COMPLETE / PASS — 2026-08-10)
  - The authoritative internal-validation pair is iOS `1.0.0 (6)` (EAS `7d159e13-a3a3-41ad-96ab-cd6f83a582b0`; TestFlight submission `9eeb37ff-7f89-49d2-b6ff-25f34adb993d`) and Android `1.0.0` versionCode `4` (EAS `808d1f45-2f03-423d-886c-1e4649c1d782`), both built from exact source SHA `bf9f80d95c1846f197bab24d96463906bc26bfce`.
  - TestFlight distribution succeeded. Matthew's physical-iPhone remediation revalidation passed: `IOS_PET_DETAIL_CRASH_REMEDIATION_PASS`, `IOS_KEYBOARD_REMEDIATION_PASS`, `VIEW_MY_BOOKINGS_REMEDIATION_PASS`, and `MOBILE_REMEDIATION_REGRESSION_PASS`.
  - Android versionCode 4 is active on Google Play Internal Testing and available to internal testers: `ANDROID_REMEDIATION_PLAY_INTERNAL_COMPLETE` and `ANDROID_REMEDIATION_VALIDATION_PASS`.
  - The Android test environment was not established as an actual phone/tablet, so `ANDROID_PHYSICAL_DEVICE_PENDING` remains accurate; no physical-device pass is claimed.
  - Build 5 and versionCode 3 are historical validation artifacts only. Earlier user-run pet-update and care-request writes succeeded historically and were not repeated.
  - See: `docs/release-notes/phase-24a-9c2-paired-remediation-revalidation-closeout.md`

- Phase 24A-9C.1: iOS Physical Smoke Defect Remediation (✅ COMPLETE / KIRO IMPLEMENTATION_CORRECT / COMMITTED AND PUSHED / REVALIDATED IN BUILD 6 — 2026-08-10)
  - Implementation commit `2c3e22a95e0062bed5e40f42e39e4669f94a1d43` fixed the legacy pet-value crash, keyboard obscuration, and nested Bookings navigation.
  - Pre-build validation remained: 0 TypeScript errors; 18/18 constants; 9/9 adapters; 31/31 backend; 29/29 My Pets; 19/19 Intake + Bookings; 109/109 full mobile tests across 10 suites; clean diff check.
  - Corrected iOS Build 6 and Android versionCode 4 subsequently passed Matthew's remediation validation within the documented platform-evidence boundary.
  - See: `docs/release-notes/phase-24a-9c1-ios-physical-smoke-defect-remediation.md`

- Phase 24A-9B.4: Google Play Internal Testing Setup (🔗 COMPLETE / ANDROID VERSIONCODE 3 UPLOADED / INTERNAL TESTING ACTIVE / `3 (1.0.0)` AVAILABLE TO INTERNAL TESTERS / ZERO PUBLIC RELEASE — 2026-08-09)
  - Android AAB (EAS `e2bc9a1d-666b-4698-882f-6aa7ba7c2132`) manually uploaded to Google Play Console Internal Testing track.
  - Play Console confirmed: `Latest release: 3 (1.0.0)` — Available to internal testers.
  - Google Play service-account JSON / EAS Submit automation not yet configured (future pipeline hardening item).
  - Ryan remains paused; public release remains unapproved.
  - See: `docs/release-notes/phase-24a-9b4-google-play-internal-testing.md`

- Phase 24A-9B: Paired iOS + Android Internal Builds (✅ COMPLETE / ORIGINAL PAIRED IOS + ANDROID ARTIFACTS CREATED / SUPERSEDED FOR REMEDIATION VALIDATION / ZERO PUBLIC RELEASE — 2026-08-09)
  - Compiled paired mobile binaries from exact Git SHA `8a1ce46c0a8bd0d02f4000188b21e115b370281c` and shared marketing version `1.0.0`.
  - iOS build `1.0.0 (5)` (EAS build ID `c7b7d9da-056b-45a8-86cd-cd6882969464`) auto-submitted to Apple App Store Connect / TestFlight (`fe722283-3205-4a87-8d9a-40162407966c`).
  - Android build `1.0.0` versionCode `3` (EAS build ID `e2bc9a1d-666b-4698-882f-6aa7ba7c2132`) signed `.aab` uploaded to Google Play Internal Testing. Play Console: `Latest release: 3 (1.0.0)` — Available to internal testers.
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 18 backend customer pet tests, 13 backend status parity tests, 104 full mobile tests across 10 suites.
  - Public publishing remains unapproved; Ryan testing remains paused; production write smoke testing remains unapproved.
  - See: `docs/release-notes/phase-24a-9b-paired-ios-android-internal-builds.md`

- Phase 24A-9A: Cross-Platform Mobile Release Pipeline Assessment & Preparation (✅ COMPLETE / RELEASE PIPELINE DEFINED / PAIRED IOS + ANDROID RELEASE MODEL ESTABLISHED / NON-WRITE SMOKE MATRIX DOCUMENTED — 2026-08-09)
  - Established repeatable paired release model (One Git SHA `60754d97c1f8cd139e81434531500f21abcdb4d5` → paired iOS IPA + Android AAB artifacts).
  - Formulated paired build commands (`eas build --platform ios` and `eas build --platform android`).
  - Defined Production Write Safety Boundary (SAFE non-write smoke testing vs WRITE approval required for pet edit save and intake submit).
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 18 backend customer pet tests, 13 backend status parity tests, 104 full mobile tests across 10 suites.
  - This preparation phase triggered zero EAS builds; its later Phase 24A-9B gate was separately approved and completed.
  - See: `docs/release-notes/phase-24a-9a-cross-platform-release-pipeline-assessment-and-preparation.md`

- Phase 24A-5: Mobile My Pets Editing (✅ COMPLETE / INTERNALLY DISTRIBUTED IN IOS BUILD 6 AND ANDROID VERSIONCODE 4 / NOT PUBLICLY RELEASED — 2026-08-09)
  - Added authenticated client self-service pet profile editing to `MyPetsScreen.tsx` using `PUT /client/pets/{petId}` (API helper `updateClientPet` in `client.ts`).
  - Pre-populates all 10 client-editable fields, enforces contract max lengths (`PET_FIELDS`), supports optional string clearing, dirty-state tracking (`isDirty`), double-submit prevention, and unsaved changes confirmation (`Alert.alert`).
  - Preserved Phase 24A-7 visual tokens (`COLORS`) and Phase 24A-8 accessibility semantics (`accessibilityRole`, `accessibilityLabel`, `accessibilityState`).
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 18 backend customer pet tests, 25 focused MyPets tests, 104 full mobile tests across 10 suites.
  - Kiro independent review: `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_5_COMMIT_DECISION`).
  - Committed (`93fe98a5c2f28481cd53a85a9479567c413a534d`) and pushed to `origin/main`; later included in the corrected internal pair and remediation revalidation. No public release occurred.
  - See: `docs/release-notes/phase-24a-5-mobile-my-pets-editing.md`

- Phase 24A-8: Accessibility Validation (✅ COMPLETE / INTERNALLY DISTRIBUTED IN IOS BUILD 6 AND ANDROID VERSIONCODE 4 / NOT PUBLICLY RELEASED — 2026-08-09)
  - Screen-reader accessibility attributes (`accessibilityRole`, `accessibilityLabel`, `accessibilityState`, `accessibilityLiveRegion`) and touch target sizes (~44pt minimum height) added across `IntakeScreen.tsx`, `BookingsScreen.tsx`, `RequestCard.tsx`, and `StatusBadge.tsx`.
  - Added 4 dedicated accessibility unit tests in `mobile/__tests__/IntakeScreen.test.tsx`.
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 18 focused tests, 93 full mobile tests across 10 suites.
  - Kiro independent review: `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_8_COMMIT_DECISION`).
  - Committed (`18b51e9170ac7d3b2de94770bd16fc02d35f22a5`) and pushed to `origin/main`; later included in the corrected internal pair and remediation revalidation. No public release occurred.
  - See: `docs/release-notes/phase-24a-8-accessibility-validation.md`

- Phase 24A-7: Visual Consistency Polish (✅ COMPLETE / INTERNALLY DISTRIBUTED IN IOS BUILD 6 AND ANDROID VERSIONCODE 4 / NOT PUBLICLY RELEASED — 2026-08-09)
  - Standardized mobile action button radii to `8px` (`BookingsScreen.tsx` header CTA, `IntakeScreen.tsx` step navigation and submit buttons) and card surface radii to `12px` (`IntakeScreen.tsx` service options grid).
  - Replaced raw `#ffffff` string literals with generated token `COLORS.white`. Assessed `MyPetsScreen.tsx` and `RequestCard.tsx` and confirmed they were already fully aligned.
  - Preserved all status badge pill shapes (`borderRadius: 99`), selection chips (`borderRadius: 20`), navigation, forms, validation, status display semantics, and business logic.
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 28 focused tests, 89 full mobile tests across 10 suites.
  - Kiro independent review: `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_7_COMMIT_DECISION`).
  - Committed (`b34f0460c50fdf5033c4155b9e07ca4ea30e3868`) and pushed to `origin/main`; later included in the corrected internal pair and remediation revalidation. No public release occurred.
  - See: `docs/release-notes/phase-24a-7-visual-consistency-polish.md`

- Phase 24A-6: Mobile Care-Request Intake Flow (✅ COMPLETE / INTERNALLY DISTRIBUTED IN IOS BUILD 6 AND ANDROID VERSIONCODE 4 / NOT PUBLICLY RELEASED — 2026-08-09)
  - Implemented complete 3-step mobile care request intake wizard (`IntakeScreen.tsx`), integrated navigation route (`AppNavigator.tsx`), added `+ Book Care` and `+ Book Pet Care` buttons (`BookingsScreen.tsx`), added API helper `submitClientRequest` (`client.ts`), and created a 10-test unit suite (`IntakeScreen.test.tsx`).
  - Derived service options from `SERVICE_TYPES` contract metadata, excluded `MEET_GREET`, enforced client terms/privacy policy agreement (`accepted_terms: true`, `accepted_privacy: true`, `terms_version: "1.0"`, `privacy_version: "1.0"`), and submitted booking requests to backend (`POST /client/request`) without client-assigned status.
  - Loaded existing read-only client pets via `getClientPets()` (`GET /client/pets`, Phase 24A-4 contract) without invoking pet modification or creation endpoints. Phase 24A-5 was still deferred at this phase checkpoint and subsequently completed.
  - Validation: 0 TypeScript errors, 18 constants, 9 adapters, 14 focused tests, 89 full mobile tests across 10 suites.
  - Kiro independent review: `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_6_COMMIT_DECISION`).
  - Committed (`2831205a092ab94b774ac7bcdaada27bea19976e`) and pushed to `origin/main`; later included in the corrected internal pair and remediation revalidation. No public release occurred.
  - See: `docs/release-notes/phase-24a-6-mobile-care-request-intake-flow.md`

- Phase 24A Roadmap & Continuity Reconciliation (📚 HISTORICAL 2026-08-07 CHECKPOINT / SUBSEQUENT PHASES 5–9C COMPLETE)
  - Reconciled Phase 24A roadmap and project continuity state across repository documentation.
  - Confirmed the combined Phase 2C contract workstream (2C.1 request statuses and 2C.2 service types) is 100% locally complete, validated, independently reviewed by Kiro, committed, and pushed.
  - At that checkpoint, Phase 24A-6 was the next unfinished feature task and Phases 5/9 remained gated. Those statements were later superseded by completed implementation, internal distribution, and 9C remediation revalidation.
  - See: `docs/release-notes/phase-24a-roadmap-continuity-reconciliation.md`

- Phase 24A-2C.1C: Mobile Request-Status Display Compatibility Wiring (✅ COMPLETE / INTERNALLY DISTRIBUTED IN IOS BUILD 6 AND ANDROID VERSIONCODE 4 / NOT PUBLICLY RELEASED — 2026-08-07)
  - Wired generated `REQUEST_STATUSES` from `mobile/src/contracts/generatedContracts.ts` into mobile status badge (`StatusBadge.tsx`) for upper-cased contract-backed badge labels and customer appointments screen (`BookingsScreen.tsx`) for exact-match entries.
  - Preserved customer contextual overrides (`ASSIGNED` → `"Scheduled"`, `JOB_CREATED` → `"Scheduled"`), staff navigation filter tabs (`RequestListScreen.tsx`), staff dashboard metrics counter (`DashboardScreen.tsx`), badge styling, colors, borders, typography, layout, padding, and accessibility properties.
  - Added 10 dedicated compatibility unit tests in `mobile/__tests__/RequestStatusDisplayCompatibility.test.tsx`. Validation: 18 constants, 9 adapters, 79 full mobile Jest tests across 9 suites.
  - Kiro independent review classified candidate as `IMPLEMENTATION_CORRECT` (`READY_FOR_PHASE_24A_2C_1C_COMMIT_DECISION`).
  - Committed (`83225b6800b3ed16eb825f61f06e1027347a2e52`) and pushed to `origin/main`; later included in the corrected internal pair. No public release occurred.
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

- Latest completed backend production release: **DOMAIN-1 ROUTE-GATE-A** (13 package-only Lambda updates, API unchanged, 2026-08-25). Latest completed Web production release: **DOMAIN-1 ROUTE-GATE-B Web v2** from runtime source `440cab2` (2026-08-25 local / 2026-08-26 UTC); ROUTE-GATE-C/B1A-LOGIN remains unapproved.
- Latest completed locally validated shared-contract phase: **Phase 24A-2C.2D.4** (assessed no-implementation closeout; Phase 2D stream locally complete).
- Current mobile distribution: Phase 24A mobile work through remediation is included in iOS Build 6 and Android versionCode 4, internally distributed and revalidated. No public-store release is approved.
- Completed Phase 24A-2B subphases: **Phase 24A-2B.1**, **Phase 24A-2B.2A**, and **Phase 24A-2B.2B**.
- Phase 24A-2B overall: **LOCALLY VALIDATED AND REVIEWED / ALL PLANNED PHASE 24A-2B CUSTOMER PET FIELD AND VALIDATION WIRING COMPLETE**. Mobile portions are present in the internal pair; no blanket web/backend production deployment is claimed.
- Phase 24A-2C.2 service-type work: **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D LOCALLY COMPLETE**. Mobile portions are present in the internal pair; no blanket web/backend production deployment is claimed. Phases 2C.2A and 2C.2C are locally validated and reviewed. Phase 2C.2B planning, 2B.1 web display compatibility, 2B.2A customer IntakeForm canonical selection, 2B.2B CareCard correction, and 2B.2C MasterScheduler canonical filter correction are locally complete at their review gates. Phase 2D.1 parity/validator hardening, Phase 2D.2 generated backend metadata, Phase 2D.3 duration/friendly-name calendar wiring, and Phase 2D.4 optional color-metadata assessment closeout are locally complete with exact behavior preserved. Backend accepted-identifier policy, production assessment, normalization, migration/deprecation, scheduler-specific metadata, additional availability changes, tenant-configurable color policy, existing-event resynchronization, and deployment remain deferred and unapproved.
- Phase 24A-2C.1 request-status work: **LOCALLY COMPLETE / WEB AND MOBILE DISPLAY COMPATIBILITY WIRED / COMMITTED AND PUSHED** across 2C.1A–2C.1C. Any web/backend production deployment decision remains separate.
- Separate deferred scopes: staff pet-contract work, mobile pet creation, backend identifier policy, production assessment/migration, branded Cognito/Postmark sender deployment, O1/E1 and broader Ryan-slice deployment, remaining Slice E design, public mobile release, additional mobile builds/distribution, and further Ryan or formal production-write testing.
- Phase 24A-1C: Cross-platform visual token alignment (✅ LOCALLY VALIDATED AND REVIEWED — 2026-07-30)
  - Aligned 6 remaining color tokens per Matthew's explicit approval: `primaryHover` (`#a37213`), `textMuted` (`#6a6a66`), `border` (`#e2dfd9`), `borderSoft` (`#edf2ee`), `success` (`#4a7c59`), `danger` (`#d64933`).
  - Contract `shared/tokens/colors.json` updated to 100% aligned (`"aligned": true` across all 13 tokens).
  - Regenerated `web/src/generated/color-tokens.css` and `mobile/src/theme/generatedColors.ts`.
  - Cleaned up duplicate manual CSS declarations in `web/src/index.css` so `@import` is authoritative.
  - Validation: 9 contract tests, 7 adapter tests, 229 web tests, Vite production build, 31 mobile Jest tests, and `tsc --noEmit` all passed.
  - See: `docs/release-notes/phase-24a-1c-visual-token-alignment.md`
- Phase 24A-4.1: Mobile My Pets Session-Expiration Test Hardening (🛡️ LOCALLY VALIDATED AND REVIEWED / SUBSEQUENTLY INCLUDED IN INTERNAL BUILD 6 AND VERSIONCODE 4 — 2026-07-30)
  - Added behavioral unit test to `mobile/__tests__/MyPetsScreen.test.tsx` verifying session-expiration logout invocation and error UI suppression.
  - Validation: 14 focused tests pass (+1 test), 32 complete mobile suite tests pass, `tsc --noEmit` clean (0 errors). Zero application source changed.
  - See: `docs/release-notes/phase-24a-41-mobile-my-pets-session-expiration-test-hardening.md`
- Phase 24A-4: Mobile My Pets Read-Only Screen (✅ COMPLETE / INTERNALLY DISTRIBUTED IN IOS BUILD 6 AND ANDROID VERSIONCODE 4 / NOT PUBLICLY RELEASED — 2026-07-30)
  - Original implementation at commit `33e579c` (2026-07-25). Phase 24A-4 was reconciliation and validation only — no mobile source changes.
  - Customer-facing read-only screen using authenticated `GET /client/pets`.
  - Independent Kiro re-review PASSED: navigation access, API integration, read-model fields, strict read-only, UI states, accessibility all confirmed.
  - Tests at the local checkpoint: 13 focused + 31 complete suite passed, TypeScript 0 errors. No build occurred in that phase; the screen was subsequently included in the corrected internal pair.
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
  - Terraform reconciliation (2026-08-21): `infra/prod/budgets.tf` now declares the complete intentional production set (ACTUAL 80%, ACTUAL 100%, FORECASTED 80%) with the existing subscriber, $20 limit, and `Client=TogAndDogs` scope unchanged. This correction eliminated known drift before E3A Gate A and was included in the approved saved-plan apply as a confirmed budget no-op; AWS Budget behavior did not change.
  - Not blocked by or blocking Phase 1B.5C-A.
  - See `docs/planning/phase-23b-aws-budget-coverage-and-cost-visibility-dashboard.md`
  - See `docs/release-notes/phase-23b-step-1-budget-coverage-verification.md`
  - See `docs/release-notes/phase-23b-cost-visibility-dashboard-and-budget-alerts.md`
  - See `docs/operations/aws-cost-visibility-operating-guide.md`

## Cross-Platform UI Alignment

- Direction approved: shared design tokens, terminology, validation, API contracts.
- React/Vite remains the web framework. Expo/React Native remains mobile.
- No website rewrite to React Native Web.
- Mobile pet editing API (PUT /client/pets/{petId}) was deployed 2026-07-28 and validated 2026-07-30 via Phase 1B.5C-A. Phase 24A-5 (Mobile My Pets Editing) is 100% LOCALLY COMPLETE (committed and pushed).
- Phase 24A-1A–9C are complete within their approved boundaries. Slice D2 is committed and pushed and the mobile source passes 123/123 tests across 13 suites; unbuilt D1/D2 source is not included in the current internal builds.
- Corrected iOS Build 6 and Android versionCode 4 are internally distributed and revalidated. No public Apple App Store or Google Play Production release, Ryan expansion, or additional EAS work is approved.
- Ryan's physical Android install and operational review are confirmed; the full historical remediation smoke matrix was not rerun, and Phase 24A-9D formal production-write validation remains separately gated.
- Web customer self-service password recovery is production frontend deployed and passed Matthew's live Cognito E2E validation on 2026-08-15. The separate branded Cognito/Postmark sender remains committed/pushed but not deployed.

## Latest Completed Releases

- Web Customer Self-Service Password Recovery (✅ PRODUCTION FRONTEND DEPLOYED / SAFE SMOKE PASS / COGNITO E2E PASS — 2026-08-15)
- Ryan O1 Overnight Fixed Scheduling (✅ COMMITTED / PUSHED / NOT DEPLOYED — 2026-08-18)
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

**Production deployment 22P/22R failed manual validation due to drawer stability and viewport scrollbar/overflow issues. Release 22V deployed the combined drawer fixes (22S) and client bookings date/window display fixes (22U) to production. Manual validation passed successfully. No hotfix/main branch divergence remains — production now runs from `main`. Matthew ran a controlled smoke test (Release 22X) and found three findings. Release 22Y completed a read-only triage of these findings, identifying Cognito password reset restrictions and API Gateway DELETE method deployment issues as root causes. Release 22ZA implemented the mobile responsive foundation and accessible slide-out navigation drawer (pre-deploy validated). Release 22ZB implemented the full-screen Profile Editor mobile sheet layout (pre-deploy validated). Release 22ZC added keyboard-accessible stat cards, responsive filter controls stacking, and accessible data-label column labels on mobile request cards (pre-deploy validated). Phase 1B.2A backend-only Lambda package apply completed successfully, deploying the pet creation is_active hardening code to production. Phase 1B.2A ClientPetIndex GSI-only apply completed successfully, creating the global secondary database index in production (index backfilled and status ACTIVE). Phase 1B.2A ClientPetIndex query cutover deployed to production on 2026-07-20 (0 added, 13 changed, 0 destroyed). All 13 Lambda functions verified Active/Successful with expected CodeSha256. Matthew authenticated manual smoke PASSED (admin login, Client Management page, client drawer, admin pet list). Phase 1B.3 frontend deployed to production with /my-pets route, card-click drawer interaction, accessible cards, and mobile bottom-sheet. Hook-order hotfix applied. Matthew confirmed production works. Phase 1B.3 COMPLETE and CLOSED. Phase 1B.4A–E Client Drawer Editor Consolidation deployed to production. Matthew confirmed drawer View/Edit/Create experience works correctly, inline editor retired, Staff Management unaffected. Phase 1B.4A–E COMPLETE and CLOSED. Phase 1B.4F–H remain deferred. Phase 1B.5 (Pet Management and Client–Pet Association) is active. Phase 1B.5A and 1B.5A.1 deployed and validated (2026-07-22). Phase 1B.5B-A Staff Pet Editor and hotfixes deployed and validated (2026-07-23). Phase 1B.5C-A Customer Pet Editing deployed (2026-07-28) and validated (2026-07-30). Phase 1B.5C-A.1 admin pet care field hotfix deployed and validated (2026-07-30). Phase 1B.5C-B (active staff count fix) and 1B.5C-C (staff edit double-click fix) deployed (2026-07-28) and validated (2026-07-30). Phase 1B.5C-D.1 (platform-managed protected admin controls) deployed, seeded, and validated (2026-07-30). Phase 1B.5C-D.2 (remove legacy config protection) converged via D.1 deployment and validated (2026-07-30). The later Web Customer Self-Service Password Recovery frontend deployment completed safe production smoke and live Cognito E2E validation on 2026-08-15; the established backend deployment baseline remains Phase 1B.5C-D.2.**

**Next options:**
- Preview V1 onboarding deployment assessment (read-only/design-only); password recovery was already deployed separately on 2026-08-15
- Phase 24A-9D: Formal production-write validation (separately gated; not authorized by the completed 9C revalidation)
- Phase 1B.5D–E: Pet Lifecycle safeguards and booking integration (deferred)
- Address remaining Phase 1B.4F–H staff drawer alignment (deferred, low priority)
- Begin Release 22ZD — Scheduler, Client Management, Platform Admin mobile polish (Phase 4 of 22Z plan)
- A later explicit deployment decision is required for the independently reviewed Release 22Y Finding 2 frontend fix; Google Calendar disconnect/API Gateway remediation remains separate and unapproved.
- Budget notification Terraform drift reconciliation (deferred, requires separate review and Matthew approval)
- Continue SaaS maturity priorities using the guide's self-service gap matrix: Stripe Checkout, billing dashboard, and pricing/signup remain blocked or sequenced behind EIN/product decisions; broader self-service invites require product/security/Cognito design.
