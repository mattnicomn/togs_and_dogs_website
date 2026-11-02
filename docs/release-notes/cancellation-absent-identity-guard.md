# Cancellation Absent-Identity Ownership Guard - Inactive Acceptance (PR54)

**Date:** 2026-11-01 (America/New_York). **Disposition:** `CANCELLATION_ABSENT_IDENTITY_GUARD_INACTIVE_NOT_INTEGRATED`.

Matthew explicitly approved ONE new dependent Draft PR, stacked on PR53, that closes the documented absent-identity insertion race identified in the PR51 ownership-absence design assessment. Design direction only - not runtime activation, migration, or production acceptance.

## Dependency and scope

Branch `codex/cancellation-absent-identity-guard` is based on PR53 head `569c39aa0554f1d4966b1a5fa9382a045bc39794` (target branch `codex/cancellation-access-adapter`). PR52 base `3d610dd2d670300acdd2831ae88af9ca53cf66f8` and PR51 `cafeba56735a34efe9b59fdf248e3f8835b8631b` are unchanged on their own branches; this PR carries its own modified copies of the inherited contract modules on the NEW branch only. No existing PR51/52/53 branch is edited. Main verified `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.

## The race this closes

PR51's commit `ConditionExpression` pinned identity fields only by equality (`#a = :a`) for fields present and fenced at observation, plus `#rev = :rev` / `#inc = :inc`. A field ABSENT at observation (and therefore unfenced) that a concurrent writer INSERTED before commit was caught only transitively by the revision pin - i.e. only if that writer advanced `legacy_write_revision`. A non-conforming/legacy writer that inserted an identity field without bumping the revision could slip an unfenced ownership field past the condition. The repo's writer inventory does not yet prove the all-writers revision-advance invariant, so the race was reachable.

## Correction (inactive, design-only)

1. **PR53 access adapter** - `_bundle` derives, from the bundle-attested request (not a caller input), the set of identity fields whose KEY is absent (present-but-NULL/empty already fails `OWNERSHIP_SHAPE`). Exposed as typed evidence `AccessEvidence.absent_identity_fields`; `verify_current` re-derives and digest-binds it (`ACCESS_ABSENCE_BINDING`). Present ∪ absent == identity universe by construction for an eligible record.
2. **PR52 preparation** - `prepare_commit` independently derives the absent set from the attested request, asserts it is DISJOINT from the present identity bindings (`ABSENCE_CONTRADICTS_PRESENT`, a fail-closed invariant), carries it on `CommitCommand.absent_identity_fields`, and adds the `ABSENT_IDENTITY_NOT_INSERTED` guard marker. Exhaustiveness is NOT imposed on this path, so legacy/offline callers are not newly broken.
3. **PR51 transaction** - for each verified-absent identity field, `transaction()` emits `attribute_not_exists(#x_j)` on the REQUEST `Update`, in a distinct `#x` name namespace. Present-field equalities (`#a`), revision/incarnation pins, audit/marker/start/reservation/lifetime/receipt conditions are all unchanged. `authorize()` validates supplied `absent_fields` are known identity fields, unique, and disjoint from the present fence (`ACCESS_ABSENCE_BINDING`); absence evidence is optional on the legacy path and exhaustiveness is not required there. The existing `OVERSIZE_REFUSED` check re-validates the 4096-byte ConditionExpression and 300KB transaction envelope with the added clauses.

Preserved: equality conditions for present fields; revision/incarnation guards; receipt create-only, reservation-absent, live-permanent-lifetime behavior; email-only fence still refuses; the subject/profile fence requirement.

## Offline condition-evaluation tests

`tests/backend/test_cancellation_absent_identity_guard.py` (9 cases) includes a minimal synthetic evaluator for the closed clause grammar PR51 emits and evaluates the ACTUAL generated `ConditionExpression` against synthetic stored-item states (not only strings):

- Absent field remains absent -> condition PASSES.
- Absent field inserted, revision unchanged -> DENIES (the race this PR closes).
- Absent field inserted, revision changed -> DENIES.
- Present field changed / removed / NULL -> DENIES.
- Conflicting (present+absent) and forged (unknown/duplicate) absence evidence -> rejected by `authorize()` before any transaction is built.
- Existing successful transaction (clean snapshot; and legacy no-absent-fields path) -> remains valid.
- Condition <= 4096 bytes; TransactWriteItems envelope within limits.

## Validation

Targeted cancellation suite (4 modules): **215 passed, 23 subtests passed** (prior 206+23; +9 new), Python 3.13.3, deterministic. The three inherited contract suites remain green, confirming backward compatibility (absence evidence optional; disjointness invariant holds; no fixture regressions).

Full guarded backend: see the delivery record. If a stable runner is unavailable, recorded as `FULL_BACKEND_NOT_VERIFIED` without claiming historical 77-failure parity; the PR53 74-failure baseline evidence is retained at `D:\petcare-rollback\pr53-evidence\13e9f5d\`.

## Rollback and mixed-version safety

- The change is additive conditions on an INACTIVE contract; reverting the PR restores PR53 `569c39a`. No stored data is written by any path here; rollback is a pure branch operation with no migration.
- Mixed-version: the guard is strictly MORE restrictive (it only ever refuses more), so new-code commits never accept anything old-code would reject. It protects the cancellation commit only; full ownership integrity still requires the separately-tracked all-writers revision-advance / writer-protection closure. Necessary, not sufficient.

## Remaining gates

All-writers revision-advance invariant audit (or coordinated writer protection); hosted/stable-runner full-suite confirmation; real-verifier trust/provenance/freshness; storage/reconciliation adapter; source-status/resubmission policy; retention/recovery; exact-principal transactional IAM; UX/release evidence. PR54 remains inactive and not merge-ready. No parent-branch edits, runtime integration, AWS/Terraform/Cognito/IAM, migration/backfill, enrollment, Stripe/tenant, distribution, or Ryan testing occurred.
