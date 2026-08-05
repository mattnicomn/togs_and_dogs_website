# Phase 24A-2C.2D.1 — Service-Duration Parity and Validator Hardening

**Status:** **LOCALLY IMPLEMENTED, VALIDATED, INDEPENDENTLY REVIEWED, AND DOCUMENTED / PARITY AND VALIDATOR HARDENING COMPLETE / NO RUNTIME BEHAVIOR CHANGE / NOT DEPLOYED**

**Implementation and local closeout date:** 2026-08-05

**Starting checkpoint:** `dd51c044105d1bc5ab284eabc8d30e1b73cb6457` (`main`, matching `origin/main`)

**Starting commit:** `feat: add canonical MasterScheduler service filters`

## 1. Scope and authorization

Matthew explicitly approved one bounded local Phase 24A-2C.2D.1 candidate to strengthen canonical service validation, prove complete generated-adapter equality, add focused backend calendar parity/fallback characterization, run local validation, and prepare the applicable documentation after independent review.

The approved implementation modifies only:

- `shared/validate-constants.mjs`;
- `shared/validate-contract-adapters.mjs`.

It adds only:

- `tests/backend/test_phase24a_service_duration_contract_parity.py`.

This is validation and characterization work only. It does not centralize runtime metadata or change application behavior.

## 2. Starting checkpoint

Work began on `main` at `dd51c044105d1bc5ab284eabc8d30e1b73cb6457`, with local `HEAD` equal to `origin/main`, an empty stash, and only the exact independently reviewed three-file candidate present when documentation closeout resumed. No branch creation or switch occurred.

The latest completed validated production release remains Phase 1B.5C-D.2. Phase 24A remains local-only and is not deployed or distributed.

## 3. Problem statement

The canonical `shared/constants/service-types.json` already held five metadata fields for seven services, and the generator already emitted the complete object to web and mobile. However:

- canonical validation did not fully enforce the complete field shape and types;
- adapter validation did not prove complete canonical/web/mobile `SERVICE_TYPES` equality;
- no focused suite proved that canonical durations and short labels matched the active backend calendar helper while preserving current override, unresolved, color, all-day, and window behavior.

Phase 2D.1 closes those evidence gaps without changing the contract or runtime source.

## 4. Canonical validator hardening

`shared/validate-constants.mjs` now requires every canonical service entry to:

- be a plain object;
- contain `label`, `labelLong`, `durationMinutes`, `availableInIntake`, and `supportedOnMobile`;
- contain no null or undefined required value;
- use nonempty strings for `label` and `labelLong`;
- use a numeric, finite, integer `durationMinutes` greater than zero;
- use exact booleans for `availableInIntake` and `supportedOnMobile`.

No contract field or value changed. Calendar color, calendar title, and workflow metadata were not added to the contract. Identifier, metadata, pet-field, API-path, and unrelated canonical validation behavior remains intact.

## 5. Adapter equality hardening

`shared/validate-contract-adapters.mjs` now proves complete equality among:

- canonical `SERVICE_TYPES` and generated web `SERVICE_TYPES`;
- canonical `SERVICE_TYPES` and generated mobile `SERVICE_TYPES`;
- generated web and mobile `SERVICE_TYPES`.

Equality covers service membership, identifier order, all five metadata fields, exact labels, exact durations, exact booleans, and the absence of missing or extra services or metadata. Failure messages distinguish canonical-to-web, canonical-to-mobile, and web-to-mobile failures.

Existing complete `PET_FIELDS` validation remains intact. Deterministic generation continues to produce zero diff. Generator source and both generated adapters are unchanged; no adapter output was manually generated or modified as part of the candidate.

## 6. Backend parity-test coverage

The new focused suite contains 48 tests using:

- the real canonical JSON file;
- real `common.google_calendar._build_event_body()` behavior;
- synthetic request records only;
- no Google API calls, production credentials, tokens, calendar IDs, or production data.

The suite compares contract metadata to actual event start/end, timezone, title, description, duration, color, all-day shape, and window-derived timing. It does not monkeypatch the backend duration or friendly-name maps and does not assert request/job persistence.

## 7. Exact canonical parity matrix

| Canonical identifier | Contract duration | Contract `label` | Characterized backend result |
|---|---:|---|---|
| `WALK_30MIN` | 30 minutes | `30-Min Walk` | Exact duration and label parity |
| `WALK_60MIN` | 60 minutes | `60-Min Walk` | Exact duration and label parity |
| `DROPIN_1HR` | 60 minutes | `1-Hour Drop-in` | Exact duration and label parity |
| `DROPIN_3HR` | 180 minutes | `3-Hour Drop-in` | Exact duration and label parity |
| `OVERNIGHT` | 720 minutes | `Overnight Care` | Exact duration and label parity |
| `PET_SITTING` | 60 minutes | `Pet Sitting` | Exact duration and label parity |
| `MEET_GREET` | 45 minutes | `Meet & Greet` | Exact duration and label parity |

For timed events without an explicit override, the event start remains unchanged, end minus start equals the canonical duration, and both start and end retain `America/New_York`.

## 8. Override and fallback behavior

The focused characterization confirms the exact existing behavior:

- a truthy numeric `scheduled_duration` overrides the canonical default;
- a truthy numeric string accepted by `int(...)` also overrides the default;
- missing, zero, blank-string, and null overrides retain falsey fallthrough to the canonical default or unresolved fallback;
- unresolved values retain the generic 60-minute duration;
- matching remains exact and case-sensitive;
- `DOG_WALKING`, `WALKING`, `OTHER`, arbitrary unknown values, lowercase canonical variants, and mixed-case canonical variants remain unresolved;
- legacy and unknown labels remain raw;
- null, blank, and missing service values retain their exact existing title/description behavior;
- unresolved color remains `8`.

No alias, mapping, trimming, normalization, rejection rule, or canonical equivalence was introduced.

## 9. Color, all-day, and window characterization

Colors remain backend-only characterization and are not canonical contract authority:

- walk services: `9`;
- drop-in services: `7`;
- overnight: `6`;
- pet sitting: `10`;
- meet and greet: `3`;
- unresolved services: `8`.

All-day events retain the current exclusive next-date end. Canonical durations and the unresolved 60-minute fallback do not affect the all-day event shape.

Recognized visit-window starts remain:

- `MORNING`: 08:00;
- `MIDDAY`: 11:00;
- `AFTERNOON`: 14:00;
- `EVENING`: 17:00.

The applicable canonical duration is added after each inferred start. `window_type` and visit-window semantics remain unchanged.

## 10. Final validation totals

| Validation | Final result |
|---|---|
| Shared canonical constants | 18/18 passed |
| Shared adapter validation | 7/7 passed |
| Deterministic generation check | Passed; zero diff |
| Focused Phase 2D.1 parity suite | 48/48 passed |
| Calendar hardening regression | 18/18 passed |
| All-day regression | 12/12 passed |
| Multi-day regression | 22/22 passed |
| Combined affected backend set | 100/100 passed |
| `node --check` for both modified `.mjs` files | Passed |
| Python AST parsing and pytest collection | Passed; 48 tests collected |
| `git diff --check` | Passed |

The requested `py` launcher returned `No installed Python found!` in this environment. The available `python` executable (Python 3.13.3) ran the identical collection, focused, regression, and combined commands successfully.

Pytest reproduced the non-functional warning that it could not write `.pytest_cache` in this workspace. Collection and execution succeeded, and no candidate cache, bytecode, coverage, build, or other transient artifact remains.

Web and mobile suites were not run because no web or mobile source changed. No web/mobile regression surface is introduced by validation-only shared scripts and backend tests.

## 11. Independent review

Kiro independently verified the exact three-file implementation candidate and reproduced:

- 18 shared constant checks;
- 7 shared adapter checks;
- 48 focused parity tests;
- 100 combined affected backend tests.

Kiro returned `READY_FOR_PHASE_24A_2C_2D_1_DOCUMENTATION_AND_LOCAL_CLOSEOUT`. No blocking correction was identified.

## 12. Exact files changed

Implementation and test:

- `shared/validate-constants.mjs`;
- `shared/validate-contract-adapters.mjs`;
- `tests/backend/test_phase24a_service_duration_contract_parity.py`.

Documentation:

- `docs/planning/phase-24a-2c2-service-type-contract-wiring.md`;
- `docs/planning/phase-24a-2c2b-selector-normalization-design.md` — continuity correction only;
- `docs/project-continuity/current-state.md`;
- `docs/project-continuity/document-map.md`;
- `docs/release-notes/index.md`;
- `docs/release-notes/phase-24a-2c2d1-service-duration-parity-validator-hardening.md`.

## 13. Explicit exclusions

The candidate did not change:

- `shared/constants/service-types.json` or any contract property/value;
- `shared/generate-contract-adapters.mjs`;
- generated web or mobile adapters;
- Google Calendar runtime logic;
- backend handlers;
- request/job persistence;
- scheduling behavior;
- event titles, durations, colors, starts, timezones, or all-day behavior;
- web or mobile source/tests;
- notifications or payments;
- infrastructure or deployment configuration;
- production data or production systems;
- dependencies, lockfiles, build configuration, or distribution settings.

No Google Calendar invocation, production-data inspection, external-system mutation, Terraform action, S3 sync, CloudFront invalidation, Cognito/Stripe/tenant action, mobile build, store action, or tester change occurred.

## 14. Risks and rollback

The primary risk is documentation or validation becoming stricter than the current canonical shape while runtime behavior remains independently duplicated in backend maps. Focused parity tests expose drift before runtime centralization is attempted.

Rollback is limited to reverting the two validator edits, removing the focused test, and reverting the six documentation records. No contract, generated adapter, runtime, backend handler, data, web, mobile, infrastructure, or production rollback is required.

## 15. Approval and deployment gates

Phase 2D.1 local closeout does not authorize staging, commit, push, deployment, backend packaging, adapter generation, runtime wiring, production-data access, Google Calendar invocation, or existing-event changes. Any commit or push requires a separate Matthew decision. Any deployment requires a separate reviewed deployment plan and explicit approval.

Phase 24A-2C.2 remains partially complete locally. Phase 2D overall is not complete.

## 16. Subsequent and remaining deferred work

Phase 2D.2 subsequently completed its deterministic generated backend service metadata adapter locally, with independent review, no runtime consumption, and no deployment. See `docs/release-notes/phase-24a-2c2d2-generated-backend-service-metadata-adapter.md`.

- **2D.3:** calendar runtime duration and friendly-name wiring;
- **2D.4:** optional calendar color metadata;
- backend service-identifier acceptance policy;
- production assessment;
- legacy normalization;
- migration/deprecation;
- deployment review;
- existing-event resynchronization.

Each item requires separate planning, validation, risk/rollback review, and explicit approval. No production migration or resynchronization is presumed necessary.

## 17. Final status

**PHASE 24A-2C.2D.1 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / COMMITTED AND PUSHED AT `0b066339c6c208dba09458572bc666c9676e1951` / NO RUNTIME BEHAVIOR CHANGE / NOT DEPLOYED**

**Phase 24A-2C.2:** **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D.1 COMPLETE / 2C.2D.2 COMPLETE / 2C.2D.3–2C.2D.4 DEFERRED / NOT DEPLOYED OR DISTRIBUTED**
