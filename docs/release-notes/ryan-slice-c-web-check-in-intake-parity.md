# Ryan Cross-Platform Alignment Slice C — Web Check-In Intake Parity

**Status:** ✅ **COMMITTED / PUSHED / NOT DEPLOYED**

**Independent review:** `RYAN_SLICE_C_IMPLEMENTATION_CORRECT` / `RYAN_SLICE_C_READY_FOR_COMMIT_DECISION`

**Implementation date:** 2026-08-17

**Starting checkpoint:** `80af551a4f65337356173d63fc6cad0e56a96846`

**Scope:** Web customer intake eligibility, Check-In scheduling controls, payload/review parity, focused tests, and continuity documentation only

## Outcome

Web customer intake now interprets the generated service contract using the same canonical active/new-booking-eligible model as Mobile. The target new-request list is `WALK_20MIN`, `CHECK_IN`, and `OVERNIGHT`; legacy services and `MEET_GREET` remain readable elsewhere but are not customer-new-request options.

The contract currently has `supportedOnMobile` but no `supportedOnWeb` field. Web therefore uses `lifecycle === "active"` plus `newBookingEligibility === "eligible"` without a Web-only allowlist or invented capability field. `availableInIntake` remains unchanged transitional compatibility metadata in the canonical/generated contract. A repository search found no remaining Web runtime consumer after this change; contract-shape tests continue to characterize the field, and removal is deferred until all platform consumers and compatibility obligations are reviewed together.

## Check-In schedule and state

For `CHECK_IN`, the form derives all scheduling rules from generated `SERVICE_TYPES` metadata:

- confirmed 30-minute duration;
- visits/day options `1`, `2`, and `3`;
- allowed window order `MORNING`, `MIDDAY`, `EVENING`;
- labels and structured ranges Morning `06:30–09:30`, Mid-day `10:30–15:30`, Evening `18:00–21:30`;
- `match_visits_per_day` exact-count behavior.

One visit requires one window. Two visits allow exactly two distinct windows and prevent a third. Three visits automatically select all three. Count changes retain the earliest still-valid canonical selections: 2→1 keeps one, 1→3 selects all, and 3→2 keeps the first two in contract order. Changing service clears Check-In-only state; returning to Check-In starts clean.

Native radio and checkbox semantics provide keyboard operation and exposed selected/disabled states. Fieldsets, legends, screen-reader labels, associated error descriptions, visible focus treatment, and responsive 44px controls preserve the existing Web form design.

## Payload and review parity

New Check-In requests submit:

- `service_type: "CHECK_IN"`;
- `visits_per_day` as `1`, `2`, or `3`;
- `visit_windows` in canonical contract order;
- the existing sorted `selected_dates`, pet/care, sitter, timing, and policy fields.

The obsolete singular `visit_window` is omitted. Walk and Overnight omit `visits_per_day`, `visit_windows`, and `visit_window`, so no Check-In scheduling state leaks into their requests. Public and authenticated-client API routing remains unchanged, and the client still assigns no status.

The existing pet step now includes an accessible request summary. Check-In shows its short contract label, confirmed 30-minute duration, visits/day, friendly canonical windows/ranges, and selected dates. It shows no pricing. Overnight intentionally omits the unresolved historical 720-minute compatibility duration.

## Boundaries and selector classification

- **Customer new-request selector:** `IntakeForm` changed to canonical active/eligible membership and the new Check-In controls.
- **Admin booking creation selector:** `AdminDashboard` remains a static operational compatibility selector. Adding full Check-In booking controls belongs in a separately reviewed C1/admin slice; changing only its membership would create invalid writes.
- **Filters:** `MasterScheduler` service options remain historical/filter compatibility and were not changed.
- **Display-only/historical:** `AdminDashboard`, `ClientPortal`, `CareCard`, and `MasterScheduler` retain their current fallback/read behavior. Their legacy window-label maps were not made a second source for Check-In intake rules.

No Walk scheduling window was invented. Walk submission remains distribution/deployment-gated on the unresolved operational scheduling policy. Overnight receives no new time model and does not expose its unresolved compatibility duration. Pricing and deposits remain excluded.

## Local validation

- Focused Web IntakeForm: 18/18 passed.
- Complete Web legacy suite: 99/99 passed.
- Complete Web Vitest suite: 271/271 passed across 22 files.
- Vite build: succeeded; 110 modules transformed.
- Static duplication review: IntakeForm has generic generated-metadata consumption only; test literals are expectations. Generated contract content remains authoritative. Existing AdminDashboard and ClientPortal window maps are classified as untouched legacy/display compatibility.
- Shared/generated files did not change, so shared validation/regeneration was not applicable.
- `git diff --check`: passed (line-ending conversion notices only).

## Explicitly deferred

- Admin booking-creation Check-In UX and transactional controls.
- Walk scheduling/window policy.
- Final Overnight hours/duration/window policy.
- Pricing for Check-In tiers, deposit policy, and Stripe automation.
- Decisions on future new-booking eligibility for pending legacy services.
- Slice E workflow next-action simplification and Slice F public WordPress content/pricing alignment.
- Any Web/backend deployment or cross-platform distribution.

Slices A and B remain committed/pushed/not deployed. D1 and D2 remain committed/pushed but not built, distributed, deployed, or received by Ryan; Android versionCode 4 contains neither. No backend, Mobile, shared contract, generated adapter, auth/RBAC, tenant, Cognito, Postmark, Stripe, Calendar, Terraform, public-site, production-data, build-distribution, or production action occurred. `TENANT_RESOLUTION_MODE=multi` is unchanged.

---

**RYAN_SLICE_C_COMMITTED_PUSHED_NOT_DEPLOYED**
