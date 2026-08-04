# Phase 24A-2C.2B.2A — Customer Intake Canonical Service Selection

**Status:** **LOCAL IMPLEMENTATION COMPLETE / CUSTOMER INTAKE EMITS SIX CANONICAL AVAILABLE-IN-INTAKE SERVICE TYPES / LEGACY IDENTIFIERS REMAIN READ-COMPATIBLE / NOT DEPLOYED / AWAITING INDEPENDENT RE-REVIEW**

**Implementation date:** 2026-08-04
**Starting checkpoint:** `14cb6ec1519733b36a88e1dfc12b20be6c997531`

## Authorization and business policy

Matthew explicitly approved these decisions:

- `DOG_WALKING` and `WALKING` are not automatically mapped to a canonical duration and remain legacy read-compatible identifiers.
- New customer intake offers explicit `WALK_30MIN` and `WALK_60MIN` choices.
- `OTHER` is not emitted for new service requests; legacy values remain readable.
- Customer intake offers the six canonical services whose contract metadata has `availableInIntake: true`.
- `MEET_GREET` remains excluded because `availableInIntake` is false.
- AdminDashboard retains all seven canonical choices, MasterScheduler remains unchanged, and mobile remains without a selector.
- CareCard's ineffective PET-profile `service_type` field is unchanged and remains separately gated.
- No alias, normalization, record rewrite, backend enforcement, production-data inspection, migration, deployment, or distribution is approved.

## Exact membership and label change

### Before

| Order | Identifier | Visible label |
|---:|---|---|
| 1 | `PET_SITTING` | `Pet Sitting (Check-ins)` |
| 2 | `DOG_WALKING` | `Daily Dog Walking` |
| 3 | `OVERNIGHT` | `Overnight Care` |

### After

| Order | Identifier | Contract `labelLong` |
|---:|---|---|
| 1 | `WALK_30MIN` | `30-Minute Walk` |
| 2 | `WALK_60MIN` | `60-Minute Walk` |
| 3 | `DROPIN_1HR` | `1-Hour Drop-in` |
| 4 | `DROPIN_3HR` | `3-Hour Drop-in` |
| 5 | `OVERNIGHT` | `Overnight Care` |
| 6 | `PET_SITTING` | `Pet Sitting` |

The implementation imports generated `SERVICE_TYPES` from `../generated/contracts`, retains contract object order, filters only entries where `availableInIntake === true`, and renders each entry's `labelLong`. It does not sort or define local service labels.

`DOG_WALKING`, `WALKING`, `OTHER`, `MEET_GREET`, and arbitrary identifiers are absent from new customer intake. The unrelated pet-species value `OTHER` remains unchanged.

## Preserved behavior

- The initial/default `service_type` remains `PET_SITTING`; no placeholder or implicit default was invented.
- The selected canonical identifier remains the exact raw `service_type` placed in the existing payload spread.
- Focused tests prove unchanged submission for `WALK_30MIN`, `WALK_60MIN`, `DROPIN_3HR`, and authenticated-client `OVERNIGHT`.
- No mapping or normalization function was added.
- Public and authenticated-client API endpoints, authentication branching, request structure, consent metadata, non-service fields, loading, success, error, and retry behavior remain unchanged.
- Required-service validation still rejects an empty selection.
- Styles and accessibility structure remain unchanged.
- Legacy identifier display/read compatibility remains in existing AdminDashboard, ClientPortal, mobile, notification, and calendar fallback paths.

## Test coverage

`web/tests/IntakeFormServiceTypes.test.jsx` renders the real IntakeForm with mocked authentication and API boundaries. It proves:

- exactly six options, exact canonical values/order, and exact contract-derived labels;
- `PET_SITTING` default parity;
- absence of `DOG_WALKING`, `WALKING`, `OTHER`, and `MEET_GREET`;
- empty-service validation;
- exact public payload, including all existing non-service fields;
- raw canonical submission without normalization;
- authenticated-client endpoint and payload behavior;
- loading, error, and retry behavior without any real API call.

Pre-change characterization passed 5/5 before the source modification. Post-change focused coverage passes 7/7.

## Validation results

| Validation | Result |
|---|---|
| Shared constants | 18/18 passed |
| Generated adapter validation | 6/6 passed, deterministic |
| Focused IntakeForm | 7/7 passed in 1 file |
| Legacy web | 99/99 passed |
| Complete Vitest | 158/158 passed across 15 files |
| Unique complete web | 257 tests passed |
| Vite build | Passed; 108 modules transformed |
| Build assets | `index-aRRxk0NM.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png` |
| Changed test lint | 0 errors, 0 warnings |
| IntakeForm lint | 2 errors, 0 warnings; both pre-existing (`staffOptionsLoading`, synchronous effect state update) |
| Complete web lint | 51 errors, 9 warnings; exact known pre-change baseline |
| Candidate-introduced lint | 0 errors, 0 warnings |

The complete Vitest run emitted one jsdom `Not implemented: navigation to another Document` message not reproduced by the focused suite. The build retained the existing Vite deprecated-option and large-chunk warnings. All test/build commands exited without open-handle or asynchronous-leak findings.

No existing bounded backend test proves all six identifiers in one request-creation matrix, and no backend source changed: `NO_BACKEND_REGRESSION_REQUIRED_FOR_FRONTEND_SELECTOR_ONLY_SCOPE`.

No shared runtime dependency or mobile code changed: `NO_MOBILE_REGRESSION_REQUIRED_FOR_WEB_INTAKE_SELECTOR_ONLY_SCOPE`.

## Scope and safety audit

Application source changed only in `web/src/components/IntakeForm.jsx`. Test scope is only `web/tests/IntakeFormServiceTypes.test.jsx`.

Unchanged: CareCard, AdminDashboard, MasterScheduler, ClientPortal, mobile source/tests, backend source/tests, shared service contract, generated adapters, generator, validators, API paths, dependencies, lockfiles, build configuration, Terraform, infrastructure, Cognito, tenants, Stripe, Google Calendar, and production data.

No stored record was modified. No production API/data inspection, migration, deployment, S3 sync, CloudFront invalidation, Terraform action, mobile build, distribution, or tester change occurred. Phase 24A-2C.2D and Phase 24A-2C.1 were not started.

## Remaining Phase 24A-2C.2B boundaries

Phase 24A-2C.2B is only partially implemented:

- planning: complete;
- 2B.2A customer IntakeForm canonical selection: locally implemented, awaiting independent review;
- CareCard cleanup: not approved;
- display compatibility: deferred;
- backend accepted-identifier policy: deferred;
- production assessment: not approved;
- migration/deprecation: not approved.

**Final status:** **LOCAL IMPLEMENTATION COMPLETE / CUSTOMER INTAKE EMITS SIX CANONICAL AVAILABLE-IN-INTAKE SERVICE TYPES / LEGACY IDENTIFIERS REMAIN READ-COMPATIBLE / NOT DEPLOYED / AWAITING INDEPENDENT RE-REVIEW**
