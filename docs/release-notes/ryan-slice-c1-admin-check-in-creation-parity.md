# Ryan Cross-Platform Alignment Slice C1 — Admin Check-In Creation Parity

**Status:** ✅ **COMMITTED / PUSHED / NOT DEPLOYED**

**Independent review:** `RYAN_SLICE_C1_IMPLEMENTATION_CORRECT` / `RYAN_SLICE_C1_READY_FOR_COMMIT_DECISION`

**Implementation date:** 2026-08-17

**Starting checkpoint:** `3eea140e010a691c0d31dc16b6ceb618d9c76d33`

**Scope:** Existing Web Admin New Visit modal, focused rendered tests, and continuity documentation only

## Outcome

The owner/admin-only `+ New Visit` workflow can now create contract-valid Check-In bookings for an existing tenant-scoped client, including clients managed entirely by staff without a Cognito login. The modal derives its complete service catalog from generated `SERVICE_TYPES`, adds `WALK_20MIN` and `CHECK_IN`, retains all seven prior admin options and the existing `PET_SITTING` default, and contains no duplicated static admin service map.

Admin creation intentionally remains broader than customer intake: every canonical contract service remains available for staff-managed operational and historical compatibility. This preserves `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `PET_SITTING`, and admin-scheduled `MEET_GREET` while also exposing the three target services.

## Actual creation architecture and workflow semantics

`AdminDashboard` is mounted at `/admin`. Its owner/admin capability gate opens the existing New Visit modal, which selects an active client, one or more existing pets, up to 14 dates, an optional preferred sitter, and notes. Inline pet creation continues to use the existing staff-managed pet/profile path.

Submission calls `createAdminBooking`, which posts the unchanged admin fields to authenticated `POST /client/requests` and adds `source: admin_created`. The existing `intake_handler` admin branch enforces owner/admin RBAC and tenant/client membership, then persists an immediately `APPROVED` `VISIT_BOOKING`. It is therefore a direct approved-booking path, not a customer request awaiting review and not a frontend-created job path. It invokes the existing job Lambda asynchronously; the backend remains authoritative for child jobs.

No backend change was required. Slice B already validates and canonicalizes admin Check-In writes, persists the singular compatibility field internally, expands selected dates × selected windows, assigns stable occurrence identities, and gives every child one Calendar event. The existing examples remain `1×1=1`, `1×2=2`, `1×3=3`, `3×2=6`, and `7×3=21`.

## Check-In controls and payload

For the contract entry whose `windowSelectionMode` is `match_visits_per_day`, the modal consumes generated:

- `visitsPerDayOptions` (`1`, `2`, `3`);
- `allowedWindowIds` in canonical order;
- active window labels and structured start/end times;
- the exact-count selection rule.

The rendered windows are Morning `06:30–09:30`, Mid-day `10:30–15:30`, and Evening `18:00–21:30`. One visit requires one window; two visits permit exactly two and disable the third; three visits select all three automatically. Payload arrays use canonical order rather than click order.

Transitions normalize deterministically: 2→1 retains the earliest selected canonical window, 1→3 selects all, and 3→2 retains Morning and Mid-day. Changing away from Check-In clears `visits_per_day` and all windows. Returning from Walk or Overnight starts with a clean Check-In schedule.

Check-In submits `service_type`, numeric `visits_per_day`, ordered `visit_windows`, and the existing client, pet, sorted-date, optional sitter, and notes fields. It does not submit legacy singular `visit_window`, status, assignment, or invented client-facing fields. Walk and Overnight omit every Check-In-only field. Contract-marked legacy compatibility services retain the existing single legacy Visit Window control and payload behavior.

## Preserved safety and deferred policy

- Admin-created Check-In remains `APPROVED` / `VISIT_BOOKING`, with unchanged owner/admin RBAC, tenant isolation, entitlements, preferred-sitter semantics, job invocation, loading, success, error, and refresh behavior.
- The preferred sitter remains informational at creation; assignment is not bypassed.
- Admin creation sends no `REQUEST_RECEIVED` or approval notification. Later assignment keeps the existing once-per-batch `STAFF_ASSIGNED` and `VISIT_SCHEDULED` behavior.
- Check-In parent Calendar sync remains suppressed. Slice B children own one 30-minute event each at canonical `06:30`, `10:30`, or `18:00`, with stable replay-safe identities.
- No real request, booking, job, Calendar event, or notification was created.
- Walk receives no Check-In window, pricing, or scheduling policy. Its scheduling policy remains unresolved.
- Overnight receives no Check-In controls, start/end hours, pricing, or presentation of the unresolved 720-minute compatibility duration.
- No Cognito user is created or required for an existing staff-managed client.

Native fieldsets, legends, radio buttons, checkboxes, disabled/selected states, keyboard behavior, associated human-readable errors, global visible-focus treatment, and 44px control targets preserve Web accessibility patterns. Contract implementation names such as `allowedWindowIds` and `windowSelectionMode` are not exposed as UI copy.

## Static duplication review

- Canonical identifiers, structured times, lifecycle, eligibility, visit-count options, and active Check-In window membership remain authoritative in the generated adapter.
- `AdminDashboard` performs generic generated-metadata consumption for the service catalog and Check-In model; it defines no parallel target-service list, Check-In visits list, window list, labels, or time values.
- Existing AdminDashboard historical window display/export maps and the unchanged single-window legacy selector are compatibility behavior for non-Check-In records and admin-created legacy services. They are not used to drive the Check-In controls or payload.
- Canonical identifiers and times in rendered tests are expectations that prove the adapter-backed UI and payload.
- `availableInIntake` remains generated compatibility metadata. Admin creation does not use customer eligibility to remove historical staff capabilities; customer Web continues to use the separately documented active/new-booking-eligible interpretation.

## Local validation

- AdminDashboard service/creation suite: 13/13 passed, including the strengthened contract-catalog case and nine new rendered C1 cases.
- Combined C1 + Slice C IntakeForm: 31/31 passed.
- Complete Web Vitest: 280/280 passed across 22 files.
- Complete Web legacy suite: 99/99 passed.
- Web build: succeeded with 110 modules transformed.
- Focused Slice B backend characterization: 31/31 passed; backend source was unchanged.
- Candidate test file lint: no findings. `AdminDashboard.jsx` retains its exact pre-change 18-error/5-warning baseline; C1 introduced no new lint finding.
- `git diff --check`: passed (line-ending conversion notices only).

## Explicitly excluded

No shared contract, generated adapter, backend, Mobile, infrastructure, production data, tenant, `TENANT_RESOLUTION_MODE`, Cognito, Postmark, Stripe, Terraform, WordPress, Web deployment, Mobile build/distribution, TestFlight, or Google Play change occurred. Pricing, Walk scheduling, final Overnight timing, workflow simplification, public-site alignment, and all deployment/distribution decisions remain separately gated.

---

**RYAN_SLICE_C1_COMMITTED_PUSHED_NOT_DEPLOYED**
