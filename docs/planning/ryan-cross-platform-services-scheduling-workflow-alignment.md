# Ryan Cross-Platform Services, Scheduling & Workflow Alignment

**Source:** Ryan operational platform review (2026-08-15)
**Status:** Assessment Complete / Field Feedback Captured / Implementation Not Started

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
| WALK_60MIN | 60-Minute Walk | Deprecate | Remove from intake; keep for historical |
| DROPIN_1HR | 1-Hour Drop-in | Deprecate | Merge into Check-In model |
| DROPIN_3HR | 3-Hour Drop-in | Deprecate | Not in Ryan's model |
| OVERNIGHT | Overnight Care | OVERNIGHT (update scheduling) | Duration/window model change |
| PET_SITTING | Pet Sitting | CHECK_IN "Check-In" | Rename + visits-per-day model |
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
| A | Canonical service/time-window contract update in `shared/constants/` | None | Not Started |
| B | Backend booking/job/calendar support for visits-per-day and updated windows | A | Not Started |
| C | Web service-selection UX (admin booking + client intake) | A, B | Not Started |
| D | Mobile parity + dashboard navigation | A, B | Not Started |
| E | Workflow next-action simplification | C, D | Not Started |
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
