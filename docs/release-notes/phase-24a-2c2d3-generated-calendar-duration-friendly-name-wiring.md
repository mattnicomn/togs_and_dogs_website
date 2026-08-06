# Phase 24A-2C.2D.3 — Generated Google Calendar Duration and Friendly-Name Metadata Wiring

**Status:** **LOCALLY IMPLEMENTED, VALIDATED, INDEPENDENTLY REVIEWED, AND DOCUMENTED / GENERATED CALENDAR DURATION AND FRIENDLY-NAME WIRING COMPLETE / EXACT BEHAVIOR PRESERVED / NOT DEPLOYED**

**Date:** 2026-08-05
**Base checkpoint:** `e7113c4d103305e464f43335b406ee6146742015` (`feat: add generated backend service metadata`)

---

## 1. Scope and authorization

Matthew explicitly authorized the bounded local Phase 24A-2C.2D.3 implementation candidate to wire the generated backend `SERVICE_TYPES` adapter into `src/backend/common/google_calendar.py`. This phase replaces the handwritten `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` dictionaries with generated metadata derivations, preserves exact symbol names and runtime behavior, updates AST test assertions to prove `google_calendar.py` is the exactly-one approved runtime consumer, adds 11 edge-characterization tests for `scheduled_duration`, and prepares local closeout documentation after independent review.

The authorization explicitly excluded:
- changes to contract values, generators, or generated metadata adapters;
- modification of `_build_event_body()` or the `scheduled_duration` override evaluation;
- modification of `SERVICE_COLORS` or `WINDOW_START_HOURS`;
- runtime identifier normalization, lowercasing, uppercasing, trimming, or alias mapping;
- backend handler, request/job persistence, scheduling, notification, status, or API changes;
- web or mobile changes;
- infrastructure or dependency changes;
- production-data access;
- Google Calendar API calls or event resynchronization;
- Phase 2D.4 optional color metadata;
- staging, commit, push, packaging, deployment, or mobile distribution.

## 2. Starting checkpoint

Implementation began on `main` at `e7113c4d103305e464f43335b406ee6146742015`, with `HEAD` equal to `origin/main`, a clean working tree, and an empty stash. Documentation closeout began from the same base with only the exact independently reviewed three-file implementation candidate present.

The latest completed validated production release remains Phase 1B.5C-D.2. Phase 24A remains local-only and is not deployed or distributed. Phase 2D.1 and Phase 2D.2 are committed and pushed at the base checkpoint; Phase 2D.3 is complete locally and not committed or pushed by this closeout.

## 3. Problem statement

Phase 24A-2C.2D.1 proved canonical duration and friendly-name parity for all seven canonical service types, and Phase 24A-2C.2D.2 generated the commit-ready Python backend metadata module `src/backend/common/generated_service_types.py`. However, `google_calendar.py` continued to rely on handwritten dictionary literals for `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES`. Phase 2D.3 eliminates duplicate backend metadata definitions by deriving both maps directly from the generated contract adapter without altering runtime calendar behavior, duration calculations, title formatting, or fallback logic.

## 4. Runtime import and metadata alias

In `src/backend/common/google_calendar.py`:

```python
from common.generated_service_types import SERVICE_TYPES

SERVICE_METADATA = SERVICE_TYPES["services"]
```

`SERVICE_METADATA` provides direct access to the canonical `services` dictionary.

## 5. Duration-map derivation

The handwritten `SERVICE_DURATIONS` literal was replaced with:

```python
SERVICE_DURATIONS = {
    service_type: metadata["durationMinutes"]
    for service_type, metadata in SERVICE_METADATA.items()
}
```

The resulting dictionary matches prior handwritten values byte-for-byte:
- `WALK_30MIN`: 30
- `WALK_60MIN`: 60
- `DROPIN_1HR`: 60
- `DROPIN_3HR`: 180
- `OVERNIGHT`: 720
- `PET_SITTING`: 60
- `MEET_GREET`: 45

## 6. Friendly-name-map derivation

The handwritten `FRIENDLY_SERVICE_NAMES` literal was replaced with:

```python
FRIENDLY_SERVICE_NAMES = {
    service_type: metadata["label"]
    for service_type, metadata in SERVICE_METADATA.items()
}
```

The resulting dictionary matches prior handwritten values byte-for-byte:
- `WALK_30MIN`: `30-Min Walk`
- `WALK_60MIN`: `60-Min Walk`
- `DROPIN_1HR`: `1-Hour Drop-in`
- `DROPIN_3HR`: `3-Hour Drop-in`
- `OVERNIGHT`: `Overnight Care`
- `PET_SITTING`: `Pet Sitting`
- `MEET_GREET`: `Meet & Greet`

## 7. Selection of `label` over `labelLong`

Canonical metadata defines both `label` (short display) and `labelLong` (expanded title). `FRIENDLY_SERVICE_NAMES` derives exclusively from `metadata["label"]` because:
1. Historical Google Calendar event titles expect `30-Min Walk` and `60-Min Walk`.
2. Using `labelLong` would output `30-Minute Walk` and `60-Minute Walk`, breaking byte-for-byte title parity for calendar events.
3. Contract `label` guarantees exact 100% string equality with existing backend friendly names across all seven canonical services.

## 8. Exact behavior-preservation boundary

- Symbol names `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` remain unchanged for full backward compatibility with callers and tests.
- `_build_event_body()` remains unmodified.
- The `scheduled_duration` override evaluation remains:
  ```python
  duration_mins = int(item.get('scheduled_duration') or SERVICE_DURATIONS.get(service_type, 60))
  ```
- `SERVICE_COLORS` remains handwritten: `{ 'WALK_30MIN': '9', 'WALK_60MIN': '9', 'DROPIN_1HR': '7', 'DROPIN_3HR': '7', 'OVERNIGHT': '6', 'PET_SITTING': '10', 'MEET_GREET': '3' }`. Unknown types fall back to color `'8'`.
- `WINDOW_START_HOURS` remains handwritten (`MORNING`: 8, `MIDDAY`: 11, `AFTERNOON`: 14, `EVENING`: 17).
- Fallback duration for unknown/unresolved services remains `60` minutes.
- Fallback title for unknown/unresolved services remains the raw supplied string.
- Fallback title for missing service remains `"Service"`.
- Event summary and description formatting remain unchanged.
- All-day start/end exclusive date calculations remain unchanged.
- Timezone remains `America/New_York`.
- Google API POST, PUT, delete, retry, and token handling remain unchanged.

## 9. Scheduled-duration edge characterization

11 new characterization tests in `tests/backend/test_phase24a_service_duration_contract_parity.py` document and preserve existing edge behavior:
1. Whitespace-padded numeric strings (e.g. `" 90 "`) are accepted by `int()`, yielding 90 minutes.
2. String `"0"` is truthy, yielding 0 minutes.
3. Negative integers (e.g. `-30`) are accepted by `int()`, causing end time to precede start time.
4. Floats (e.g. `90.7`) are converted by `int()`, truncating toward zero (90 minutes).
5. Boolean `True` is converted by `int()`, yielding 1 minute.
6. Boolean `False` is falsey, falling through to canonical or default duration.
7. Whitespace-only strings raise `ValueError`.
8. Malformed strings raise `ValueError`.
9. Decimal strings (e.g. `"90.5"`) raise `ValueError`.
10. Truthy overrides on unknown services win over the unknown 60-minute fallback.
11. Malformed truthy overrides on all-day items raise `ValueError` before all-day event body construction.

Phase 2D.3 did not correct, sanitize, or normalize any of these behaviors. They are characterization-only and remain candidates for a separately approved future policy decision.

## 10. Exactly-one-approved-consumer AST test transition

`tests/backend/test_phase24a_generated_service_types.py` replaced the Phase 2D.2 `test_no_backend_runtime_source_consumes_generated_service_types()` with `test_exactly_one_approved_backend_runtime_consumer_of_generated_service_types()`.

The AST inspection walk scans all `src/backend/**/*.py` files and verifies:
- `src/backend/common/google_calendar.py` is the **EXACTLY ONE** runtime consumer.
- The import statement matches `from common.generated_service_types import ...`.
- No backend handlers, status modules, notification modules, scheduling modules, or other common modules import generated metadata.
- Literal static imports (`import common.generated_service_types`), aliased imports, and literal dynamic imports (`importlib.import_module`, `__import__`) are detected and flagged if present elsewhere.
- `google_calendar.SERVICE_METADATA is SERVICE_TYPES["services"]` holds true.
- `google_calendar.SERVICE_DURATIONS` and `google_calendar.FRIENDLY_SERVICE_NAMES` match generated contract data.
- `google_calendar._build_event_body()` does not mutate `SERVICE_TYPES`.

## 11. Validation results

| Validation Suite | Result | Notes |
|---|---|---|
| Shared constants validator | **18/18 passed** | `node shared/validate-constants.mjs` |
| Shared adapter validator | **8/8 passed** | `node shared/validate-contract-adapters.mjs` |
| Python syntax compilation | **Clean (0 errors)** | `py -m py_compile ...` |
| Generated backend metadata tests | **6/6 passed** | `test_phase24a_generated_service_types.py` |
| Service duration parity tests | **59/59 passed** | `test_phase24a_service_duration_contract_parity.py` (48 existing + 11 new) |
| Calendar hardening regression | **18/18 passed** | `test_r7d_calendar_hardening.py` |
| All-day calendar regression | **12/12 passed** | `test_r6g_calendar_all_day.py` |
| Multi-day jobs regression | **22/22 passed** | `test_r7e_multi_day_jobs.py` |
| **Combined affected backend suite** | **117/117 passed** | All 5 test files executed together in 6.61s |
| `git diff --check` | **Clean (0 errors)** | Zero formatting or trailing whitespace issues |

Pytest executed under Python 3.13.3 (`py` launcher). All transient `__pycache__` directories were removed.

## 12. Independent review

Kiro independently reviewed the exact three-file implementation candidate and confirmed:
- exact three-file scope;
- behavior-preserving runtime wiring;
- `SERVICE_DURATIONS` derived from canonical `durationMinutes`;
- `FRIENDLY_SERVICE_NAMES` derived from canonical `label`;
- `labelLong` not used;
- `_build_event_body()` unchanged;
- handwritten color behavior unchanged;
- no identifier normalization;
- 18 shared constants checks passed;
- 8 shared adapter checks passed;
- 117 combined affected backend tests passed;
- generated metadata, contracts, web, and mobile files unchanged;
- returned classification: `BEHAVIOR_PRESERVING_GENERATED_METADATA_WIRING`;
- returned recommendation: `READY_FOR_PHASE_24A_2C_2D_3_DOCUMENTATION_AND_LOCAL_CLOSEOUT`.

No blocking correction was identified.

## 13. Files changed

### Implementation & Tests
1. `src/backend/common/google_calendar.py`
   - Added import `from common.generated_service_types import SERVICE_TYPES`.
   - Added `SERVICE_METADATA = SERVICE_TYPES["services"]`.
   - Replaced handwritten `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` literals with metadata dict comprehensions.
2. `tests/backend/test_phase24a_generated_service_types.py`
   - Replaced no-consumer test with `test_exactly_one_approved_backend_runtime_consumer_of_generated_service_types()`.
   - Added `test_google_calendar_wiring_matches_generated_service_types()`, `test_unknown_service_uses_fallback_color_eight_in_google_calendar()`, and `test_build_event_body_does_not_mutate_imported_service_types()`.
3. `tests/backend/test_phase24a_service_duration_contract_parity.py`
   - Added 11 edge-case characterization tests for `scheduled_duration`.

### Documentation
4. `docs/planning/phase-24a-2c2-service-type-contract-wiring.md`
5. `docs/project-continuity/current-state.md`
6. `docs/project-continuity/document-map.md`
7. `docs/release-notes/index.md`
8. `docs/release-notes/phase-24a-2c2d3-generated-calendar-duration-friendly-name-wiring.md` (this file)
9. `docs/release-notes/phase-24a-2c2d2-generated-backend-service-metadata-adapter.md` (stale reference correction)
10. `docs/planning/phase-24a-2c2b-selector-normalization-design.md` (stale reference correction)

## 14. Explicit exclusions

Unchanged by Phase 2D.3:
- `shared/constants/service-types.json`;
- `shared/generate-contract-adapters.mjs`;
- `shared/validate-constants.mjs`;
- `shared/validate-contract-adapters.mjs`;
- `src/backend/common/generated_service_types.py`;
- `web/src/generated/contracts.js`;
- `mobile/src/contracts/generatedContracts.ts`;
- backend handlers (`intake_handler.py`, `job_handler.py`, etc.);
- request/job persistence;
- status, notification, and scheduling modules;
- web application source and tests;
- mobile application source and tests;
- Terraform files, API Gateway, Cognito, Postmark, and Stripe;
- dependencies and lockfiles;
- production data and production environments.

## 15. Deployment and existing-event implications

- All 13 AWS Lambda functions share the backend zip archive hash. A future backend deployment will package the updated `google_calendar.py` and `generated_service_types.py` into all 13 Lambdas.
- Only execution paths importing `google_calendar.py` (calendar sync, event creation, event update) load the generated metadata.
- No deployment is required for local closeout.
- Existing Google Calendar events are not automatically altered by committing or deploying this change, because canonical durations and friendly names match prior handwritten maps 100%.
- Future normal user actions (status changes, assignment updates, admin edits) issuing full-body calendar updates will produce byte-identical duration and summary output.
- No event migration, backfill, or resynchronization is required.
- Production smoke testing, event resynchronization, and deployment remain separate approval gates. No deployment is authorized now.

## 16. Risks and rollback

- **Risk Assessment:** Low. The derived duration and friendly-name dictionaries are proven 100% equal to the handwritten literals. 117 backend tests verify zero runtime behavioral regression.
- **Local Rollback:**
  1. Remove `from common.generated_service_types import SERVICE_TYPES` and `SERVICE_METADATA` from `google_calendar.py`.
  2. Restore handwritten `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` dictionary literals.
  3. Revert `test_phase24a_generated_service_types.py` to assert zero runtime consumers.
  4. Remove the 11 edge-characterization tests from `test_phase24a_service_duration_contract_parity.py`.
  5. Revert documentation updates.
- **Post-Deployment Rollback:** Deploy the prior backend archive. No event repair or resynchronization would be necessary since output values are identical.

## 17. Approval gates

Local closeout does not authorize staging, commit, push, backend packaging, deployment, production-data access, Google Calendar API invocation, or Phase 2D.4 color work. Commit and push require a separate Matthew decision. Deployment requires a separately reviewed plan and explicit approval.

Backend identifier policy, production assessment, normalization, migration/deprecation, and existing-event resynchronization each retain their own approval gates.

## 18. Remaining deferred work

- tenant-configurable calendar color policy;
- backend service-identifier acceptance policy;
- production assessment;
- normalization and migration/deprecation;
- existing-event resynchronization;
- backend deployment review.

Phase 24A-2C.2 remains partially complete locally. Planned Phase 2D backend service-metadata workstream is locally complete across all four subphases (2D.1, 2D.2, 2D.3, 2D.4).

## 19. Final status

**PHASE 24A-2C.2D.3 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / DOCUMENTATION PREPARED / AWAITING COMMIT DECISION / EXACT BEHAVIOR PRESERVED / NOT DEPLOYED**

**Phase 24A-2C.2:** **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D LOCALLY COMPLETE / NOT DEPLOYED OR DISTRIBUTED**
