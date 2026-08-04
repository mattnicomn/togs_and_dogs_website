# Phase 24A-2C.2A — Web Admin Service-Type Display-Label Contract Wiring

**Date:** 2026-08-03
**Status:** LOCALLY VALIDATED AND REVIEWED / WEB ADMIN SERVICE-TYPE DISPLAY LABELS WIRED / NOT DEPLOYED OR DISTRIBUTED

## Approval and Scope

Matthew explicitly approved behavior-preserving `AdminDashboard` service-type display-label wiring only. This local change replaces the duplicated seven-entry long-label and dispatch-label maps with the existing generated `SERVICE_TYPES` adapter and leaves service identifiers, payloads, stored values, search behavior, exports, workflow classification, availability, durations, other components, mobile, backend, and production systems unchanged.

## Implementation

- `AdminDashboard.jsx` now imports `SERVICE_TYPES` from `web/src/generated/contracts.js`.
- Long display/search labels use the case-sensitive `SERVICE_TYPES.services[serviceType]?.labelLong` lookup. Blank-like values still return `UNKNOWN SERVICE`; unknown nonblank values still retain their existing case while underscores become spaces and word initials are uppercased.
- Dispatch-friendly labels normalize the lookup key to uppercase and use `SERVICE_TYPES.services[key]?.label`. Recognized lowercase and mixed-case canonical identifiers still receive canonical short labels; unknown nonblank values still return the original supplied value exactly; blank-like values still return `''`.
- The New Visit selector retains seven explicit options in the exact order `PET_SITTING`, `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, `MEET_GREET`. Only their text nodes now reference explicit `labelLong` properties. `PET_SITTING` remains the default; no iteration, filtering, sorting, duration use, or availability use was introduced.

## Behavioral Characterization and Parity

Before the source change, the focused real-component suite passed 4/4 after two test-harness query corrections. The same expectations pass after the source change and prove:

- byte-for-byte long labels for all seven canonical identifiers;
- unchanged long fallbacks for `DOG_WALKING`, `WALKING`, `OTHER`, `HOUSE_SITTING`, lowercase/mixed-case canonical variants, null, undefined, and empty string;
- unchanged case-insensitive dispatch recognition for all seven canonical identifiers and lowercase/mixed-case variants;
- unchanged original-value dispatch fallback for noncanonical/arbitrary unknown identifiers and unchanged blank-like output;
- exact selector values, order, membership, text, default, and `MEET_GREET` inclusion, with no noncanonical option;
- search remains based on the existing long-label output;
- the exact New Visit payload retains the selected raw `service_type` identifier;
- raw request backup rows retain raw nonblank `service_type` values and existing blank sanitization;
- Daily Dispatch retains the existing short-label output.

Search expressions, raw request mapping, payload construction, workflow-classification arrays, dispatch row structure, and runtime messages were not changed.

## Independent Review and Validation

Kiro independently confirmed that the candidate delta contains exactly the expected six implementation files, the scope is correctly bounded, the long-label and short-label behavior is preserved, and the selector values, order, membership, labels, and default are unchanged. AG independently completed the remaining build, lint, mobile, TypeScript, and backend regression validation. No correction was required.

- Shared constants: 18/18 passed.
- Generated adapter validation: 6/6 passed, including deterministic zero second diff.
- Focused `AdminDashboardServiceTypes.test.jsx`: 4/4 passed before and after wiring.
- Existing AdminDashboard suites: 43/43 passed across 2 files.
- Phase 1B.3: 20/20 passed.
- Complete legacy: 99/99 passed.
- Complete Vitest: 151/151 passed across 14 files.
- Unique complete web total: 250 passed (99 legacy + 151 Vitest; focused runs are not double-counted).
- Vite 8.0.8 build: passed; assets `dist/index.html`, `dist/assets/index-D7UoV5fJ.js`, `dist/assets/index-bVFIMo3n.css`, and `dist/assets/usmh-logo-CrRnxp7-.png`.
- Focused test lint: 0 errors, 0 warnings.
- Candidate-introduced lint: 0 errors, 0 warnings.
- `AdminDashboard.jsx` retains 18 errors and 5 warnings that existed before this candidate.
- Complete web lint retains 51 errors and 9 warnings in unrelated pre-existing code. These findings were not introduced, modified, or remediated by this phase.
- Mobile: 6/6 suites and 42/42 tests passed; TypeScript reported 0 errors. `mobile/package.json` has no lint script.
- Documented backend calendar regression: 30/30 passed with 0 failed and 0 skipped.

The complete Vitest run emitted the existing JSDOM `Not implemented: navigation to another Document` notice. The build emitted the existing `optimizeDeps.esbuildOptions` deprecation notice and greater-than-500-kB chunk warning. Successful required runs reported no open-handle or asynchronous-leak failures.

Validation did not modify tracked contracts or adapters. Build output remained ignored and was not staged.

## Scope Audit

Unchanged: `shared/constants/service-types.json`, both generated adapters, generators, validators, `IntakeForm.jsx`, `CareCard.jsx`, `MasterScheduler.jsx`, `ClientPortal.jsx`, workflow classification, identifiers, payload shape, raw export mapping, duration and availability behavior, mobile source/tests, backend source/tests, API Gateway, Terraform, Cognito, tenants, Stripe, Google Calendar, and production data.

No production data was inspected or modified. No production API call, deployment, S3 sync, CloudFront invalidation, Terraform action, EAS build, mobile distribution, tester change, or notification action occurred.

## Deferred Work

Phase 24A-2C.2 overall is **PARTIALLY COMPLETE LOCALLY / PHASE 24A-2C.2A COMPLETE / PHASES 24A-2C.2B, 24A-2C.2C, AND 24A-2C.2D DEFERRED / NOT DEPLOYED OR DISTRIBUTED**:

- 2C.2A: locally validated and reviewed; Web Admin service-type display labels wired; not deployed or distributed;
- 2C.2B: selector membership/availability normalization deferred and not approved;
- 2C.2C: mobile service-label wiring deferred and not approved;
- 2C.2D: duration/scheduling metadata deferred and not approved.

Normalization of `DOG_WALKING`, `WALKING`, and `OTHER`; production-data inspection or migration; production deployment; mobile build or distribution; Ryan testing; and unrelated lint remediation remain separate, deferred, and unapproved.

This record does not claim full Phase 24A-2C.2 completion, production deployment, production validation, mobile distribution, Ryan testing, or unrelated lint remediation.
