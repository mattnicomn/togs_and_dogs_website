# Ryan Cross-Platform Alignment Slice A — Canonical Service + Time-Window Contract

**Status:** ✅ **LOCAL IMPLEMENTATION COMPLETE / NOT DEPLOYED**

**Implementation date:** 2026-08-15

**Starting checkpoint:** `428926cac2b914448a2512f1e3c7fcb314be1e6c`

**Scope:** Canonical shared contract, deterministic generated adapters, validation, and pure characterization tests only

## Outcome

The existing `shared/constants/service-types.json` contract now represents the Ryan target service model, legacy service compatibility, structured visit windows, and the Check-In visit/window relationship without changing booking creation, job multiplication, Calendar event creation, current selector membership, pricing, or production behavior.

The contract remains one cross-platform source. The existing generator emits the complete cleaned `services` and `windows` roots through the established `SERVICE_TYPES` export in Web, Mobile, and Backend adapters.

## Service schema

Every service now has the established labels/duration/runtime compatibility fields plus:

- `durationStatus`: `confirmed`, `historical`, or `unresolved`;
- `lifecycle`: `active` or `legacy`;
- `newBookingEligibility`: `eligible`, `ineligible`, or `pending`;
- `visitsPerDayOptions`;
- `allowedWindowIds`;
- `windowSelectionMode`: `match_visits_per_day`, `unresolved`, or `legacy_compatibility`.

Service identifiers remain the object keys, preserving the repository's established implicit-ID convention without duplicating an `id` field.

### Target identities

| ID | Label / long label | Duration | Lifecycle | New-booking direction | Window policy |
|---|---|---:|---|---|---|
| `WALK_20MIN` | `20-Min Walk` / `20-Minute Walk` | 20 | active | eligible | unresolved |
| `CHECK_IN` | `Check-In` / `30-Minute Check-In` | 30 | active | eligible | match visits/day |
| `OVERNIGHT` | `Overnight Care` | existing compatibility value 720 | active | eligible | unresolved |
| `MEET_GREET` | `Meet & Greet` | 45 | active | not customer-new-booking eligible | existing compatibility |

`WALK_20MIN` and `CHECK_IN` deliberately retain `availableInIntake: false` in Slice A. Existing Web and Mobile intake code consumes that legacy runtime field dynamically; changing it here would perform Slice C/D UX work before Slice B transactional support. `newBookingEligibility: eligible` records the approved target direction without changing today's selector membership.

For `OVERNIGHT`, `durationMinutes: 720` remains byte-compatible with current Calendar behavior, while `durationStatus: unresolved` makes clear that Ryan has not approved final operational hours/duration. No start/end or allowed windows were invented.

## Legacy compatibility

`WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, and `PET_SITTING` remain canonical and readable with their historical labels and durations. They are marked `lifecycle: legacy`; no identifier is removed, aliased, normalized, or rewritten.

- `WALK_30MIN` and `PET_SITTING` are ineligible for the target new-booking model.
- `WALK_60MIN`, `DROPIN_1HR`, and `DROPIN_3HR` use `newBookingEligibility: pending` because their future availability is not approved.
- `PET_SITTING` retains the exact `Pet Sitting` historical description and is not reinterpreted as `CHECK_IN`.
- Existing `availableInIntake` values remain unchanged to avoid transactional/UI changes in Slice A.

## Structured time windows

| ID | Label | Start | End | Lifecycle / eligibility |
|---|---|---|---|---|
| `MORNING` | Morning | `06:30` | `09:30` | active / eligible |
| `MIDDAY` | Mid-day | `10:30` | `15:30` | active / eligible |
| `EVENING` | Evening | `18:00` | `21:30` | active / eligible |
| `AFTERNOON` | Afternoon | `null` | `null` | legacy / ineligible |
| `ANYTIME` | Anytime | `null` | `null` | legacy / ineligible |

Active values use machine-readable 24-hour `HH:mm` fields. `AFTERNOON` and `ANYTIME` remain readable for persisted records; their bounds are `null` because the current clients contain conflicting presentation ranges and no new authoritative legacy bounds were approved.

## Check-In rule metadata

`CHECK_IN` declares:

- `visitsPerDayOptions: [1, 2, 3]`;
- `allowedWindowIds: [MORNING, MIDDAY, EVENING]`;
- `windowSelectionMode: match_visits_per_day`.

The combination deterministically represents:

- 1 visit: exactly one active Check-In window;
- 2 visits: exactly two distinct active Check-In windows;
- 3 visits: all three active Check-In windows.

Pure contract tests prove count, distinctness, and active-membership behavior. Transactional enforcement remains deferred.

## Generation and validation

The existing deterministic generator was updated to name the input as a complete service contract and document that `SERVICE_TYPES` now contains `services` plus `windows`. It regenerated:

- `web/src/generated/contracts.js`;
- `mobile/src/contracts/generatedContracts.ts`;
- `src/backend/common/generated_service_types.py`.

Shared validation now proves exact service/window field shape, enums, structured time format/order, legacy retention, unresolved policies, Check-In selection metadata, complete ordered adapter equality, and deterministic zero-second-diff generation. Backend, Web, and Mobile adapter tests characterize the new contract.

## Local validation

- Shared constants: 22/22 passed.
- Cross-adapter validation and deterministic-generation checks: 9/9 passed.
- Focused Backend contract/generated/calendar parity: 83/83 passed.
- Focused Web contract/intake/admin/display-label coverage: 55/55 passed.
- Complete Web: 99/99 legacy plus 260/260 Vitest passed; Vite build succeeded with 110 modules transformed.
- Focused Mobile contract/label coverage: 33/33 passed.
- Complete Mobile: 109/109 passed across 10 suites; TypeScript `tsc --noEmit` passed. Existing Intake test `act()` console warnings and Jest force-exit/open-handle notice remain unchanged and were not remediated.
- Complete Backend: 880 passed / the same documented 97 environment/baseline failures. All affected contract/calendar suites pass; candidate-only failures: 0.
- Explicit two-run SHA-256 comparison: Web, Mobile, and Backend generated files remained byte-identical.
- `git diff --check`: passed (line-ending conversion notices only).

## Hard-coded compatibility inventory

The final static search classifies canonical JSON and generated files as authoritative/generated, and test occurrences as fixtures or contract characterization. The following runtime duplicates remain deliberately deferred:

- **Slice B:** backend `VALID_VISIT_WINDOWS`, intake default/normalization behavior, Calendar `WINDOW_START_HOURS`, service workflow classifiers, notification service labels, and provider-specific `SERVICE_COLORS` compatibility.
- **Slice C:** Web IntakeForm window membership/range strings, AdminDashboard window maps/order/defaults/static options, ClientPortal window display map, and current static service selectors/filters.
- **Slice D:** Mobile IntakeScreen window membership/range strings and default selection.

These existing definitions intentionally continue to represent current transactional/UI behavior in Slice A. Replacing them now would broaden the candidate into backend or UX work.

## Explicitly deferred

- **Slice B:** booking validation/enforcement, dates × visits/day job creation, multiple Calendar events, notification behavior, and runtime window mapping.
- **Slice C:** Web Walk/Check-In selection, visit-count picker, and multi-window UX.
- **Slice D:** Mobile service selection/parity and dashboard navigation.
- **Slice E:** primary-next-action workflow simplification.
- Pricing, deposit, Stripe automation, Walk window policy, final Overnight timing, and undecided legacy availability.

No authentication, authorization, tenant resolution, `TENANT_RESOLUTION_MODE`, payment, email, Cognito, Postmark, secret, production-data, infrastructure, deployment, EAS, TestFlight, Google Play, or public-site change occurred.

---

**RYAN_SLICE_A_LOCAL_IMPLEMENTATION_READY_FOR_REVIEW**
