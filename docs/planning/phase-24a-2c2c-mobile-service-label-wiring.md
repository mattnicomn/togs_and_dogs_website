# Phase 24A-2C.2C — Mobile Service-Type Display-Label Contract Wiring Plan

**Status:** **PLANNING COMPLETE / IMPLEMENTATION NOT APPROVED / INTENTIONAL VISIBLE LABEL CHANGE REQUIRES MATTHEW APPROVAL**

**Planning Date:** 2026-08-03

**Planning Checkpoint:** `ac9797ec9533a271111a4fda4351f503c5198cc6`

**Authorization:** Matthew approved documentation-only planning. Mobile implementation, tests, contract or adapter changes, builds, distribution, tester changes, deployment, and production-data activity are not authorized.

---

## 1. Background

Phase 24A-2 created `shared/constants/service-types.json`, and Phase 24A-2A generated its `SERVICE_TYPES` object into `mobile/src/contracts/generatedContracts.ts`. Phase 24A-2C.2A subsequently wired the Web Admin display contexts and is locally validated and reviewed. Phase 24A-2C.2 overall remains partially complete.

Phase 24A-2C.2C is a separate mobile display-label proposal. Four mobile render sites currently use identical local underscore formatters. Canonical uppercase identifiers therefore render as uppercase words with spaces rather than the contract’s friendlier punctuation and wording. This plan proposes consolidating those four local functions into one shared display-only helper that returns the contract `label` for an exact canonical identifier and preserves the exact legacy formatter for every other value.

The seven canonical outputs will intentionally change visibly. This is an **INTENTIONAL VISIBLE UX IMPROVEMENT**, not byte-identical behavior preservation, and implementation requires separate explicit Matthew approval.

## 2. Current Mobile Formatter Inventory

All four current implementations are semantically identical:

```ts
(service || '')
  .split('_')
  .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
  .join(' ')
```

| Current owner | Current use | Data-flow finding |
|---|---|---|
| `mobile/src/screens/BookingsScreen.tsx` | Booking-card service detail | Display-only; raw request data is fetched, status-sorted, and rendered. Formatter output is not persisted or passed to an API. |
| `mobile/src/screens/ScheduleScreen.tsx` | Expanded visit service detail | Display-only; the raw `service_type` is copied into the per-date visit model and rendering alone invokes the formatter. Status/date/role filtering and date sorting do not use its output. |
| `mobile/src/screens/RequestDetailScreen.tsx` | Request-detail service metadata | Display-only; route parameters contain the raw request, selected date, and job identifier. Assignment/review/completion actions do not use the formatted label. |
| `mobile/src/components/RequestCard.tsx` | Request-list card service detail | Display-only; navigation passes the raw request object. Review/assignment actions use request, job, client, and worker identifiers, not the formatted label. |

Repository-wide mobile source inspection found no additional `formatServiceType` implementation or call site. No current formatter output is used in API payloads, navigation parameters, filtering, sorting, selectors, feature availability, accessibility labels, analytics, or test identifiers.

The surrounding `RequestListScreen` filters by request status and sorts by creation/request identifier. `DashboardScreen` derives counts from statuses and selected dates. Neither uses service labels. The mobile API client passes server data and action identifiers without calling any display formatter. No mobile service selector or service-submission workflow exists in current source.

One shared helper is therefore structurally safe. All four contexts present the same concise service metadata and have no established context-specific long wording; the contract `label`, rather than `labelLong`, is the appropriate property in every current mobile context.

## 3. Canonical `SERVICE_TYPES` Inventory

Canonical source: `shared/constants/service-types.json`. The complete object is already present in `mobile/src/contracts/generatedContracts.ts`; no contract, generator, validator, regeneration, or adapter change is required.

| Identifier | `label` | `labelLong` | `durationMinutes` | `availableInIntake` | `supportedOnMobile` |
|---|---|---|---:|---|---|
| `WALK_30MIN` | `30-Min Walk` | `30-Minute Walk` | 30 | `true` | `true` |
| `WALK_60MIN` | `60-Min Walk` | `60-Minute Walk` | 60 | `true` | `true` |
| `DROPIN_1HR` | `1-Hour Drop-in` | `1-Hour Drop-in` | 60 | `true` | `true` |
| `DROPIN_3HR` | `3-Hour Drop-in` | `3-Hour Drop-in` | 180 | `true` | `true` |
| `OVERNIGHT` | `Overnight Care` | `Overnight Care` | 720 | `true` | `true` |
| `PET_SITTING` | `Pet Sitting` | `Pet Sitting` | 60 | `true` | `true` |
| `MEET_GREET` | `Meet & Greet` | `Meet & Greet` | 45 | `false` | `true` |

## 4. Current Versus Proposed Canonical Label Matrix

| Identifier | Exact current mobile output | Proposed contract output | Classification |
|---|---|---|---|
| `WALK_30MIN` | `WALK 30MIN` | `30-Min Walk` | Intentional visible UX improvement |
| `WALK_60MIN` | `WALK 60MIN` | `60-Min Walk` | Intentional visible UX improvement |
| `DROPIN_1HR` | `DROPIN 1HR` | `1-Hour Drop-in` | Intentional visible UX improvement |
| `DROPIN_3HR` | `DROPIN 3HR` | `3-Hour Drop-in` | Intentional visible UX improvement |
| `OVERNIGHT` | `OVERNIGHT` | `Overnight Care` | Intentional visible UX improvement |
| `PET_SITTING` | `PET SITTING` | `Pet Sitting` | Intentional visible UX improvement |
| `MEET_GREET` | `MEET GREET` | `Meet & Greet` | Intentional visible UX improvement |

These changes are deliberate and user-visible in every mobile surface that currently renders the corresponding identifier. They must not be described or tested as byte-for-byte parity with current canonical output.

## 5. Exact Fallback Behavior

The existing formatter uppercases only each token’s first character and preserves the rest of each token exactly. It does not title-case uppercase input. The future helper must retain this formatter as its fallback rather than returning a raw underscore identifier or applying new normalization.

| Input | Exact current and required future fallback output |
|---|---|
| `DOG_WALKING` | `DOG WALKING` |
| `WALKING` | `WALKING` |
| `OTHER` | `OTHER` |
| `HOUSE_SITTING` | `HOUSE SITTING` |
| `walk_30min` | `Walk 30min` |
| `Walk_30Min` | `Walk 30Min` |
| representative arbitrary unknown `CUSTOM_CARE_2HR` | `CUSTOM CARE 2HR` |
| `null` | `''` |
| `undefined` | `''` |
| empty string | `''` |

Required helper semantics, in order:

1. Return `''` for nullish or empty input.
2. Attempt exact, case-sensitive `SERVICE_TYPES.services[type]?.label` lookup.
3. Return the contract `label` for a recognized canonical identifier.
4. Otherwise return the exact legacy formatter output:

```ts
(service || '')
  .split('_')
  .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
  .join(' ')
```

The helper must not uppercase or lowercase the lookup key, trim or normalize identifiers, return the raw underscore value, fully title-case unknowns, or alias `DOG_WALKING`, `WALKING`, or `OTHER` to canonical services. Lowercase `walk_30min` and mixed-case `Walk_30Min` are not exact canonical keys and must continue through the legacy fallback.

## 6. Identifier and Payload-Safety Findings

- `PetRequest.service_type` remains an unrestricted `string`; the proposal changes no identifier type or stored value.
- The helper receives a service identifier for rendering and returns display text only.
- `BookingsScreen` performs no service mutation.
- `ScheduleScreen` preserves the raw identifier while expanding selected dates into visits.
- `RequestCard` navigation passes the original request object unchanged.
- `RequestDetailScreen` action payloads retain their current request, job, client, and worker identifiers.
- No API-client method receives formatted service text from these locations.
- No service identifier, API shape, payload value, navigation value, backend record, or production record may change in 2C.2C.

## 7. Selector and Feature-Availability Boundary

Current mobile source contains no service selector and no service-submission workflow. Phase 2C.2C must not add either one. It must not add, remove, reorder, rename, generate, filter, or default any service options. It must not change screen availability, workflow capability, request visibility, assignment rules, or any role behavior.

`availableInIntake` is outside the display-helper responsibility. It must not be imported, read, filtered on, or treated as authorization to expose a mobile intake workflow. Selector membership and noncanonical normalization remain Phase 24A-2C.2B concerns and are deferred.

## 8. `supportedOnMobile` Boundary

All seven canonical entries currently set `supportedOnMobile: true`, but Phase 2C.2C must not consume that field. It is metadata, not a runtime feature gate for this proposal. The shared helper formats any exact canonical identifier present in received data; it must not hide records, suppress labels, filter lists, create availability rules, or infer a service selector from `supportedOnMobile`.

Any future change that uses `supportedOnMobile` for feature availability requires separate planning, behavioral tests, product decisions, and explicit approval.

## 9. `durationMinutes` Boundary

`durationMinutes` is unrelated to display-label selection. Phase 2C.2C must not read it or change schedule expansion, visit timing, sorting, calendar behavior, duration fallbacks, or backend scheduling. The backend remains the runtime scheduling authority. Duration and scheduling centralization remain deferred to Phase 24A-2C.2D.

## 10. Proposed Implementation Scope

After separate explicit Matthew approval, implement one display-only helper in `mobile/src/utils/serviceLabels.ts`:

- import the existing generated `SERVICE_TYPES` adapter;
- accept the same nullish/string values tolerated by current runtime behavior;
- return `SERVICE_TYPES.services[type].label` for an exact canonical key;
- otherwise return exact legacy formatter output;
- export one function used by all four current render sites;
- remove only the four now-duplicated local formatter declarations;
- leave every caller’s raw data flow and JSX placement unchanged.

No generator or adapter change or regeneration is needed. Direct inspection found no context that should retain local wording or use `labelLong`; if implementation-time evidence contradicts that finding, stop and revise the plan rather than expanding scope.

## 11. Expected Future Source Files

- `mobile/src/utils/serviceLabels.ts` — new shared display helper.
- `mobile/src/screens/BookingsScreen.tsx` — replace local function with helper import/call.
- `mobile/src/screens/ScheduleScreen.tsx` — replace local function with helper import/call.
- `mobile/src/screens/RequestDetailScreen.tsx` — replace local function with helper import/call.
- `mobile/src/components/RequestCard.tsx` — replace local function with helper import/call.
- Phase 24A-2C.2C release and necessary continuity documentation.

No other source file is expected. Any need to alter API clients, navigation, types, contracts, adapters, generators, validators, build configuration, web, or backend is a scope contradiction requiring a revised plan and new approval.

## 12. Expected Future Test Files

- `mobile/__tests__/serviceLabels.test.ts` — new exhaustive helper characterization/regression suite.
- Focused existing screen/component tests where practical. `mobile/__tests__/BookingsScreen.test.tsx` is the only existing focused test among the four current formatter owners and should add a real canonical rendering assertion plus raw-data/API parity where feasible.
- If meaningful integration coverage for `ScheduleScreen`, `RequestDetailScreen`, or `RequestCard` cannot fit an existing focused suite, add the smallest behavioral screen/component test file necessary. Such additions must remain inside the separately approved implementation candidate.

`mobile/__tests__/generatedContracts.test.ts` should run unchanged. No source-string or AST-only assertion should substitute for behavioral coverage.

## 13. Characterization-First Test Plan

Before modifying application source, add helper expectations that explicitly capture the intended split between changed canonical output and preserved fallback output.

### Canonical cases

Cover all seven exact identifiers and first establish their legacy outputs. The post-change expectations must then assert their exact contract `label` values from the matrix in Section 4. This expectation change is intentional and requires Matthew’s implementation approval.

### Fallback cases

Before and after wiring, prove exact output for:

- `DOG_WALKING`, `WALKING`, `OTHER`, and `HOUSE_SITTING`;
- an arbitrary unknown identifier such as `CUSTOM_CARE_2HR`;
- lowercase `walk_30min` and mixed-case `Walk_30Min`;
- `null`, `undefined`, and empty string.

### Integration and safety cases

Post-change behavioral tests must prove:

1. Every exact canonical identifier returns its exact contract `label`.
2. Every noncanonical and arbitrary unknown identifier retains exact legacy fallback output.
3. Lowercase and mixed-case canonical variants remain fallback values.
4. Nullish and empty values remain `''`.
5. All four real render contexts use the shared helper.
6. Existing API payloads remain unchanged.
7. Existing navigation parameters remain unchanged.
8. No selector value, order, membership, or default changes.
9. No service becomes newly available or unavailable.
10. `availableInIntake`, `supportedOnMobile`, and `durationMinutes` are not consumed.
11. Existing generated-contract tests pass.
12. The complete mobile test suite passes.
13. TypeScript remains clean.

Tests must use synthetic fixtures, exercise the real helper and practical real component/screen boundaries, mock API/auth/navigation boundaries, avoid production calls, avoid source-string or AST-only assertions, and avoid relying on test execution order.

## 14. Validation Commands

From repository root:

```powershell
node shared/validate-constants.mjs
node shared/validate-contract-adapters.mjs
```

From `mobile/`:

```powershell
npx jest __tests__/serviceLabels.test.ts
npx jest __tests__/BookingsScreen.test.tsx
npm test
npm run typecheck
```

Run any additional focused screen/component suites actually changed or added by the approved implementation. `mobile/package.json` has no lint script, so do not invent a mobile lint command.

Web and backend regressions are not required for this mobile-only display change because direct inspection found no shared runtime or backend behavioral dependency. If future implementation evidence finds such a dependency, stop and revise the validation scope. No EAS build is needed or authorized for local validation.

## 15. Risk and Rollback Boundary

**Risk:** **LOW TO MODERATE**.

The data behavior is display-only, but all seven canonical mobile labels change visibly, exact unknown fallback semantics are easy to normalize accidentally, and four render owners must adopt the same helper consistently.

Primary risks:

- choosing `labelLong` or local wording instead of `label`;
- accidental case, whitespace, or identifier normalization;
- degraded display of noncanonical or unknown values;
- missing a formatter owner or leaving inconsistent output;
- unintentionally changing accessibility text if future code reuses rendered strings;
- testing only the helper without practical render integration;
- allowing metadata fields to become implicit feature gates.

Rollback is limited to reverting the bounded mobile helper/source/test/release commit. No contract, adapter, backend, production-data, store, build, distribution, or tester rollback should be needed because none is part of the implementation.

## 16. Build, Distribution, and Tester Gates

Local Jest and TypeScript validation do not authorize distribution. The following remain separately gated and unapproved:

- EAS build or any APK, AAB, or IPA generation;
- TestFlight upload or configuration;
- Google Play or App Store activity;
- tester-list or tester-setting changes;
- Ryan testing, which remains paused;
- mobile production distribution or public release.

A future EAS build and tester-visible validation require separate explicit Matthew approval after local implementation is reviewed.

## 17. Approval Classifications

| Scope | Classification |
|---|---|
| Phase 24A-2C.2C planning | `APPROVED FOR DOCUMENTATION ONLY` |
| Phase 24A-2C.2C implementation | `ROADMAP_ONLY_NO_EXPLICIT_APPROVAL` |
| Intentional canonical mobile label changes | `REQUIRE EXPLICIT MATTHEW APPROVAL` |
| EAS build | `NOT APPROVED` |
| TestFlight | `NOT APPROVED` |
| Google Play | `NOT APPROVED` |
| App Store | `NOT APPROVED` |
| Tester changes | `NOT APPROVED` |
| Ryan testing | `PAUSED` |
| Production deployment | `NOT APPROVED` |
| Production-data inspection or migration | `NOT APPROVED` |

## 18. Explicit Exclusions

This planning phase does not authorize or perform:

- mobile source or test implementation;
- contract, adapter, generator, validator, or adapter-regeneration work;
- web or backend source/test work;
- API payload, navigation, selector, filtering, sorting, accessibility, analytics, test-identifier, feature-availability, or role-behavior changes;
- use of `availableInIntake`, `supportedOnMobile`, or `durationMinutes`;
- backend validation, scheduling, notification, Google Calendar, or stored-data changes;
- infrastructure, Terraform, Cognito, tenant, Stripe, or production-system activity;
- production API calls or production-data inspection/migration;
- builds, deployment, distribution, store, or tester activity;
- unrelated lint remediation.

## 19. Deferred Work

- Phase 24A-2C.2B selector membership, intake availability, and noncanonical normalization decisions.
- Phase 24A-2C.2D duration and scheduling metadata.
- Any future service selector, mobile intake/submission workflow, or `supportedOnMobile` feature gate.
- Any backend allowlist, identifier migration, production-data inspection, or normalization.
- EAS build, TestFlight/Google Play/App Store activity, tester changes, and Ryan validation.
- Production deployment and distribution.

Phase 24A-2C.2A remains locally complete and reviewed. Phase 24A-2C.2 overall remains partially complete. Phase 24A-2C.2C planning is complete, its implementation has not started and is not approved, and its canonical label changes require explicit Matthew approval.

---

**PLANNING COMPLETE / PHASE 24A-2C.2C IMPLEMENTATION NOT APPROVED / INTENTIONAL VISIBLE LABEL CHANGE REQUIRES MATTHEW APPROVAL**
