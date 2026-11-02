# Cancellation Absent-Identity Ownership Guard - Inactive Acceptance (PR54)

**Date:** 2026-11-01 (America/New_York). **Disposition:** `CANCELLATION_ABSENT_IDENTITY_GUARD_INACTIVE_NOT_INTEGRATED`.

Matthew explicitly approved ONE new dependent Draft PR, stacked on PR53, that closes the documented absent-identity insertion race identified in the PR51 ownership-absence design assessment. Design direction only - not runtime activation, migration, or production acceptance.

## Dependency and scope

Branch `codex/cancellation-absent-identity-guard` is based on PR53 head `569c39aa0554f1d4966b1a5fa9382a045bc39794` (target branch `codex/cancellation-access-adapter`). PR52 base `3d610dd2d670300acdd2831ae88af9ca53cf66f8` and PR51 `cafeba56735a34efe9b59fdf248e3f8835b8631b` are unchanged on their own branches; this PR carries its own modified copies of the inherited contract modules on the NEW branch only. No existing PR51/52/53 branch is edited. Main verified `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.

## The race this closes

PR51's commit `ConditionExpression` pinned identity fields only by equality (`#a = :a`) for fields present and fenced at observation, plus `#rev = :rev` / `#inc = :inc`. A field ABSENT at observation (and therefore unfenced) that a concurrent writer INSERTED before commit was caught only transitively by the revision pin - i.e. only if that writer advanced `legacy_write_revision`. A non-conforming/legacy writer that inserted an identity field without bumping the revision could slip an unfenced ownership field past the condition. The repo's writer inventory does not yet prove the all-writers revision-advance invariant, so the race was reachable. (The first correction made absence fencing available but optional; the Corrective subsection below makes complete coverage mandatory for the protected client path, which is what actually closes the race.)

## Correction (inactive, design-only)

1. **PR53 access adapter** - `_bundle` derives, from the bundle-attested request (not a caller input), the set of identity fields whose KEY is absent (present-but-NULL/empty already fails `OWNERSHIP_SHAPE`). Exposed as typed evidence `AccessEvidence.absent_identity_fields`; `verify_current` re-derives and digest-binds it (`ACCESS_ABSENCE_BINDING`). Present ∪ absent == identity universe by construction for an eligible record.
2. **PR52 preparation** - `prepare_commit` independently derives the absent set from the attested request, asserts it is DISJOINT from the present identity bindings (`ABSENCE_CONTRADICTS_PRESENT`, a fail-closed invariant), carries it on `CommitCommand.absent_identity_fields`, and adds the `ABSENT_IDENTITY_NOT_INSERTED` guard marker. Exhaustiveness is NOT imposed on this path, so legacy/offline callers are not newly broken.
3. **PR51 transaction** - for each verified-absent identity field, `transaction()` emits `attribute_not_exists(#x_j)` on the REQUEST `Update`, in a distinct `#x` name namespace. Present-field equalities (`#a`), revision/incarnation pins, audit/marker/start/reservation/lifetime/receipt conditions are all unchanged. `authorize()` validates supplied `absent_fields` are known identity fields, unique, and disjoint from the present fence (`ACCESS_ABSENCE_BINDING`); absence evidence is optional on the legacy path and exhaustiveness is not required there. The existing `OVERSIZE_REFUSED` check re-validates the 4096-byte ConditionExpression and 300KB transaction envelope with the added clauses.

Preserved: equality conditions for present fields; revision/incarnation guards; receipt create-only, reservation-absent, live-permanent-lifetime behavior; email-only fence still refuses; the subject/profile fence requirement.

## Corrective: mandatory protected-path coverage at `transaction()` (scope expansion)

An independent contract-boundary review of the first correction proved the fence was still **bypassable on the default path**: because absence evidence was optional and exhaustiveness was not imposed, a protected CLIENT cancellation constructed with the default empty `absent_fields=()` built a `ConditionExpression` with NO `attribute_not_exists` identity clauses, so inserting an unfenced identity field (without a revision bump) still passed the condition - the exact race the guard was meant to close. Optional, caller-opt-in absence evidence does not close a race.

The corrective (approved scope expansion, inactive/design-only) makes complete coverage a **mandatory structural precondition at the real condition-construction boundary** - PR51 `transaction()` - gated to the client protected path (`plan.access.role == "client"`):

- Every binding/absent field must be a known identity field (`PROTECTED_IDENTITY_COVERAGE_FIELD`).
- No duplicates within present or within absent (`PROTECTED_IDENTITY_COVERAGE_DUPLICATE`).
- Present and absent must be DISJOINT (`PROTECTED_IDENTITY_COVERAGE_CONTRADICTION`).
- Present ∪ absent must EXHAUST the identity universe `{client_email, linked_client_profile_id, cognito_sub}` (`PROTECTED_IDENTITY_COVERAGE_INCOMPLETE`).

This fails closed on the omitted/default empty-absence case, partial coverage, and contradictory/duplicate evidence, so a transaction can never be built that leaves an identity field in an unaccounted third state. The check runs BEFORE the condition body is assembled, so an underprotected client commit never materializes.

Placement rationale: the enforcement lives in `transaction()`, not in `authorize()`. `authorize()` stays permissive (well-formedness + disjointness only, exhaustiveness NOT required) so inherited non-protected/legacy and offline callers are not newly broken; the mandatory exhaustiveness applies only where a real DynamoDB condition is actually constructed for a protected client. Absence fields are NOT treated as authenticated by this check - completeness of the fence is a structural precondition; real trusted-verifier / bridge provenance and freshness remain a separate, still-pending gate (see Remaining gates).

Error ordering: the previously ambiguous `OVERSIZE_REFUSED` / `CONDITIONAL_REFUSAL` interactions in inherited fixtures were resolved by giving each inherited protected-client fixture complete, record-consistent coverage (present identity fields that exist in the record are equality-fenced; the remaining identity fields are attested-absent and genuinely missing from the record), NOT by reordering or weakening `transaction()`. Both prior "ordering" failures were symptoms of incomplete fixtures, not real ordering conflicts.

## Offline condition-evaluation tests

`tests/backend/test_cancellation_absent_identity_guard.py` (11 cases) includes a minimal synthetic evaluator for the closed clause grammar PR51 emits and evaluates the ACTUAL generated `ConditionExpression` against synthetic stored-item states (not only strings):

- Absent field fenced with `attribute_not_exists`; present field still equality-fenced.
- Absent field remains absent -> condition PASSES.
- Absent field inserted, revision unchanged -> DENIES (the race this PR closes).
- Absent field inserted, revision changed -> DENIES.
- Present field changed / removed / NULL -> DENIES.
- Default/partial coverage (omitted or incomplete absence evidence) -> refuses at construction with `PROTECTED_IDENTITY_COVERAGE_INCOMPLETE` before any transaction is built.
- Complete valid coverage -> builds and fences every identity field (equality for present, `attribute_not_exists` for absent).
- Conflicting (present+absent) and forged (unknown/duplicate) absence evidence -> rejected by `authorize()` (`ACCESS_ABSENCE_BINDING`) before any transaction is built.
- Existing successful transaction (complete-coverage clean snapshot) -> remains valid.
- Condition <= 4096 bytes; TransactWriteItems envelope within limits.

## Validation

Targeted cancellation suite (4 modules): **217 passed, 23 subtests passed** (prior 206+23; +11 new PR54 cases), Python 3.13.3, pytest 9.0.2, deterministic. The three inherited contract suites remain green. Inherited protected-client fixtures were updated ON THE PR54 BRANCH ONLY to carry complete, record-consistent present/absent identity coverage so they satisfy the new mandatory precondition; each fixture's original test intent and security assertions (identity-change refusal, stale-read refusal, replay freshness) are preserved. No parent branch was edited.

New / changed PR54 guard cases include: default empty-absence coverage refuses at construction (`PROTECTED_IDENTITY_COVERAGE_INCOMPLETE`); partial coverage refuses; complete valid coverage succeeds and fences every identity field; and the insert-without-revision-bump race is denied against the actual generated `ConditionExpression`.

Full guarded backend: see the delivery record. If a stable runner is unavailable, recorded as `FULL_BACKEND_NOT_VERIFIED` without claiming historical 77-failure parity; the PR53 74-failure baseline evidence is retained at `D:\petcare-rollback\pr53-evidence\13e9f5d\`.

## Rollback and mixed-version safety

- The change is additive conditions on an INACTIVE contract; reverting the PR restores PR53 `569c39a`. No stored data is written by any path here; rollback is a pure branch operation with no migration.
- Mixed-version: the guard is strictly MORE restrictive (it only ever refuses more), so new-code commits never accept anything old-code would reject. It protects the cancellation commit only; full ownership integrity still requires the separately-tracked all-writers revision-advance / writer-protection closure. Necessary, not sufficient.

## Remaining gates

All-writers revision-advance invariant audit (or coordinated writer protection); hosted/stable-runner full-suite confirmation; real-verifier trust/provenance/freshness; storage/reconciliation adapter; source-status/resubmission policy; retention/recovery; exact-principal transactional IAM; UX/release evidence. PR54 remains inactive and not merge-ready. No parent-branch edits, runtime integration, AWS/Terraform/Cognito/IAM, migration/backfill, enrollment, Stripe/tenant, distribution, or Ryan testing occurred.
