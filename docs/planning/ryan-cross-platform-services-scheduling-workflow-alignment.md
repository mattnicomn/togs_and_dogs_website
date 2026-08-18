# Ryan Cross-Platform Services, Scheduling & Workflow Alignment

**Source:** Ryan operational platform review (2026-08-15)
**Status:** Slices A–C, C1, D1–D2, and R1 Hardening Committed / Pushed / Not Deployed; D1–D2 Not Built or Distributed; Slices E and F Deferred

---

## Confirmed Service Direction

| Service | Duration | Visits/Day | Intake |
|---------|----------|-----------|--------|
| 20-Minute Walk | 20 min | — | ✅ |
| Check-In | 30 min | 1, 2, or 3 (selectable) | ✅ |
| Overnight | TBD | — | ✅ |
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
- Walk window policy and Overnight operational duration/window policy remain explicitly unresolved.
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

Overnight should have its own scheduling model and should NOT automatically inherit the three Check-In windows. Exact hours require Ryan clarification.

### Walk

Whether the 20-Minute Walk uses Morning/Mid-day/Evening windows or another scheduling approach requires Ryan clarification.

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

Validation: focused Intake 23/23, TypeScript pass, and full Mobile 123/123 across 13 suites. D2 has not been built, distributed, deployed, or received by Ryan. Walk windows, Overnight timing/duration, pricing, deposits, and legacy eligibility decisions remain unresolved.

See `docs/release-notes/ryan-slice-d2-mobile-check-in-intake-parity.md`.

---

## Slice C Local Web Intake Result

Slice C is committed and pushed but not deployed after independent review returned `RYAN_SLICE_C_IMPLEMENTATION_CORRECT`. Web customer intake now uses the canonical active/new-booking-eligible interpretation and presents `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT`. The generated contract supplies Check-In visits/day, allowed windows, labels, structured times, exact count behavior, canonical ordering, confirmed duration, and review display.

Check-In submits `visits_per_day` plus ordered `visit_windows`; Walk and Overnight omit all Check-In-only fields. Count/service transitions deterministically normalize or clear hidden state. Overnight does not surface the unresolved 720-minute compatibility duration, and neither Walk nor Overnight receives an invented scheduling policy. The contract has no `supportedOnWeb` field, so Web needs no platform-specific allowlist; `availableInIntake` remains unchanged transitional compatibility metadata with no remaining Web runtime consumer.

Validation: focused IntakeForm 18/18, full Web 99/99 legacy plus 271/271 Vitest across 22 files, and Vite build success with 110 modules transformed. No shared/generated, backend, Mobile, production, deployment, distribution, pricing, Calendar, or public-site change occurred.

See `docs/release-notes/ryan-slice-c-web-check-in-intake-parity.md`.

---

## Slice C1 Local Admin Creation Result

Slice C1 is committed and pushed but not deployed after independent review returned `RYAN_SLICE_C1_IMPLEMENTATION_CORRECT`. The existing owner/admin New Visit modal derives the complete canonical catalog from generated `SERVICE_TYPES`, adding the target Walk and Check-In entries while preserving the seven prior staff-managed compatibility services and `PET_SITTING` default.

Check-In alone renders contract-derived 1/2/3 visits and Morning/Mid-day/Evening structured windows, enforces the exact selected-window count, normalizes count/service transitions, and submits canonical ordered `visits_per_day` plus `visit_windows`. Walk and Overnight omit Check-In-only fields and receive no invented timing or pricing policy. Legacy compatibility services retain their existing single-window behavior.

The real API path is the existing authenticated `/client/requests` admin branch. It immediately creates an `APPROVED` `VISIT_BOOKING` for a tenant-scoped existing/offline client and asynchronously invokes jobs. Slice B already validates this path and owns date×window child jobs plus Calendar events, so no backend change was required. Creation notification, later assignment notification batching, preferred-sitter semantics, RBAC, and tenant isolation are unchanged.

Validation: AdminDashboard 13/13, combined C1 + Slice C 31/31, full Web 280/280 Vitest plus 99/99 legacy, successful 110-module build, and focused Slice B backend 31/31. No deployment, production write, Calendar event, notification, Mobile, shared/generated, backend, infrastructure, or public-site action occurred.

See `docs/release-notes/ryan-slice-c1-admin-check-in-creation-parity.md`.

---

## Release Readiness Hardening R1 Local Result

R1 is committed and pushed but not deployed after independent review returned `RYAN_RELEASE_READINESS_HARDENING_R1_IMPLEMENTATION_CORRECT`. The Web MasterScheduler now derives its complete readable operational/history filter catalog from generated `SERVICE_TYPES`, so target `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT` records are directly filterable alongside the retained legacy services. `All Services`, exact case-sensitive filtering, canonical display labels, occurrence data, and existing selection/action handoff remain unchanged.

Real-handler backend characterization proves: a simulated interruption during 3 dates × 2 windows converges on retry to exactly six stable Check-In children with no duplicates; six-child cancellation cascades consistently, deduplicates Calendar event IDs, and tolerates existing already-gone semantics; and 2 dates × 3 windows assignment reaches all six children with one `STAFF_ASSIGNED` and one `VISIT_SCHEDULED` notification for the batch.

R1 adds no scheduling business policy. Walk windows/start time, Overnight duration/hours, pricing, deposits, and legacy retirement remain explicit decision gates. No deployment, production validation/write, Mobile build, or distribution occurred.

See `docs/release-notes/ryan-release-readiness-hardening-r1.md`.

---

## Workflow Simplification Direction

Each operational screen should expose one obvious primary next action where practical.

| Phase | Recommended Action |
|-------|-------------------|
| Intake reviewed | Approve & Schedule (pre-filled booking form) |
| Booking created | Assign Sitter |
| Sitter assigned | View in Calendar |
| Visit day (staff mobile) | Start Visit → Complete Visit |

**Preserved safety gates:** RBAC, required human review, payment authorization, cancellation confirmation, tenant isolation, and notification confirmation must NOT be bypassed.

---

## Current → Target Service Mapping

| Current ID | Current Label | Target | Change |
|------------|-------------|--------|--------|
| WALK_30MIN | 30-Minute Walk | WALK_20MIN "20-Minute Walk" | Rename + duration (30→20) |
| WALK_60MIN | 60-Minute Walk | Legacy; future availability pending | Keep historical; no retirement/new-booking decision yet |
| DROPIN_1HR | 1-Hour Drop-in | Legacy; future availability pending | Keep historical; do not presume replacement/migration |
| DROPIN_3HR | 3-Hour Drop-in | Legacy; future availability pending | Keep historical; do not presume retirement |
| OVERNIGHT | Overnight Care | OVERNIGHT (update scheduling) | Duration/window model change |
| PET_SITTING | Pet Sitting | Target model adds CHECK_IN "Check-In" | Keep PET_SITTING historical meaning; do not reinterpret records |
| MEET_GREET | Meet & Greet | Unchanged | Already excluded from intake |

Legacy IDs must remain readable for historical bookings.

---

## Public Website Alignment (toganddogs.com)

| Item | Current | Target | Action |
|------|---------|--------|--------|
| Walk duration | "15–18 minute walk" | "20-minute walk" | Update copy |
| Check-In visits | "2x visits" only | 1, 2, or 3 visits/day | Add pricing tiers |
| Overnight | "12-4 hours of care" ⚠️ AMBIGUOUS | Clarify with Ryan | Fix wording |
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
| E | Workflow next-action simplification | C, D1, D2 | Not Started |
| F | Public website content alignment (toganddogs.com) | Ryan pricing decisions | Not Started |

**Recommended order:** A → B → C + D (parallel) → E → F

---

## Open Business Decisions (Ryan/Matthew)

| # | Decision | Owner | Blocking |
|---|----------|-------|----------|
| 1 | Price for Check-In 1 visit/day | Ryan | Slice F |
| 2 | Confirm price for Check-In 2 visits/day ($45/day) | Ryan | Slice F |
| 3 | Price for Check-In 3 visits/day | Ryan | Slice F |
| 4 | Exact Overnight hours/duration | Ryan | Slice A/B |
| 5 | Whether 20-Minute Walk uses Morning/Mid-day/Evening windows | Ryan | Slice A |
| 6 | Whether 60-Minute Walk remains or is retired | Ryan | Slice A |
| 7 | Whether Drop-In 1HR/3HR remain for new bookings | Ryan | Slice A |
| 8 | Whether $35 deposit is still current | Ryan | Slice F |
| 9 | In-app pricing automation vs admin Stripe links | Matthew/Ryan | Future |

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
