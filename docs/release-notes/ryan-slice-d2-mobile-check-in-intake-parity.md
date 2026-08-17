# Ryan Cross-Platform Alignment Slice D2 — Mobile Check-In Intake Parity

**Status:** ✅ **COMMITTED / PUSHED / NOT BUILT / NOT DISTRIBUTED / NOT DEPLOYED**

**Implementation date:** 2026-08-17

**Commit closeout date:** 2026-08-17

**Starting checkpoint:** `7e048227812472bb23d736a06403540c2f9ab057`

**Feedback source:** Ryan's approved operational review on his physically confirmed Android phone

**Independent review:** `RYAN_SLICE_D2_IMPLEMENTATION_CORRECT` / `RYAN_SLICE_D2_READY_FOR_COMMIT_DECISION`

**Scope:** Mobile customer care-request intake, focused mobile tests, and continuity documentation only

## Outcome

The existing three-step mobile care-request wizard now derives its new-booking service selector from active, mobile-supported, canonically eligible `SERVICE_TYPES` metadata. It presents exactly 20-Minute Walk, Check-In, and Overnight for new requests while preserving historical identifiers in the generated contract for read compatibility.

For Check-In only, the schedule step consumes the generated `visitsPerDayOptions`, `windowSelectionMode`, `allowedWindowIds`, and structured window metadata. The screen displays contract-derived Morning, Mid-day, and Evening labels and formats their generated start/end values for customers. It does not define a second service catalog, visits/day list, window list, or raw time source.

## Check-In selection and payload semantics

- One visit/day requires exactly one active window.
- Two visits/day requires exactly two distinct windows and prevents selecting a third.
- Three visits/day automatically selects all three canonical windows.
- Submitted arrays are normalized to canonical contract order rather than tap order.
- Valid Check-In requests add `visits_per_day` and `visit_windows` to the unchanged customer request payload.
- The mobile client does not send the legacy singular `visit_window`; Slice B derives compatibility behavior from the canonical array.
- Walk and Overnight payloads omit both Check-In-only fields.

The traced non-Check-In backend compatibility path accepts omitted window fields and performs its existing legacy normalization server-side. Mobile therefore does not invent or transmit a new Walk scheduling policy.

Changing visits/day trims or expands selections into a valid state. Changing services clears Check-In state; switching back starts with no visit count or windows selected. This prevents hidden Check-In values from leaking into Walk or Overnight requests.

## Preserved intake behavior and safety

The existing date selection, pet loading and selection, care details, preferred sitter, policy acceptance, review, API helper, submit lock, API error handling, success screen, and authenticated client context remain in place. No client-assigned status was added.

The review step shows the canonical Check-In label, confirmed 30-minute duration, visits/day, and friendly selected-window labels. Confirmed Walk duration remains visible. Overnight's unresolved compatibility duration is not presented as newly approved customer copy. No price is displayed.

The new count and window controls use existing mobile card/chip styling, at least 44-point touch targets, button roles, descriptive labels and hints, and selected/disabled accessibility state.

## Local validation

- Focused Intake coverage: 23/23 passed, including eight D2-specific integration tests.
- Mobile TypeScript: passed with 0 errors.
- Full mobile Jest regression: 123/123 passed across 13 suites.
- Mocked payload characterization covers one-, two-, and three-visit Check-In requests, canonical ordering, singular-field omission, and no client-assigned status.
- State tests cover 2 → 1, 1 → 3, Check-In → Walk → Check-In, and Check-In → Overnight.
- Invalid coverage includes missing count, insufficient windows, third-window prevention, duplicate toggling, and absence of legacy `AFTERNOON`/`ANYTIME` controls.
- Static review found canonical identifiers, visits/day values, and raw window times only in the generated adapter or test expectations; runtime intake code consumes generated metadata and contains only display formatting.
- The full suite retains the pre-existing React 19 `act(...)` console warnings in `IntakeScreen.test.tsx`; all tests pass.

## Cross-platform sequencing and deferred decisions

The existing Web customer intake still uses the unchanged legacy `availableInIntake` selector model. D2 changes no shared contract value, generated adapter, or Web source; therefore its mobile target-service presentation does not automatically alter Web. Slice C must add the target Web selector, Check-In visits/day and multi-window controls, matching payload semantics, and review display.

**Slice C is required before cross-platform release. D2 must not be deployed alone while Web remains semantically behind without separate review and approval.**

Walk time-window policy, Overnight start/end/duration, all pricing and deposit decisions, legacy service retirement/eligibility decisions, and workflow simplification remain unresolved. D2 invents none of them.

No build, Expo update, EAS action, TestFlight or Google Play change, distribution, deployment, production write, Calendar mutation, notification, Cognito/Postmark change, Stripe change, tenant change, Terraform action, or public-site edit occurred. `TENANT_RESOLUTION_MODE=multi` is unchanged. Ryan has not received D2, and the current Android versionCode 4 contains neither D1 nor D2.

---

**RYAN_SLICE_D2_COMMITTED_PUSHED_NOT_BUILT_NOT_DISTRIBUTED**
