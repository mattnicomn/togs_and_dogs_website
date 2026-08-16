# Ryan Cross-Platform Alignment Slice B — Check-In Booking / Job / Calendar Semantics

**Status:** ✅ **LOCAL IMPLEMENTATION COMPLETE / NOT DEPLOYED / UNSTAGED FOR INDEPENDENT REVIEW**

**Implementation date:** 2026-08-15

**Starting checkpoint:** `53818bc6c2075a98cf8c909ce71239a4704e724a`

**Scope:** Backend request validation, persistence, child-job expansion, Calendar timing/idempotency, focused tests, and continuity documentation only

## Outcome

New `CHECK_IN` transactional writes now persist `visits_per_day` plus the complete canonical `visit_windows` selection and expand `selected_dates × visit_windows` into individual child service occurrences. This candidate is local-only. It has not changed production behavior.

## Request and validation model

The backend uses the generated Slice A contract through one runtime facade. For `CHECK_IN` only:

- `visits_per_day` must be one of the contract's `visitsPerDayOptions`;
- `visit_windows` is required, distinct, exact-case, and limited to the contract's `allowedWindowIds`;
- its count must equal `visits_per_day` under `match_visits_per_day`;
- canonical contract order is persisted deterministically;
- the legacy singular `visit_window` is retained as the first canonical selection for existing readers.

Missing fields, `0`, `4`, duplicates, count mismatch, `AFTERNOON`, unknown values, and other noncanonical selections are rejected for new Check-In writes. Other services keep their existing normalization behavior. Historical records are not migrated or mutated.

## Child-job and idempotency model

The existing selected-date expansion now forms the Cartesian product of ordered dates and ordered Check-In windows. Each child stores its service date, one occurrence-specific `visit_window`/`visit_windows`, the booking selection, visits/day, global occurrence index/count, and occurrence window.

Examples covered locally include `1×1=1`, `1×2=2`, `1×3=3`, `3×1=3`, `3×2=6`, `3×3=9`, and `7×3=21`.

Check-In child job IDs are deterministic UUIDv5 values derived from request ID, date, and window. Morning and Evening on the same date are different logical jobs; replay of the same date/window reuses the same job. Existing request-level `job_id`/`job_ids` guards remain in place. A deterministic Google-compatible event ID is also persisted per child so a repeated Calendar insert resolves as the existing logical event rather than creating a duplicate.

## Calendar behavior

Parent-request Calendar sync is suppressed for all new Check-In bookings, including one-day/one-visit bookings. Every Check-In child owns one Calendar event.

Check-In timing comes from generated structured window metadata:

| Window | Start | Duration |
|---|---:|---:|
| Morning | 06:30 | 30 minutes |
| Mid-day | 10:30 | 30 minutes |
| Evening | 18:00 | 30 minutes |

The old `WINDOW_START_HOURS` map remains only on the historical non-Check-In compatibility path. Removing it would change established Walk, Pet Sitting, Afternoon, and other legacy event timing and would prematurely decide unresolved Walk/Overnight policy. `CHECK_IN` has no active dependence on that map.

## Notifications and compatibility

Job creation still sends no notifications. Review notifications remain request/booking-level. Assignment still loops through all child jobs but uses its existing once-per-batch guard for `STAFF_ASSIGNED` and `VISIT_SCHEDULED`; job multiplication does not multiply customer/staff notifications.

- `WALK_30MIN` multi-day and single-day job behavior remains unchanged.
- `PET_SITTING` keeps its historical meaning and Calendar behavior.
- `AFTERNOON` and `ANYTIME` remain readable on historical paths but are invalid for new Check-In writes.
- `WALK_20MIN` receives no Check-In validation, multiplication, or canonical timing policy.
- `OVERNIGHT` receives no new duration or window assumption.

## Local validation

- Focused Slice B: 31/31 passed.
- Existing multi-day, Calendar, generated-contract, and admin-booking affected regression: passed.
- Assignment and notification regression: 73/73 passed.
- Full backend differential: 911 passed / the same 97 environment/baseline failures as the clean checkpoint; candidate-only failures 0.
- `git diff --check`: passed (line-ending conversion notices only).

## Explicitly deferred

- Slice C Web service/visit-count/multi-window UX.
- Slice D Mobile parity and dashboard navigation.
- Slice E workflow next-action simplification.
- Pricing, deposit, Stripe automation, Walk scheduling policy, final Overnight timing, undecided legacy availability, existing-event resynchronization, and any production migration.

No auth, RBAC, tenant resolution, `TENANT_RESOLUTION_MODE`, Cognito, Postmark, Stripe, secrets, Terraform, production data, production Calendar, public website, mobile source/distribution, EAS, TestFlight, Google Play, or deployment action occurred.

---

**RYAN_SLICE_B_LOCAL_IMPLEMENTATION_READY_FOR_REVIEW**
