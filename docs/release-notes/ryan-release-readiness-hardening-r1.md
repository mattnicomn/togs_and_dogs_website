# Ryan Cross-Platform Release Readiness Hardening R1 — Scheduler Parity + Check-In Resiliency

**Status:** ✅ **COMMITTED / PUSHED / NOT DEPLOYED**

**Implementation date:** 2026-08-17

**Starting checkpoint:** `2494352cc750ff77496f33d23db6ccebd4c1c25f`

**Independent review:** `RYAN_RELEASE_READINESS_HARDENING_R1_IMPLEMENTATION_CORRECT` / `RYAN_RELEASE_READINESS_HARDENING_R1_READY_FOR_COMMIT_DECISION`

**Scope:** MasterScheduler service-filter membership, Check-In backend resiliency characterization, focused regression tests, and current-state documentation only

## Outcome

The Web MasterScheduler's service filter no longer maintains a separate seven-item legacy membership list. It consumes the complete ordered generated `SERVICE_TYPES.services` catalog and its canonical long labels, retaining `All Services` and exact case-sensitive `service_type` equality.

The resulting operational/history catalog is:

1. `WALK_20MIN` — 20-Minute Walk
2. `CHECK_IN` — 30-Minute Check-In
3. `WALK_30MIN` — 30-Minute Walk
4. `WALK_60MIN` — 60-Minute Walk
5. `DROPIN_1HR` — 1-Hour Drop-in
6. `DROPIN_3HR` — 3-Hour Drop-in
7. `OVERNIGHT` — Overnight Care
8. `PET_SITTING` — Pet Sitting
9. `MEET_GREET` — Meet & Greet

This is deliberately the complete readable canonical catalog, not the customer new-booking eligibility subset. Historical/operational legacy records remain directly filterable. Unknown aliases and case variants remain visible only through `All Services`, as before.

## Scheduler characterization

- Check-In records remain visible under `All Services` and are directly selectable under the Check-In filter.
- Canonical service-only display remains `30-Minute Check-In`; an existing truthy occurrence/window display value remains raw and unchanged.
- Existing start date/time fields and the original selected object are preserved for downstream Care Card assignment/completion actions.
- `WALK_20MIN` and `OVERNIGHT` are directly filterable and displayable without inventing a start-time, window, duration, or hours policy.
- Customer intake eligibility, the admin New Visit catalog, payloads, scheduler status/staff/date/search behavior, and filtering equality are unchanged.

## Check-In resiliency characterization

### Interrupted batch retry

A real `job_handler` test simulates a 3-date × 2-window batch interrupted on its third child persistence attempt. The first two deterministic children remain locally persisted while the parent is not linked. Retrying the same handler reuses those stable UUIDv5 identities, creates the remaining four, and links exactly the intended six ordered IDs. Final state contains six unique children and six Calendar sync calls total, with no duplicate child or event creation.

### Multi-window cancellation

A real cancellation-handler plus real cascade-helper test uses six linked Check-In children. All six reach `CANCELLED`; an unrelated job is untouched. Five child Calendar references collapse to four unique event IDs because one ID is shared. Each unique ID is called once, and two simulated already-gone results (the existing 404/410-compatible return shape) are tolerated while stale references are removed. All Calendar work is mocked.

### Assignment propagation and notification batching

A real assignment-handler test assigns a 2-date × 3-window parent. All six children receive `ASSIGNED`, the same sitter identity, and Calendar synchronization; the parent receives the consistent assignment state. Notifications remain exactly once per batch: one `STAFF_ASSIGNED` and one `VISIT_SCHEDULED`, with no per-child spam. All Calendar and notification work is mocked.

## Validation

- Scheduler focused: `npm exec vitest run tests/ServiceTypeDisplayOwners.test.jsx` — 16/16 passed.
- Slice C Intake: `npm exec vitest run tests/IntakeFormServiceTypes.test.jsx` — 18/18 passed.
- Slice C1 AdminDashboard: `npm exec vitest run tests/AdminDashboardServiceTypes.test.jsx` — 13/13 passed.
- Full Web Vitest: `npm run test:components` — 281/281 passed across 22 files.
- Legacy Web: `npm run test:legacy` — 99/99 passed across 15 suites.
- Web build: `npm run build` — succeeded with 110 modules transformed.
- Slice B plus R1 backend: `python -m pytest tests/backend/test_ryan_slice_b_check_in_transactions.py tests/backend/test_ryan_release_readiness_hardening_r1.py -q` — 34/34 passed.
- New interrupted-retry, cancellation, and assignment file: `python -m pytest tests/backend/test_ryan_release_readiness_hardening_r1.py -q` — 3/3 passed.
- Mobile TypeScript: `npm run typecheck` — passed with 0 errors.
- Focused Mobile D1/D2: `npm test -- --runInBand __tests__/DashboardScreen.test.tsx __tests__/RequestListNavigation.test.tsx __tests__/AppNavigator.test.tsx __tests__/IntakeScreen.test.tsx` — 29/29 passed across 4 suites.
- Full Mobile: `npm run test:ci -- --runInBand` — 123/123 passed across 13 suites. Existing Intake React `act(...)` warnings and Jest force-exit notice remain nonblocking and unchanged.
- `git diff --check` — passed; line-ending conversion notices only.

## Continuity reconciliation

Current authoritative records now state that Slices A–C, C1, D1–D2, and R1 are committed and pushed but not deployed; D1/D2 have not been built or distributed and are absent from Android versionCode 4; and Ryan's physical Android install is confirmed. The release index no longer describes Slice B as unstaged, and the document map includes Slice A, C1, and R1. Dated historical checkpoint wording was retained where it remains accurate as history.

## Explicitly unchanged and deferred

No backend application source, shared contract, generated adapter, Mobile source, API payload, runtime validation, customer eligibility, infrastructure, production data, tenant, Calendar, notification, Cognito/Postmark, Stripe, Terraform, public-site, deployment, EAS build, TestFlight, or Google Play action occurred.

R1 does not choose Walk scheduling windows/start time, Overnight duration/hours, pricing, deposits, legacy service retirement, Stripe automation, Slice E workflow simplification, or Slice F public-site alignment. Those remain separate decision and approval gates.

---

**RYAN_RELEASE_READINESS_HARDENING_R1_COMMITTED_PUSHED_NOT_DEPLOYED**
