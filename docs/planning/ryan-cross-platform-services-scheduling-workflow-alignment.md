# Ryan Cross-Platform Services, Scheduling & Workflow Alignment

**Source:** Ryan operational platform review (2026-08-15)
**Status:** Slices A–B and D1–D2 Committed / Pushed / Not Deployed; D1–D2 Not Built or Distributed; Slices C, E, and F Deferred

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

The existing Web customer intake remains on the unchanged `availableInIntake` model. Slice C must implement the target service selector, Check-In visits/day and multi-window collection, payload semantics, and review display before a cross-platform release. This temporary difference is implementation sequencing only; D2 must not be deployed alone without separate approval.

Validation: focused Intake 23/23, TypeScript pass, and full Mobile 123/123 across 13 suites. D2 has not been built, distributed, deployed, or received by Ryan. Walk windows, Overnight timing/duration, pricing, deposits, and legacy eligibility decisions remain unresolved.

See `docs/release-notes/ryan-slice-d2-mobile-check-in-intake-parity.md`.

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
| A | Canonical service/time-window contract update in `shared/constants/` | None | Local Implementation Complete / Not Deployed |
| B | Backend booking/job/calendar support for visits-per-day and updated windows | A | Committed / Pushed / Not Deployed |
| C | Web service-selection UX (admin booking + client intake) | A, B | Not Started |
| D1 | Mobile dashboard navigation | A, B | Committed / Pushed / Not Built / Not Distributed / Not Deployed |
| D2 | Mobile service-selection/intake parity | A, B | Committed / Pushed / Not Built / Not Distributed / Not Deployed |
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
