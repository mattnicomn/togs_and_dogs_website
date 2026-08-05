# Phase 24A-2C.2B.2C — MasterScheduler Canonical Service-Filter Correction

**Status:** **LOCALLY IMPLEMENTED, VALIDATED, INDEPENDENTLY REVIEWED, AND DOCUMENTED / PHASE 24A-2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / NOT DEPLOYED**

**Implementation, validation, independent review, and documentation date:** 2026-08-05
**Starting checkpoint:** `411342f1d3efbf5a981d8cbaa57570f7f925dfdc`

## Scope and authorization

Matthew explicitly approved one bounded local MasterScheduler service-filter correction: retain the existing static filter and exact case-sensitive `service_type` equality, add the three missing canonical scheduler filter options, extend the real-component coverage, run local validation, and prepare the minimum applicable documentation. No staging, commit, push, deployment, production-data access, backend change, contract change, adapter change, API-client change, mobile change, infrastructure change, or unrelated remediation was authorized.

## Problem statement

MasterScheduler could display records using all seven canonical service identifiers under `All Services`, but its static service filter exposed only `WALK_30MIN`, `DROPIN_1HR`, `DROPIN_3HR`, and `OVERNIGHT`. Staff could not isolate legitimate `WALK_60MIN`, `PET_SITTING`, or `MEET_GREET` scheduler records by exact service type.

## Exact filter correction

Three static options were added to `web/src/components/MasterScheduler.jsx`:

- `WALK_60MIN` / `60m Walk` immediately after `WALK_30MIN`;
- `PET_SITTING` / `Pet Sitting` immediately after `OVERNIGHT`;
- `MEET_GREET` / `Meet & Greet` immediately after `PET_SITTING`.

The exact final order is:

1. `ALL` — `All Services`
2. `WALK_30MIN` — `30m Walk`
3. `WALK_60MIN` — `60m Walk`
4. `DROPIN_1HR` — `1hr Drop-in`
5. `DROPIN_3HR` — `3hr Drop-in`
6. `OVERNIGHT` — `Overnight`
7. `PET_SITTING` — `Pet Sitting`
8. `MEET_GREET` — `Meet & Greet`

The default remains `ALL`.

## Unchanged filter semantics

The implementation retains the existing exact, case-sensitive predicate:

```js
filters.service === 'ALL' || i.service_type === filters.service
```

Filtering continues to use only `service_type`; `window_type` does not participate. Pending-intake cards remain outside the service-filter path. Desktop and mobile continue to consume the same filtered scheduler collection. Existing date, staff, status, search, clear-filter, count, selection, callback, navigation, grouping, scheduling, and display behavior remains unchanged.

## Legacy and unknown behavior

No explicit filter options were added for `DOG_WALKING`, `WALKING`, `OTHER`, arbitrary unknown identifiers, case variants, blank strings, null, or undefined values. Those records remain visible under `All Services` when they pass the other scheduler filters, and they do not match a canonical service selection. No mapping, aliasing, normalization, rewriting, migration, allowlist, rejection rule, or backend policy was introduced.

## Test coverage

`web/tests/ServiceTypeDisplayOwners.test.jsx` continues to render the real MasterScheduler. Seven tests were added, increasing that focused file from 8 to 15 tests. The coverage proves:

- exact option values, labels, order, and `ALL` default;
- all seven canonical exact-equality selections;
- legacy, unknown, lowercase, mixed-case, blank, null, and undefined behavior;
- `service_type` filtering despite overlapping `window_type` values;
- pending-intake independence and original callback arguments;
- desktop/mobile filtered-collection parity;
- unchanged date, staff, status, search, clear-filter, and visit-count behavior;
- input-array, record, and callback-object identity preservation;
- viewport, timer, and mock restoration.

Existing canonical and compatibility display-label coverage remains unchanged.

## Final validation results

| Validation | Result |
|---|---|
| Focused `ServiceTypeDisplayOwners` | 15/15 passed |
| Service-label helper | 29/29 passed |
| CareCard | 22/22 passed |
| AdminDashboard/IntakeForm regressions | 11/11 passed across 2 files |
| Legacy web | 99/99 passed |
| Complete Vitest | 231/231 passed across 19 files |
| Unique complete web | 330 tests passed |
| Shared constants | 18/18 passed |
| Generated adapter validation | 6/6 passed, deterministic |
| Vite build | Passed; 109 modules transformed |
| Build assets | `index-C5FqHoe-.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png` |
| Changed test lint | 0 errors, 0 warnings |
| MasterScheduler focused lint | 1 error, 0 warnings; pre-existing unused `onAssign` only |
| Complete web lint | 51 errors, 9 warnings; established baseline |
| Candidate-introduced lint | 0 errors, 0 warnings |
| Diff whitespace check | Passed |

Complete Vitest retained the existing jsdom navigation notice. The build retained the existing Vite `optimizeDeps.esbuildOptions` deprecation and large-chunk warnings. No unrelated lint was changed.

## Independent review

Kiro independently verified the exact two-file implementation candidate, the three static options and their positions, the unchanged `ALL` default, exact case-sensitive `service_type` equality, absence of legacy options, unchanged excluded systems, and the key validation matrix. It returned `READY_FOR_PHASE_24A_2C_2B_2C_DOCUMENTATION_AND_LOCAL_CLOSEOUT`; no blocking correction was identified.

## Files changed

Implementation and test:

- `web/src/components/MasterScheduler.jsx`
- `web/tests/ServiceTypeDisplayOwners.test.jsx`

Documentation:

- `docs/planning/phase-24a-2c2-service-type-contract-wiring.md`
- `docs/planning/phase-24a-2c2b-selector-normalization-design.md`
- `docs/project-continuity/current-state.md`
- `docs/project-continuity/document-map.md`
- `docs/release-notes/index.md`
- `docs/release-notes/phase-24a-2c2b2c-masterscheduler-canonical-service-filter.md`

## Explicit exclusions

Contracts, generated adapters, generators, validators, API clients, backend source, backend accepted-identifier policy, persistence, request/job records, scheduling durations, workflow classification, Google Calendar, notifications, mobile, infrastructure, production data, production systems, dependencies, lockfiles, and build configuration were unchanged. No production data was inspected, and repository evidence does not establish which legacy identifiers currently exist in production.

No deployment, S3 sync, CloudFront invalidation, Terraform action, mobile build/distribution, tester change, request/job/booking mutation, or external-system operation occurred. Passing tests and local closeout do not authorize deployment.

## Risks and rollback

The bounded risk is limited to staff-visible filter membership and the possibility that filter choices could be mistaken for a backend allowlist. Tests explicitly preserve exact equality and legacy behavior. Rollback is limited to removing the three options, the seven focused tests, and the corresponding documentation; no data, backend, contract, adapter, mobile, calendar, or infrastructure rollback is required.

## Approval and deployment gates

Phase 24A-2C.2B is locally complete for the approved frontend scope only. Backend accepted-identifier allowlisting/rejection, legacy normalization, production-data assessment, migration/deprecation, scheduler-specific contract metadata, further product/service availability changes, and deployment remain separate future decisions requiring explicit approval.

The latest completed validated production release remains Phase 1B.5C-D.2. Phase 24A remains local-only and not deployed. Phase 24A-2C.2 remains partially complete because Phase 24A-2C.2D is deferred. Phase 24A-2C.1 also remains deferred.

**Final status:** **LOCALLY IMPLEMENTED, VALIDATED, INDEPENDENTLY REVIEWED, AND DOCUMENTED / PHASE 24A-2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / NOT DEPLOYED**
