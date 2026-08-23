# Ryan Cross-Platform Services, Scheduling & Workflow Alignment

**Source:** Ryan operational platform review (2026-08-15)
**Status:** Slices A–C, C1, D1–D2, R1 Hardening, W1, O1, E1, and E2 Not Deployed; E3A Backend/API Gate A Deployed / Gate B0 Complete / B1A–B3 Not Approved; E3B/E3B.1 Not Built, Distributed, or Deployed; Slice F Deferred

---

## Confirmed Service Direction

| Service | Duration | Visits/Day | Intake |
|---------|----------|-----------|--------|
| 20-Minute Walk | 20 min | — | ✅ |
| Check-In | 30 min | 1, 2, or 3 (selectable) | ✅ |
| Overnight | 600 min nominal; fixed 21:00→07:00 next day | — | ✅ |
| Meet & Greet | ~45 min | — | ❌ (admin-scheduled) |

Ryan explicitly confirmed "1–3" means the number of Check-In visits PER DAY.

---

## Confirmed Time Windows

| ID | Label | Hours |
|----|-------|-------|
| MORNING | Morning | 06:30–09:30 |
| MIDDAY | Mid-day | 10:30–15:30 |
| EVENING | Evening | 18:00–21:30 |

## Slice A Local Contract Result

Slice A is locally implemented and committed. The existing canonical `shared/constants/service-types.json` contains both `services` and structured `windows`, with deterministic Web, Mobile, and Backend generated adapters.

- New canonical target IDs: `WALK_20MIN` and `CHECK_IN`.
- `CHECK_IN` encodes `[1, 2, 3]` visits/day, active windows `[MORNING, MIDDAY, EVENING]`, and `match_visits_per_day` selection mode.
- Historical `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, and `PET_SITTING` remain readable and historically labeled.
- Undecided future eligibility for `WALK_60MIN`, `DROPIN_1HR`, and `DROPIN_3HR` is explicitly `pending`.
- New target eligibility is separate from the unchanged legacy `availableInIntake` runtime flag, preventing premature Slice C/D selector changes.
- W1 resolved new 20-Minute Walk scheduling. O1 resolved new Overnight scheduling as fixed 21:00→07:00 the following local date (committed/pushed/not deployed), while unmarked historical Overnight records retain legacy compatibility.
- `AFTERNOON` and `ANYTIME` remain legacy-readable with no invented canonical time bounds.

See `docs/release-notes/ryan-slice-a-canonical-service-time-window-contract.md`.

## Slice B Local Transactional Result

Slice B is committed and pushed but not deployed. New `CHECK_IN` writes require contract-valid `visits_per_day` and distinct `visit_windows`; ordered dates × ordered windows produce deterministic child jobs and one canonical-time Calendar event per child. Stable job and Calendar occurrence identities make replay duplicate-safe. Legacy services/windows remain readable, booking-level notification batching is preserved, and Walk/Overnight policy is unchanged.

See `docs/release-notes/ryan-slice-b-check-in-booking-job-calendar-semantics.md`.

### Check-In Window Rules

- 1 visit/day: customer/staff selects one window
- 2 visits/day: customer/staff selects two distinct windows
- 3 visits/day: Morning + Mid-day + Evening (all three)

### Overnight

Matthew approved a separate fixed Overnight scheduling model: each selected date is the local start date, service runs 21:00 through 07:00 on the following local date, and nominal duration is 600 minutes. Overnight does not inherit Check-In windows and exposes no time/window selector. O1 is committed, pushed, and not deployed.

### Walk

W1 resolved the new 20-Minute Walk model as exactly one Morning, Mid-day, or Evening window applied to every selected date.

---

## Mobile Dashboard Navigation Feedback

Ryan wants dashboard/home stat cards to be tappable:

| Card | Navigation Target |
|------|------------------|
| Pending Review | Requests filtered to PENDING_REVIEW |
| Needs Sitter | Requests filtered to APPROVED |
| Scheduled | Schedule |
| Today's Visits | Schedule (today) |
| This Week's Visits | Schedule |

### Slice D1 Local Dashboard Navigation Result

Slice D1 is committed and pushed but not built, distributed, or deployed. Pending Review and Needs Sitter navigate to the existing Requests tab with transient contract-checked `PENDING_REVIEW` and `APPROVED` filters. Scheduled, Today's Visits, and This Week's Visits navigate to the existing Schedule tab. Because the current admin/owner Schedule has no date/range route contract, D1 does not invent today/week parameters; date-focused navigation remains deferred. All five cards have button semantics, meaningful labels and hints, and unchanged full-card visual surfaces.

See `docs/release-notes/ryan-slice-d1-mobile-dashboard-navigation.md`.

---

## Slice D2 Local Mobile Intake Result

Slice D2 is committed and pushed but not built, distributed, or deployed. Independent review returned `RYAN_SLICE_D2_IMPLEMENTATION_CORRECT`. Mobile customer intake now presents the active, mobile-supported services whose canonical `newBookingEligibility` is `eligible`: 20-Minute Walk, Check-In, and Overnight. Check-In alone consumes contract-derived visits/day options, active allowed windows, window labels, and structured times; it submits canonical ordered `visits_per_day` and `visit_windows`. Changing counts or services normalizes or clears Check-In-only state, and Walk/Overnight payloads omit those fields.

Web Slice C and admin Slice C1 are now committed and pushed but not deployed. They consume the same canonical target service and Check-In metadata without changing Mobile source. D2 remains absent from the current internal builds and must not be distributed or deployed without a separately reviewed cross-platform release decision.

Validation at D2 closeout was focused Intake 23/23, TypeScript pass, and full Mobile 123/123 across 13 suites. D2 has not been built, distributed, deployed, or received by Ryan. W1 resolved new Walk scheduling, and O1 resolved the approved fixed Overnight schedule (committed/pushed/not deployed). Overnight pricing, deposits, and legacy eligibility decisions remain unresolved.

See `docs/release-notes/ryan-slice-d2-mobile-check-in-intake-parity.md`.

---

## Slice C Local Web Intake Result

Slice C is committed and pushed but not deployed after independent review returned `RYAN_SLICE_C_IMPLEMENTATION_CORRECT`. Web customer intake now uses the canonical active/new-booking-eligible interpretation and presents `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT`. The generated contract supplies Check-In visits/day, allowed windows, labels, structured times, exact count behavior, canonical ordering, confirmed duration, and review display.

Check-In submits `visits_per_day` plus ordered `visit_windows`; Walk and Overnight omit all Check-In-only fields. Count/service transitions deterministically normalize or clear hidden state. O1 now adds contract-derived fixed Overnight display/review while preserving client omission of scheduling fields. The contract has no `supportedOnWeb` field, so Web needs no platform-specific allowlist; `availableInIntake` remains unchanged transitional compatibility metadata with no remaining Web runtime consumer.

Validation: focused IntakeForm 18/18, full Web 99/99 legacy plus 271/271 Vitest across 22 files, and Vite build success with 110 modules transformed. No shared/generated, backend, Mobile, production, deployment, distribution, pricing, Calendar, or public-site change occurred.

See `docs/release-notes/ryan-slice-c-web-check-in-intake-parity.md`.

---

## Slice C1 Local Admin Creation Result

Slice C1 is committed and pushed but not deployed after independent review returned `RYAN_SLICE_C1_IMPLEMENTATION_CORRECT`. The existing owner/admin New Visit modal derives the complete canonical catalog from generated `SERVICE_TYPES`, adding the target Walk and Check-In entries while preserving the seven prior staff-managed compatibility services and `PET_SITTING` default.

Check-In alone renders contract-derived 1/2/3 visits and Morning/Mid-day/Evening structured windows, enforces the exact selected-window count, normalizes count/service transitions, and submits canonical ordered `visits_per_day` plus `visit_windows`. O1 now gives Overnight fixed contract context without a selector or scheduling payload. Legacy compatibility services retain their existing single-window behavior.

The real API path is the existing authenticated `/client/requests` admin branch. It immediately creates an `APPROVED` `VISIT_BOOKING` for a tenant-scoped existing/offline client and asynchronously invokes jobs. Slice B already validates this path and owns date×window child jobs plus Calendar events, so no backend change was required. Creation notification, later assignment notification batching, preferred-sitter semantics, RBAC, and tenant isolation are unchanged.

Validation: AdminDashboard 13/13, combined C1 + Slice C 31/31, full Web 280/280 Vitest plus 99/99 legacy, successful 110-module build, and focused Slice B backend 31/31. No deployment, production write, Calendar event, notification, Mobile, shared/generated, backend, infrastructure, or public-site action occurred.

See `docs/release-notes/ryan-slice-c1-admin-check-in-creation-parity.md`.

---

## Release Readiness Hardening R1 Local Result

R1 is committed and pushed but not deployed after independent review returned `RYAN_RELEASE_READINESS_HARDENING_R1_IMPLEMENTATION_CORRECT`. The Web MasterScheduler now derives its complete readable operational/history filter catalog from generated `SERVICE_TYPES`, so target `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT` records are directly filterable alongside the retained legacy services. `All Services`, exact case-sensitive filtering, canonical display labels, occurrence data, and existing selection/action handoff remain unchanged.

Real-handler backend characterization proves: a simulated interruption during 3 dates × 2 windows converges on retry to exactly six stable Check-In children with no duplicates; six-child cancellation cascades consistently, deduplicates Calendar event IDs, and tolerates existing already-gone semantics; and 2 dates × 3 windows assignment reaches all six children with one `STAFF_ASSIGNED` and one `VISIT_SCHEDULED` notification for the batch.

R1 added no scheduling business policy. W1 subsequently resolved new Walk windows/start time, and O1 resolved new Overnight hours/duration (committed/pushed/not deployed). Pricing, deposits, and legacy retirement remain explicit decision gates. No deployment, production validation/write, Mobile build, or distribution occurred.

See `docs/release-notes/ryan-release-readiness-hardening-r1.md`.

---

## W1 20-Minute Walk Canonical Scheduling Local Result

W1 is committed and pushed, not deployed, and independently reviewed as `RYAN_W1_WALK_CANONICAL_SCHEDULING_IMPLEMENTATION_CORRECT`. Matthew and Ryan approved exactly one canonical Morning (06:30–09:30), Mid-day (10:30–15:30), or Evening (18:00–21:30) window for each new `WALK_20MIN` request. The same window applies to every selected date; no per-date window model was introduced.

The shared contract and generated adapters now express `windowSelectionMode: exactly_one`. Web customer, Web Admin New Visit, and Mobile intake provide contract-derived single-selection controls and `visit_windows: [<canonical ID>]` without `visits_per_day`. Backend new-write validation, deterministic one-child-per-date creation, stable Calendar identity, exact canonical start, and 20-minute duration are aligned. Legacy Walk/window reads and booking-level assignment notification batching remain intact.

See `docs/release-notes/ryan-w1-walk-canonical-scheduling-windows.md`.

---

## O1 Overnight Fixed Scheduling Result

O1 is committed, pushed, independently reviewed as correct, and not deployed. Matthew approved fixed `OVERNIGHT` service from local 21:00 on each selected start-date through local 07:00 on the following date, with 600-minute nominal duration and no visits/day, selectable window, custom time, or custom range.

The generic contract and regenerated adapters express the fixed schedule. New-write validation rejects client scheduling fields and persists a backend-owned fixed marker. That marker distinguishes new O1 records from unmarked historical Overnight records, which retain legacy 720-minute/all-day or exact-time compatibility without migration. One deterministic child is created per selected start-date. Calendar constructs the start and following-date end as separate local wall clocks, preserving 21:00→07:00 across DST changes. Web customer, Admin, Mobile, and MasterScheduler show the fixed following-morning context; payload, assignment, cancellation, and booking-level notifications retain their existing surrounding behavior.

Validation: shared 23/23, adapters 9/9, focused O1 backend 22/22, affected backend 90/90, focused Web 52/52, full Web 286/286 plus legacy 99/99/build, and Mobile typecheck/Intake 28/28/combined Intake+D1 34/34/full 128/128. Independent review returned `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_IMPLEMENTATION_CORRECT`. O1 has not been built, distributed, deployed, received by Ryan, or exercised against production systems.

See `docs/release-notes/ryan-o1-overnight-fixed-scheduling.md`.

---

## Workflow Simplification Direction

Each operational screen should expose one obvious primary next action where practical.

| Phase | Recommended Action |
|-------|-------------------|
| Intake reviewed | Approve & Open Scheduler (existing approval + local handoff) |
| Booking created | Assign Sitter |
| Sitter assigned | View in Calendar |
| Visit day (staff mobile) | Start Visit → Complete Visit |

**Preserved safety gates:** RBAC, required human review, payment authorization, cancellation confirmation, tenant isolation, and notification confirmation must NOT be bypassed.

### Slice E1 Local Web Admin Result

Slice E1 is implemented and validated locally but not deployed. A pure resolver now distinguishes backend status transitions from assignment and navigation handoffs. `APPROVED`, `BOOKED`, and `JOB_CREATED` visit bookings surface **Assign Sitter**, which opens the existing staff selector and retains the existing `assignWorker` payload. `ASSIGNED` and `SCHEDULED` bookings surface **View in Calendar**, which switches to the existing Scheduler using current in-memory data without issuing a navigation-only API request. `ASSIGN` and `VIEW_CALENDAR` are blocked from the `reviewRequest` status path.

Complete, Cancel, Archive, Edit, intake approval, confirmation, RBAC, notification, Calendar, service-type, and status-compatibility behavior remain unchanged. `MasterScheduler.jsx`, APIs, contracts, backend, infrastructure, and Mobile source were not changed. Validation: focused E1 16/16, required combined suites 58/58, full Vitest 302/302, legacy 99/99, build success with 111 modules, and zero E1-introduced lint findings.

See `docs/release-notes/ryan-slice-e1-web-admin-guided-actions.md`.

### Slice E2 Local Web Admin Result

Slice E2 is implemented and validated locally but not deployed. Customer-intake approval now exposes **Approve & Open Scheduler** with a distinct approval-to-Scheduler semantic. It submits exactly one existing canonical `APPROVED` operation through `/admin/review`; it never calls `createAdminBooking()`, never invents a combined backend status, and never automatically retries approval.

After approval succeeds, AdminDashboard boundedly reads the existing admin-request list up to five times—immediately and then every 500 ms, for a maximum 2-second window—matches the same `request_id`, merges the refreshed request locally, and recognizes `job_id` or non-empty `job_ids` readiness. It then opens the existing Scheduler. If readiness is delayed or reconciliation fails, approval remains successful, Scheduler still opens, and a non-destructive initialization warning instructs the admin to refresh before assigning. Approval failure performs no polling and no navigation. An in-flight ref prevents duplicate submissions.

The action opens Scheduler but does not assign a sitter or complete scheduling. Existing Scheduler date filtering is unchanged, so a future booking may exist in Scheduler data without being visible in the current day/week. E1 assignment/navigation, standard visit-booking approval, Complete, Cancel, Archive, Edit, secondary actions, RBAC, notifications, backend automation, Calendar behavior, and tenant enforcement remain unchanged. Validation: E1+E2 focused 24/24, required combined suites 86/86, full Web 310/310 plus legacy 99/99, build success with 111 modules, zero E2-introduced lint findings, and diff check pass.

See `docs/release-notes/ryan-slice-e2-intake-approval-scheduler-handoff.md`.

### Slice E3A Production Backend and Read-Contract Result

Slice E3A backend/API Gate A was deployed and non-write verified on 2026-08-21. Authenticated `POST /admin/job/start` targets one canonical `ASSIGNED` child JOB and atomically writes server UTC `started_at`, actor/update metadata, and one `JOB_STARTED` child audit entry. It preserves child and parent status plus assignment; no canonical `IN_PROGRESS`, Calendar mutation, notification, or parent write exists. Owner/admin conventions are preserved, while staff identity must match child `worker_id`. Conditional writes and strongly consistent replay resolution ensure one first timestamp/audit event and return the original persisted result on replay.

The existing exact admin-request read now exposes authoritative child occurrences with unambiguous parent relationship, date/end-date/window/index/count, child status, worker, start/end time, Start metadata, completion metadata, and visit notes. Same-date Check-In windows remain distinct and deterministic; Walk and Overnight children retain their generated occurrence semantics. Legacy singular `job_id` and missing optional fields are read safely without migration or historical inference.

Complete is unchanged and remains valid with or without Start metadata. E3A itself includes no Mobile UI; E3B subsequently added Mobile consumption and E3B.1 hardened it. Early/late/same-day policy, correction, mandatory Start, client visibility, notifications, Calendar effects, offline time, and admin-on-behalf UX remain deferred decisions.

Gate A used exact RC `732e48b` and the exact reviewed saved Terraform plan (`14 added, 14 changed, 1 destroyed`). All 13 Lambdas and API deployment `886zij` passed health/configuration checks; unauthenticated Start/GET boundaries returned 401 and OPTIONS returned 200. Matthew-approved Gate B0 completed on 2026-08-23 with exactly one `AdminEnableUser` for the sole existing `test_tenant_alpha` identity. The identity remains `CONFIRMED`, `client,owner`, and test-tenant mapped; credentials were preserved. No safe authenticated session was available, so login was not attempted. Tenant data remains metadata-only, and no notification, Start, Complete, or data/profile creation occurred. B1A, B1B, B2, B3, Mobile build/distribution, tester changes, and Ryan testing remain unapproved.

See `docs/release-notes/ryan-slice-e3a-child-start-contract-occurrence-read-model.md`.

### Slice E3B.1 Local Mobile Safety Result

E3B.1 is implemented and validated locally but not deployed, built, distributed, or included in current internal builds. One resolver supplies both Start and Complete with an exact child action ID. Authoritative occurrence identity wins, any route/occurrence or parent/occurrence disagreement blocks mutation with a refresh-required state, singular legacy identity works without a route ID, and ambiguous multi-child identity is never guessed from dates or ordering.

A synchronous shared visit-mutation lock prevents duplicate immediate Start calls and keeps Complete from racing Start reconciliation. Mounted/request-sequence guards prevent late Start, refetch, or Complete results from updating an obsolete screen. Start uses only server or authoritative-refetch metadata and introduces no `IN_PROGRESS`; Complete keeps exact per-child notes behavior and never calls parent review `COMPLETED`.

If exact Schedule hydration fails, safely known list-level dates/windows remain visible as distinct non-actionable placeholders with empty child IDs and a refresh-required message. The existing 1 + N hydration pattern is intentionally unchanged and remains a future optimization. No E3A/E3B backend, contract, Calendar, notification, or product-policy semantic changed. Focused E3B.1 19/19, full Mobile 148/148, TypeScript, shared validators, and unchanged E3A 24/24 pass.

See `docs/release-notes/ryan-slice-e3b1-mobile-visit-workflow-safety-remediation.md`.

---

## Current → Target Service Mapping

| Current ID | Current Label | Target | Change |
|------------|-------------|--------|--------|
| WALK_30MIN | 30-Minute Walk | WALK_20MIN "20-Minute Walk" | Rename + duration (30→20) |
| WALK_60MIN | 60-Minute Walk | Legacy; future availability pending | Keep historical; no retirement/new-booking decision yet |
| DROPIN_1HR | 1-Hour Drop-in | Legacy; future availability pending | Keep historical; do not presume replacement/migration |
| DROPIN_3HR | 3-Hour Drop-in | Legacy; future availability pending | Keep historical; do not presume retirement |
| OVERNIGHT | Overnight Care | OVERNIGHT fixed 21:00→07:00 next day | O1 committed/pushed/not deployed; historical records unchanged |
| PET_SITTING | Pet Sitting | Target model adds CHECK_IN "Check-In" | Keep PET_SITTING historical meaning; do not reinterpret records |
| MEET_GREET | Meet & Greet | Unchanged | Already excluded from intake |

Legacy IDs must remain readable for historical bookings.

---

## Public Website Alignment (toganddogs.com)

| Item | Current | Target | Action |
|------|---------|--------|--------|
| Walk duration | "15–18 minute walk" | "20-minute walk" | Update copy |
| Check-In visits | "2x visits" only | 1, 2, or 3 visits/day | Add pricing tiers |
| Overnight | "12-4 hours of care" ⚠️ AMBIGUOUS | Fixed 9:00 PM–7:00 AM; pricing still TBD | Slice F copy change remains gated |
| Pricing | $45/day (2 visits), $90/day overnight | TBD for 1 and 3 visits | Business decision |

Do NOT edit the WordPress site in any implementation slice. Website alignment is Slice F.

---

## Implementation Slices

| Slice | Scope | Dependencies | Status |
|-------|-------|-------------|--------|
| A | Canonical service/time-window contract update in `shared/constants/` | None | Committed / Pushed / Not Deployed |
| B | Backend booking/job/calendar support for visits-per-day and updated windows | A | Committed / Pushed / Not Deployed |
| C | Web customer intake Check-In parity | A, B | Committed / Pushed / Not Deployed |
| C1 | Web Admin Check-In creation parity | A, B, C | Committed / Pushed / Not Deployed |
| D1 | Mobile dashboard navigation | A, B | Committed / Pushed / Not Built / Not Distributed / Not Deployed |
| D2 | Mobile service-selection/intake parity | A, B | Committed / Pushed / Not Built / Not Distributed / Not Deployed |
| R1 | Scheduler parity + Check-In resiliency hardening | A–C, C1, D1–D2 | Committed / Pushed / Not Deployed |
| W1 | 20-Minute Walk canonical scheduling windows | A–C1, D2, R1 | Committed / Pushed / Not Deployed |
| O1 | Overnight fixed 21:00→07:00 next-day scheduling | A–C1, D2, R1, W1 | Committed / Pushed / Not Deployed |
| E1 | Web Admin Assign Sitter + View in Calendar handoffs | C, D1, D2 | Implemented / Validated / Not Deployed |
| E2 | Web Admin intake approval → bounded reconciliation → Scheduler handoff | E1 | Implemented / Validated / Not Deployed |
| E3A | Child Start contract + occurrence-aware exact-request read | E1, E2 | Backend/API Gate A Deployed / Gate B0 Complete / B1A–B3 Not Approved |
| E3B | Mobile occurrence-safe Start/Complete consumption | E3A | Implemented / Validated / Not Built / Not Distributed / Not Deployed |
| E3B.1 | Mobile visit workflow safety remediation | E3B | Implemented / Validated / Not Built / Not Distributed / Not Deployed |
| E | Remaining workflow next-action simplification | E1, E2, E3A | E1–E3B.1 complete locally; deployment/build planning separately gated |
| F | Public website content alignment (toganddogs.com) | Ryan pricing decisions | Not Started |

**Recommended order:** A → B → C + D (parallel) → E → F

---

## Open Business Decisions (Ryan/Matthew)

| # | Decision | Owner | Blocking |
|---|----------|-------|----------|
| 1 | Price for Check-In 1 visit/day | Ryan | Slice F |
| 2 | Confirm price for Check-In 2 visits/day ($45/day) | Ryan | Slice F |
| 3 | Price for Check-In 3 visits/day | Ryan | Slice F |
| 4 | Whether 60-Minute Walk remains or is retired | Ryan | Slice A |
| 5 | Whether Drop-In 1HR/3HR remain for new bookings | Ryan | Slice A |
| 6 | Whether $35 deposit is still current | Ryan | Slice F |
| 7 | In-app pricing automation vs admin Stripe links | Matthew/Ryan | Future |

Pricing does NOT block Slice A contract work. Slice A can proceed with service IDs, labels, durations, and window definitions without resolving pricing.

---

## Cross-Platform Alignment Rule

Any operational service or workflow change must be assessed across Web, Mobile, Shared contracts, Backend, Calendar/scheduling, and Notifications.

These MUST remain aligned:
- Service IDs and labels
- Durations and visit-count rules
- Time-window definitions
- Statuses and allowed actions
- Validation rules
- Scheduling semantics and workflow state

Web and mobile layouts may differ. Business behavior must not.
