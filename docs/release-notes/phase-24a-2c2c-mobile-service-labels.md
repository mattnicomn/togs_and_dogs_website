# Phase 24A-2C.2C — Mobile Service-Type Display-Label Contract Wiring

**Date:** 2026-08-03

**Status:** **LOCAL IMPLEMENTATION COMPLETE / MOBILE SERVICE-TYPE DISPLAY LABELS WIRED / INTENTIONAL CANONICAL LABEL IMPROVEMENTS COMPLETE / NOT BUILT OR DISTRIBUTED / AWAITING INDEPENDENT RE-REVIEW**

## Approval and Scope

Matthew explicitly approved the bounded local implementation of the intentional mobile service-type display-label improvements documented in the Phase 24A-2C.2C plan. The candidate adds one type-safe display helper, replaces four duplicated display-only formatters, and adds real integration coverage for all four production render paths.

The candidate does not alter identifiers, payloads, navigation values, selectors, filtering, sorting, service availability, durations, contracts, generated adapters, generators, validators, web behavior, backend behavior, production data, build configuration, distribution, or tester settings.

## Intentional Canonical Label Improvements

These changes are intentional visible UX improvements, not byte-identical behavior preservation:

| Canonical identifier | Previous mobile display | New contract `label` display |
|---|---|---|
| `WALK_30MIN` | `WALK 30MIN` | `30-Min Walk` |
| `WALK_60MIN` | `WALK 60MIN` | `60-Min Walk` |
| `DROPIN_1HR` | `DROPIN 1HR` | `1-Hour Drop-in` |
| `DROPIN_3HR` | `DROPIN 3HR` | `3-Hour Drop-in` |
| `OVERNIGHT` | `OVERNIGHT` | `Overnight Care` |
| `PET_SITTING` | `PET SITTING` | `Pet Sitting` |
| `MEET_GREET` | `MEET GREET` | `Meet & Greet` |

## Shared Helper Architecture and Type Safety

New `mobile/src/utils/serviceLabels.ts` imports the existing generated `SERVICE_TYPES` adapter and defines:

- `ServiceTypeKey = keyof typeof SERVICE_TYPES.services`;
- a helper-local `isCanonicalServiceType` type predicate;
- an own-property guard using `Object.prototype.hasOwnProperty.call`;
- bounded legacy formatter fallback logic;
- exported `getServiceTypeLabel(value: string | null | undefined)`.

Direct arbitrary-string indexing was unsafe because `SERVICE_TYPES.services` is generated with `as const`, producing a narrow union of seven known keys rather than a broad string index signature. The own-property type guard proves the runtime string is one of those exact keys before indexing. It also prevents prototype-chain values such as `toString` from being mistaken for canonical services.

The helper does not use `any`, mutate the contract, normalize keys, or broaden generated types. Lookup remains exact and case-sensitive. It reads only the recognized service’s short `label`; it does not read `labelLong`, `availableInIntake`, `supportedOnMobile`, or `durationMinutes`.

## Exact Legacy Fallback Preservation

Every noncanonical, unknown, or case-variant identifier continues through the exact prior formatter: split on underscores, uppercase only each token’s first character, preserve the remainder, and join with spaces.

| Input | Preserved output |
|---|---|
| `DOG_WALKING` | `DOG WALKING` |
| `WALKING` | `WALKING` |
| `OTHER` | `OTHER` |
| `HOUSE_SITTING` | `HOUSE SITTING` |
| `UNKNOWN_SERVICE_TYPE` | `UNKNOWN SERVICE TYPE` |
| `walk_30min` | `Walk 30min` |
| `Walk_30Min` | `Walk 30Min` |
| `null` | `''` |
| `undefined` | `''` |
| empty string | `''` |
| prototype-like `toString` | `ToString` |

There is no uppercasing, lowercasing, trimming, aliasing, full title-casing, raw underscore fallback, or legacy-to-canonical mapping.

## Four Formatter Owners Migrated

Only the duplicated local formatter and its call were replaced in each owner:

- `mobile/src/screens/BookingsScreen.tsx`;
- `mobile/src/screens/ScheduleScreen.tsx`;
- `mobile/src/screens/RequestDetailScreen.tsx`;
- `mobile/src/components/RequestCard.tsx`.

Surrounding JSX, styles, text hierarchy, loading/empty/error states, request data, API calls, action payloads, and navigation remain unchanged. No service text participates in a custom accessibility label or test identifier.

`BookingsScreen` still calls `getClientRequests()` with no formatter-derived value. `ScheduleScreen` still calls `getAdminRequests('ALL')` and passes the raw request, selected date, and job ID to `RequestDetail`. `RequestCard` still passes the original raw request object to `RequestDetail`. Review, assignment, and completion calls retain their exact existing identifiers and payload construction.

## Characterization and Integration Coverage

Before source changes, real render characterization passed 2/2 suites and 8/8 tests, proving:

- current canonical output in BookingsScreen, ScheduleScreen, RequestDetailScreen, and RequestCard;
- exact noncanonical `DOG_WALKING` fallback in a real RequestCard;
- unchanged Schedule API invocation.

The first attempted characterization run exposed a test-harness-only issue: new tests did not await RNTL v14 `render`, leaving the global query surface unbound and producing `act()` warnings for Schedule state updates. The tests were corrected to use the repository’s established awaited-render pattern. The successful pre-change characterization and every subsequent run emitted no React `act()` warnings.

Post-change coverage includes:

- `mobile/__tests__/serviceLabels.test.ts`: 23/23 focused helper tests covering all seven canonical values, seven legacy/unknown/case fallbacks, three blank-like values, the prototype-like key, four metadata-like inputs, and contract non-mutation;
- `mobile/__tests__/BookingsScreen.test.tsx`: existing 4/4 suite strengthened to assert `Pet Sitting` and unchanged `getClientRequests()` invocation;
- `mobile/__tests__/ServiceTypeLabelOwners.test.tsx`: 4/4 tests covering ScheduleScreen, RequestDetailScreen, RequestCard, exact noncanonical fallback, unchanged Schedule API input, and raw Schedule/RequestCard navigation values;
- focused post-change total: 3/3 suites and 31/31 tests;
- owner-focused total: 2/2 suites and 8/8 tests;
- all four production render paths use the real helper; the helper is not mocked.

All fixtures are synthetic. API, authentication, staff, modal, and navigation boundaries are mocked. No source-string or AST-only assertions and no production calls are used.

## Validation

- Shared constants: 18/18 passed; 0 failed, skipped, cancelled, or todo.
- Generated adapter validation: 6/6 passed; deterministic zero second diff; 0 failed, skipped, cancelled, or todo.
- Focused helper: 23/23 passed.
- Focused owner integration: 8/8 passed across 2 suites.
- Focused combined: 31/31 passed across 3 suites.
- Complete mobile: 8/8 suites and 69/69 tests passed; 0 failed and 0 skipped.
- TypeScript: `tsc --noEmit` passed with 0 errors.
- Mobile lint: **NO MOBILE LINT SCRIPT CONFIGURED**.
- Final successful focused and complete runs emitted no console warnings/errors, React `act()` warnings, open-handle notices, or asynchronous-leak notices.
- Validation changed no tracked contract or generated-adapter content.
- Web classification: **NO_WEB_REGRESSION_REQUIRED_FOR_MOBILE_DISPLAY_ONLY_SCOPE**.
- Backend classification: **NO_BACKEND_REGRESSION_REQUIRED_FOR_MOBILE_DISPLAY_ONLY_SCOPE**.

No mobile build is required for this local validation. The repository’s mobile instructions required review of the versioned Expo documentation before code changes; no Expo API, dependency, configuration, or build behavior changed.

## Scope Audit

Unchanged:

- `shared/constants/service-types.json`;
- `mobile/src/contracts/generatedContracts.ts`;
- `mobile/__tests__/generatedContracts.test.ts`;
- shared generator and validators;
- mobile API client, navigation configuration, request/booking types, selectors, filtering, sorting, feature availability, and build configuration;
- `availableInIntake`, `supportedOnMobile`, and `durationMinutes` runtime consumption;
- web and backend source/tests;
- infrastructure, Terraform, Cognito, tenants, Stripe, Google Calendar, and production data.

No EAS build, Expo distribution build, APK/AAB/IPA generation, TestFlight/Google Play/App Store action, tester change, Ryan testing, production-data inspection, production API call, deployment, S3 sync, CloudFront invalidation, Terraform action, notification action, or unrelated remediation occurred.

## Phase Boundary

Phase 24A-2C.2 remains partially complete:

- 2C.2A: locally validated and reviewed;
- 2C.2B: deferred and not approved;
- 2C.2C: locally implemented and awaiting independent re-review; not built or distributed;
- 2C.2D: deferred and not approved.

This record does not claim full Phase 24A-2C.2 completion, build, distribution, TestFlight/Google Play/App Store availability, Ryan testing, selector normalization, service-availability filtering, duration centralization, production deployment, production validation, production-data inspection, or unrelated remediation.

---

**LOCAL IMPLEMENTATION COMPLETE / MOBILE SERVICE-TYPE DISPLAY LABELS WIRED / INTENTIONAL CANONICAL LABEL IMPROVEMENTS COMPLETE / NOT BUILT OR DISTRIBUTED / AWAITING INDEPENDENT RE-REVIEW**
