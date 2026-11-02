# Shared REQUEST Write-Safety Contract — S0a Inactive Acceptance

**Date:** 2026-11-01 (America/New_York). **Disposition:** `REQUEST_WRITE_SAFETY_S0A_INACTIVE_NOT_INTEGRATED`.

Matthew explicitly approved ONE new dependent Draft PR, stacked on PR54, delivering the **smallest reviewable first slice (S0a)** of the shared REQUEST write-safety contract: three PURE decision/construction functions in `src/backend/common/request_write.py`, offline tests, and docs. Design direction only — no runtime activation, no caller adoption, no execution, no AWS.

## Dependency and scope

Branch `codex/request-write-safety-contract` is based on PR54 head `cbbee7fb73bdab20b169ed0445e8fc535f9f1770` (target branch `codex/cancellation-absent-identity-guard`). No PR51/52/53/54 branch is edited; this PR adds two new files and docs on the NEW branch only. Main verified `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.

S0a implements EXACTLY three functions and NOTHING that executes:
- `classify_adoption(snapshot) -> AdoptionDisposition`
- `build_update(key, expected, plan, disposition) -> UpdateSpec | Refusal`
- `interpret_failure(evidence) -> FailureClassification`

## What S0a is — and is not

S0a is the pure **decision surface** of a REQUEST mutation: it decides whether a row may be fenced, constructs (but never issues) the conditional `UpdateItem` spec, and classifies a write failure. It opens no boto3/SDK client, performs no network/DB call, imports no handler, is imported by no production module, and contains no create/delete/tombstone/transaction execution. Those are later, separately approved slices (S0b create-only, S0c delete+tombstone, S0d coupled transactions), plus the read-only deployed-fleet inventory.

**A helper cannot protect legacy writers.** It only fences writes that call it. S0a makes no claim about unfenced, out-of-repo, old-artifact, queued or manual writers. This limit is a hard contract term, not a caveat.

## Security contract (as implemented)

1. **Legacy adoption — compatible ≠ safe-to-adopt.** `classify_adoption` returns `ADOPT_ELIGIBLE` only when the row carries a well-formed `legacy_write_revision` (and, when present, a well-formed `record_incarnation`). Missing or malformed version/lifetime metadata → `QUARANTINE_UNVERSIONED`; a non-REQUEST / missing-tenant / malformed snapshot → `REFUSE_INELIGIBLE`. A missing revision is **not** treated as a safe zero. There is **no SEEDING / override / bypass** parameter anywhere in the API.
2. **Quarantine is a refusal.** `build_update` refuses any disposition other than `ADOPT_ELIGIBLE` (`ADOPTION_REFUSED`), so an unversioned row cannot produce a fence.
3. **Conditions.** Every generated `UpdateItem` condition binds `attribute_exists(PK/SK)`, `company_id = :tenant` (tenant at write-time), `legacy_write_revision = :rev`, incarnation `= :inc` when present, and `status = :source_status` ONLY when the caller declares a status transition. The update ALWAYS advances the revision (`SET legacy_write_revision = :next`).
4. **PR54-complete ownership coverage for protected clients.** When `protected_client` is set, present/absent identity evidence must be well-formed, duplicate-free, DISJOINT, and EXHAUSTIVE over `{client_email, linked_client_profile_id, cognito_sub}`, and the present fence must include a subject/profile identity (email alone is rejected). Present fields are equality-fenced; absent fields get `attribute_not_exists`, so an insert-without-revision-bump is still rejected. Contradictory/incomplete/malformed evidence is refused.
5. **Identity immutability.** A plan may never SET/REMOVE an identity field or a reserved field (`PK/SK/company_id/client_id/request_id/legacy_write_revision/record_incarnation`); ownership is proven via the present/absent coverage, never by mutating an identity field.
6. **Named SET/REMOVE only; unknown fields preserved.** There is no whole-item/upsert form; the update names only plan fields + optional audit append + the revision advance, so concurrent unknown fields survive.
7. **Failure semantics.** `interpret_failure` defaults to `INDETERMINATE`. A bare `conditional_check_failed` is INDETERMINATE (cause unobservable). A transaction cancellation is INDETERMINATE unless it carries a `ConditionalCheckFailed` reason AND a deliberate re-read proving the specific divergence. Specific results (`STALE`, `TENANT_MISMATCH`, `RETIRED`, `ABSENT`) are returned only when evidence-backed (per-item reason or re-read). No blind retry; no silent upsert.
8. **Structural vs provenance.** All checks are STRUCTURAL shape/coverage checks. They do NOT authenticate provenance — a well-formed snapshot/plan is a shape, not proof that a trusted adapter observed it. Real provenance/freshness/authentication remain separate pending gates.

## Offline tests

`tests/backend/test_request_write.py` (40 cases) is AWS-free and deterministic. Besides refusal/classification assertions, it includes a minimal evaluator for the closed clause grammar `build_update` emits and **evaluates the actual generated `ConditionExpression` against synthetic stored-item states** (not just strings): valid state passes; stale revision, cross-tenant, diverged incarnation/source-status, changed/removed present identity, and inserted-absent-identity-without-revision-bump all fail. Coverage also includes quarantine/missing-metadata, the unversioned-writer race characterization, ownership coverage (incomplete/partial/contradictory/duplicate/unknown/email-only), malformed plans/inputs, indeterminate vs evidence-backed failures, and no-upsert / no-SDK / no-execution properties.

## Validation

Scoped run (S0a + the four inherited cancellation suites): **257 passed, 23 subtests passed** (217 inherited + 40 new S0a), Python 3.13.3, pytest 9.0.2. S0a is additive and imported by nothing, so the inherited suites are unchanged. Full guarded backend not run here; recorded `FULL_BACKEND_NOT_VERIFIED` (prior PR53 74-failure baseline retained at `D:\petcare-rollback\pr53-evidence\13e9f5d\`).

## Remaining approval gates

- **S0b** create-only fencing; **S0c** delete + transactional separate-key permanent tombstones (ABA); **S0d** coupled `transact_write_items`.
- **Deployed-fleet inventory** (separately-authorized, read-only AWS audit): which Lambdas/artifacts write REQUEST, whether all writers adopt the helper, drain/ordering before any adoption is trusted. Until then no legacy row is safe-to-adopt and no caller adoption is authorized.
- Caller adoption slices (payment → cancellation → ownership → intake → lifecycle), each its own PR with explicit live-workflow-impact approval.

S0a remains inactive and not merge-ready. No parent-branch edits, runtime integration, AWS/Terraform/Cognito/IAM, migration/backfill, Stripe/tenant, distribution, or Ryan testing occurred.
