# Phase 24A-2C.2B.2B — CareCard Service-Type Correction

**Status:** **LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / CARECARD SERVICE-TYPE CORRECTION COMPLETE / NOT DEPLOYED**

**Implementation and local validation date:** 2026-08-05
**Independent review and local closeout date:** 2026-08-05
**Starting checkpoint:** `536111a580b8368b8f87d61bada9f2300b613bbd`

## Authorization and outcome

Matthew explicitly approved only the bounded local Option 2 CareCard correction. The ineffective editable Service Type selector was removed. Service Type remains visible as read-only information in Visit Details, and no request/booking editor or PET-level service preference was created.

The display source is request-first: `pet._originItem?.service_type` when present, otherwise historical `pet.service_type`. Exact canonical identifiers use the existing `getKnownServiceTypeLabel` helper and generated `labelLong`; the same helper supplies `DOG_WALKING` → `Daily Dog Walking`, `WALKING` → `Dog Walking`, and `OTHER` → `Other`. Unknown, lowercase, and mixed-case nonblank values remain raw and untrimmed. Null, undefined, empty, and whitespace-only values display `Not Specified`.

CareCard now explicitly removes the top-level `service_type` inherited through `formData` before calling `onUpdate`. Every other existing save field and value, including `pet_id`, `client_id`, request metadata, active-pet selection, multi-pet behavior, callbacks, status handling, and new/fallback PET flow, remains unchanged. This does not persist or edit request service data.

## Backend characterization boundary

Backend source is unchanged. Focused tests now document the existing behavior:

- staff/admin PUT succeeds but ignores a submitted new `service_type`;
- an absent stored field is not added, while an existing stored field is preserved if a different value is submitted;
- staff/admin POST does not copy `service_type` into a new PET;
- client PUT rejects `service_type` with HTTP 400 before persistence;
- customer PET response sanitization excludes a stored `service_type`;
- a rejected client request leaves unrelated stored attributes unchanged.

These tests characterize existing ignored/rejected behavior only. They do not authorize or introduce backend validation, normalization, aliases, persistence, or deployment.

## Focused frontend coverage

`web/tests/CareCardServiceType.test.jsx` uses the real CareCard and real service-label helper. Its 22 tests cover all seven canonical labels, all three approved aliases, request-first precedence, historical fallback, raw unknown/lowercase/mixed-case values, missing and blank values, read-only edit mode, exact save-payload omission with all other fields preserved, identifier/callback parity, input immutability, active multi-pet selection, and the new/fallback creation flow.

## Validation results

| Validation | Result |
|---|---|
| Focused CareCard | 22/22 passed |
| Existing service-label/owner regressions | 37/37 passed across 2 files |
| AdminDashboard/IntakeForm regressions | 11/11 passed across 2 files |
| Legacy web | 99/99 passed |
| Complete Vitest | 224/224 passed across 19 files |
| Unique complete web | 323 tests passed |
| Focused backend staff/admin PET suite | 23/23 passed |
| Focused backend customer PET suite | 18/18 passed |
| Focused backend combined | 41/41 passed |
| Shared constants | 18/18 passed |
| Generated adapter validation | 6/6 passed, deterministic |
| Vite build | Passed; 109 modules transformed |
| Build assets | `index-C-Rflmrt.js`, `index-bVFIMo3n.css`, `usmh-logo-CrRnxp7-.png` |
| New focused test lint | 0 errors, 0 warnings |
| CareCard focused lint | 6 errors, 1 warning; exact pre-change baseline |
| Complete web lint | 51 errors, 9 warnings; established pre-change baseline |
| Candidate-introduced lint | 0 errors, 0 warnings |
| Diff whitespace check | Passed |

The focused backend run retained existing `datetime.utcnow()` deprecation warnings and a local pytest-cache permission warning. Complete Vitest retained the existing jsdom navigation notice; the build retained the existing Vite `optimizeDeps` deprecation and large-chunk notices. No unrelated lint was changed.

Kiro independently confirmed the exact 10-file candidate, CareCard implementation, request-first precedence, helper-backed known labels, raw unknown values, `Not Specified` blank/null behavior, top-level save-payload omission, complete web results, and unchanged excluded systems. It returned `READY_FOR_LOCAL_PHASE_24A_2C_2B_2B_CLOSEOUT` with no blocking correction. Its noted nullish-coalescing nuance is intentional: empty or whitespace-only request-origin values display `Not Specified` rather than falling back to historical PET data, matching Matthew's approved requirement.

## Scope and safety audit

Application source changed only in `web/src/components/CareCard.jsx`. Frontend coverage was added only in `web/tests/CareCardServiceType.test.jsx`; backend changes are test-only in the two existing PET-handler suites.

Contracts, generated adapters, generators, validators, API clients, dependencies, lockfiles, CSS, AdminDashboard, ClientPortal, MasterScheduler, IntakeForm, MyPets, mobile, backend source, scheduling, notifications, persistence rules, infrastructure, and production data were unchanged. No production-data inspection, migration, API action, deployment, S3/CloudFront/Terraform action, mobile build/distribution, or tester change occurred.

Phase 24A-2C.2 remains partially complete locally. Phase 24A-2C.2B remains partially implemented locally; backend accepted-identifier policy, additional selector decisions, production assessment, and migration remain deferred. Phase 24A-2C.2D remains deferred. The latest validated production release remains Phase 1B.5C-D.2. Passing tests do not authorize deployment.

**Final status:** **LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / CARECARD SERVICE-TYPE CORRECTION COMPLETE / NOT DEPLOYED**
