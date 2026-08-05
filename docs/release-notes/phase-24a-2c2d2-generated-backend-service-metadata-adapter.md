# Phase 24A-2C.2D.2 — Generated Backend Service-Metadata Adapter

**Status:** **LOCALLY IMPLEMENTED, VALIDATED, INDEPENDENTLY REVIEWED, AND DOCUMENTED / GENERATED BACKEND SERVICE-METADATA ADAPTER COMPLETE / NO RUNTIME CONSUMPTION / NOT DEPLOYED**

**Date:** 2026-08-05
**Base checkpoint:** `0b066339c6c208dba09458572bc666c9676e1951` (`test: harden service duration contract parity`)

---

## 1. Scope and authorization

Matthew explicitly approved one bounded local Phase 24A-2C.2D.2 candidate to extend the existing shared generator with deterministic backend Python service metadata, validate exact canonical/web/mobile/backend parity, add focused backend import/equality/no-consumer tests, and prepare the applicable documentation after independent review.

The authorization excluded runtime consumption, Phase 2D.3 calendar wiring, contract or contract-value changes, handler or persistence changes, web/mobile changes, infrastructure, dependencies, production-data access, Google Calendar invocation, staging, commit, push, and deployment.

## 2. Starting checkpoint

Implementation began on `main` at `0b066339c6c208dba09458572bc666c9676e1951`, with `HEAD` equal to `origin/main`, a clean working tree, and an empty stash. Documentation closeout began from the same base with only the exact independently reviewed four-file implementation candidate present.

The latest completed validated production release remains Phase 1B.5C-D.2. Phase 24A remains local-only and is not deployed or distributed. Phase 2D.1 is committed and pushed at the base checkpoint; Phase 2D.2 is not committed or pushed by this closeout.

## 3. Problem statement

The canonical service contract already generated complete `SERVICE_TYPES` objects for web and mobile, while backend calendar metadata remained independently handwritten. Phase 2D.1 proved canonical/backend duration and short-label parity but deliberately did not create a backend adapter or alter runtime behavior.

Phase 2D.2 closes only the deterministic backend-adapter gap. It creates commit-ready generated Python metadata that a future separately approved phase may consume, without importing it into any runtime source today.

## 4. Generator changes

`shared/generate-contract-adapters.mjs` now generates web, mobile, and backend targets through the existing command:

```text
node shared/generate-contract-adapters.mjs
```

The generator continues reading `shared/constants/service-types.json` and stripping only top-level underscore-prefixed metadata keys. It preserves the cleaned root `services` wrapper, service and field order, exact camelCase names, string values, integer values, and boolean values.

A recursive type-aware Python literal serializer supports objects, arrays, strings, finite numbers, booleans, and null. Booleans and null are mapped by value type to `True`, `False`, and `None`; no broad serialized-text replacement occurs. Output is deterministic UTF-8 with four-space indentation, double-quoted keys/strings, trailing commas, one final newline, the canonical source path, the existing generation command, and no timestamp.

All target contents are constructed before writes begin. The new Python target uses same-directory temporary-file replacement with cleanup on failure. The existing web/mobile write flow was not broadly refactored, no dependency was added, and no backend-only command was created.

## 5. Exact generated module design

Generated path:

```text
src/backend/common/generated_service_types.py
```

The file contains only generated header comments and one plain-dictionary assignment:

```python
SERVICE_TYPES = {
    "services": {
        # Exact cleaned canonical entries
    },
}
```

It contains no imports, functions, helpers, type declarations, service aliases, normalization, side effects, or derived duration, label, or color maps. No runtime backend source imports it.

## 6. Validator changes

`shared/validate-contract-adapters.mjs` now proves complete equality among canonical, generated web, generated mobile, and generated backend Python `SERVICE_TYPES`.

Validation covers root membership/order, exact service membership/order, all five exact metadata fields and their order, exact label and duration values, exact boolean values, type preservation, and absence of missing or extra services or fields. All six canonical/cross-adapter equality relationships are asserted. Existing `PET_FIELDS`, path, helper, security, and prior adapter checks remain intact.

Deterministic zero-diff validation reads web, mobile, and backend targets before generation, runs the single generator command, rereads all three, and requires byte-for-byte equality.

## 7. Safe Python parsing and launcher fallback

The Node validator invokes a Python standard-library subprocess with `spawnSync`. The subprocess:

- parses syntax with `ast.parse`;
- accepts exactly one executable statement;
- requires a direct assignment to `SERVICE_TYPES`;
- extracts only the literal with `ast.literal_eval`;
- serializes it with `json.dumps(..., ensure_ascii=False, allow_nan=False)`.

No JavaScript or Python `eval` is used. The validator does not import the generated module and does not arbitrarily execute generated code.

Windows launcher fallback is `python`, `py -3`, then `python3`; non-Windows fallback is `python3`, then `python`. Missing or unusable launchers, invalid syntax, invalid assignment shape, invalid JSON, equality drift, and deterministic drift produce explicit failures. Local validation used `python` with Python 3.13.3.

## 8. Focused backend test coverage

`tests/backend/test_phase24a_generated_service_types.py` contains three focused tests proving:

- real import through `common.generated_service_types`;
- exact equality with canonical JSON after stripping only top-level underscore-prefixed metadata;
- exact root, service, and five-field ordering;
- exact string types;
- positive integer durations whose exact type is `int`, preventing booleans from passing;
- exact boolean availability types;
- module resolution beneath `src/backend/common`;
- absence of runtime backend imports of the generated module.

The no-consumer scan checks static import forms plus literal `__import__` and `importlib.import_module` calls. It is expected to change only during a separately approved Phase 2D.3 runtime-consumption implementation.

## 9. Web/mobile byte parity

Generation left these committed targets byte-identical to the base checkpoint:

- `web/src/generated/contracts.js`;
- `mobile/src/contracts/generatedContracts.ts`.

`git diff --exit-code` passed for both files. Phase 2D.2 introduces no web or mobile source, test, build, selector, payload, or behavior change.

## 10. No-runtime-consumption safeguards

Phase 2D.2 did not modify the canonical contract, `shared/validate-constants.mjs`, `src/backend/common/__init__.py`, `src/backend/common/google_calendar.py`, any handler, request/job persistence, scheduling, notifications, APIs, web, mobile, infrastructure, dependencies, or lockfiles.

Google Calendar `SERVICE_DURATIONS`, `FRIENDLY_SERVICE_NAMES`, `SERVICE_COLORS`, fallback handling, and event construction remain runtime authority. No event title, duration, color, start, end, fallback, all-day, or visit-window behavior changed. No Google API call or production-data access occurred.

## 11. Exact validation totals

| Validation | Result |
|---|---:|
| Shared canonical constants | 18/18 passed |
| Shared adapter validation | 8/8 passed |
| Three-target deterministic generation | Passed; zero diff |
| Generated backend focused tests | 3/3 passed |
| Phase 2D.1 parity suite | 48/48 passed |
| Calendar hardening regression | 18/18 passed |
| All-day regression | 12/12 passed |
| Multi-day regression | 22/22 passed |
| Combined affected backend set | 103/103 passed |
| Generator and validator Node syntax | Passed |
| Web/mobile byte parity | Passed |
| `git diff --check` | Passed |

Pytest emitted a non-functional cache warning because `.pytest_cache` was not writable. Tests still passed, and all repository-local pytest/Python cache artifacts were removed after validation; no transient file remains.

## 12. Independent review result

Kiro independently verified the exact four-file implementation candidate and reproduced:

- 18 shared constant checks;
- 8 shared adapter checks;
- deterministic generation across all three targets;
- web/mobile byte parity;
- 103 combined affected backend tests.

Kiro confirmed the generated Python structure, complete canonical/web/mobile/backend equality, no runtime backend import, and no contract, handler, calendar, web, mobile, or infrastructure change. Kiro returned `READY_FOR_PHASE_24A_2C_2D_2_DOCUMENTATION_AND_LOCAL_CLOSEOUT`; no blocking correction was identified.

## 13. Exact files changed

Implementation candidate:

- modified `shared/generate-contract-adapters.mjs`;
- modified `shared/validate-contract-adapters.mjs`;
- created `src/backend/common/generated_service_types.py`;
- created `tests/backend/test_phase24a_generated_service_types.py`.

Documentation closeout:

- modified `docs/planning/phase-24a-2c2-service-type-contract-wiring.md`;
- modified `docs/project-continuity/current-state.md`;
- modified `docs/project-continuity/document-map.md`;
- modified `docs/release-notes/index.md`;
- created this release note;
- corrected the direct stale 2D.1 commit/2D.2 status in `docs/release-notes/phase-24a-2c2d1-service-duration-parity-validator-hardening.md`;
- corrected the direct stale 2D.2 continuity statement in `docs/planning/phase-24a-2c2b-selector-normalization-design.md`.

## 14. Explicit exclusions

No contract or value, canonical validator, runtime consumer, Google Calendar helper, handler, persistence, scheduling, notification, API, web/mobile source or generated bytes, infrastructure, Terraform, dependency, lockfile, build configuration, production data, production system, Cognito, Stripe, tenant, tester, store, or distribution setting changed.

No Lambda package was built. Nothing was staged, committed, pushed, deployed, or distributed.

## 15. Packaging and deployment implications

The generated module resides under `src/backend/common`, so any future Terraform backend archive will include it. All 13 Lambda functions share that archive and its hash. Deploying Phase 2D.2 independently would therefore cause unnecessary all-Lambda package churn despite the module being unused.

No deployment is required for local closeout, and none is authorized. A future separately approved Phase 2D.3 deployment may package the locally complete 2D.2 adapter and approved runtime wiring together, subject to its own review, plan, approval, and validation.

## 16. Risks and rollback

Primary local risks are serializer drift, Python launcher availability, invalid generated syntax/shape, accidental web/mobile changes, or premature runtime consumption. The safe AST parser, complete cross-target equality, deterministic byte checks, focused import/type tests, no-consumer scan, and exact file scope mitigate them.

Local rollback is limited to reverting the generator and validator changes, deleting the generated Python module and focused tests, and reverting these documentation updates. No data, request/job, Google Calendar, event, web/mobile, infrastructure, or production rollback is required because there is no runtime consumption or deployment.

## 17. Approval gates

This local closeout does not authorize staging, commit, push, backend packaging, deployment, production-data access, Google Calendar invocation, or Phase 2D.3 runtime wiring. Commit and push require a separate Matthew decision. Deployment requires a separately reviewed plan and explicit approval.

Backend identifier policy, production assessment, normalization, migration/deprecation, and existing-event resynchronization each retain their own approval gates.

## 18. Remaining deferred work

- **2D.4:** optional calendar color metadata;
- backend service-identifier acceptance policy;
- production assessment;
- normalization and migration/deprecation;
- existing-event resynchronization;
- backend deployment review.

Phase 24A-2C.2 remains partially complete locally. Phase 2D overall is not complete.

## 19. Final status

**PHASE 24A-2C.2D.2 LOCALLY VALIDATED AND INDEPENDENTLY REVIEWED / DOCUMENTATION PREPARED / AWAITING COMMIT DECISION / NO RUNTIME CONSUMPTION / NOT DEPLOYED**

**Phase 24A-2C.2:** **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D.1 COMPLETE / 2C.2D.2 COMPLETE / 2C.2D.3 COMPLETE / 2C.2D.4 DEFERRED / NOT DEPLOYED OR DISTRIBUTED**
